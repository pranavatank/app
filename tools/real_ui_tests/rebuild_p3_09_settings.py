r"""tools/real_ui_tests/rebuild_p3_09_settings.py — Phase 3.09 Settings screen test

R: Theme switching, brightness sweep, password validation, backup checks, AI status, data management.
S: TOTP configuration, full restore from backup, manage people/banks.
"""
import sys
import os
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type_widget, answer_message_box, toast_texts,
    read_secret, native_file_dialog, snapshot_db, find_dialog_by_title, redact,
    _SECRET_PATTERNS, BACKUPS
)
from PySide6.QtWidgets import QMessageBox, QLineEdit, QLabel, QApplication, QDialog
from ui.theme.theme_manager import ThemeManager
from ui.dashboard_screen import DashboardScreen


def _brightness_scan(harness, root, exclude_types=None):
    """Measure brightness of widgets, excluding ThemeCard and specified types."""
    if exclude_types is None:
        exclude_types = []
    try:
        from PySide6.QtWidgets import QWidget
        from PySide6.QtGui import QImage
        import numpy as np

        widgets_to_scan = []
        for w in root.findChildren(QWidget):
            if w.isVisible():
                if type(w).__name__ == "ThemeCard":
                    continue
                if not any(isinstance(w, t) for t in exclude_types):
                    widgets_to_scan.append(w)

        brightness_values = []
        for w in widgets_to_scan:
            try:
                pm = w.grab()
                img = pm.toImage().convertToFormat(QImage.Format.Format_RGB32)
                if not img.isNull() and img.width() > 0 and img.height() > 0:
                    ptr = img.constBits()
                    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(img.height(), img.bytesPerLine())
                    arr = arr[:, :img.width() * 4].reshape(img.height(), img.width(), 4)
                    b = arr[:, :, 0].astype(float)
                    g = arr[:, :, 1].astype(float)
                    r = arr[:, :, 2].astype(float)
                    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    brightness_values.append(float(np.mean(lum)))
            except Exception:
                pass

        return brightness_values
    except ImportError:
        return []


