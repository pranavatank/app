"""
ui/setup_screen.py — First-run password setup.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QCheckBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.auth import setup_master_password
from config import APP_NAME
from ui.logo import logo_pixmap, set_window_icon
from ui.theme import Theme, ThemeManager
from ui.icons import set_btn_icon
from ui.widgets.toast_utils import show_warning, show_success


class SetupScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Setup")
        set_window_icon(self)
        self.setFixedSize(480, 600)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setObjectName("setupWindow")
        self._build_ui()
        self._center_on_screen()
        # Defensive only: closes itself before Settings is reachable (see
        # login_screen.py's identical note) — registered for consistency.
        ThemeManager.register_on_change(self.refresh_theme)

    def refresh_theme(self, *_args):
        """Defensive-only (see __init__) — re-apply shadow effect and update
        strength bar styling if needed. Card/strip styles are now in global QSS."""
        if hasattr(self, "_card"):
            self._card.setGraphicsEffect(Theme.shadow_elevated())
        # Re-trigger strength display in case current text is set
        if hasattr(self, "pwd_input"):
            self._update_strength(self.pwd_input.text())

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)

        self._card = card = QFrame()
        card.setObjectName("setupCard")
        card.setFixedWidth(400)
        card.setGraphicsEffect(Theme.shadow_elevated())

        cl = QVBoxLayout(card)
        cl.setContentsMargins(40, 36, 40, 36)
        cl.setSpacing(0)

        # Logo
        logo = QLabel()
        logo_pm = logo_pixmap(88)
        if not logo_pm.isNull():
            logo.setPixmap(logo_pm)
        else:
            logo.setText("PF")
            logo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(logo)
        cl.addSpacing(8)

        self._strip = strip = QFrame()
        strip.setObjectName("setupStrip")
        strip.setMinimumHeight(4)
        cl.addWidget(strip)
        cl.addSpacing(14)

        title = QLabel("Welcome")
        title.setObjectName("setupTitle")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(title)

        subtitle = QLabel("Set a master password to secure your data")
        subtitle.setObjectName("setupSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(subtitle)
        cl.addSpacing(26)

        # Password
        cl.addWidget(self._lbl("Master Password"))
        cl.addSpacing(4)
        self.pwd_input = self._field("Enter master password", password=True)
        self.pwd_input.setAccessibleName("Master password input")
        self.pwd_input.setAccessibleDescription("Enter your master password to secure your data.")
        self.pwd_input.textChanged.connect(self._update_strength)
        cl.addWidget(self.pwd_input)
        cl.addSpacing(5)

        self.strength_bar = QFrame()
        self.strength_bar.setObjectName("setupStrengthBar")
        self.strength_bar.setMinimumHeight(4)
        self.strength_bar.setProperty("strength", "empty")
        cl.addWidget(self.strength_bar)

        self.strength_label = QLabel("")
        self.strength_label.setObjectName("setupStrengthLabel")
        cl.addWidget(self.strength_label)
        cl.addSpacing(14)

        # Confirm
        cl.addWidget(self._lbl("Confirm Password"))
        cl.addSpacing(4)
        self.confirm_input = self._field("Re-enter master password", password=True)
        self.confirm_input.setAccessibleName("Confirm password input")
        self.confirm_input.setAccessibleDescription("Re-enter your master password to confirm.")
        cl.addWidget(self.confirm_input)
        cl.addSpacing(16)

        # TOTP
        self.totp_check = QCheckBox("Enable two-factor authentication (TOTP)")
        self.totp_check.setObjectName("setupTotpCheck")
        self.totp_check.setAccessibleName("Enable two-factor authentication")
        self.totp_check.setAccessibleDescription("Enable TOTP for additional security using Google Authenticator or similar.")
        cl.addWidget(self.totp_check)
        cl.addSpacing(24)

        # Create button
        self.btn_setup = Theme.btn("  Create Account", "primary", height=46, min_width=320)
        set_btn_icon(self.btn_setup, "create_account", size=16)
        self.btn_setup.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.btn_setup.setAccessibleName("Create account")
        self.btn_setup.setAccessibleDescription("Create your account with the entered password.")
        self.btn_setup.clicked.connect(self._on_setup)
        cl.addWidget(self.btn_setup)
        cl.addSpacing(12)

        self.setTabOrder(self.pwd_input, self.confirm_input)
        self.setTabOrder(self.confirm_input, self.totp_check)
        self.setTabOrder(self.totp_check, self.btn_setup)

        note = QLabel("Your password cannot be recovered. Keep it safe.")
        note.setObjectName("setupNote")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(note)

        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()
        root.addLayout(h)
        root.addStretch(1)

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("setupFieldLabel")
        return l

    def _field(self, placeholder: str, password: bool = False) -> QLineEdit:
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setMinimumHeight(42)
        if password:
            e.setEchoMode(QLineEdit.EchoMode.Password)
        return e

    def _update_strength(self, text: str):
        n = len(text)
        if n == 0:
            self.strength_bar.setProperty("strength", "empty")
            self.strength_label.setText("")
            self.strength_label.setProperty("strength", "empty")
        elif n < 8:
            self.strength_bar.setProperty("strength", "weak")
            self.strength_label.setText("Weak — use at least 8 characters")
            self.strength_label.setProperty("strength", "weak")
        elif n < 12:
            self.strength_bar.setProperty("strength", "moderate")
            self.strength_label.setText("Moderate")
            self.strength_label.setProperty("strength", "moderate")
        else:
            self.strength_bar.setProperty("strength", "strong")
            self.strength_label.setText("Strong ✓")
            self.strength_label.setProperty("strength", "strong")
        # Trigger style update
        self.strength_bar.style().unpolish(self.strength_bar)
        self.strength_bar.style().polish(self.strength_bar)
        self.strength_label.style().unpolish(self.strength_label)
        self.strength_label.style().polish(self.strength_label)

    def _on_setup(self):
        pwd     = self.pwd_input.text()
        confirm = self.confirm_input.text()
        if len(pwd) < 8:
            show_warning("Password must be at least 8 characters.")
            return
        if pwd != confirm:
            show_warning("Passwords do not match.")
            return
        totp_uri = setup_master_password(pwd, self.totp_check.isChecked())
        if totp_uri:
            show_success(f"Scan this URI in Google Authenticator:\n\n{totp_uri}")
        show_success("Account created! Please log in.")
        from ui.login_screen import LoginScreen
        self.login = LoginScreen()
        self.login.show()
        self.close()

    def _center_on_screen(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        geo = self.frameGeometry()
        geo.moveCenter(screen.center())
        self.move(geo.topLeft())
