"""
ui/login_screen.py — Login screen. Fully theme-aware via Theme tokens.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from core.auth import verify_login, is_totp_enabled, get_privacy_mode
from core.session import session
from config import APP_NAME
from ui.logo import logo_pixmap, set_window_icon
from ui.theme import Theme, ThemeManager
from ui.icons import set_btn_icon, icon_label as app_icon_label
from ui.widgets.loader import Loader


class LoginScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        set_window_icon(self)
        self.setFixedSize(560, 650)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setObjectName("LoginRoot")
        self._totp_required = is_totp_enabled()
        self._build_ui()
        self._center_on_screen()
        # Defensive only: this window is closed before Settings is reachable
        # (login happens before the theme switcher exists), so a live theme
        # switch can never actually occur while it's visible.

    def _badge_specs(self) -> list[tuple[str, str, str]]:
        return [
            ("Encrypted",  Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK),
            ("Offline",    Theme.INFO_LIGHT,    Theme.INFO_DARK),
            ("2FA On" if self._totp_required else "2FA Optional",
             Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK),
        ]

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        center_layout = QVBoxLayout()
        center_layout.addStretch(1)

        # ── Main card ─────────────────────────────────────────────────────────
        self._card = card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(500)
        card.setGraphicsEffect(Theme.shadow_elevated())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(14)

        # ── Hero header ───────────────────────────────────────────────────────
        self._hero = hero = QFrame()
        hero.setObjectName("LoginHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(14)

        logo_container = QFrame()
        logo_container.setObjectName("LoginLogoContainer")
        logo_container.setFixedSize(86, 86)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo = QLabel()
        logo_pix = logo_pixmap(66)
        if not logo_pix.isNull():
            logo.setPixmap(logo_pix)
        else:
            logo.setText("PF")
            logo.setObjectName("LoginLogoText")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(logo)
        hero_layout.addWidget(logo_container)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        t = QLabel(APP_NAME)
        t.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        t.setObjectName("LoginLogoText")
        hero_text.addWidget(t)
        s = QLabel("Offline-first financial vault")
        s.setObjectName("LoginLogoSubtitle")
        hero_text.addWidget(s)
        hero_layout.addLayout(hero_text)
        hero_layout.addStretch()
        layout.addWidget(hero)

        # ── Capability badges ─────────────────────────────────────────────────
        self._badges: list[QLabel] = []
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        for txt, bg, fg in self._badge_specs():
            b = QLabel(txt)
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b.setStyleSheet(Theme.badge_style(bg, fg, radius=10, padding="4px 10px", size=11, weight=600))
            badges_row.addWidget(b)
            self._badges.append(b)
        badges_row.addStretch()
        layout.addLayout(badges_row)

        # ── Form area ─────────────────────────────────────────────────────────
        self._form_card = form_card = QFrame()
        form_card.setObjectName("LoginFormCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(10)

        form_layout.addWidget(self._lbl("Master Password"))
        self.pwd_input = self._field("Enter your master password", password=True)
        self.pwd_input.setAccessibleName("Master password")
        self.pwd_input.setAccessibleDescription("Enter the master password used to unlock the app.")
        self.pwd_input.returnPressed.connect(self._on_login)
        form_layout.addWidget(self.pwd_input)

        self.lbl_otp = self._lbl("One-Time Password")
        self.otp_input = self._field("6-digit code from authenticator")
        self.otp_input.setAccessibleName("One-time password")
        self.otp_input.setAccessibleDescription("Enter the 6-digit code from your authenticator app.")
        self.otp_input.setMaxLength(6)
        self.otp_input.returnPressed.connect(self._on_login)
        if self._totp_required:
            form_layout.addWidget(self.lbl_otp)
            form_layout.addWidget(self.otp_input)
        layout.addWidget(form_card)

        # ── Error ─────────────────────────────────────────────────────────────
        self.error_label = QLabel("")
        self.error_label.setObjectName("LoginErrorLabel")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # ── Unlock button ─────────────────────────────────────────────────────
        self.btn_login = Theme.btn(" Unlock", "hero", height=52, min_width=280)
        set_btn_icon(self.btn_login, "unlock", color="#FFFFFF", size=18)
        self.btn_login.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setAccessibleName("Unlock account")
        self.btn_login.setAccessibleDescription("Unlock the application after entering your password.")
        self.btn_login.clicked.connect(self._on_login)
        layout.addWidget(self.btn_login)

        self.setTabOrder(self.pwd_input, self.otp_input if self._totp_required else self.btn_login)
        if self._totp_required:
            self.setTabOrder(self.otp_input, self.btn_login)

        note = QLabel("Device-bound encryption")
        note.setObjectName("LoginNote")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(card)
        h.addStretch()
        center_layout.addLayout(h)
        center_layout.addStretch(1)
        root.addLayout(center_layout)

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("LoginFieldLabel")
        return l

    def _field(self, placeholder: str, password: bool = False) -> QLineEdit:
        e = QLineEdit()
        e.setObjectName("loginField")
        e.setPlaceholderText(placeholder)
        e.setMinimumHeight(46)
        if password:
            e.setEchoMode(QLineEdit.EchoMode.Password)
        return e

    def _on_login(self):
        pwd = self.pwd_input.text()
        otp = self.otp_input.text() if self._totp_required else None
        if not pwd:
            self._show_error("Please enter your password.")
            return
        self.error_label.hide()
        self.btn_login.setEnabled(False)
        self.pwd_input.setEnabled(False)
        self.otp_input.setEnabled(False)
        self.btn_login.setText("Verifying…")

        # Password/TOTP verification does real crypto work (KDF hashing) and
        # can take a noticeable moment — run it off the UI thread so the
        # loader spinner actually animates instead of the window freezing.
        Loader.run(
            self,
            fn=lambda: verify_login(pwd, otp),
            message="Unlocking your vault…",
            subtitle="Verifying your credentials",
            on_done=self._on_verify_done,
            on_error=self._on_verify_error,
        )

    def _on_verify_done(self, result):
        success, message, aes_key = result
        if not success:
            self._show_error(message)
            self._reset_login_form()
            return

        session.login(aes_key)
        session.set_privacy_mode(get_privacy_mode())

        # Building the dashboard (DB queries + full widget tree) must happen
        # on the main thread and can itself take a moment — keep a loader up
        # and defer the heavy construction one event-loop tick so the loader
        # has actually painted before the work starts.
        self._dashboard_loader = Loader(
            self, "Loading your dashboard…", subtitle="Preparing accounts and reports")
        self._dashboard_loader.show()
        QTimer.singleShot(30, self._finish_login)

    def _on_verify_error(self, exc: Exception):
        self._show_error(f"Login failed: {exc}")
        self._reset_login_form()

    def _finish_login(self):
        from ui.dashboard_screen import DashboardScreen
        self.dashboard = DashboardScreen()
        self.dashboard.showMaximized()
        # Start periodic backups (best-effort) after successful login
        try:
            from core.backup_manager import schedule_periodic_backups
            schedule_periodic_backups(interval_hours=24.0)
        except Exception:
            pass

        # Show onboarding once if not shown before
        try:
            from config import DATA_DIR
            import os
            from ui.onboarding import OnboardingDialog
            flag = os.path.join(DATA_DIR, "onboarding_shown")
            if not os.path.exists(flag):
                dlg = OnboardingDialog(self)
                dlg.exec()
                try:
                    os.makedirs(DATA_DIR, exist_ok=True)
                    with open(flag, "w") as fh:
                        fh.write("1")
                except Exception:
                    pass
        except Exception:
            pass

        if hasattr(self, "_dashboard_loader"):
            self._dashboard_loader.hide()
        self.close()

    def _reset_login_form(self):
        self.btn_login.setEnabled(True)
        self.btn_login.setText(" Unlock")
        self.pwd_input.setEnabled(True)
        self.otp_input.setEnabled(True)
        self.pwd_input.clear()
        self.otp_input.clear()
        self.pwd_input.setFocus()

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _center_on_screen(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        frame_geo = self.frameGeometry()
        frame_geo.moveCenter(screen.center())
        self.move(frame_geo.topLeft())
