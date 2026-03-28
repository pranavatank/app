"""
ui/login_screen.py — Beautiful login screen with centered card layout.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.auth import verify_login, is_totp_enabled
from core.session import session
from config import APP_NAME
from ui.theme import Theme


class LoginScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setFixedSize(480, 520)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(f"background-color: {Theme.BG};")
        self._totp_required = is_totp_enabled()
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

        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(0)

        # Logo + gradient bar
        logo_lbl = QLabel("💰")
        logo_lbl.setFont(QFont("Segoe UI Emoji", 32))
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_lbl)
        layout.addSpacing(10)

        # Gradient accent strip
        strip = QFrame()
        strip.setFixedHeight(4)
        strip.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {Theme.PRIMARY}, stop:1 {Theme.SUCCESS});
            border-radius: 2px;
        """)
        layout.addWidget(strip)
        layout.addSpacing(16)

        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Secure · Offline · Personal")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px; letter-spacing: 1px;")
        layout.addWidget(subtitle)
        layout.addSpacing(28)

        # Password field
        layout.addWidget(self._field_label("Master Password"))
        layout.addSpacing(5)
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("Enter your master password")
        self.pwd_input.setFixedHeight(42)
        self.pwd_input.returnPressed.connect(self._on_login)
        layout.addWidget(self.pwd_input)
        layout.addSpacing(14)

        # OTP field (conditional)
        self.lbl_otp = self._field_label("One-Time Password")
        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("6-digit code from authenticator")
        self.otp_input.setMaxLength(6)
        self.otp_input.setFixedHeight(42)
        self.otp_input.returnPressed.connect(self._on_login)

        if self._totp_required:
            layout.addWidget(self.lbl_otp)
            layout.addSpacing(5)
            layout.addWidget(self.otp_input)
            layout.addSpacing(14)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet(f"""
            color: {Theme.DANGER}; font-size: 12px;
            background: {Theme.DANGER_LIGHT};
            border-radius: 6px; padding: 6px;
        """)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        layout.addSpacing(8)

        layout.addStretch()

        # Unlock button
        self.btn_login = QPushButton("🔓  Unlock")
        self.btn_login.setObjectName("primaryBtn")
        self.btn_login.setFixedHeight(46)
        self.btn_login.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.btn_login.clicked.connect(self._on_login)
        layout.addWidget(self.btn_login)
        layout.addSpacing(14)

        note = QLabel("🔒  This app is bound to this device")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(note)

        # Center card
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

    def _on_login(self):
        pwd = self.pwd_input.text()
        otp = self.otp_input.text() if self._totp_required else None

        if not pwd:
            self._show_error("Please enter your password.")
            return

        self.btn_login.setEnabled(False)
        self.btn_login.setText("Verifying…")

        success, message, aes_key = verify_login(pwd, otp)

        if success:
            session.login(aes_key)
            self._open_dashboard()
        else:
            self._show_error(message)
            self.btn_login.setEnabled(True)
            self.btn_login.setText("🔓  Unlock")
            self.pwd_input.clear()
            self.otp_input.clear()
            self.pwd_input.setFocus()

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _open_dashboard(self):
        from ui.dashboard_screen import DashboardScreen
        self.dashboard = DashboardScreen()
        self.dashboard.showMaximized()
        self.close()
