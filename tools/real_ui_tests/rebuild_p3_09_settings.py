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
    _SECRET_PATTERNS, BACKUPS, answer_modal_dialog, wait_until, assert_foreground,
    login_to_dashboard,
)
from tools.real_ui_test_harness import find_by_accessible_name
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMessageBox, QLineEdit, QLabel, QApplication, QDialog
from ui.theme.theme_manager import ThemeManager
from ui.dashboard_screen import DashboardScreen
from ui.manage_data_screen import ManageDataScreen
from ui.dialogs.person_dialog import PersonDialog
from ui.dialogs.bank_dialog import BankDialog


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
    import json
    from pathlib import Path
    from core import session
    config_file = Path(session._CONFIG_FILE)
    orig_sidebar_open = None
    if config_file.exists():
        prefs = json.loads(config_file.read_text())
        orig_sidebar_open = prefs.get("sidebar_open")
    for theme_name in theme_names:
        if theme_name in settings_page._theme_cards:
            card = settings_page._theme_cards[theme_name]
            os_click_widget(p.harness, card, wait=0.8)
            p.harness.settle(0.5)

            current_theme = ThemeManager.current_name()
            ok_theme = current_theme == theme_name
            p.checks.check(f"settings theme {theme_name} applied", ok_theme, f"got {current_theme}")

            if current_theme == theme_name:
                if config_file.exists():
                    prefs = json.loads(config_file.read_text())
                    ok_sidebar = "sidebar_open" in prefs and prefs["sidebar_open"] == orig_sidebar_open
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

            ok_no_change = before_hash is not None and after_hash is not None and before_hash == after_hash
            p.checks.check("settings password hash unchanged", ok_no_change)
        else:
            p.checks.check("settings password inputs found", False)
    except Exception as e:
        p.checks.check("settings password validation", False, repr(e))

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
        p.checks.check("settings backup creation", False, repr(e))

    try:
        prearm = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.No, expect_title="Confirm Restore")
        os_click(p.harness, settings_page, "Restore database from backup", wait=0.8)
        p.harness.settle(0.5)

        ok_prearm = prearm.done and prearm.info.get("title") == "Confirm Restore" and prearm.info.get("error") is None
        p.checks.check("settings restore prearm ran", ok_prearm, detail=str(prearm.info) if not ok_prearm else "")
        if not ok_prearm:
            p.checks.check("settings restore cancelled", False, detail=prearm.info.get('error', 'prearm failed'))
        else:
            p.checks.check("settings restore cancelled", True)
    except Exception as e:
        p.checks.check("settings restore test", False, repr(e))

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
        p.checks.check("settings AI availability", False, repr(e))

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
            p.checks.check(f"settings {dialog_title}", False, repr(e))


def _totp_secret(p):
    rows = p.sql("SELECT totp_secret FROM AuthSecurity LIMIT 1")
    return rows[0][0] if rows else None


