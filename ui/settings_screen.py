"""
ui/settings_screen.py — Security & Settings with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QCheckBox, QFileDialog,
    QMessageBox, QScrollArea, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

import os, shutil
from datetime import datetime

from ui.theme import Theme
from core.session import session
from core.auth import change_password, is_totp_enabled, enable_totp, disable_totp
from config import DB_PATH, BACKUP_DIR


def _get_device_info() -> dict:
    """Safe device info helper."""
    try:
        from core.auth import get_device_fingerprint
        import platform
        return {"device_id": get_device_fingerprint(), "platform": platform.platform()}
    except Exception:
        return {"device_id": "Unknown", "platform": "Unknown"}


class SettingsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._sx = Theme.get_settings_styles()
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("settingsRoot")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setObjectName("settingsContent")
        cl = QVBoxLayout(content)
        cl.setSpacing(16)
        cl.setContentsMargins(0,0,0,0)

        cl.addWidget(self._build_security_section())
        cl.addWidget(self._build_data_management_section())
        cl.addWidget(self._build_privacy_section())
        cl.addWidget(self._build_backup_section())
        cl.addWidget(self._build_device_section())
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Ensure object-name based app stylesheet selectors are applied on first render.
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_security_section(self) -> QGroupBox:
        group = QGroupBox("🔐  Security")
        group.setObjectName("settingsSection")
        group.setStyleSheet(self._sx["section_group"])
        group.setTitle("🔐  Security")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 4, 8, 8)

        # Change password
        pwd_frame = self._settings_card()
        pl = QVBoxLayout(pwd_frame)
        pl.addWidget(self._card_title("Change Master Password"))
        form = QFormLayout(); form.setSpacing(10)
        self.current_pwd = self._pwd_field("Current password")
        self.new_pwd     = self._pwd_field("New password")
        self.confirm_pwd = self._pwd_field("Confirm new password")
        form.addRow("Current:", self.current_pwd)
        form.addRow("New:", self.new_pwd)
        form.addRow("Confirm:", self.confirm_pwd)
        pl.addLayout(form)
        btn = QPushButton("Change Password")
        btn.setObjectName("primaryBtn"); btn.setFixedHeight(36)
        btn.setMinimumWidth(180)
        btn.setStyleSheet(self._sx["button_primary"])
        btn.clicked.connect(self._on_change_password)
        pl.addWidget(btn)
        layout.addWidget(pwd_frame)

        # TOTP
        totp_frame = self._settings_card()
        tl = QVBoxLayout(totp_frame)
        tl.addWidget(self._card_title("Two-Factor Authentication"))
        self.totp_checkbox = QCheckBox("Enable TOTP (Time-based OTP)")
        self.totp_checkbox.setChecked(is_totp_enabled())
        self.totp_checkbox.setStyleSheet(self._sx["checkbox"])
        self.totp_checkbox.stateChanged.connect(self._on_totp_toggle)
        tl.addWidget(self.totp_checkbox)
        note = QLabel("Requires a compatible authenticator app (e.g. Google Authenticator).")
        note.setObjectName("mutedLabel")
        note.setStyleSheet(self._sx["muted"])
        tl.addWidget(note)
        layout.addWidget(totp_frame)

        return group

    def _build_data_management_section(self) -> QGroupBox:
        group = QGroupBox("🗂  Data Management")
        group.setObjectName("settingsSection")
        group.setStyleSheet(self._sx["section_group"])
        group.setTitle("🗂  Data Management")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 4, 8, 8)

        person_frame = self._settings_card()
        pl = QVBoxLayout(person_frame)
        pl.addWidget(self._card_title("Family Members (Persons)"))
        d1 = QLabel("Add or manage family members for finance tracking.")
        d1.setStyleSheet(self._sx["text"])
        pl.addWidget(d1)
        btn = QPushButton("Manage Persons")
        btn.setObjectName("primaryBtn"); btn.setFixedHeight(36)
        btn.setMinimumWidth(180)
        btn.setStyleSheet(self._sx["button_primary"])
        btn.clicked.connect(self._on_manage_persons)
        pl.addWidget(btn)
        layout.addWidget(person_frame)

        account_frame = self._settings_card()
        al = QVBoxLayout(account_frame)
        al.addWidget(self._card_title("Bank Accounts"))
        d2 = QLabel("Add or manage bank accounts for each family member.")
        d2.setStyleSheet(self._sx["text"])
        al.addWidget(d2)
        btn2 = QPushButton("Manage Bank Accounts")
        btn2.setObjectName("primaryBtn"); btn2.setFixedHeight(36)
        btn2.setMinimumWidth(200)
        btn2.setStyleSheet(self._sx["button_primary"])
        btn2.clicked.connect(self._on_manage_accounts)
        al.addWidget(btn2)
        layout.addWidget(account_frame)

        return group

    def _build_privacy_section(self) -> QGroupBox:
        group = QGroupBox("🕵️  Privacy")
        group.setObjectName("settingsSection")
        group.setStyleSheet(self._sx["section_group"])
        group.setTitle("🕵️  Privacy")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 4, 8, 8)

        frame = self._settings_card()
        fl = QVBoxLayout(frame)
        fl.addWidget(self._card_title("Privacy Mode"))
        self.privacy_checkbox = QCheckBox("Mask all financial amounts")
        self.privacy_checkbox.setChecked(session.privacy_mode)
        self.privacy_checkbox.setStyleSheet(self._sx["checkbox"])
        self.privacy_checkbox.stateChanged.connect(self._on_privacy_toggle)
        fl.addWidget(self.privacy_checkbox)
        note = QLabel("All amounts will display as ₹ ****. Toggle to reveal.")
        note.setObjectName("mutedLabel")
        note.setStyleSheet(self._sx["muted"])
        fl.addWidget(note)
        layout.addWidget(frame)

        return group

    def _build_backup_section(self) -> QGroupBox:
        group = QGroupBox("💾  Backup & Restore")
        group.setObjectName("settingsSection")
        group.setStyleSheet(self._sx["section_group"])
        group.setTitle("💾  Backup & Restore")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 4, 8, 8)

        bk_frame = self._settings_card()
        bl = QVBoxLayout(bk_frame)
        bl.addWidget(self._card_title("Create Backup"))
        d3 = QLabel("Copy your database to a safe location.")
        d3.setStyleSheet(self._sx["text"])
        bl.addWidget(d3)
        btn = QPushButton("Create Backup")
        btn.setObjectName("successBtn"); btn.setFixedHeight(36)
        btn.setMinimumWidth(170)
        btn.setStyleSheet(self._sx["button_success"])
        btn.clicked.connect(self._on_create_backup)
        bl.addWidget(btn)
        layout.addWidget(bk_frame)

        rs_frame = self._settings_card()
        rl = QVBoxLayout(rs_frame)
        rl.addWidget(self._card_title("Restore from Backup"))
        warn = QLabel("⚠  This will replace your current database. All data will be lost!")
        warn.setObjectName("warningLabel")
        warn.setStyleSheet(self._sx["warning"])
        rl.addWidget(warn)
        btn2 = QPushButton("Restore Backup")
        btn2.setObjectName("dangerBtn"); btn2.setFixedHeight(36)
        btn2.setMinimumWidth(170)
        btn2.setStyleSheet(self._sx["button_danger"])
        btn2.clicked.connect(self._on_restore_backup)
        rl.addWidget(btn2)
        layout.addWidget(rs_frame)

        return group

    def _build_device_section(self) -> QGroupBox:
        group = QGroupBox("💻  Device Information")
        group.setObjectName("settingsSection")
        group.setStyleSheet(self._sx["section_group"])
        group.setTitle("💻  Device Information")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 4, 8, 8)

        frame = self._settings_card()
        fl = QFormLayout(frame)
        info = _get_device_info()
        dev_id = QLabel(info.get("device_id","Unknown")[:24] + "…")
        dev_id.setStyleSheet("font-family: monospace; font-size: 12px;")
        fl.addRow("Device ID:", dev_id)
        fl.addRow("Platform:", QLabel(info.get("platform","Unknown")[:60]))
        note = QLabel("This app is bound to this device for security.")
        note.setObjectName("mutedLabel")
        note.setStyleSheet(self._sx["muted"])
        fl.addRow("", note)
        layout.addWidget(frame)

        return group

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _settings_card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("settingsCard")
        f.setStyleSheet(self._sx["card"])
        f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        f.setAutoFillBackground(True)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 38))
        f.setGraphicsEffect(shadow)
        return f

    def _card_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet(self._sx["card_title"])
        return lbl

    def _pwd_field(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(38)
        edit.setStyleSheet(self._sx["line_edit"])
        return edit

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_change_password(self):
        cur = self.current_pwd.text()
        new = self.new_pwd.text()
        conf = self.confirm_pwd.text()
        if not cur or not new or not conf:
            QMessageBox.warning(self, "Missing Fields", "Please fill all password fields."); return
        if new != conf:
            QMessageBox.warning(self, "Mismatch", "New passwords do not match."); return
        if len(new) < 8:
            QMessageBox.warning(self, "Weak Password", "Password must be at least 8 characters."); return
        success, msg = change_password(cur, new)
        if success:
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
                    f"Scan this URI with your authenticator:\n\n{uri}")
            else:
                disable_totp()
                QMessageBox.information(self, "TOTP Disabled", "Two-factor authentication has been disabled.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            self.totp_checkbox.setChecked(not enabled)

    def _on_privacy_toggle(self, state):
        enabled = bool(state)
        session.set_privacy_mode(enabled)
        if self.parent_window: self.parent_window.refresh_overview()

    def _on_create_backup(self):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"backup_{ts}.db")
            shutil.copy2(DB_PATH, dest)
            QMessageBox.information(self, "Backup Created", f"Saved to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def _on_restore_backup(self):
        reply = QMessageBox.warning(self, "Confirm Restore",
            "WARNING: This will REPLACE your current database.\nAll current data will be lost!\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        path, _ = QFileDialog.getOpenFileName(self, "Select Backup", BACKUP_DIR, "Database (*.db)")
        if not path: return
        try:
            shutil.copy2(path, DB_PATH)
            QMessageBox.information(self, "Restored", "Database restored. Please restart the app.")
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", str(e))

    def _on_manage_persons(self):
        from ui.dialogs.person_dialog import PersonManagementDialog
        PersonManagementDialog(self).exec()

    def _on_manage_accounts(self):
        from ui.dialogs.account_dialog import AccountManagementDialog
        AccountManagementDialog(self).exec()

    def refresh(self):
        self.totp_checkbox.setChecked(is_totp_enabled())
        self.privacy_checkbox.setChecked(session.privacy_mode)
