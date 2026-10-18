"""Native connection library and editor, sharing the CLI's profile store."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from .profiles import Profile, ProfileStore
from . import credentials, shortcuts
from .detection import DetectionTask
from .icons import IconFetch, import_icon
from .theme import ThemeController

MODES = [('Detect automatically', 'auto'), ('High Performance (Mac)', 'apple'), ('Standard VNC', 'vnc')]
MACHINES = [('Detect automatically', 'auto'), ('Mac mini', 'mac-mini'), ('Mac Studio', 'mac-studio'),
            ('MacBook', 'macbook'), ('iMac', 'imac'), ('Desktop', 'desktop'), ('Laptop', 'laptop'), ('Server', 'server')]
ICON_MODES = [('Online Mac artwork', 'online'), ('Fetch from the Mac (SSH)', 'mac'),
              ('Lucide icon', 'lucide'), ('Custom image', 'custom'), ('Omascreen icon', 'app')]


def combo(options, value):
    box = QComboBox()
    for label, data in options:
        box.addItem(label, data)
    box.setCurrentIndex(max(0, box.findData(value)))
    return box


def label(text, points=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if points:
        font = widget.font()
        font.setPointSize(points)
        font.setWeight(QFont.Weight.DemiBold)
        widget.setFont(font)
    return widget


class ConnectionEditor(QDialog):
    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = replace(profile)
        self.result_profile = None
        self.detect_task = self.icon_task = None
        self.setWindowTitle('Connection — Omascreen')
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label('Connection settings', 20))
        tabs = QTabWidget()
        layout.addWidget(tabs)
        connection, display, artwork = QWidget(), QWidget(), QWidget()
        tabs.addTab(connection, 'Connection')
        tabs.addTab(display, 'Display & input')
        tabs.addTab(artwork, 'Icon')
        form = QFormLayout(connection)
        form.setVerticalSpacing(12)
        self.name, self.host, self.username = QLineEdit(profile.name), QLineEdit(profile.host), QLineEdit(profile.username)
        self.host.setPlaceholderText('mac.local or 192.168.1.20')
        self.username.setPlaceholderText('Mac account name (optional for VNC)')
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(profile.port)
        self.protocol = combo(MODES, profile.protocol)
        for title, widget in [('Name', self.name), ('Address', self.host), ('Port', self.port),
                              ('Username', self.username), ('Connection mode', self.protocol)]:
            form.addRow(title, widget)
        self.detect_button = QPushButton('Detect Mac / VNC capabilities')
        self.detect_button.clicked.connect(self.detect)
        form.addRow(self.detect_button)
        self.detection_status = label('Auto mode checks the server when you connect and offers the available modes.')
        form.addRow(self.detection_status)
        self.launcher = QCheckBox('Show this connection as an app in the Omarchy menu')
        self.launcher.setChecked(shortcuts.shortcut_path(profile).exists() if profile.name and profile.host else True)
        form.addRow(self.launcher)
        settings = QFormLayout(display)
        settings.setVerticalSpacing(12)
        self.fullscreen = QCheckBox('Open fullscreen')
        self.fullscreen.setChecked(profile.fullscreen)
        settings.addRow(self.fullscreen)
        settings.addRow(label('The following options apply to High Performance connections. Standard VNC uses TigerVNC’s own controls.'))
        self.apple_widgets = []
        self.options = {}
        for field, title in [('audio', 'Play remote audio'), ('curtain', 'Blank the physical Mac display'),
                             ('ctrl_as_cmd', 'Map Ctrl to Command'), ('grab_keyboard', 'Capture keyboard shortcuts')]:
            widget = QCheckBox(title)
            widget.setChecked(getattr(profile, field))
            self.options[field] = widget
            self.apple_widgets.append(widget)
            settings.addRow(widget)
        for field, title, values in [('resolution', 'Resolution', ['auto','1920x1080','2560x1440','3840x2160']),
                                      ('scale', 'HiDPI', ['auto','on','off']), ('codec','Video codec',['auto','hevc','avc'])]:
            widget = combo([(v.capitalize(), v) for v in values], getattr(profile, field))
            self.options[field] = widget
            self.apple_widgets.append(widget)
            settings.addRow(title, widget)
        self.protocol.currentIndexChanged.connect(self.mode_changed)
        self.mode_changed()
        icons = QFormLayout(artwork)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icons.addRow(self.preview)
        self.icon_mode = combo(ICON_MODES, profile.icon_mode)
        self.machine = combo(MACHINES, profile.machine)
        for i in range(self.machine.count()):
            sample = replace(profile, machine=self.machine.itemData(i), icon_mode='lucide')
            self.machine.setItemIcon(i, QIcon(str(shortcuts.profile_icon(sample))))
        self.model = QLineEdit(profile.detected_model)
        self.model.setPlaceholderText('Detected with Bonjour; e.g. Mac13,1')
        self.ssh_host = QLineEdit(profile.ssh_host)
        self.ssh_host.setPlaceholderText('Optional separate SSH / local address')
        icons.addRow('Icon source', self.icon_mode)
        icons.addRow('Device / Lucide icon', self.machine)
        icons.addRow('Mac model identifier', self.model)
        icons.addRow('SSH address', self.ssh_host)
        self.fetch_button = QPushButton('Download icon')
        self.fetch_button.clicked.connect(self.fetch)
        self.upload_button = QPushButton('Choose image…')
        self.upload_button.clicked.connect(self.upload)
        icons.addRow(self.fetch_button)
        icons.addRow(self.upload_button)
        self.icon_hint = label('')
        icons.addRow(self.icon_hint)
        self.icon_mode.currentIndexChanged.connect(self.icon_changed)
        self.machine.currentIndexChanged.connect(self.update_preview)
        self.icon_changed()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        profile = replace(self.profile, name=self.name.text(), host=self.host.text(), username=self.username.text(),
            port=self.port.value(), protocol=self.protocol.currentData(), fullscreen=self.fullscreen.isChecked(),
            machine=self.machine.currentData(), icon_mode=self.icon_mode.currentData(),
            detected_model=self.model.text().strip(), ssh_host=self.ssh_host.text().strip())
        for field, widget in self.options.items():
            setattr(profile, field, widget.isChecked() if isinstance(widget, QCheckBox) else widget.currentData())
        profile.validate()
        return profile

    def mode_changed(self):
        for widget in self.apple_widgets:
            widget.setEnabled(self.protocol.currentData() != 'vnc')

    def update_preview(self):
        profile = replace(self.profile, icon_mode=self.icon_mode.currentData(), machine=self.machine.currentData())
        self.preview.setPixmap(QIcon(str(shortcuts.profile_icon(profile))).pixmap(QSize(128, 128)))

    def icon_changed(self):
        mode = self.icon_mode.currentData()
        self.fetch_button.setVisible(mode in ('online', 'mac'))
        self.fetch_button.setText('Fetch from Mac' if mode == 'mac' else 'Download icon')
        self.upload_button.setVisible(mode == 'custom')
        self.machine.setEnabled(mode == 'lucide')
        self.model.setVisible(mode == 'online')
        self.ssh_host.setEnabled(mode in ('online', 'mac'))
        hints = {'online': 'Matching artwork downloads to your local cache. No SSH or File Sharing is needed on the local network. Newer models may be missing from the catalog.',
                 'mac': 'Reads the Mac’s exact icon over an existing trusted SSH key login. Enable Remote Login on the Mac; File Sharing is not needed.',
                 'lucide': 'Choose a device above. Lucide icons are bundled and work offline.',
                 'custom': 'Choose a PNG, JPEG, WebP or SVG. A copy is saved with Omascreen.',
                 'app': 'Use the Omascreen app icon.'}
        self.icon_hint.setText(hints[mode])
        self.update_preview()

    def detect(self):
        try:
            profile = self.values()
        except ValueError as error:
            QMessageBox.warning(self, 'Connection details', str(error))
            return
        self.detect_button.setEnabled(False)
        self.detection_status.setText('Checking the server…')
        self.detect_task = DetectionTask(self)
        self.detect_task.finished.connect(self.detected)
        self.detect_task.start(profile)

    def detected(self, result, error):
        self.detect_button.setEnabled(True)
        if error:
            self.detection_status.setText(error)
            return
        self.detection_status.setText(result.message)
        if result.model:
            self.model.setText(result.model)
        self.profile.detected_machine = result.machine or self.profile.detected_machine
        self.update_preview()

    def fetch(self):
        try:
            profile = self.values()
        except ValueError as error:
            QMessageBox.warning(self, 'Connection details', str(error))
            return
        self.fetch_button.setEnabled(False)
        self.icon_hint.setText('Fetching artwork…')
        self.icon_task = IconFetch(self)
        self.icon_task.finished.connect(self.fetched)
        self.icon_task.start(profile)

    def fetched(self, path, error):
        self.fetch_button.setEnabled(True)
        if error:
            self.icon_hint.setText(error)
            return
        self.profile.fetched_icon = path
        self.icon_hint.setText('Icon saved locally. Save the connection to update its app launcher.')
        self.update_preview()

    def upload(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose a connection icon', '', 'Images (*.png *.jpg *.jpeg *.webp *.svg)')
        if path:
            try:
                self.profile.icon = import_icon(self.values(), path)
                self.update_preview()
            except (ValueError, OSError) as error:
                QMessageBox.warning(self, 'Could not import image', str(error))

    def save(self):
        try:
            self.result_profile = self.values()
            if self.result_profile.icon_mode == 'custom' and not self.result_profile.icon:
                raise ValueError('Choose a custom image first.')
        except ValueError as error:
            QMessageBox.warning(self, 'Connection details', str(error))
            return
        self.accept()


class Manager(QWidget):
    def __init__(self):
        super().__init__()
        self.profiles = []
        self.setWindowTitle('Omascreen')
        self.setWindowIcon(QIcon(str(shortcuts.icon_path('auto'))))
        self.resize(860, 560)
        self.setMinimumSize(720, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.addWidget(label('Omascreen', 26))
        heading.addWidget(label('Your remote desktops, one click away.'))
        header.addLayout(heading, 1)
        add = QPushButton('＋ Add connection')
        add.clicked.connect(self.add)
        header.addWidget(add)
        layout.addLayout(header)
        body = QHBoxLayout()
        layout.addLayout(body, 1)
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search connections…')
        self.search.textChanged.connect(self.filter)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setIconSize(QSize(64, 64))
        self.list.setSpacing(6)
        self.list.currentRowChanged.connect(self.selected)
        self.list.itemDoubleClicked.connect(lambda _: self.connect())
        left.addWidget(self.list)
        body.addLayout(left, 3)
        right = QVBoxLayout()
        right.setContentsMargins(24, 16, 0, 16)
        self.art = QLabel()
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addStretch()
        right.addWidget(self.art)
        self.name, self.details = label('', 21), label('')
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.name)
        right.addWidget(self.details)
        self.connect_button = QPushButton('Connect')
        self.connect_button.setMinimumHeight(42)
        self.connect_button.clicked.connect(self.connect)
        right.addWidget(self.connect_button)
        actions = QHBoxLayout()
        self.edit_button, self.remove_button = QPushButton('Edit'), QPushButton('Remove')
        self.edit_button.clicked.connect(self.edit)
        self.remove_button.clicked.connect(self.remove)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.remove_button)
        right.addLayout(actions)
        self.launcher = QCheckBox('Show as an app in the Omarchy menu')
        self.launcher.clicked.connect(self.toggle_launcher)
        right.addWidget(self.launcher)
        right.addStretch()
        body.addLayout(right, 3)
        self.status = label('')
        layout.addWidget(self.status)
        self.reload()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reload)
        self.timer.start(2000)

    def current(self):
        item = self.list.currentItem()
        return next((p for p in self.profiles if item and p.id == item.data(Qt.ItemDataRole.UserRole)), None)

    def reload(self):
        try:
            profiles = ProfileStore().load()
        except (ValueError, OSError) as error:
            self.status.setText(str(error))
            return
        if profiles == self.profiles and self.list.count():
            return
        previous = self.current()
        self.profiles = sorted(profiles, key=lambda p: p.name.casefold())
        self.list.blockSignals(True)
        self.list.clear()
        index = 0
        for i, p in enumerate(self.profiles):
            item = QListWidgetItem(QIcon(str(shortcuts.profile_icon(p))), f'{p.name}\n{p.host}')
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            item.setSizeHint(QSize(280, 84))
            self.list.addItem(item)
            if previous and p.id == previous.id:
                index = i
        self.list.blockSignals(False)
        self.list.setCurrentRow(index if self.profiles else -1)
        self.filter()
        self.selected()
        self.status.setText(f'{len(profiles)} saved connection' + ('' if len(profiles) == 1 else 's'))

    def filter(self):
        query = self.search.text().casefold()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(query not in item.text().casefold())

    def selected(self, *_):
        p = self.current()
        self.name.setText(p.name if p else 'Add your first connection')
        self.details.setText((p.host + '\n' + dict((v,k) for k,v in MODES)[p.protocol]) if p else 'Connect to a Mac or any standard VNC desktop.')
        self.art.setPixmap(QIcon(str(shortcuts.profile_icon(p) if p else shortcuts.icon_path('auto'))).pixmap(QSize(160,160)))
        for widget in (self.connect_button, self.edit_button, self.remove_button, self.launcher):
            widget.setEnabled(p is not None)
        self.launcher.setChecked(bool(p and shortcuts.shortcut_path(p).exists()))

    def add(self):
        self.open_editor(Profile.new())

    def edit(self):
        if profile := self.current():
            self.open_editor(profile)

    def open_editor(self, profile):
        editor = ConnectionEditor(profile, self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = editor.result_profile
            store = ProfileStore()
            profiles = store.load()
            if any(p.id != updated.id and p.name.casefold() == updated.name.casefold() for p in profiles):
                raise ValueError('That connection name is already in use.')
            store.save([p for p in profiles if p.id != updated.id] + [updated])
            if editor.launcher.isChecked():
                shortcuts.create(updated)
            else:
                shortcuts.remove(updated)
            self.reload()
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.ItemDataRole.UserRole) == updated.id:
                    self.list.setCurrentRow(i)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, 'Could not save connection', str(error))

    def connect(self):
        if profile := self.current():
            subprocess.Popen([sys.executable, '-m', 'screen_sharing.entry_launcher', profile.id], start_new_session=True)

    def toggle_launcher(self, enabled):
        if profile := self.current():
            try:
                shortcuts.create(profile) if enabled else shortcuts.remove(profile)
            except OSError as error:
                QMessageBox.warning(self, 'Could not update app launcher', str(error))
            self.selected()

    def remove(self):
        if not (profile := self.current()):
            return
        if QMessageBox.question(self, 'Remove connection', f'Remove {profile.name}, its app launcher and saved password?') != QMessageBox.StandardButton.Yes:
            return
        try:
            store = ProfileStore()
            profiles = store.load()
            credentials.remove(profile.id)
            shortcuts.remove(profile)
            store.save([p for p in profiles if p.id != profile.id])
            self.reload()
        except (ValueError, OSError, credentials.keyring.errors.KeyringError) as error:
            QMessageBox.warning(self, 'Could not remove connection', str(error))


def main():
    app = QApplication.instance() or QApplication(['omascreen'])
    app.setApplicationName('Omascreen')
    app.setDesktopFileName('omascreen')
    app.theme_controller = ThemeController(app)
    window = Manager()
    window.show()
    return app.exec()
