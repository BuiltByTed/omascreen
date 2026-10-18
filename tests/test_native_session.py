import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
import time

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
import pytest

from screen_sharing.native.session import SessionDialog
from screen_sharing.native.profiles import Profile
from screen_sharing.proxy.liveness import RECONNECT_EXIT_CODE


@pytest.fixture(scope='module')
def app():
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    return application


def test_failed_connection_stays_native_and_allows_retry(app, monkeypatch):
    monkeypatch.setattr('screen_sharing.native.session.credentials.available',lambda: False)
    profile = replace(Profile.new(),name='Offline Mac',host='127.0.0.1',username='test',port=1)
    dialog = SessionDialog(profile)
    dialog.show()
    dialog.password.setText('test-not-a-real-password')
    dialog.connect_session()
    deadline=time.monotonic()+10
    while dialog.process is not None and time.monotonic()<deadline:
        app.processEvents()
        time.sleep(.01)
    assert dialog.process is None
    assert dialog.isVisible()
    assert dialog.password.text() == ''
    assert dialog.connect_button.text() == 'Retry'
    assert not dialog.connect_button.isEnabled()
    assert not dialog.progress.isVisible()
    assert 'Couldn’t connect' in dialog.status.text()
    assert all('test-not-a-real-password' not in line for line in dialog.logs)
    dialog.hide()


def test_ready_is_parsed_across_reads_and_saves_only_after_connection(app, monkeypatch):
    monkeypatch.setattr('screen_sharing.native.session.credentials.available',lambda: False)
    dialog = SessionDialog(replace(Profile.new(),name='Mac',host='mac.local',username='ted'))
    chunks = iter([b'SCREEN_SHARING_VIEW',b'ER_READY\n'])
    class Process:
        def readAllStandardOutput(self): return next(chunks)
    dialog.process=Process()
    dialog.show()
    dialog.read_output()
    assert not dialog.ready and dialog.isVisible()
    dialog.read_output()
    assert dialog.ready and not dialog.isVisible()
    dialog.process=None


def _drain_process(app, dialog):
    deadline = time.monotonic() + 5
    while dialog.process is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert dialog.process is None


def test_reconnect_retains_unsaved_password_and_retries_until_ready(app, monkeypatch):
    monkeypatch.setattr('screen_sharing.native.session.credentials.available', lambda: False)
    launches = []
    def arguments(profile, password):
        # Exercise real QProcess/stdin/output handling. No credential is put
        # in the child's arguments; the fake viewer reads it from its pipe.
        assert password is None
        launches.append(profile.id)
        code = [RECONNECT_EXIT_CODE, 1, 0][len(launches) - 1]
        ready = len(launches) != 2
        return ['-c',
                'import sys; p = sys.stdin.readline(); '
                'assert len(p) > 1; '
                + ('print("SCREEN_SHARING_VIEWER_READY", flush=True); ' if ready else '')
                + f'sys.exit({code})']
    monkeypatch.setattr('screen_sharing.native.session.session_arguments', arguments)
    dialog = SessionDialog(Profile.new())
    dialog.password.setText('temporary-test-password')
    dialog.connect_session()
    _drain_process(app, dialog)
    assert dialog.reconnecting and dialog.retry_timer.isActive()
    assert dialog.retry_timer.interval() == 1000
    assert dialog._session_password == 'temporary-test-password'
    assert dialog.password.text() == ''
    assert dialog.secret is None  # no persistent keyring save requested
    assert dialog.progress.isVisible() and not dialog.form.isVisible()

    dialog.retry_timer.stop()
    dialog._start_session()  # simulate timer firing after network is still down
    _drain_process(app, dialog)
    assert dialog.reconnecting and dialog.retry_timer.interval() == 2000

    dialog.retry_timer.stop()
    dialog._start_session()
    _drain_process(app, dialog)
    assert len(launches) == 3
    assert dialog.ready and not dialog.reconnecting
    assert not dialog.retry_timer.isActive()
    assert dialog._session_password is None  # normal close clears it
    assert all('temporary-test-password' not in line for line in dialog.logs)
    dialog.hide()


def test_cancel_during_reconnect_prevents_timer_from_starting_another_child(app, monkeypatch):
    monkeypatch.setattr('screen_sharing.native.session.credentials.available', lambda: False)
    dialog = SessionDialog(Profile.new())
    dialog._session_password = 'temporary-test-password'
    dialog.process_finished(RECONNECT_EXIT_CODE, QProcess.ExitStatus.NormalExit)
    assert dialog.retry_timer.isActive()
    dialog.reject()
    assert not dialog.retry_timer.isActive()
    assert dialog._session_password is None
    dialog._start_session()  # even a queued timer callback is harmless
    assert dialog.process is None
    dialog.hide()


@pytest.mark.parametrize('exit_status,code', [
    (QProcess.ExitStatus.NormalExit, 2),  # credentials rejected by the Mac
    (QProcess.ExitStatus.CrashExit, 1),   # crash / child failed to start
    (QProcess.ExitStatus.NormalExit, 0),  # explicit viewer close
])
def test_reconnect_stops_on_auth_failure_crash_or_user_close(app, monkeypatch, exit_status, code):
    monkeypatch.setattr('screen_sharing.native.session.credentials.available', lambda: False)
    dialog = SessionDialog(Profile.new())
    dialog._session_password = 'temporary-test-password'
    dialog.reconnecting = True
    dialog.process_finished(code, exit_status)
    assert not dialog.retry_timer.isActive()
    assert dialog._session_password is None
    if code == 2:
        assert 'Sign-in failed' in dialog.status.text()
        assert dialog.form.isVisible()
    dialog.hide()


def test_omarchy_palette_changes_without_restart(app, tmp_path, monkeypatch):
    from screen_sharing.native.theme import ThemeController
    from PySide6.QtGui import QPalette
    theme = tmp_path / 'colors.toml'
    monkeypatch.setattr('screen_sharing.native.theme.theme_paths',lambda: [theme])
    theme.write_text('background = "#121212"\nforeground = "#bebebe"\naccent = "#e68e0d"')
    controller = ThemeController(app)
    assert app.palette().color(QPalette.ColorRole.Window).name() == '#121212'
    assert app.palette().color(QPalette.ColorRole.Highlight).name() == '#e68e0d'
    theme.write_text('background = "#eff1f5"\nforeground = "#4c4f69"\naccent = "#8839ef"')
    controller.reload()
    assert app.palette().color(QPalette.ColorRole.Window).name() == '#eff1f5'
    assert app.palette().color(QPalette.ColorRole.Text).name() == '#4c4f69'
    controller.timer.stop()
