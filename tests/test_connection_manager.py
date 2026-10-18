from dataclasses import replace
from pathlib import Path
import socket
import threading

import pytest
from PySide6.QtWidgets import QApplication
from screen_sharing.native.profiles import Profile, ProfileStore
from screen_sharing.native import commands, icons, shortcuts, vnc
from screen_sharing.native.detection import detect
from screen_sharing.native.manager import ConnectionEditor, Manager


@pytest.fixture(scope='module')
def app():
    from PySide6.QtCore import QCoreApplication, QEvent
    application = QApplication.instance() or QApplication([])
    yield application
    for window in application.topLevelWidgets():
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    monkeypatch.setattr(shortcuts, 'refresh', lambda: None)
    return tmp_path


def profile(**kw):
    return replace(Profile.new(), name='Desk', host='localhost', **kw)


def test_generic_vnc_cli_needs_no_mac_username(isolated, monkeypatch):
    assert commands.main(['add','Server','--host','localhost','--protocol','vnc','--shortcut']) == 0
    p = ProfileStore().load()[0]
    monkeypatch.setattr(vnc.shutil, 'which', lambda _: '/usr/bin/vncviewer')
    args = vnc.viewer_arguments(replace(p, host='::1', port=5998))
    assert args[-1] == '[::1]::5998'
    assert '-UserName' not in args
    assert commands.main(['shortcut','Server','--remove']) == 0
    assert not shortcuts.shortcut_path(p).exists()
    assert len(ProfileStore().load()) == 1


def test_editor_preserves_fields_and_icon_options(app, isolated):
    p = profile(username='alice', protocol='apple', icon_mode='lucide', machine='laptop')
    dialog = ConnectionEditor(p)
    dialog.host.setText('new.local')
    dialog.protocol.setCurrentIndex(dialog.protocol.findData('vnc'))
    assert all(not w.isEnabled() for w in dialog.apple_widgets)
    dialog.icon_mode.setCurrentIndex(dialog.icon_mode.findData('app'))
    dialog.save()
    assert dialog.result_profile.host == 'new.local'
    assert dialog.result_profile.icon_mode == 'app'
    assert dialog.result_profile.username == 'alice'
    dialog.close()


def test_manager_refresh_preserves_selection(app, isolated):
    a, b = profile(), profile()
    b.name = 'Other'
    ProfileStore().save([a,b])
    manager = Manager()
    manager.list.setCurrentRow(1)
    ProfileStore().save([a,replace(b, name='Changed')])
    manager.reload()
    assert manager.current().id == b.id
    manager.search.setText('localhost')
    assert not manager.list.item(0).isHidden()
    manager.close()


def test_custom_icon_is_copied_and_launcher_uses_it(app, isolated):
    p = profile()
    source = shortcuts.ASSETS / 'omascreen.png'
    copied = icons.import_icon(p, source)
    assert Path(copied).exists() and Path(copied) != source
    p = replace(p, icon=copied, icon_mode='custom')
    assert shortcuts.profile_icon(p) == Path(copied)
    assert f'Icon={copied}' in shortcuts.create(p).read_text()
    assert Path(copied).stat().st_mode & 0o777 == 0o600


def test_online_download_is_pinned_bounded_and_validated(app, isolated, monkeypatch):
    p = profile(detected_model='Mac13,1')
    url = icons.online_icon_url(p)
    assert '/b66fbfa86b5faaeea1c7723ea49e523d5d7f10d5/images/com.apple.macstudio.icns.png' in url
    from io import BytesIO
    image = (shortcuts.ASSETS / 'omascreen.png').read_bytes()
    monkeypatch.setattr(icons, 'urlopen', lambda request, timeout: BytesIO(image))
    result = icons.fetch_online_icon(p)
    assert Path(result).read_bytes() == image
    monkeypatch.setattr(icons, 'urlopen', lambda request, timeout: BytesIO(b'<html>not an image</html>'))
    with pytest.raises(ValueError):
        icons.fetch_online_icon(p)
    assert Path(result).read_bytes() == image
    with pytest.raises(ValueError, match='No online icon'):
        icons.online_icon_url(replace(p, detected_model='Unknown999,1'))


@pytest.mark.parametrize('banner,security,is_apple', [(b'RFB 003.008\n',b'\x02',False),(b'RFB 003.889\n',b'\x1e',True)])
def test_detection_closes_before_authentication(monkeypatch, banner, security, is_apple):
    server = socket.socket()
    server.bind(('127.0.0.1',0)); server.listen(1)
    received=[]
    def serve():
        with server:
            client,_=server.accept()
            with client:
                client.settimeout(3)
                client.sendall(banner)
                received.append(client.recv(12))
                client.sendall(bytes([len(security)])+security)
                received.append(client.recv(1))
    thread=threading.Thread(target=serve);thread.start()
    monkeypatch.setattr('screen_sharing.native.detection.bonjour_model', lambda host: ('',''))
    result=detect(profile(port=server.getsockname()[1]))
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert received == [banner, b'']
    assert result.apple is is_apple
    assert result.high_performance is (None if is_apple else False)
