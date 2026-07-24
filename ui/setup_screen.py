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


class SetupScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Setup")
        set_window_icon(self)
        self.setFixedSize(480, 600)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(self._root_css())
        self._build_ui()
        self._center_on_screen()
        # Defensive only: closes itself before Settings is reachable (see
        # login_screen.py's identical note) — registered for consistency.
        ThemeManager.register_on_change(self.refresh_theme)

    @staticmethod
    def _root_css() -> str:
        return f"background-color: {Theme.BG};"

    @staticmethod
    def _card_css() -> str:
        return Theme.tinted_surface_style(radius=16, selector="QFrame#SetupCard")

    def refresh_theme(self, *_args):
        """Defensive-only (see __init__) — restyles the static chrome; the
        strength bar/label depend on runtime password-strength state, not
        theme, so they're left to their own update logic rather than guessed
        at here."""
        self.setStyleSheet(self._root_css())
        if hasattr(self, "_card"):
            self._card.setStyleSheet(self._card_css())
        if hasattr(self, "_strip"):
            self._strip.setStyleSheet(Theme.panel_strip_style(radius=2))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)

        self._card = card = QFrame()
        card.setObjectName("SetupCard")
        card.setStyleSheet(self._card_css())
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
        strip.setFixedHeight(4)
        strip.setStyleSheet(Theme.panel_strip_style(radius=2))
        cl.addWidget(strip)
        cl.addSpacing(14)

        title = QLabel("Welcome")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=22, weight=700))
        cl.addWidget(title)

        subtitle = QLabel("Set a master password to secure your data")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=13))
        cl.addWidget(subtitle)
        cl.addSpacing(26)

        # Password
        cl.addWidget(self._lbl("Master Password"))
        cl.addSpacing(4)
        self.pwd_input = self._field("Enter master password", password=True)
        self.pwd_input.textChanged.connect(self._update_strength)
        cl.addWidget(self.pwd_input)
        cl.addSpacing(5)

        self.strength_bar = QFrame()
        self.strength_bar.setFixedHeight(4)
        self.strength_bar.setStyleSheet(f"background: {Theme.BORDER}; border-radius: 2px;")
        cl.addWidget(self.strength_bar)

        self.strength_label = QLabel("")
        self.strength_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
        cl.addWidget(self.strength_label)
        cl.addSpacing(14)

        # Confirm
        cl.addWidget(self._lbl("Confirm Password"))
        cl.addSpacing(4)
        self.confirm_input = self._field("Re-enter master password", password=True)
        cl.addWidget(self.confirm_input)
        cl.addSpacing(16)

        # TOTP
        self.totp_check = QCheckBox("Enable two-factor authentication (TOTP)")
        self.totp_check.setStyleSheet(Theme.muted_style(12))
        cl.addWidget(self.totp_check)
        cl.addSpacing(24)

        # Create button
        self.btn_setup = Theme.btn("  Create Account", "primary", height=46, min_width=320)
        set_btn_icon(self.btn_setup, "create_account", size=16)
        self.btn_setup.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.btn_setup.clicked.connect(self._on_setup)
        cl.addWidget(self.btn_setup)
        cl.addSpacing(12)

        self.setTabOrder(self.pwd_input, self.confirm_input)
        self.setTabOrder(self.confirm_input, self.totp_check)
        self.setTabOrder(self.totp_check, self.btn_setup)

        note = QLabel("Your password cannot be recovered. Keep it safe.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(Theme.text_style(color=Theme.WARNING, size=11))
        cl.addWidget(note)

        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()
        root.addLayout(h)
        root.addStretch(1)

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=600))
        return l

    def _field(self, placeholder: str, password: bool = False) -> QLineEdit:
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(42)
        if password:
            e.setEchoMode(QLineEdit.EchoMode.Password)
        return e

    def _update_strength(self, text: str):
        n = len(text)
        if n == 0:
            self.strength_bar.setStyleSheet(f"background: {Theme.BORDER}; border-radius: 2px;")
            self.strength_label.setText("")
        elif n < 8:
            self.strength_bar.setStyleSheet(
                Theme.panel_strip_style(Theme.DANGER_GRADIENT_START, Theme.DANGER_GRADIENT_END, radius=2))
            self.strength_label.setText("Weak — use at least 8 characters")
            self.strength_label.setStyleSheet(Theme.text_style(color=Theme.DANGER, size=11))
        elif n < 12:
            self.strength_bar.setStyleSheet(
                Theme.panel_strip_style(Theme.WARNING_GRADIENT_START, Theme.WARNING_GRADIENT_END, radius=2))
            self.strength_label.setText("Moderate")
            self.strength_label.setStyleSheet(Theme.text_style(color=Theme.WARNING, size=11))
        else:
            self.strength_bar.setStyleSheet(
                Theme.panel_strip_style(Theme.SUCCESS_GRADIENT_START, Theme.SUCCESS_GRADIENT_END, radius=2))
            self.strength_label.setText("Strong ✓")
            self.strength_label.setStyleSheet(Theme.text_style(color=Theme.SUCCESS, size=11))

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

    def _center_on_screen(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        geo = self.frameGeometry()
        geo.moveCenter(screen.center())
        self.move(geo.topLeft())
