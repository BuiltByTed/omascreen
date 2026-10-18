"""Exercise process shutdown: in-process widget tests cannot catch PySide cleanup crashes."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('with_editor', [False, True])
def test_manager_process_exits_cleanly(tmp_path, with_editor):
    source = '''
import resource
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from screen_sharing.native import manager
from screen_sharing.native.profiles import Profile, ProfileStore
from dataclasses import replace
app = QApplication(['omascreen-shutdown-test'])
profile = replace(Profile.new(), name='Example', host='example.invalid', icon_mode='app')
ProfileStore().save([profile])
def close_manager():
    for widget in app.topLevelWidgets():
        if isinstance(widget, manager.Manager):
            widget.close()
def edit_then_close():
    window = next(w for w in app.topLevelWidgets() if isinstance(w, manager.Manager))
    def cancel_editor():
        for widget in app.topLevelWidgets():
            if isinstance(widget, manager.ConnectionEditor):
                widget.reject()
    QTimer.singleShot(30, cancel_editor)
    window.open_editor(profile)
    close_manager()
QTimer.singleShot(100, edit_then_close if WITH_EDITOR else close_manager)
raise SystemExit(manager.main())
'''.replace('WITH_EDITOR', repr(with_editor))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen',
               XDG_CONFIG_HOME=str(tmp_path / 'config'), XDG_DATA_HOME=str(tmp_path / 'data'))
    # Use this checkout even if a different application version is installed.
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', source],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