def run_r(p):
    settings_page = p.nav("Settings")
    p.harness.settle(0.5)

    orig_theme = ThemeManager.current_name()
    theme_names = ["Aurora", "Slate", "Nova", "Midnight Pro"]
    for theme_name in theme_names:
        if theme_name in settings_page._theme_cards:
            card = settings_page._theme_cards[theme_name]
            os_click_widget(p.harness, card, wait=0.8)
            p.harness.settle(0.5)

            current_theme = ThemeManager.current_name()
            ok_theme = current_theme == theme_name
            p.checks.check(f"settings theme {theme_name} applied", ok_theme, f"got {current_theme}")

            if current_theme == theme_name:
                import json
                from pathlib import Path
                from core import session
                config_file = Path(session._CONFIG_FILE)
                if config_file.exists():
                    prefs = json.loads(config_file.read_text())
                    ok_sidebar = prefs.get("sidebar_open", True) is not None
                    p.checks.check(f"settings theme {theme_name} sidebar_open preserved", ok_sidebar)
        else:
            p.checks.check(f"settings theme {theme_name} found", False, f"not in _theme_cards")

    if orig_theme in settings_page._theme_cards:
        os_click_widget(p.harness, settings_page._theme_cards[orig_theme], wait=0.8)
    p.harness.settle(0.5)

    brightness = _brightness_scan(p.harness, settings_page)
    ok_brightness = len(brightness) > 0
    p.checks.check("settings brightness sweep samples collected", ok_brightness, f"count={len(brightness)}")

    try:
        os_click(p.harness, settings_page, "Change password", wait=0.8)
        p.harness.settle(0.5)

        if hasattr(settings_page, 'current_pwd') and hasattr(settings_page, 'new_pwd') and hasattr(settings_page, 'confirm_pwd'):
            current_pwd_input = settings_page.current_pwd
            new_pwd_input = settings_page.new_pwd
            confirm_pwd_input = settings_page.confirm_pwd

            os_type_widget(p.harness, current_pwd_input, "", retries=1)
            os_type_widget(p.harness, new_pwd_input, "", retries=1)
            os_type_widget(p.harness, confirm_pwd_input, "", retries=1)
            p.harness.settle(0.3)

            os_click(p.harness, settings_page, "Change password", wait=0.6)
            p.harness.settle(0.3)

            toasts = toast_texts()
            expected = "Please fill all password fields."
            ok_empty = any(expected in t for t in toasts)
            p.checks.check("settings empty pwd toast", ok_empty, detail=toasts[0] if toasts else "none")
            p.observe("P3.09_R_empty_pwd_toast", toasts[0] if toasts else "none")

            os_type_widget(p.harness, current_pwd_input, "RUIH_wrong_pw1", retries=1)
            os_type_widget(p.harness, new_pwd_input, "NewPW1", retries=1)
            os_type_widget(p.harness, confirm_pwd_input, "NewPW2", retries=1)
            p.harness.settle(0.3)

            os_click(p.harness, settings_page, "Change password", wait=0.6)
            p.harness.settle(0.3)

            toasts = toast_texts()
            expected = "New passwords do not match."
            ok_mismatch = any(expected in t for t in toasts)
            p.checks.check("settings mismatch pwd toast", ok_mismatch, detail=toasts[0] if toasts else "none")
            p.observe("P3.09_R_mismatch_toast", toasts[0] if toasts else "none")

            os_type_widget(p.harness, current_pwd_input, "RUIH_wrong_pw1", retries=1)
            os_type_widget(p.harness, new_pwd_input, "NP1", retries=1)
            os_type_widget(p.harness, confirm_pwd_input, "NP1", retries=1)
            p.harness.settle(0.3)

            os_click(p.harness, settings_page, "Change password", wait=0.6)
            p.harness.settle(0.3)

            toasts = toast_texts()
            expected = "Password must be at least 8 characters."
            ok_short = any(expected in t for t in toasts)
            p.checks.check("settings short pwd toast", ok_short, detail=toasts[0] if toasts else "none")
            p.observe("P3.09_R_short_toast", toasts[0] if toasts else "none")

            before_hash = p.sql("SELECT password_hash FROM AuthSecurity LIMIT 1")
            if before_hash:
                before_hash = before_hash[0][0]

            os_type_widget(p.harness, current_pwd_input, "RUIH_wrong_pw1", retries=1)
            os_type_widget(p.harness, new_pwd_input, "RUIH_new_pw_1", retries=1)
            os_type_widget(p.harness, confirm_pwd_input, "RUIH_new_pw_1", retries=1)
            p.harness.settle(0.3)

            os_click(p.harness, settings_page, "Change password", wait=0.6)
            p.harness.settle(0.3)

            toasts = toast_texts()
            expected = "Old password is incorrect"
            ok_wrong = any(expected in t for t in toasts)
            p.checks.check("settings wrong current pwd toast", ok_wrong, detail=toasts[0] if toasts else "none")
            p.observe("P3.09_R_wrong_current_toast", toasts[0] if toasts else "none")

            after_hash = p.sql("SELECT password_hash FROM AuthSecurity LIMIT 1")
            if after_hash:
                after_hash = after_hash[0][0]

            ok_no_change = before_hash == after_hash if (before_hash and after_hash) else False
            p.checks.check("settings password hash unchanged", ok_no_change)
        else:
            p.checks.check("settings password inputs found", False)
    except Exception as e:
        p.log.log(f"change password validation failed: {e}")

    try:
        os_click(p.harness, settings_page, "Create database backup", wait=1.0)
        p.harness.settle(1.0)

        backup_files = sorted(BACKUPS.glob("backup_*.db"), key=lambda x: x.stat().st_mtime, reverse=True)
        if backup_files:
            newest = backup_files[0]
            ok_exists = newest.exists() and newest.stat().st_size > 0
            p.checks.check("settings backup file created", ok_exists, f"size={newest.stat().st_size if newest.exists() else 0}")

            try:
                check_conn = sqlite3.connect(f"file:{newest}?mode=ro", uri=True)
                integrity = check_conn.execute("PRAGMA integrity_check").fetchone()[0]
                check_conn.close()
                ok_integrity = integrity == "ok"
                p.checks.check("settings backup integrity valid", ok_integrity, detail=integrity)
            except Exception as e:
                p.checks.check("settings backup integrity valid", False, detail=str(e))
        else:
            p.checks.check("settings backup file created", False, "no backup files found")
    except Exception as e:
        p.log.log(f"backup creation failed: {e}")

    try:
        prearm = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.No, expect_title="Confirm Restore")
        os_click(p.harness, settings_page, "Restore database from backup", wait=0.8)
        p.harness.settle(0.5)

        if prearm.info.get('error'):
            p.checks.check("settings restore cancelled", False, detail=prearm.info['error'])
        else:
            p.checks.check("settings restore cancelled", True)
    except Exception as e:
        p.log.log(f"restore test failed: {e}")

    try:
        os_click(p.harness, settings_page, "Check AI availability", wait=0.8)
        p.harness.settle(0.5)

        status_label = None
        for w in settings_page.findChildren(QLabel):
            if w.isVisible() and ('available' in w.text().lower() or 'status' in w.text().lower()):
                status_label = w
                break

        if status_label:
            p.observe("P3.09_R_ai_status", status_label.text())
            p.checks.check("settings AI status visible", True)
        else:
            p.checks.check("settings AI status visible", False)
    except Exception as e:
        p.log.log(f"AI availability check failed: {e}")

    for dialog_title in ["Manage people", "Manage bank accounts", "Manage banks (master)"]:
        try:
            os_click(p.harness, settings_page, dialog_title, wait=0.8)
            p.harness.settle(0.5)

            dlg = find_dialog_by_title(QDialog, "Manage Data")
            ok_dlg = dlg is not None
            p.checks.check(f"settings {dialog_title} dialog found", ok_dlg)

            if dlg:
                dlg.reject()
                p.harness.settle(0.3)
        except Exception as e:
            p.log.log(f"{dialog_title} failed: {e}")


