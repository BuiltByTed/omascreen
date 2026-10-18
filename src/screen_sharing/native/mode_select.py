"""Offer a connection mode after a bounded, asynchronous capability probe."""
from dataclasses import replace
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QCheckBox, QDialogButtonBox
from .detection import DetectionTask
from .profiles import ProfileStore


class ModeDialog(QDialog):
    def __init__(self, profile):
        super().__init__()
        self.profile, self.selected = profile, None
        self.setWindowTitle(f'{profile.name} — Omascreen')
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.status = QLabel('Detecting the remote computer…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.apple = QPushButton('High Performance · Apple Screen Sharing')
        self.apple.setEnabled(False)
        self.apple.clicked.connect(lambda: self.choose('apple'))
        layout.addWidget(self.apple)
        self.standard = QPushButton('Standard · VNC')
        self.standard.clicked.connect(lambda: self.choose('vnc'))
        layout.addWidget(self.standard)
        self.remember = QCheckBox('Remember this choice for this connection')
        self.remember.setChecked(True)
        layout.addWidget(self.remember)
        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.rejected.connect(self.reject)
        layout.addWidget(cancel)
        self.task = DetectionTask(self)
        self.task.finished.connect(self.detected)
        self.task.start(replace(profile))

    def detected(self, result, error):
        if error:
            self.status.setText('Could not detect the server. You can still try a connection.')
            self.apple.setEnabled(True)
            return
        self.profile = replace(self.profile, detected_model=result.model or self.profile.detected_model,
                               detected_machine=result.machine or self.profile.detected_machine)
        self.apple.setEnabled(result.apple and result.high_performance is not False)
        self.status.setText(result.message + ('\nStandard VNC on a Mac may require a separate VNC password in Screen Sharing settings.' if result.apple else ''))
        if not result.apple:
            self.choose('vnc')

    def choose(self, protocol):
        if protocol == 'apple' and not self.profile.username:
            self.status.setText('Enter your Mac username in the connection settings before using High Performance.')
            return
        self.selected = replace(self.profile, protocol=protocol)
        if self.remember.isChecked():
            try:
                store = ProfileStore()
                profiles = store.load()
                store.save([replace(p, protocol=protocol,
                    detected_model=self.profile.detected_model or p.detected_model,
                    detected_machine=self.profile.detected_machine or p.detected_machine)
                    if p.id == self.profile.id else p for p in profiles])
            except (OSError, ValueError):
                self.status.setText('Could not save this choice. Connection settings may have changed.')
                return
        self.accept()


def choose_mode(profile):
    dialog = ModeDialog(profile)
    return dialog.selected if dialog.exec() == QDialog.DialogCode.Accepted else None
