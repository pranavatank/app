"""
tools/real_ui_tests/test_add_bank_flow.py — Real, on-screen test:
Settings -> Manage Banks -> Add Bank -> Save -> verify -> cleanup.

Uses tools/real_ui_test_harness.py's primary (QTest + accessible-name lookup)
interaction path. Follows the same pattern as test_add_person_flow.py.

Self-cleans the bank record it creates so repeated runs don't pollute the real
database. If a run is interrupted before cleanup, look for a bank with nickname
starting with RUIH_ below and delete it manually.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_add_bank_flow.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

# Amounts print with the rupee sign; the Windows console defaults to cp1252 and
# raises UnicodeEncodeError on it, which would kill a passing test at the report.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QApplication

from tools.real_ui_test_harness import RealUIHarness
from ui.dashboard_screen import DashboardScreen
from ui.theme.theme_manager import ThemeManager
from ui.manage_data_screen import ManageDataScreen
from ui.dialogs.bank_dialog import BankDialog
from models.bank import get_all_banks, delete_bank

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)
TEST_BANK_NICKNAME = "RUIH_TestBank_01"
TEST_BANK_NAME = "Jana Small Finance Bank"

failures = []


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        failures.append(label)
    return condition


def dump_names(root, label=""):
    """Dump all accessible names under a widget tree for inspection."""
    from PySide6.QtWidgets import QWidget
    print(f"--- accessible names under {label or root} ---")
    for w in [root] + root.findChildren(QWidget):
        n = w.accessibleName()
        if n:
            print(f"  {n!r:55} {type(w).__name__:22} visible={w.isVisible()} enabled={w.isEnabled()}")


def main():
    before = get_all_banks()
    before_count = len(before)
    print(f"[db] banks before: count={before_count}")

    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    print(f"[dpr] {harness.dpr}")
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("00_dashboard")

    # 1. Navigate to Settings via the real sidebar button widget.
    settings_btn = dashboard._nav_buttons[8]
    harness.click(settings_btn)
    harness.settle(1.5)
    harness.shot("01_settings")
    title_lbl = getattr(dashboard, "page_title_lbl", None)
    check("Settings page title shows 'Settings'", title_lbl and title_lbl.text() == "Settings")
    check("Settings is at nav index 8", dashboard.stack.currentIndex() == 8)

    # 2. Click "Manage banks (master)" on the Settings screen, found by accessible name.
    settings_screen = dashboard.settings_page
    manage_banks_btn = harness.find(settings_screen, "Manage banks (master)")
    if not check("Found 'Manage banks (master)' button", manage_banks_btn is not None):
        harness.shot("FAIL_no_manage_banks_btn")
        return report(harness)

    harness.click(manage_banks_btn)
    harness.shot("02_manage_data_dialog")

    manage_dialog = harness.find_dialog(QDialog, "Manage Data")
    if not check("Manage Data dialog opened", manage_dialog is not None):
        harness.shot("FAIL_no_manage_dialog")
        return report(harness)

    # 3. Switch to Banks tab (index 1).
    mds = manage_dialog.findChild(ManageDataScreen)
    if mds:
        mds.tabs.setCurrentIndex(1)  # Banks
        harness.settle(1.0)
    harness.shot("02b_manage_data_banks_tab")

    # 4. Dump names to verify the controls exist.
    dump_names(manage_dialog, "ManageDataScreen-Banks")

    # 5. Click "Add bank" inside the Banks tab, found by accessible name.
    # BankDialog is opened via .exec() — a BLOCKING modal call.
    # Use the QTimer.singleShot pattern from test_add_person_flow.py.
    add_bank_btn = harness.find(manage_dialog, "Add bank")
    if not check("Found 'Add bank' button", add_bank_btn is not None):
        harness.shot("FAIL_no_add_bank_btn")
        return report(harness)

    fill_result = {}

    def _fill_and_save_bank_dialog():
        bank_dialog = harness.find_dialog(BankDialog, timeout=2.0)
        fill_result["dialog_opened"] = bank_dialog is not None
        if bank_dialog is None:
            return
        harness.shot("03_bank_dialog_open")
        harness.type_into(bank_dialog, "Bank nickname", TEST_BANK_NICKNAME)
        harness.type_into(bank_dialog, "Bank name", TEST_BANK_NAME)
        harness.shot("04_bank_fields_filled")

        # Verify fields hold the typed values
        nickname_widget = harness.find(bank_dialog, "Bank nickname")
        name_widget = harness.find(bank_dialog, "Bank name")
        if nickname_widget:
            fill_result["nickname_ok"] = nickname_widget.text() == TEST_BANK_NICKNAME
        if name_widget:
            fill_result["name_ok"] = name_widget.text() == TEST_BANK_NAME

        save_btn = harness.find(bank_dialog, "Save bank")
        fill_result["save_btn_found"] = save_btn is not None
        if save_btn is not None:
            harness.click(save_btn)
        fill_result["dialog_closed"] = not bank_dialog.isVisible()

    QTimer.singleShot(0, _fill_and_save_bank_dialog)
    harness.click(add_bank_btn, wait=1.5)
    harness.shot("05_after_bank_save")

    if not check("'Add bank' dialog opened", fill_result.get("dialog_opened", False)):
        harness.shot("FAIL_no_bank_dialog")
        return report(harness)
    check("Nickname field holds typed text", fill_result.get("nickname_ok", False))
    check("Bank name field holds typed text", fill_result.get("name_ok", False))
    if not check("Found Save button", fill_result.get("save_btn_found", False)):
        harness.shot("FAIL_no_save_btn")
        return report(harness)
    check("Add bank dialog closed after Save", fill_result.get("dialog_closed", False))

    # 6. Verify: bank appears in DB and in the visible table.
    after = get_all_banks()
    after_names = {b.get("nickname") for b in after if b.get("nickname")}
    check(f"'{TEST_BANK_NICKNAME}' present in database after save",
          TEST_BANK_NICKNAME in after_names)

    # Record the bank_id for cleanup
    bank_id_for_cleanup = None
    for b in after:
        if b.get("nickname") == TEST_BANK_NICKNAME or b.get("bank_name") == TEST_BANK_NAME:
            bank_id_for_cleanup = b["bank_id"]
            break

    # Check visible table
    table_nicknames = []
    if mds:
        for r in range(mds.banks_table.rowCount()):
            item = mds.banks_table.item(r, 0)
            if item:
                table_nicknames.append(item.text())
    check(f"'{TEST_BANK_NICKNAME}' present in visible Banks table (no manual refresh needed)",
          TEST_BANK_NICKNAME in table_nicknames)

    # 7. Test Cancel path - verify count before and after
    before_cancel_count = len(get_all_banks())
    cancel_result = {}

    def _test_cancel_bank_dialog():
        bank_dialog = harness.find_dialog(BankDialog, timeout=2.0)
        cancel_result["dialog_opened"] = bank_dialog is not None
        if bank_dialog is None:
            return
        harness.type_into(bank_dialog, "Bank nickname", "RUIH_CancelBank")
        cancel_btn = harness.find(bank_dialog, "Cancel bank dialog")
        cancel_result["cancel_btn_found"] = cancel_btn is not None
        if cancel_btn is not None:
            harness.click(cancel_btn)
        harness.settle(0.5)
        cancel_result["dialog_closed"] = not bank_dialog.isVisible()

    QTimer.singleShot(0, _test_cancel_bank_dialog)
    harness.click(add_bank_btn, wait=1.5)
    harness.shot("06_cancel_bank_flow")

    check("Cancel dialog opened", cancel_result.get("dialog_opened", False))
    check("Cancel button found", cancel_result.get("cancel_btn_found", False))
    check("Cancel dialog closed", cancel_result.get("dialog_closed", False))

    # Verify no new row was added
    after_cancel = get_all_banks()
    check("Bank count unchanged after Cancel", len(after_cancel) == before_cancel_count)

    harness.shot("07_final_state")
    manage_dialog.close()
    harness.close()
    return report(harness, after=after, bank_id=bank_id_for_cleanup)


def report(harness, after=None, bank_id=None):
    # Cleanup: delete any bank whose nickname or name starts with RUIH_
    banks = after if after is not None else get_all_banks()
    test_rows = [b for b in banks if (b.get("nickname") or "").startswith("RUIH_") or
                 (b.get("bank_name") or "").startswith("RUIH_")]

    before_cleanup_count = len(get_all_banks())
    for row in test_rows:
        delete_bank(row["bank_id"])
        print(f"[cleanup] deleted test bank_id={row['bank_id']} nickname={row.get('nickname')}")

    after_cleanup = get_all_banks()
    after_cleanup_count = len(after_cleanup)

    print("\n===== SUMMARY =====")
    print(f"Bank count: before={len([b for b in (get_all_banks() if not after else after)])}, after cleanup={after_cleanup_count}")
    if failures:
        print(f"{len(failures)} check(s) FAILED:")
        for f in failures:
            print(f"  - {f}")
    else:
        print("All checks PASSED.")
    print(f"Screenshots saved to: {harness.screenshot_dir}")

    # Always close every top-level window before exiting
    app = QApplication.instance()
    if app:
        for w in list(app.topLevelWidgets()):
            w.close()
        app.processEvents()

    return 1 if failures else 0


def _close_all_windows():
    """Close every top-level window, whatever happened. A failed assertion must
    never leave a test window (or a blocking modal) on the user's screen."""
    try:
        from PySide6.QtWidgets import QApplication, QDialog
        app = QApplication.instance()
        if not app:
            return
        for w in list(app.topLevelWidgets()):
            try:
                if isinstance(w, QDialog) and w.isVisible():
                    w.reject()
            except Exception:
                pass
        for w in list(app.topLevelWidgets()):
            try:
                w.close()
            except Exception:
                pass
        app.processEvents()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        rc = main()
    except BaseException:
        import traceback
        traceback.print_exc()
        rc = 1
    finally:
        _close_all_windows()
    sys.exit(rc)
