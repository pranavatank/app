"""Security and database restore recovery dialogs used by SettingsScreen."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout


class TOTPEnrollmentDialog(QDialog):
    """Persistent enrollment URI display with an explicit clipboard action."""

    def __init__(self, provisioning_uri: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TOTP Enrollment")
        self.setModal(True)
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        instructions = QLabel(
            "Add this account to your authenticator app. Keep this window open "
            "until setup is complete."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self.uri_input = QLineEdit(provisioning_uri)
        self.uri_input.setReadOnly(True)
        self.uri_input.setAccessibleName("TOTP enrollment URI")
        self.uri_input.setToolTip("Select and copy the enrollment URI")
        layout.addWidget(self.uri_input)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.copy_button = QPushButton("Copy URI")
        self.copy_button.setAccessibleName("Copy TOTP enrollment URI")
        self.copy_button.clicked.connect(self._copy_uri)
        buttons.addWidget(self.copy_button)
        self.close_button = QPushButton("Done")
        self.close_button.setAccessibleName("Close TOTP enrollment")
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _copy_uri(self):
        QApplication.clipboard().setText(self.uri_input.text())
        self.copy_button.setText("Copied")


class RestoreRecoveryDialog(QDialog):
    """Keep recovery instructions visible after an incomplete database restore."""

    def __init__(self, recovery_path: str, parent=None):
        super().__init__(parent)
        self.recovery_path = recovery_path
        self.setWindowTitle("Restore Recovery Required")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        message = QLabel(
            "The database restore and automatic rollback both failed. The app "
            "has been locked to prevent use of an uncertain database. Keep the "
            "recovery snapshot below and restore it before reopening the app."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        self.path_input = QLineEdit(recovery_path)
        self.path_input.setReadOnly(True)
        self.path_input.setAccessibleName("Recovery snapshot path")
        layout.addWidget(self.path_input)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.copy_button = QPushButton("Copy path")
        self.copy_button.clicked.connect(self._copy_path)
        buttons.addWidget(self.copy_button)
        self.close_button = QPushButton("Close app")
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _copy_path(self):
        QApplication.clipboard().setText(self.path_input.text())
        self.copy_button.setText("Copied")
