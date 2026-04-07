"""
ui/settings_screen.py — Security & Settings. All buttons use Theme.btn() for guaranteed visibility.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QFormLayout, QLineEdit, QCheckBox, QFileDialog,
    QMessageBox, QScrollArea, QFrame
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
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setSpacing(18)
        cl.setContentsMargins(0, 0, 0, 0)

        cl.addWidget(self._section_security())
        cl.addWidget(self._section_data())
        cl.addWidget(self._section_privacy())
        cl.addWidget(self._section_backup())
        cl.addWidget(self._section_device())
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

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
        self.current_pwd = self._pwd_field("Current password")
        self.new_pwd     = self._pwd_field("New password")
        self.confirm_pwd = self._pwd_field("Confirm new password")
        form.addRow("Current:", self.current_pwd)
        form.addRow("New:", self.new_pwd)
        form.addRow("Confirm:", self.confirm_pwd)
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
        self.totp_checkbox.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 14px;")
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
        btn1 = Theme.btn("Manage Persons", "primary", height=38, min_width=180)
        btn1.clicked.connect(self._on_manage_persons)
        cl1.addWidget(btn1)
        gl.addWidget(card1)

        card2 = self._card()
        cl2 = QVBoxLayout(card2)
        cl2.addWidget(self._card_title("Bank Accounts"))
        cl2.addWidget(self._muted("Add or manage bank accounts for each family member."))
        btn2 = Theme.btn("Manage Bank Accounts", "primary", height=38, min_width=200)
        btn2.clicked.connect(self._on_manage_accounts)
        cl2.addWidget(btn2)
        gl.addWidget(card2)

        card3 = self._card()
        cl3 = QVBoxLayout(card3)
        cl3.addWidget(self._card_title("Banks (Master)"))
        cl3.addWidget(self._muted("Manage bank master entries and display nicknames."))
        btn3 = Theme.btn("Manage Banks", "primary", height=38, min_width=180)
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
        self.privacy_checkbox.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 14px;")
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
        warn.setStyleSheet(f"color: {Theme.WARNING_DARK}; font-size: 13px; font-weight: 600;")
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
        info = _device_info()
        dev_id = QLabel(info["device_id"][:28] + "…")
        dev_id.setStyleSheet("font-family: monospace; font-size: 12px;")
        fl.addRow("Device ID:", dev_id)
        fl.addRow("Platform:", QLabel(info["platform"][:60]))
        fl.addRow("", self._muted("This app is bound to this device for security."))
        gl.addWidget(card)

        return g

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
                margin-top: 18px;
                padding: 16px 16px 12px 16px;
                background-color: {Theme.SURFACE};
                font-weight: 700;
                font-size: 14px;
                color: {Theme.PRIMARY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px; padding: 0 6px;
                background-color: {Theme.SURFACE};
                color: {Theme.PRIMARY};
            }}
        """)
        return g

    def _card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
                padding: 14px;
            }}
        """)
        f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return f

    def _card_title(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        l.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        return l

    def _muted(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; background: transparent;")
        return l

    def _pwd_field(self, placeholder: str) -> QLineEdit:
        e = QLineEdit()
        e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(38)
        return e

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

    def _on_privacy_toggle(self, state):
        session.set_privacy_mode(bool(state))
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
