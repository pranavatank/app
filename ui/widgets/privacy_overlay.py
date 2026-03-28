"""
ui/widgets/privacy_overlay.py — Privacy mode with PIN reveal (Phase 8)
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class PrivacyPinDialog(QDialog):
    """Dialog to enter PIN for revealing masked values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Privacy Mode")
        self.setModal(True)
        self.setFixedSize(300, 180)
        
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("🔒 Privacy Mode Active")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Info
        info = QLabel("Enter your master password to reveal values")
        info.setStyleSheet("font-size: 11px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        # PIN input
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setPlaceholderText("Master Password")
        self.pin_input.returnPressed.connect(self.accept)
        layout.addWidget(self.pin_input)

        # Buttons
        btn_layout = QVBoxLayout()
        
        btn_reveal = QPushButton("Reveal")
        btn_reveal.setObjectName("primaryBtn")
        btn_reveal.clicked.connect(self.accept)
        btn_layout.addWidget(btn_reveal)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def get_pin(self) -> str:
        """Get entered PIN."""
        return self.pin_input.text()


def mask_amount(amount: float) -> str:
    """Mask an amount value."""
    return "₹ ••••••"


def reveal_with_pin(parent, callback):
    """
    Show PIN dialog and execute callback if correct.
    
    Args:
        parent: Parent widget
        callback: Function to call on successful PIN entry
    """
    dialog = PrivacyPinDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        pin = dialog.get_pin()
        
        # Verify PIN (check against master password)
        from core.auth import verify_password
        if verify_password(pin):
            callback()
        else:
            QMessageBox.warning(
                parent,
                "Invalid Password",
                "The password you entered is incorrect."
            )
