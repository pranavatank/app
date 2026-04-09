"""
ui/settings_screen.py — Security & Settings. All buttons use Theme.btn() for guaranteed visibility.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QFormLayout, QLineEdit, QCheckBox, QFileDialog,
    QMessageBox, QScrollArea, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import os, shutil
from datetime import datetime

from ui.theme import Theme
from core.session import session
from core.auth import change_password, is_totp_enabled, enable_totp, disable_totp
from config import DB_PATH, BACKUP_DIR


def _device_info() -> dict:
    try:
        from core.auth import get_device_fingerprint
        import platform
        return {"device_id": get_device_fingerprint(),
                "platform": f"{platform.system()} {platform.release()}"}
    except Exception:
        return {"device_id": "Unknown", "platform": "Unknown"}


class SettingsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.badge_totp = None
        self.badge_privacy = None
        self.badge_backup = None
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("SettingsRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)

        layout.addWidget(self._header_card())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setSpacing(14)
        cl.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._section_security(), 0, 0)
        grid.addWidget(self._section_data(), 0, 1)
        grid.addWidget(self._section_privacy(), 1, 0)
        grid.addWidget(self._section_backup(), 1, 1)
        grid.addWidget(self._section_device(), 2, 0, 1, 2)

        cl.addLayout(grid)
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _header_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("SettingsHeaderCard")
        card.setStyleSheet(
            Theme.card_style(
                bg=Theme.SURFACE,
                border_color=Theme.BORDER,
                radius=12,
                padding=0,
                selector="QFrame#SettingsHeaderCard",
            )
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(16))
        title_col.addWidget(title)

        subtitle = QLabel("Security, privacy, backup and data controls")
        subtitle.setStyleSheet(Theme.muted_style(12))
        title_col.addWidget(subtitle)

        top.addLayout(title_col)
        top.addStretch()

        quick_backup = Theme.btn("Quick Backup", "success", height=38, min_width=130)
        quick_backup.clicked.connect(self._on_create_backup)
        top.addWidget(quick_backup)
        layout.addLayout(top)

        badges = QHBoxLayout()
        badges.setSpacing(8)
        self.badge_totp = QLabel()
        self.badge_privacy = QLabel()
        self.badge_backup = QLabel()
        badges.addWidget(self.badge_totp)
        badges.addWidget(self.badge_privacy)
        badges.addWidget(self.badge_backup)
        badges.addStretch()
        layout.addLayout(badges)

        self._refresh_header_badges()
        return card

    def _refresh_header_badges(self):
        if self.badge_totp is not None:
            totp_enabled = is_totp_enabled()
            self.badge_totp.setText("2FA Enabled" if totp_enabled else "2FA Disabled")
            self.badge_totp.setStyleSheet(
                Theme.badge_style(
                    Theme.SUCCESS_LIGHT if totp_enabled else Theme.WARNING_LIGHT,
                    Theme.SUCCESS_DARK if totp_enabled else Theme.WARNING_DARK,
                    radius=10,
                    padding="4px 10px",
                    size=11,
                    weight=600,
                )
            )

        if self.badge_privacy is not None:
            self.badge_privacy.setText("Privacy On" if session.privacy_mode else "Privacy Off")
            self.badge_privacy.setStyleSheet(
                Theme.badge_style(
                    Theme.INFO_LIGHT if session.privacy_mode else Theme.SURFACE_ALT,
                    Theme.INFO_DARK if session.privacy_mode else Theme.TEXT_SECONDARY,
                    radius=10,
                    padding="4px 10px",
                    size=11,
                    weight=600,
                )
            )

        if self.badge_backup is not None:
            self.badge_backup.setText(f"Backup Folder: {os.path.basename(BACKUP_DIR)}")
            self.badge_backup.setStyleSheet(
                Theme.badge_style(Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK, radius=10, padding="4px 10px", size=11, weight=600)
            )

    # ── Sections ─────────────────────────────────────────────────────────────

    def _section_security(self) -> QGroupBox:
        g = self._group("🔐  Security")
        gl = QVBoxLayout(g)
        gl.setSpacing(14)

        # Change password card
        card = self._card()
        cl = QVBoxLayout(card)
        cl.addWidget(self._card_title("Change Master Password"))
        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.current_pwd = self._pwd_field("Current password")
        self.new_pwd     = self._pwd_field("New password")
        self.confirm_pwd = self._pwd_field("Confirm new password")
        form.addRow(self._form_lbl("Current"), self.current_pwd)
        form.addRow(self._form_lbl("New"), self.new_pwd)
        form.addRow(self._form_lbl("Confirm"), self.confirm_pwd)
        cl.addLayout(form)
        btn = Theme.btn("Change Password", "primary", height=38, min_width=180)
        btn.clicked.connect(self._on_change_password)
        cl.addWidget(btn)
        gl.addWidget(card)

        # TOTP card
        card2 = self._card()
        cl2 = QVBoxLayout(card2)
        cl2.addWidget(self._card_title("Two-Factor Authentication (TOTP)"))
        self.totp_checkbox = QCheckBox("Enable TOTP (Time-based OTP)")
        self.totp_checkbox.setChecked(is_totp_enabled())
        self.totp_checkbox.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=14, weight=500))
        self.totp_checkbox.stateChanged.connect(self._on_totp_toggle)
        cl2.addWidget(self.totp_checkbox)
        note = QLabel("Requires a compatible authenticator app (e.g. Google Authenticator).")
        note.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        cl2.addWidget(note)
        gl.addWidget(card2)

        return g

    def _section_data(self) -> QGroupBox:
        g = self._group("🗂  Data Management")
        gl = QVBoxLayout(g)
        gl.setSpacing(14)

        card1 = self._card()
        cl1 = QVBoxLayout(card1)
        cl1.addWidget(self._card_title("Family Members (Persons)"))
        cl1.addWidget(self._muted("Add or manage family members for finance tracking."))
        btn1 = Theme.btn("Manage Persons", "primary", height=40, min_width=180)
        btn1.clicked.connect(self._on_manage_persons)
        cl1.addWidget(btn1)
        gl.addWidget(card1)

        card2 = self._card()
        cl2 = QVBoxLayout(card2)
        cl2.addWidget(self._card_title("Bank Accounts"))
        cl2.addWidget(self._muted("Add or manage bank accounts for each family member."))
        btn2 = Theme.btn("Manage Bank Accounts", "info", height=40, min_width=210)
        btn2.clicked.connect(self._on_manage_accounts)
        cl2.addWidget(btn2)
        gl.addWidget(card2)

        card3 = self._card()
        cl3 = QVBoxLayout(card3)
        cl3.addWidget(self._card_title("Banks (Master)"))
        cl3.addWidget(self._muted("Manage bank master entries and display nicknames."))
        btn3 = Theme.btn("Manage Banks", "secondary", height=40, min_width=180)
        btn3.clicked.connect(self._on_manage_banks)
        cl3.addWidget(btn3)
        gl.addWidget(card3)

        return g

    def _section_privacy(self) -> QGroupBox:
        g = self._group("🕵️  Privacy")
        gl = QVBoxLayout(g)

        card = self._card()
        cl = QVBoxLayout(card)
        cl.addWidget(self._card_title("Privacy Mode"))
        self.privacy_checkbox = QCheckBox("Mask all financial amounts")
        self.privacy_checkbox.setChecked(session.privacy_mode)
        self.privacy_checkbox.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=14, weight=500))
        self.privacy_checkbox.stateChanged.connect(self._on_privacy_toggle)
        cl.addWidget(self.privacy_checkbox)
        cl.addWidget(self._muted("All amounts will display as ₹ ****. Toggle to reveal."))
        gl.addWidget(card)

        return g

    def _section_backup(self) -> QGroupBox:
        g = self._group("💾  Backup & Restore")
        gl = QVBoxLayout(g)
        gl.setSpacing(14)

        card1 = self._card()
        cl1 = QVBoxLayout(card1)
        cl1.addWidget(self._card_title("Create Backup"))
        cl1.addWidget(self._muted("Copy your database to a safe location."))
        btn1 = Theme.btn("💾  Create Backup", "success", height=38, min_width=170)
        btn1.clicked.connect(self._on_create_backup)
        cl1.addWidget(btn1)
        gl.addWidget(card1)

        card2 = self._card()
        cl2 = QVBoxLayout(card2)
        cl2.addWidget(self._card_title("Restore from Backup"))
        warn = QLabel("⚠  This will replace your current database. All data will be lost!")
        warn.setStyleSheet(Theme.text_style(color=Theme.WARNING_DARK, size=13, weight=600))
        cl2.addWidget(warn)
        btn2 = Theme.btn("🔄  Restore Backup", "danger", height=38, min_width=170)
        btn2.clicked.connect(self._on_restore_backup)
        cl2.addWidget(btn2)
        gl.addWidget(card2)

        return g

    def _section_device(self) -> QGroupBox:
        g = self._group("💻  Device Information")
        gl = QVBoxLayout(g)

        card = self._card()
        fl = QFormLayout(card)
        fl.setSpacing(10)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info = _device_info()
        dev_id = QLabel(info["device_id"][:28] + "…")
        dev_id.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12) + " font-family: Consolas, 'Courier New', monospace;")
        fl.addRow(self._form_lbl("Device ID"), dev_id)
        fl.addRow(self._form_lbl("Platform"), QLabel(info["platform"][:60]))
        fl.addRow("", self._muted("This app is bound to this device for security."))
        gl.addWidget(card)

        return g

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet(f"""
            QGroupBox {{
                border: none;
                margin-top: 8px;
                background: transparent;
                font-size: 14px;
                font-weight: 700;
                color: {Theme.PRIMARY_DARK};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 6px;
            }}
        """)
        return g

    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("SettingsCard")
        f.setStyleSheet(
            Theme.card_style(
                bg=Theme.SURFACE,
                border_color=Theme.BORDER,
                radius=12,
                padding=14,
                selector="QFrame#SettingsCard",
            )
        )
        f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return f

    def _card_title(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        l.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))
        return l

    def _muted(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(Theme.muted_style(12))
        return l

    def _pwd_field(self, placeholder: str) -> QLineEdit:
        e = QLineEdit()
        e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(38)
        e.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.SURFACE_ALT};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                border-radius: 10px;
                padding: 0 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                background-color: {Theme.SURFACE};
            }}
        """)
        return e

    def _form_lbl(self, text: str) -> QLabel:
        l = QLabel(f"{text}:")
        l.setStyleSheet(Theme.section_label_style())
        return l

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_change_password(self):
        cur = self.current_pwd.text()
        new = self.new_pwd.text()
        conf = self.confirm_pwd.text()
        if not all([cur, new, conf]):
            QMessageBox.warning(self, "Missing", "Please fill all password fields."); return
        if new != conf:
            QMessageBox.warning(self, "Mismatch", "New passwords do not match."); return
        if len(new) < 8:
            QMessageBox.warning(self, "Too Short", "Password must be at least 8 characters."); return
        ok, msg = change_password(cur, new)
        if ok:
            QMessageBox.information(self, "Success", "Password changed successfully!")
            for f in [self.current_pwd, self.new_pwd, self.confirm_pwd]:
                f.clear()
        else:
            QMessageBox.warning(self, "Failed", msg)

    def _on_totp_toggle(self, state):
        enabled = bool(state)
        try:
            if enabled:
                uri = enable_totp()
                QMessageBox.information(self, "TOTP Enabled",
                    f"Scan this URI with your authenticator app:\n\n{uri}")
            else:
                disable_totp()
                QMessageBox.information(self, "TOTP Disabled",
                    "Two-factor authentication has been disabled.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            self.totp_checkbox.setChecked(not enabled)
        finally:
            self._refresh_header_badges()

    def _on_privacy_toggle(self, state):
        session.set_privacy_mode(bool(state))
        self._refresh_header_badges()
        if self.parent_window:
            self.parent_window.refresh_overview()

    def _on_create_backup(self):
        try:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"backup_{ts}.db")
            shutil.copy2(DB_PATH, dest)
            QMessageBox.information(self, "Backup Created", f"Saved to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def _on_restore_backup(self):
        reply = QMessageBox.warning(
            self, "Confirm Restore",
            "WARNING: This will REPLACE your current database.\nAll current data will be lost!\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File", BACKUP_DIR, "Database Files (*.db)")
        if not path: return
        try:
            shutil.copy2(path, DB_PATH)
            QMessageBox.information(self, "Restored",
                "Database restored successfully. Please restart the app.")
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", str(e))

    def _on_manage_persons(self):
        from ui.dialogs.person_dialog import PersonManagementDialog
        PersonManagementDialog(self).exec()

    def _on_manage_accounts(self):
        from ui.dialogs.account_dialog import AccountManagementDialog
        AccountManagementDialog(self).exec()

    def _on_manage_banks(self):
        from ui.dialogs.bank_dialog import BankManagementDialog
        BankManagementDialog(self).exec()

    def refresh(self):
        self.totp_checkbox.setChecked(is_totp_enabled())
        self.privacy_checkbox.setChecked(session.privacy_mode)
        self._refresh_header_badges()