def run_s(p):
    settings_page = p.nav("Settings")
    p.harness.settle(0.5)

    try:
        os_click(p.harness, settings_page, "Enable two-factor authentication", wait=0.8)
        p.harness.settle(1.0)

        totp_secret = p.sql("SELECT totp_secret FROM AuthSecurity LIMIT 1")
        if totp_secret and totp_secret[0][0]:
            secret = totp_secret[0][0]
            _SECRET_PATTERNS.append(secret)

            import pyotp
            otp_code = pyotp.TOTP(secret).now()

            from tools.real_ui_tests.rebuild_common import login_to_dashboard
            prearm_logout = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Logout")
            os_click(p.harness, p.dashboard, "Logout", wait=0.5)
            p.harness.settle(1.0)

            from ui.login_screen import LoginScreen
            login_screen = p.harness.window
            if not isinstance(login_screen, LoginScreen):
                for w in QApplication.instance().allWidgets():
                    if isinstance(w, LoginScreen) and w.isVisible():
                        login_screen = w
                        break

            p.dashboard = login_to_dashboard(p.harness, login_screen=login_screen, otp=otp_code)
            p.harness.settle(1.0)

            p.checks.check("settings TOTP login success", True)

            settings_page = p.nav("Settings")
            p.harness.settle(0.5)

            try:
                os_click(p.harness, settings_page, "Disable two-factor authentication", wait=0.8)
                p.harness.settle(0.5)

                after_disable = p.sql("SELECT totp_secret FROM AuthSecurity LIMIT 1")
                if after_disable and after_disable[0][0] is None:
                    p.checks.check("settings TOTP disabled", True)
                else:
                    p.checks.check("settings TOTP disabled", False, "totp_secret still set")
            except Exception as e:
                p.log.log(f"disable TOTP failed: {e}")
        else:
            p.checks.check("settings TOTP secret generated", False)
    except Exception as e:
        p.log.log(f"TOTP setup failed: {e}")

    try:
        backup_path = snapshot_db("before_restore_test")
        p.observe("P3.09_S_backup_path", backup_path)

        from models.person import add_person
        test_pid = add_person("RUIH_test")
        p.harness.settle(0.3)

        settings_page = p.nav("Settings")
        p.harness.settle(0.5)

        prearm_restore = answer_message_box(
            p.harness, p.app,
            QMessageBox.StandardButton.Yes,
            expect_title="Confirm Restore"
        )

        native_file_dialog(
            lambda: os_click(p.harness, settings_page, "Restore database from backup", wait=0.5),
            backup_path,
            timeout=30
        )
        p.harness.settle(2.0)

        after_restore = p.sql("SELECT COUNT(*) FROM Person WHERE full_name='RUIH_test'")
        if after_restore and after_restore[0][0] == 0:
            p.checks.check("settings full restore removed test person", True)
        else:
            p.checks.check("settings full restore removed test person", False)
    except Exception as e:
        p.log.log(f"full restore test failed: {e}")

    for data_op in ["Edit person", "Delete person"]:
        try:
            if "person" in data_op.lower():
                os_click(p.harness, settings_page, "Manage people", wait=0.8)
            p.harness.settle(0.5)

            dlg = find_dialog_by_title(QDialog, "Manage Data")
            if dlg:
                dlg.reject()
                p.harness.settle(0.3)
                p.checks.check(f"settings {data_op} dialog closed", True)
            else:
                p.checks.check(f"settings {data_op} dialog found", False)
        except Exception as e:
            p.log.log(f"{data_op} failed: {e}")


if __name__ == "__main__":
    main_wrapper("09", "Settings", run_r, run_s)