def _toggle_totp_checkbox(p, settings_page, want_enabled):
    """OS-click the checkbox indicator; the centre of the full-width checkbox
    widget is not a reliable click target."""
    checkbox = find_by_accessible_name(settings_page, "Enable two-factor authentication")
    for _ in range(2):
        if checkbox.isChecked() == want_enabled:
            break
        assert_foreground(checkbox.window())
        p.harness.click_at_via_os(checkbox, QPoint(10, checkbox.height() // 2), wait=0.8)
    wait_until(p.harness, lambda: bool(_totp_secret(p)) == want_enabled, timeout=5)
    return checkbox


def _visible_login_screen():
    from ui.login_screen import LoginScreen
    return next((w for w in QApplication.instance().allWidgets() if isinstance(w, LoginScreen) and w.isVisible()), None)


def _prearm_ok(prearm):
    """True if the prearmed handler ran without error; always disarms it."""
    ran = prearm.done
    prearm.done = True
    return ran and prearm.error is None and prearm.info.get("error") is None


def _open_manage_data(p, settings_page, button_name):
    os_click(p.harness, settings_page, button_name, wait=0.8)
    dlg = find_dialog_by_title(QDialog, "Manage Data")
    return dlg, (dlg.findChild(ManageDataScreen) if dlg else None)


def _select_row_by_id(p, dlg, table, id_col, record_id):
    """OS-click the table row whose hidden ID column matches; the Edit/Delete
    buttons act on currentRow() and only warn when nothing is selected."""
    row = next((r for r in range(table.rowCount()) if table.item(r, id_col).text() == str(record_id)), None)
    if row is None:
        return None
    table.scrollToItem(table.item(row, 0))
    p.harness.settle(0.3)
    assert_foreground(dlg)
    p.harness.click_at_via_os(table.viewport(), table.visualItemRect(table.item(row, 0)).center(), wait=0.5)
    return row if table.currentRow() == row else None


def _edit_then_cancel(p, dlg, button_name, dialog_cls, title, prefill_attr, cancel_name):
    seen = {}

    def fill(edit_dlg):
        seen["prefill"] = getattr(edit_dlg, prefill_attr).text()
        os_click(p.harness, edit_dlg, cancel_name, wait=0.5)

    prearm = answer_modal_dialog(p.harness, p.app, dialog_cls, title, fill)
    os_click(p.harness, dlg, button_name, wait=0.8)
    p.harness.settle(0.5)
    return _prearm_ok(prearm), seen.get("prefill")


def _delete_with_confirm(p, dlg, button_name):
    prearm = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Delete")
    os_click(p.harness, dlg, button_name, wait=0.8)
    p.harness.settle(1.0)
    return _prearm_ok(prearm)


def _run_totp_roundtrip(p):
    settings_page = p.nav("Settings")
    p.harness.settle(0.5)

    _toggle_totp_checkbox(p, settings_page, True)
    secret = _totp_secret(p)
    if secret:
        _SECRET_PATTERNS.append(secret)
    p.checks.check("settings TOTP secret generated", bool(secret),
                   f"checkbox_checked={settings_page.totp_checkbox.isChecked()} toasts={toast_texts()}")
    if not secret:
        return
    p.checks.check("settings TOTP badge shows 2FA On", settings_page.badge_totp.text() == "2FA On",
                   settings_page.badge_totp.text())

    import pyotp
    prearm_logout = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Logout")
    os_click(p.harness, p.dashboard, "Logout", wait=0.5)
    p.harness.settle(1.0)
    p.checks.check("settings logout confirmed", _prearm_ok(prearm_logout), str(prearm_logout.info))

    wait_until(p.harness, lambda: _visible_login_screen() is not None, timeout=15)
    login_screen = _visible_login_screen()
    if login_screen is None:
        p.checks.check("settings login screen shown after logout", False)
        return
    p.checks.check("settings login screen requires OTP", login_screen.otp_input.isVisible(), "")

    p.dashboard = login_to_dashboard(p.harness, login_screen=login_screen, otp=pyotp.TOTP(secret).now())
    p.harness.settle(1.0)
    p.checks.check("settings TOTP login success", p.dashboard.isVisible(), "")

    settings_page = p.nav("Settings")
    p.harness.settle(0.5)
    checkbox = _toggle_totp_checkbox(p, settings_page, False)
    p.checks.check("settings TOTP disabled", _totp_secret(p) is None and not checkbox.isChecked(),
                   f"secret_set={bool(_totp_secret(p))} checkbox_checked={checkbox.isChecked()}")


def _run_restore(p):
    backup_path = snapshot_db("before_restore_test")
    p.observe("P3.09_S_backup_path", backup_path)

    from models.person import add_person
    add_person("RUIH_test")
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
    p.checks.check("settings restore confirmed", _prearm_ok(prearm_restore), str(prearm_restore.info))

    after_restore = p.sql("SELECT COUNT(*) FROM Person WHERE full_name='RUIH_test'")
    p.checks.check("settings full restore removed test person", bool(after_restore) and after_restore[0][0] == 0)


def _run_manage_people(p):
    from models.person import add_person
    test_person_id = add_person("RUIH_test_person")
    p.harness.settle(0.3)

    settings_page = p.nav("Settings")
    p.harness.settle(0.5)

    dlg, manage = _open_manage_data(p, settings_page, "Manage people")
    if dlg is None or manage is None:
        p.checks.check("settings Manage people dialog found", False)
        return
    table = manage.people_table

    row = _select_row_by_id(p, dlg, table, 4, test_person_id)
    p.checks.check("settings Manage people row selected", row is not None, f"person_id={test_person_id}")
    if row is None:
        dlg.reject()
        return

    opened, prefill = _edit_then_cancel(p, dlg, "Edit person", PersonDialog, "Edit Person",
                                        "nickname_input", "Cancel person dialog")
    p.checks.check("settings Edit person dialog opened", opened and prefill == "RUIH_test_person", f"prefill={prefill!r}")

    confirmed = _delete_with_confirm(p, dlg, "Delete person")
    p.checks.check("settings Delete person confirmed", confirmed)
    remaining = p.sql("SELECT COUNT(*) FROM Person WHERE person_id=?", (test_person_id,))
    p.checks.check("settings Delete person persisted", bool(remaining) and remaining[0][0] == 0)
    p.checks.check("settings Delete person removed table row",
                   all(table.item(r, 4).text() != str(test_person_id) for r in range(table.rowCount())))
    dlg.reject()
    p.harness.settle(0.3)


def _run_manage_banks(p):
    from models.bank import add_bank
    test_bank_id = add_bank("RUIH_TestBank")
    p.harness.settle(0.3)

    settings_page = p.nav("Settings")
    p.harness.settle(0.5)

    dlg, manage = _open_manage_data(p, settings_page, "Manage banks (master)")
    if dlg is None or manage is None:
        p.checks.check("settings Manage banks dialog found", False)
        return

    tab_bar = manage.tabs.tabBar()
    assert_foreground(dlg)
    p.harness.click_at_via_os(tab_bar, tab_bar.tabRect(1).center(), wait=0.5)
    p.checks.check("settings Banks tab opened", manage.tabs.currentIndex() == 1,
                   f"tab={manage.tabs.tabText(manage.tabs.currentIndex())}")
    table = manage.banks_table

    row = _select_row_by_id(p, dlg, table, 4, test_bank_id)
    p.checks.check("settings Manage banks row selected", row is not None, f"bank_id={test_bank_id}")
    if row is None:
        dlg.reject()
        return

    bank_name = p.sql("SELECT bank_name FROM Bank WHERE bank_id=?", (test_bank_id,))[0][0]
    opened, prefill = _edit_then_cancel(p, dlg, "Edit bank", BankDialog, "Edit Bank",
                                        "bank_name_input", "Cancel bank dialog")
    p.checks.check("settings Edit bank dialog opened", opened and prefill == bank_name, f"prefill={prefill!r}")

    confirmed = _delete_with_confirm(p, dlg, "Delete bank")
    p.checks.check("settings Delete bank confirmed", confirmed)
    remaining = p.sql("SELECT COUNT(*) FROM Bank WHERE bank_id=?", (test_bank_id,))
    p.checks.check("settings Delete bank persisted", bool(remaining) and remaining[0][0] == 0)
    dlg.reject()
    p.harness.settle(0.3)


def run_s(p):
    p.expected_titles.add("Select Backup File")

    steps = [
        ("settings TOTP setup", _run_totp_roundtrip),
        ("settings full restore", _run_restore),
        ("settings person edit/delete", _run_manage_people),
        ("settings bank edit/delete", _run_manage_banks),
    ]
    for name, step in steps:
        try:
            step(p)
        except Exception as e:
            p.checks.check(name, False, repr(e))

    # A leftover TOTP secret would make every later scratch login demand an OTP.
    from core.auth import is_totp_enabled, disable_totp
    if is_totp_enabled():
        disable_totp()
        p.observe("P3.09_S_cleanup", "TOTP was still enabled after the test; disabled it directly (non-UI cleanup)")


if __name__ == "__main__":
    main_wrapper("09", "Settings", run_r, run_s)
