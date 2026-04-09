"""
ui/login_screen.py — Login screen. All buttons use Theme.btn() for guaranteed visibility.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.auth import verify_login, is_totp_enabled
from core.session import session
from config import APP_NAME
from ui.logo import logo_pixmap, set_window_icon
from ui.theme import Theme


class LoginScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        set_window_icon(self)
        self.setFixedSize(560, 650)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setObjectName("LoginRoot")
        self.setStyleSheet(f"""
            QWidget#LoginRoot {{
                background: {Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.HERO_GRADIENT_END, diagonal=True)};
            }}
        """)
        self._totp_required = is_totp_enabled()
        self._build_ui()
        self._center_on_screen()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        # Center container
        center_layout = QVBoxLayout()
        center_layout.addStretch(1)

        # Main card shell
        card = QFrame()
        card.setObjectName("LoginCard")
        card.setStyleSheet(f"""
            QFrame#LoginCard {{
                background-color: rgba(255, 255, 255, 0.96);
                border: 1px solid rgba(255, 255, 255, 0.55);
                border-radius: 26px;
            }}
        """)
        card.setFixedWidth(500)
        card.setGraphicsEffect(self._create_shadow())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(14)

        # Hero header
        hero = QFrame()
        hero.setObjectName("LoginHero")
        hero.setStyleSheet(f"""
            QFrame#LoginHero {{
                background: {Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.HERO_GRADIENT_END)};
                border-radius: 18px;
                border: none;
            }}
        """)

        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(14)

        logo_container = QFrame()
        logo_container.setFixedSize(86, 86)
        logo_container.setStyleSheet("background: rgba(255,255,255,0.22); border-radius: 32px;")

        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo = QLabel()
        logo_pix = logo_pixmap(66)
        if not logo_pix.isNull():
            logo.setPixmap(logo_pix)
        else:
            logo.setText("PF")
            logo.setStyleSheet("color: white; font-size: 18px; font-weight: 700;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(logo)

        hero_layout.addWidget(logo_container)

        hero_text_col = QVBoxLayout()
        hero_text_col.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        hero_text_col.addWidget(title)

        subtitle = QLabel("Offline-first financial vault")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 12px; background: transparent;")
        hero_text_col.addWidget(subtitle)

        hero_layout.addLayout(hero_text_col)
        hero_layout.addStretch()
        layout.addWidget(hero)

        # Capability badges
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        for txt, bg, fg in [
            ("Encrypted", Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK),
            ("Offline", Theme.INFO_LIGHT, Theme.INFO_DARK),
            ("2FA On" if self._totp_required else "2FA Optional", Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK),
        ]:
            badge = QLabel(txt)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(Theme.badge_style(bg, fg, radius=10, padding="4px 10px", size=11, weight=600))
            badges_row.addWidget(badge)
        badges_row.addStretch()
        layout.addLayout(badges_row)

        # Form container
        form_card = QFrame()
        form_card.setObjectName("LoginFormCard")
        form_card.setStyleSheet(
            Theme.tinted_surface_style(radius=14, border_color=Theme.BORDER, selector="QFrame#LoginFormCard")
        )
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(10)

        pwd_label = self._lbl("🔑  Master Password")
        form_layout.addWidget(pwd_label)
        self.pwd_input = self._field("Enter your master password", password=True)
        self.pwd_input.returnPressed.connect(self._on_login)
        form_layout.addWidget(self.pwd_input)

        # OTP (conditional)
        self.lbl_otp = self._lbl("🔐  One-Time Password")
        self.otp_input = self._field("6-digit code from authenticator")
        self.otp_input.setMaxLength(6)
        self.otp_input.returnPressed.connect(self._on_login)
        if self._totp_required:
            form_layout.addWidget(self.lbl_otp)
            form_layout.addWidget(self.otp_input)

        layout.addWidget(form_card)

        # Error message
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            Theme.text_style(color=Theme.DANGER_DARK, size=13) +
            f" background: {Theme.DANGER_LIGHT}; border-radius: 8px; padding: 12px 16px; border: 1px solid {Theme.DANGER};"
        )
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Unlock button
        self.btn_login = Theme.btn("🔓  Unlock", "hero", height=52, min_width=280)
        self.btn_login.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self._on_login)
        layout.addWidget(self.btn_login)

        # Security note
        note = QLabel("🔒  Device-bound encryption")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=12) + " border: none;")
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
        shadow.setBlurRadius(46)
        shadow.setXOffset(0)
        shadow.setYOffset(12)
        shadow.setColor(QColor(0, 0, 0, 72))
        return shadow

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=600) + " border: none;")
        return l

    def _field(self, placeholder: str, password: bool = False) -> QLineEdit:
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(46)
        e.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                border: 1.5px solid {Theme.BORDER};
                border-radius: 10px;
                padding: 0 16px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Theme.PRIMARY};
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

    def _center_on_screen(self):
        """Center the window on the screen."""
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
