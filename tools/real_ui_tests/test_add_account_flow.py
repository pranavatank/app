"""
tools/real_ui_tests/test_add_account_flow.py — Real, on-screen test:
Settings -> Manage Accounts -> Add Account -> Save -> verify -> cleanup.

Per unit 3 spec, creates person and bank programmatically first (not via UI),
then tests the Account dialog workflow end-to-end, including Statement Import
cross-check.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_add_account_flow.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QApplication

from tools.real_ui_test_harness import RealUIHarness
from ui.dashboard_screen import DashboardScreen
from ui.theme.theme_manager import ThemeManager
from ui.manage_data_screen import ManageDataScreen
from ui.dialogs.account_dialog import AccountDialog
from models.person import add_person, get_all_persons, delete_person
from models.bank import add_bank, get_all_banks, delete_bank
from models.bank_account import get_all_accounts, delete_account

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)
TEST_PERSON_NAME = "RUIH_AcctPerson_01"
TEST_BANK_NAME = "Equitas Small Finance Bank"
TEST_BANK_NICKNAME = "RUIH_AcctBank_01"
TEST_ACCOUNT_HOLDER = "RUIH_TestHolder_01"
TEST_MASKED_ACCT_NO = "XXXX1234"

failures = []
test_person_id = None
test_bank_id = None
test_account_id = None


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
    global test_person_id, test_bank_id, test_account_id

    # 1. Create person and bank programmatically for deterministic cleanup
    test_person_id = add_person(TEST_PERSON_NAME)
    print(f"[db] created test person_id={test_person_id} name={TEST_PERSON_NAME}")

    test_bank_id = add_bank(TEST_BANK_NAME, TEST_BANK_NICKNAME)
    print(f"[db] created test bank_id={test_bank_id} nickname={TEST_BANK_NICKNAME}")

    before_accounts = get_all_accounts()
    before_accounts_count = len(before_accounts)
    print(f"[db] accounts before: count={before_accounts_count}")

    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    print(f"[dpr] {harness.dpr}")
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("00_dashboard")

    # 2. Navigate to Settings via the real sidebar button widget.
    settings_btn = dashboard._nav_buttons[8]
    harness.click(settings_btn)
    harness.settle(1.5)
    harness.shot("01_settings")
    title_lbl = getattr(dashboard, "page_title_lbl", None)
    check("Settings page title shows 'Settings'", title_lbl and title_lbl.text() == "Settings")
    check("Settings is at nav index 8", dashboard.stack.currentIndex() == 8)

    # 3. Click "Manage bank accounts" on the Settings screen
    settings_screen = dashboard.settings_page
    manage_accounts_btn = harness.find(settings_screen, "Manage bank accounts")
    if not check("Found 'Manage bank accounts' button", manage_accounts_btn is not None):
        harness.shot("FAIL_no_manage_accounts_btn")
        return report(harness)

    harness.click(manage_accounts_btn)
    harness.shot("02_manage_data_dialog")

    manage_dialog = harness.find_dialog(QDialog, "Manage Data")
    if not check("Manage Data dialog opened", manage_dialog is not None):
        harness.shot("FAIL_no_manage_dialog")
        return report(harness)

    # 4. Switch to Accounts tab (index 2).
    mds = manage_dialog.findChild(ManageDataScreen)
    if mds:
        mds.tabs.setCurrentIndex(2)  # Accounts
        harness.settle(1.0)
    harness.shot("02b_manage_data_accounts_tab")

    # 5. Dump names to verify the controls exist.
    dump_names(manage_dialog, "ManageDataScreen-Accounts")

    # 6. Click "Add account" inside the Accounts tab, found by accessible name.
    # AccountDialog is opened via .exec() — a BLOCKING modal call.
    add_account_btn = harness.find(manage_dialog, "Add account")
    if not check("Found 'Add account' button", add_account_btn is not None):
        harness.shot("FAIL_no_add_account_btn")
        return report(harness)

    fill_result = {}

    def _fill_and_save_account_dialog():
        account_dialog = harness.find_dialog(AccountDialog, timeout=2.0)
        fill_result["dialog_opened"] = account_dialog is not None
        if account_dialog is None:
            return
        harness.shot("03_account_dialog_open")

        # 6a. Select person from combo
        person_combo = harness.find(account_dialog, "Person selector")
        if person_combo:
            idx = person_combo.findText(TEST_PERSON_NAME)
            fill_result["person_found"] = idx >= 0
            if idx >= 0:
                person_combo.setCurrentIndex(idx)
            else:
                print(f"[WARN] Test person '{TEST_PERSON_NAME}' not found in Person selector")
                print(f"[WARN] Available persons: {[person_combo.itemText(i) for i in range(person_combo.count())]}")

        # 6b. Select bank from combo
        # The bank combo displays as "NICKNAME (bank_name)" when both exist
        bank_combo = harness.find(account_dialog, "Bank selector")
        if bank_combo:
            # Try multiple search patterns
            search_patterns = [
                TEST_BANK_NAME,  # Just the bank name
                f"{TEST_BANK_NICKNAME} ({TEST_BANK_NAME})",  # nickname (actual)
                TEST_BANK_NICKNAME  # Just the nickname
            ]
            idx = -1
            for pattern in search_patterns:
                idx = bank_combo.findText(pattern)
                if idx >= 0:
                    break

            fill_result["bank_found"] = idx >= 0
            if idx >= 0:
                bank_combo.setCurrentIndex(idx)
            else:
                print(f"[WARN] Test bank '{TEST_BANK_NAME}' not found in Bank selector")
                print(f"[WARN] Tried patterns: {search_patterns}")
                print(f"[WARN] Available banks: {[bank_combo.itemText(i) for i in range(bank_combo.count())]}")

        # 6c. Fill account holder name
        harness.type_into(account_dialog, "Account holder name", TEST_ACCOUNT_HOLDER)

        # 6d. Fill masked account number
        harness.type_into(account_dialog, "Masked account number", TEST_MASKED_ACCT_NO)

        # 6e. Fill opening balance
        harness.type_into(account_dialog, "Opening balance", "0")

        harness.shot("04_account_fields_filled")

        # Verify fields
        acct_holder_w = harness.find(account_dialog, "Account holder name")
        masked_acct_w = harness.find(account_dialog, "Masked account number")
        if acct_holder_w:
            fill_result["holder_ok"] = acct_holder_w.text() == TEST_ACCOUNT_HOLDER
        if masked_acct_w:
            fill_result["masked_acct_ok"] = masked_acct_w.text() == TEST_MASKED_ACCT_NO

        save_btn = harness.find(account_dialog, "Save account")
        fill_result["save_btn_found"] = save_btn is not None
        if save_btn is not None:
            harness.click(save_btn)
        fill_result["dialog_closed"] = not account_dialog.isVisible()

    QTimer.singleShot(0, _fill_and_save_account_dialog)
    harness.click(add_account_btn, wait=1.5)
    harness.shot("05_after_account_save")

    if not check("'Add account' dialog opened", fill_result.get("dialog_opened", False)):
        harness.shot("FAIL_no_account_dialog")
        return report(harness)
    check("Test person found in Person selector", fill_result.get("person_found", False))
    check("Test bank found in Bank selector", fill_result.get("bank_found", False))
    check("Account holder name field holds typed text", fill_result.get("holder_ok", False))
    check("Masked account number field holds typed text", fill_result.get("masked_acct_ok", False))
    if not check("Found Save button", fill_result.get("save_btn_found", False)):
        harness.shot("FAIL_no_save_btn")
        return report(harness)
    check("Add account dialog closed after Save", fill_result.get("dialog_closed", False))

    # 7. Verify: account appears in DB and in the visible table.
    after = get_all_accounts()
    after_names = {a.get("person_name") for a in after if a.get("person_name")}
    check(f"Test person accounts present in database after save",
          TEST_PERSON_NAME in after_names)

    # Record the account_id for cleanup
    for a in after:
        if a.get("person_name") == TEST_PERSON_NAME:
            test_account_id = a["account_id"]
            break

    # Check visible table
    table_persons = []
    if mds:
        for r in range(mds.accounts_table.rowCount()):
            item = mds.accounts_table.item(r, 0)
            if item:
                table_persons.append(item.text())
    check(f"Test person accounts present in visible Accounts table (no manual refresh needed)",
          TEST_PERSON_NAME in table_persons)

    harness.shot("06_after_table_check")

    # 8. Cross-check Statement Import screen for the new account
    manage_dialog.close()
    harness.settle(1.0)

    import_btn = dashboard._nav_buttons[5]
    harness.click(import_btn)
    harness.settle(2.0)
    harness.shot("07_statement_import_screen")

    check("Statement Import is at nav index 5", dashboard.stack.currentIndex() == 5)
    import_screen = dashboard.import_page
    if import_screen:
        # Check for the person card
        person_card_name = f"Select person: {TEST_PERSON_NAME}"
        person_card = harness.find(import_screen, person_card_name)
        if check(f"Test person card found in Statement Import", person_card is not None):
            harness.click(person_card)
            harness.settle(1.0)
            harness.shot("08_person_card_selected")

            # Check if the account card exists
            if test_account_id and test_account_id in import_screen._account_cards:
                account_card = import_screen._account_cards[test_account_id]
                check(f"Test account card found for test person in Statement Import", True)
                harness.shot("09_account_card_visible")
            else:
                check(f"Test account card found for test person in Statement Import", False)

    harness.close()
    return report(harness, after=after)


def report(harness, after=None):
    # Cleanup: delete in FK order (account first, then bank, then person)
    # We created these, so we know their IDs
    global test_account_id, test_bank_id, test_person_id

    try:
        if test_account_id:
            delete_account(test_account_id)
            print(f"[cleanup] deleted test account_id={test_account_id}")
    except Exception as e:
        print(f"[cleanup] failed to delete account: {e}")

    try:
        if test_bank_id:
            delete_bank(test_bank_id)
            print(f"[cleanup] deleted test bank_id={test_bank_id}")
    except Exception as e:
        print(f"[cleanup] failed to delete bank: {e}")

    try:
        if test_person_id:
            delete_person(test_person_id)
            print(f"[cleanup] deleted test person_id={test_person_id}")
    except Exception as e:
        print(f"[cleanup] failed to delete person: {e}")

    after_cleanup = get_all_accounts()
    after_cleanup_count = len(after_cleanup)
    before_count = len(after) if after else len(get_all_accounts())

    print("\n===== SUMMARY =====")
    print(f"Account count: after cleanup={after_cleanup_count}")
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


if __name__ == "__main__":
    sys.exit(main())
