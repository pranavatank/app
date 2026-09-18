"""
tools/real_ui_tests/test_statement_import_flow.py — Real, on-screen test:
Statement Import end-to-end with real PDF → Parse → Preview → Import → verify.

Per unit 4 spec, creates person, bank, and account programmatically first
(not via UI) to ensure clean ownership and deterministic cleanup. Then tests
the full Statement Import flow with a real PDF file, confirming transactions
land in the database.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_statement_import_flow.py
"""
import os
import sys
import time

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

from models.person import add_person, get_all_persons, delete_person
from models.bank import add_bank, get_all_banks, delete_bank
from models.bank_account import get_all_accounts, delete_account, get_accounts_for_person
from models.transaction import get_transactions, delete_transactions_by_ids
from models.fixed_deposit import get_all_fds, delete_fd

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

TEST_PERSON_NAME = "RUIH_ImportPerson_01"
TEST_BANK_NAME = "Jana Small Finance Bank"
TEST_BANK_NICKNAME = "RUIH_ImportBank_01"
TEST_PDF = r"D:\Pranav\app\data\PersonalData\Pranav\Statement\Jana - Pranav.pdf"

failures = []
test_person_id = None
test_bank_id = None
test_account_id = None
test_transactions = []
test_fds = []


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
    global test_person_id, test_bank_id, test_account_id, test_transactions, test_fds

    # 1. Snapshot baseline counts and create test person, bank, account programmatically
    before_persons = len(get_all_persons())
    before_banks = len(get_all_banks())
    before_accounts = len(get_all_accounts())
    print(f"[db] baseline — persons={before_persons}, banks={before_banks}, accounts={before_accounts}")

    test_person_id = add_person(TEST_PERSON_NAME)
    print(f"[db] created test person_id={test_person_id} name={TEST_PERSON_NAME}")

    test_bank_id = add_bank(TEST_BANK_NAME, TEST_BANK_NICKNAME)
    print(f"[db] created test bank_id={test_bank_id} nickname={TEST_BANK_NICKNAME}")

    # Create account linking person and bank
    from models.bank_account import add_account
    test_account_id = add_account(
        person_id=test_person_id,
        bank_name=TEST_BANK_NAME,
        account_type="Current",
        account_holder_name="RUIH_ImportTest",
        account_number_masked="XXXX5678",
        opening_balance=0.0
    )
    print(f"[db] created test account_id={test_account_id}")

    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    print(f"[dpr] {harness.dpr}")
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("00_dashboard")

    # 2. Navigate to Statement Import
    import_btn = dashboard._nav_buttons[5]
    harness.click(import_btn)
    harness.settle(2.0)
    harness.shot("01_statement_import_screen")

    check("Statement Import is at nav index 5", dashboard.stack.currentIndex() == 5)
    check("Statement Import page title correct",
          dashboard.page_title_lbl.text() == "Statement Import")
    check("Statement Import screen did not error during construction",
          dashboard._screen_errors.get(5) is None)

    import_screen = dashboard.import_page
    if not import_screen:
        print("[FAIL] Could not access import_page from dashboard")
        return report(harness)

    # 3. Dump accessible names on the Statement Import screen
    print("\n--- Full accessible name dump for Statement Import screen ---")
    dump_names(import_screen, "StatementImportScreen")
    print()

    # 4. Select the person card by directly clicking from _person_cards[test_person_id]
    # (Using find by accessible name is risky if multiple people have the same name; use direct widget access)
    if test_person_id not in import_screen._person_cards:
        check(f"Test person card exists in _person_cards", False)
        print(f"[debug] Available person IDs: {list(import_screen._person_cards.keys())}")
        harness.shot("FAIL_no_person_card")
        return report(harness)

    person_card = import_screen._person_cards[test_person_id]
    check(f"Test person card exists in _person_cards", True)

    harness.click(person_card)
    harness.settle(1.5)
    harness.shot("02_person_card_selected")

    # Verify person card is checked
    check("Test person card is checked after click", person_card.isChecked())

    # 5. Select the account card
    if test_account_id not in import_screen._account_cards:
        print(f"[FAIL] Test account_id {test_account_id} NOT in _account_cards")
        print(f"[FAIL] Available account IDs: {list(import_screen._account_cards.keys())}")
        check("Test account exists in _account_cards", False)
        return report(harness)

    account_card = import_screen._account_cards[test_account_id]
    check("Test account exists in _account_cards", True)

    harness.click(account_card)
    harness.settle(1.5)
    harness.shot("03_account_card_selected")

    check("Account card is checked after click", account_card.isChecked())

    # 6. Select PDF format
    harness.click(import_screen, "Select PDF format")
    harness.settle(1.0)
    harness.shot("04_pdf_format_selected")

    check("PDF format button is checked", import_screen.btn_format_pdf.isChecked())

    # 7. Set file via drop zone signal (do NOT click browse — native modal)
    if hasattr(import_screen, '_drop_zone'):
        import_screen._drop_zone.fileSelected.emit(TEST_PDF)
        harness.settle(1.5)
        harness.shot("05_file_selected")
        check("File selected (drop zone signal emitted)", True)
    else:
        check("File selected (drop zone signal emitted)", False)
        return report(harness)

    # 8. Parse — click "Next button" to trigger parsing on background thread
    next_btn = harness.find(import_screen, "Next button")
    if not check("Found Next button for parsing", next_btn is not None):
        harness.shot("FAIL_no_next_btn")
        return report(harness)

    harness.click(next_btn)
    harness.settle(2.0)

    # 9. Poll for preview table to populate (parsing is threaded)
    print("[parse] Waiting for preview table to populate (polling for up to 60s)...")
    harness.shot("06_parse_started")

    deadline = time.time() + 60
    preview_table = import_screen.preview_table if hasattr(import_screen, 'preview_table') else None
    if not preview_table:
        preview_table = harness.find(import_screen, "Transaction preview table")

    poll_count = 0
    while time.time() < deadline and (not preview_table or preview_table.rowCount() == 0):
        harness.settle(0.5)
        if preview_table:
            poll_count += 1
            if poll_count % 10 == 0:  # Print every 5 seconds
                elapsed = time.time() - (deadline - 60)
                print(f"  [poll at {elapsed:.0f}s] rowCount={preview_table.rowCount()}")
                # Check if there's any error message visible
                debug_output = import_screen.debug_output if hasattr(import_screen, 'debug_output') else None
                if debug_output and hasattr(debug_output, 'toPlainText'):
                    debug_text = debug_output.toPlainText()
                    if debug_text and len(debug_text) > 100:
                        print(f"  [debug] {debug_text[:200]}")

    elapsed_total = time.time() - (deadline - 120)
    if preview_table and preview_table.rowCount() > 0:
        check("Parse succeeded: preview table populated", True)
        print(f"[parse] Preview table has {preview_table.rowCount()} rows (after {elapsed_total:.1f}s)")

        # Print first 3 rows
        for r in range(min(3, preview_table.rowCount())):
            row_data = []
            for c in range(preview_table.columnCount()):
                item = preview_table.item(r, c)
                row_data.append(item.text() if item else "")
            print(f"  [row {r}] {row_data}")
    else:
        check("Parse succeeded: preview table populated", False)
        print(f"[parse] Timeout after {elapsed_total:.1f}s — preview_table rowCount={preview_table.rowCount() if preview_table else 'N/A'}")
        # Check debug output for error
        debug_output = import_screen.debug_output if hasattr(import_screen, 'debug_output') else None
        if not debug_output:
            debug_output = harness.find(import_screen, "Import debug output")
        if debug_output:
            debug_text = debug_output.toPlainText() if hasattr(debug_output, 'toPlainText') else str(debug_output)
            print(f"[DEBUG]\n{debug_text}")
        return report(harness)

    # 10. Import: click "Select all new transactions" then find Import button
    harness.click(import_screen, "Select all new transactions")
    harness.settle(1.0)

    # Re-dump names after reaching preview screen (button labels may have changed)
    print("\n--- Accessible names on preview screen (for Import button) ---")
    dump_names(import_screen, "StatementImport-PreviewScreen")
    print()

    # Find Import button — it may be labeled differently; look for it by trying common names
    import_btn = harness.find(import_screen, "Next button")  # Same button, relabeled for Import
    if not check("Found Import button", import_btn is not None):
        harness.shot("FAIL_no_import_btn")
        return report(harness)

    harness.click(import_btn)
    harness.settle(2.0)

    # 11. Poll for import to complete (also threaded)
    print("[import] Waiting for import to complete (polling for up to 60s)...")
    harness.shot("07_import_started")

    deadline_import = time.time() + 60
    # After import, check if screen has returned to screen 1 (person/account selection)
    # Or check if a success message appears
    while time.time() < deadline_import:
        harness.settle(1.0)
        # Simple heuristic: if person_cards are visible again, we've returned to screen 1
        if import_screen.person_cards_container.isVisible():
            print("[import] Screen returned to person selection (import complete)")
            break

    harness.shot("08_after_import")

    # 12. Cross-check database: confirm transactions exist for account_id
    print("[db] Querying transactions for account_id...")
    transactions = get_transactions(account_id=test_account_id)
    if transactions:
        check(f"Transactions imported: count={len(transactions)}", True)
        print(f"[db] Imported {len(transactions)} transactions")
        test_transactions = [t.get("transaction_id") for t in transactions if t.get("transaction_id")]
        print(f"[db] Transaction IDs: {test_transactions[:5]}...")  # Print first 5

        # Print first row details
        if transactions:
            first = transactions[0]
            print(f"[db] First row: {first}")
    else:
        check(f"Transactions imported: count={len(transactions)}", False)
        print("[db] WARNING: No transactions found for test account after import")

    # 13. Check for auto-created FDs (statement import can create them)
    print("[db] Checking for auto-created FDs...")
    fds = get_all_fds(person_id=test_person_id)
    if fds:
        print(f"[db] Found {len(fds)} FDs for test person")
        test_fds = [fd.get("fd_id") for fd in fds if fd.get("fd_id")]
    else:
        print("[db] No FDs auto-created for test person")

    harness.close()
    return report(harness)


