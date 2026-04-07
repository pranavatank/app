"""
ui/login_screen.py — Login screen. All buttons use Theme.btn() for guaranteed visibility.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QFrame, QPushButton
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
        self.setFixedSize(480, 530)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(f"background-color: {Theme.BG};")
        self._totp_required = is_totp_enabled()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Background with gradient
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Theme.PRIMARY}, stop:0.5 {Theme.INFO}, stop:1 {Theme.PURPLE});
            }}
        """)

        # Center container
        center_layout = QVBoxLayout()
        center_layout.addStretch(1)

        # Main card with modern glassmorphism effect
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.95);
                border: none;
                border-radius: 24px;
            }}
        """)
        card.setFixedWidth(440)
        card.setGraphicsEffect(self._create_shadow())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(48, 44, 48, 44)
        layout.setSpacing(0)

        # Logo with modern styling
        logo_container = QFrame()
        logo_container.setFixedSize(80, 80)
        logo_container.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Theme.PRIMARY}, stop:1 {Theme.INFO});
                border-radius: 40px;
                border: none;
            }}
        """)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo = QLabel("💰")
        logo.setFont(QFont("Segoe UI Emoji", 36))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(logo)
        
        logo_h = QHBoxLayout()
        logo_h.addStretch()
        logo_h.addWidget(logo_container)
        logo_h.addStretch()
        layout.addLayout(logo_h)
        layout.addSpacing(20)

        # Title
        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;")
        layout.addWidget(title)
        layout.addSpacing(6)

        subtitle = QLabel("Secure  •  Offline  •  Encrypted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            color: {Theme.TEXT_SECONDARY}; 
            font-size: 13px; 
            letter-spacing: 1px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(subtitle)
        layout.addSpacing(36)

        # Password field with icon
        pwd_label = self._lbl("🔑  Master Password")
        layout.addWidget(pwd_label)
        layout.addSpacing(8)
        self.pwd_input = self._field("Enter your master password", password=True)
        self.pwd_input.returnPressed.connect(self._on_login)
        layout.addWidget(self.pwd_input)
        layout.addSpacing(18)

        # OTP (conditional)
        self.lbl_otp = self._lbl("🔐  One-Time Password")
        self.otp_input = self._field("6-digit code from authenticator")
        self.otp_input.setMaxLength(6)
        self.otp_input.returnPressed.connect(self._on_login)
        if self._totp_required:
            layout.addWidget(self.lbl_otp)
            layout.addSpacing(8)
            layout.addWidget(self.otp_input)
            layout.addSpacing(18)

        # Error message
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"""
            color: {Theme.DANGER_DARK}; 
            font-size: 13px;
            background: {Theme.DANGER_LIGHT};
            border-radius: 8px; 
            padding: 12px 16px;
            border: 1px solid {Theme.DANGER};
        """)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        layout.addSpacing(10)

        # Unlock button with modern gradient
        self.btn_login = QPushButton("🔓  Unlock")
        self.btn_login.setFixedHeight(50)
        self.btn_login.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Theme.PRIMARY}, stop:1 {Theme.INFO});
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Theme.PRIMARY_DARK}, stop:1 {Theme.PRIMARY});
            }}
            QPushButton:pressed {{
                background: {Theme.PRIMARY_DARK};
            }}
            QPushButton:disabled {{
                background: {Theme.SURFACE_ALT};
                color: {Theme.TEXT_MUTED};
            }}
        """)
        self.btn_login.clicked.connect(self._on_login)
        layout.addWidget(self.btn_login)
        layout.addSpacing(20)

        # Security note
        note = QLabel("🔒  Device-bound encryption")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(f"""
            color: {Theme.TEXT_MUTED}; 
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(note)

        # Add card to center layout
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()
        center_layout.addLayout(h)
        center_layout.addStretch(1)

        root.addLayout(center_layout)

    def _create_shadow(self):
        """Create drop shadow effect for the card."""
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        from PyQt6.QtGui import QColor
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 60))
        return shadow

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"""
            font-weight: 600; 
            font-size: 13px; 
            color: {Theme.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)
        return l

    def _field(self, placeholder: str, password: bool = False) -> QLineEdit:
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(48)
        e.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.SURFACE_ALT};
                color: {Theme.TEXT_PRIMARY};
                border: 2px solid {Theme.BORDER};
                border-radius: 10px;
                padding: 0 16px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Theme.PRIMARY};
                background-color: {Theme.SURFACE};
            }}
            QLineEdit:hover {{
                border-color: {Theme.INFO};
            }}
        """)
        if password:
            e.setEchoMode(QLineEdit.EchoMode.Password)
        return e

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
            from ui.dashboard_screen import DashboardScreen
            self.dashboard = DashboardScreen()
            self.dashboard.showMaximized()
            self.close()
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
