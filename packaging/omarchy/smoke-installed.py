"""Run inside a fresh package-test container, without a source checkout on PYTHONPATH."""
import os
from pathlib import Path
import subprocess
import tempfile

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import screen_sharing
from screen_sharing.native import commands, manager, shortcuts, vnc
from screen_sharing.native.profiles import ProfileStore

assert str(Path(screen_sharing.__file__).resolve()).startswith('/usr/lib/'), screen_sharing.__file__
subprocess.run(['/usr/bin/omascreen', '--version'], check=True)
with tempfile.TemporaryDirectory(prefix='omascreen-package-check-') as folder:
    os.environ['XDG_CONFIG_HOME'] = folder + '/config'
    os.environ['XDG_DATA_HOME'] = folder + '/data'
    assert commands.main(['add', 'Test desktop', '--host', 'example.invalid',
                          '--protocol', 'vnc', '--icon-mode', 'app', '--shortcut']) == 0
    profile = ProfileStore().load()[0]
    assert shortcuts.shortcut_path(profile).is_file()
    assert shortcuts.profile_icon(profile).is_file()
    assert Path(vnc.viewer_arguments(profile)[0]).is_file()
    app = QApplication(['omascreen-package-check'])
    def close_window():
        for widget in app.topLevelWidgets():
            if isinstance(widget, manager.Manager):
                widget.close()
    QTimer.singleShot(150, close_window)
    assert manager.main() == 0
print('Installed Omascreen, launcher, icon, VNC backend and GUI shutdown verified.')