def report(harness):
    global test_person_id, test_bank_id, test_account_id, test_transactions, test_fds

    print("\n===== CLEANUP =====")

    # Delete transactions first (FK constraint)
    try:
        if test_transactions:
            delete_transactions_by_ids(test_transactions)
            print(f"[cleanup] deleted {len(test_transactions)} test transactions")
    except Exception as e:
        print(f"[cleanup] failed to delete transactions: {e}")

    # Delete FDs if any were auto-created
    try:
        for fd_id in test_fds:
            delete_fd(fd_id)
            print(f"[cleanup] deleted auto-created fd_id={fd_id}")
    except Exception as e:
        print(f"[cleanup] failed to delete FDs: {e}")

    # Delete account
    try:
        if test_account_id:
            delete_account(test_account_id)
            print(f"[cleanup] deleted test account_id={test_account_id}")
    except Exception as e:
        print(f"[cleanup] failed to delete account: {e}")

    # Delete bank
    try:
        if test_bank_id:
            delete_bank(test_bank_id)
            print(f"[cleanup] deleted test bank_id={test_bank_id}")
    except Exception as e:
        print(f"[cleanup] failed to delete bank: {e}")

    # Delete person
    try:
        if test_person_id:
            delete_person(test_person_id)
            print(f"[cleanup] deleted test person_id={test_person_id}")
    except Exception as e:
        print(f"[cleanup] failed to delete person: {e}")

    # Verify cleanup
    after_persons = len(get_all_persons())
    after_banks = len(get_all_banks())
    after_accounts = len(get_all_accounts())
    after_transactions = get_transactions(account_id=test_account_id) if test_account_id else []
    after_fds = get_all_fds(person_id=test_person_id) if test_person_id else []

    print(f"\n===== CLEANUP VERIFICATION =====")
    print(f"Persons: before cleanup should match current (baseline + 1 removed)")
    print(f"Banks: before cleanup should match current (baseline + 1 removed)")
    print(f"Accounts: before cleanup should match current (baseline + 1 removed)")
    print(f"Transactions for test account: {len(after_transactions)} (should be 0)")
    print(f"FDs for test person: {len(after_fds)} (should be 0)")

    # Additional verification: count test-prefixed rows to ensure no orphans
    all_persons = get_all_persons()
    orphan_persons = [p for p in all_persons if (p.get("name") or "").startswith("RUIH_")]
    orphan_banks = [b for b in get_all_banks() if (b.get("nickname") or "").startswith("RUIH_") or (b.get("bank_name") or "").startswith("RUIH_")]
    orphan_accounts = [a for a in get_all_accounts() if (a.get("account_holder_name") or "").startswith("RUIH_")]

    print(f"Orphan RUIH_ rows (should be empty):")
    print(f"  Persons: {len(orphan_persons)}")
    print(f"  Banks: {len(orphan_banks)}")
    print(f"  Accounts: {len(orphan_accounts)}")

    print("\n===== SUMMARY =====")
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
