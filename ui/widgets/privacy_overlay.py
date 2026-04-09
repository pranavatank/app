"""
ui/widgets/privacy_overlay.py — Privacy mode PIN-reveal dialog.
FIX: verify_password now called with correct arguments via verify_login.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ui.theme import Theme


class PrivacyPinDialog(QDialog):
    """Dialog to enter master password for revealing masked values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Privacy Mode")
        self.setModal(True)
        self.setFixedSize(340, 220)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("🔒  Privacy Mode Active")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=700))
        layout.addWidget(title)

        info = QLabel("Enter your master password to reveal amounts.")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(Theme.muted_style(12))
        layout.addWidget(info)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setPlaceholderText("Master Password")
        self.pin_input.setFixedHeight(42)
        self.pin_input.returnPressed.connect(self.accept)
        layout.addWidget(self.pin_input)

        btn_reveal = Theme.btn("Reveal", "primary", height=40, min_width=100)
        btn_reveal.clicked.connect(self.accept)
        layout.addWidget(btn_reveal)

        btn_cancel = Theme.btn("Cancel", "secondary", height=36, min_width=95)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)

    def get_password(self) -> str:
        return self.pin_input.text()


def reveal_with_password(parent, callback):
    """
    Show password dialog; call callback() only if correct.
    Uses verify_login for proper password + device verification.
    """
    dialog = PrivacyPinDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        password = dialog.get_password()
        from core.auth import verify_login
        success, _, _ = verify_login(password)
        if success:
            callback()
        else:
            QMessageBox.warning(parent, "Invalid Password",
                                "The password you entered is incorrect.")
