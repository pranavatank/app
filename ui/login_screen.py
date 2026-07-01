"""
ui/login_screen.py — Login screen. Fully theme-aware via Theme tokens.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.auth import verify_login, is_totp_enabled, get_privacy_mode
from core.session import session
from config import APP_NAME
from ui.logo import logo_pixmap, set_window_icon
from ui.theme import Theme, ThemeManager
from ui.icons import set_btn_icon, icon_label as app_icon_label


class LoginScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        set_window_icon(self)
        self.setFixedSize(560, 650)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setObjectName("LoginRoot")
        # BG: gradient for light themes, flat dark for Midnight Pro
        if ThemeManager.is_dark():
            bg = f"background-color: {Theme.BG};"
        else:
            bg = f"background: {Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.HERO_GRADIENT_END, diagonal=True)};"
        self.setStyleSheet(f"QWidget#LoginRoot {{ {bg} }}")
        self._totp_required = is_totp_enabled()
        self._build_ui()
        self._center_on_screen()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        center_layout = QVBoxLayout()
        center_layout.addStretch(1)

        # ── Main card ─────────────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("LoginCard")
        # On dark themes use the surface color directly; on light use near-white
        card_bg = Theme.SURFACE if ThemeManager.is_dark() else "rgba(255,255,255,0.97)"
        card_border = Theme.BORDER
        card.setStyleSheet(f"""
            QFrame#LoginCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 26px;
            }}
        """)
        card.setFixedWidth(500)
        card.setGraphicsEffect(Theme.shadow_elevated())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(14)

        # ── Hero header ───────────────────────────────────────────────────────
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
        logo_container.setStyleSheet("background: rgba(255,255,255,0.20); border-radius: 32px;")
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

        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        t = QLabel(APP_NAME)
        t.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        t.setStyleSheet("color: white; background: transparent;")
        hero_text.addWidget(t)
        s = QLabel("Offline-first financial vault")
        s.setStyleSheet("color: rgba(255,255,255,0.88); font-size: 12px; background: transparent;")
        hero_text.addWidget(s)
        hero_layout.addLayout(hero_text)
        hero_layout.addStretch()
        layout.addWidget(hero)

        # ── Capability badges ─────────────────────────────────────────────────
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        for txt, bg, fg in [
            ("Encrypted",  Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK),
            ("Offline",    Theme.INFO_LIGHT,    Theme.INFO_DARK),
            ("2FA On" if self._totp_required else "2FA Optional",
             Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK),
        ]:
            b = QLabel(txt)
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b.setStyleSheet(Theme.badge_style(bg, fg, radius=10, padding="4px 10px", size=11, weight=600))
            badges_row.addWidget(b)
        badges_row.addStretch()
        layout.addLayout(badges_row)

        # ── Form area ─────────────────────────────────────────────────────────
        form_card = QFrame()
        form_card.setObjectName("LoginFormCard")
        form_card.setStyleSheet(
            Theme.tinted_surface_style(radius=14, border_color=Theme.BORDER,
                                       selector="QFrame#LoginFormCard")
        )
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
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            Theme.text_style(color=Theme.DANGER_DARK, size=13) +
            f" background: {Theme.DANGER_LIGHT}; border-radius: 8px; "
            f"padding: 12px 16px; border: 1px solid {Theme.DANGER}40;"
        )
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
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=12) + " border: none;")
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
            QLineEdit:focus {{ border: 2px solid {Theme.PRIMARY}; }}
            QLineEdit:hover {{ border-color: {Theme.BORDER_FOCUS}; }}
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
            session.set_privacy_mode(get_privacy_mode())
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
            self.close()
        else:
            self._show_error(message)
            self.btn_login.setEnabled(True)
            self.btn_login.setText(" Unlock")
            self.pwd_input.clear()
            self.otp_input.clear()
            self.pwd_input.setFocus()

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _center_on_screen(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().geometry()
        self.frameGeometry().moveCenter(screen.center())
        self.move(self.frameGeometry().topLeft())
