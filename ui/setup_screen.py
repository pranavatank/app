"""
ui/setup_screen.py — First-run master password setup. Beautiful centered card layout.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from core.auth import setup_master_password
from config import APP_NAME
from ui.theme import Theme


class SetupScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Setup")
        self.setFixedSize(480, 580)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(f"background-color: {Theme.BG};")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)

        # ── Centered Card ───────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 16px;
            }}
        """)
        card.setFixedWidth(400)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(0)

        # Logo area
        logo_row = QHBoxLayout()
        logo_lbl = QLabel("💰")
        logo_lbl.setFont(QFont("Segoe UI Emoji", 28))
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_row.addStretch()
        logo_row.addWidget(logo_lbl)
        logo_row.addStretch()
        card_layout.addLayout(logo_row)
        card_layout.addSpacing(12)

        # Title
        title = QLabel("Welcome")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        card_layout.addWidget(title)
        card_layout.addSpacing(4)

        subtitle = QLabel("Set a master password to secure your data")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(28)

        # Password
        card_layout.addWidget(self._field_label("Master Password"))
        card_layout.addSpacing(4)
        self.pwd_input = self._line_edit("Enter master password", password=True)
        self.pwd_input.textChanged.connect(self._update_strength)
        card_layout.addWidget(self.pwd_input)
        card_layout.addSpacing(6)

        # Strength bar
        self.strength_bar = QFrame()
        self.strength_bar.setFixedHeight(4)
        self.strength_bar.setStyleSheet(f"background:{Theme.BORDER}; border-radius:2px;")
        card_layout.addWidget(self.strength_bar)

        self.strength_label = QLabel("")
        self.strength_label.setStyleSheet(f"font-size: 11px; color: {Theme.TEXT_MUTED};")
        card_layout.addWidget(self.strength_label)
        card_layout.addSpacing(14)

        # Confirm password
        card_layout.addWidget(self._field_label("Confirm Password"))
        card_layout.addSpacing(4)
        self.confirm_input = self._line_edit("Re-enter master password", password=True)
        card_layout.addWidget(self.confirm_input)
        card_layout.addSpacing(16)

        # TOTP checkbox
        self.totp_check = QCheckBox("Enable two-factor authentication (TOTP)")
        self.totp_check.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        card_layout.addWidget(self.totp_check)
        card_layout.addSpacing(24)

        # Setup button
        self.btn_setup = QPushButton("Create Account")
        self.btn_setup.setObjectName("primaryBtn")
        self.btn_setup.setFixedHeight(44)
        self.btn_setup.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.btn_setup.clicked.connect(self._on_setup)
        card_layout.addWidget(self.btn_setup)
        card_layout.addSpacing(12)

        # Warning note
        note = QLabel("⚠  Your password cannot be recovered. Keep it safe.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(f"color: {Theme.WARNING}; font-size: 11px;")
        card_layout.addWidget(note)

        # Center card horizontally
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()
        root.addLayout(h)
        root.addStretch(1)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {Theme.TEXT_PRIMARY};")
        return lbl

    def _line_edit(self, placeholder: str, password: bool = False) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(42)
        if password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        return edit

    def _update_strength(self, text: str):
        n = len(text)
        if n == 0:
            self.strength_bar.setStyleSheet(f"background:{Theme.BORDER}; border-radius:2px;")
            self.strength_label.setText("")
        elif n < 8:
            self.strength_bar.setStyleSheet(f"background:{Theme.DANGER}; border-radius:2px;")
            self.strength_label.setText("Weak — use at least 8 characters")
            self.strength_label.setStyleSheet(f"font-size:11px; color:{Theme.DANGER};")
        elif n < 12:
            self.strength_bar.setStyleSheet(f"background:{Theme.WARNING}; border-radius:2px;")
            self.strength_label.setText("Moderate")
            self.strength_label.setStyleSheet(f"font-size:11px; color:{Theme.WARNING};")
        else:
            self.strength_bar.setStyleSheet(f"background:{Theme.SUCCESS}; border-radius:2px;")
            self.strength_label.setText("Strong ✓")
            self.strength_label.setStyleSheet(f"font-size:11px; color:{Theme.SUCCESS};")

    def _on_setup(self):
        pwd     = self.pwd_input.text()
        confirm = self.confirm_input.text()
        if len(pwd) < 8:
            QMessageBox.warning(self, "Weak Password", "Password must be at least 8 characters.")
            return
        if pwd != confirm:
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return

        totp_uri = setup_master_password(pwd, self.totp_check.isChecked())
        if totp_uri:
            QMessageBox.information(self, "TOTP Enabled",
                f"Scan this URI in Google Authenticator:\n\n{totp_uri}")

        QMessageBox.information(self, "Setup Complete", "Account created! Please log in.")
        from ui.login_screen import LoginScreen
        self.login = LoginScreen()
        self.login.show()
        self.close()
