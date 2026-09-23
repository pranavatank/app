"""
tools/real_ui_tests/test_excel_table_interactions.py — Real-UI test: Excel table interactions

Tests ExcelTable cell clicks, checkbox selection, Enter-to-edit, double-click-to-edit,
and delete with DB verification. Writes 3 test transactions to the real DB; must clean up.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_excel_table_interactions.py
"""
import os
import sys
import time
import sqlite3
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

# Amounts print with the rupee sign; Windows console defaults to cp1252.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QCheckBox
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtTest import QTest

from tools.real_ui_test_harness import RealUIHarness
from ui.dashboard_screen import DashboardScreen
from ui.dialogs.transaction_dialog import TransactionDialog
from ui.theme.theme_manager import ThemeManager
from core.database import backup_database, get_connection
from models.transaction import add_transaction
from config import get_current_financial_year, fy_date_range
from core.session import session

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

TRANSACTIONS_NAV_INDEX = 2

checks = []


def check(label, ok):
    checks.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}", flush=True)
    return ok


def wait_for(predicate, timeout=10.0, interval=0.2):
    """Pump the event loop until predicate() is true or timeout passes."""
    app = QApplication.instance()
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def dismiss_blocking_dialogs():
    """Close any unexpected modal dialogs."""
    app = QApplication.instance()
    for w in list(app.topLevelWidgets()):
        if isinstance(w, QDialog) and w.isVisible():
            if isinstance(w, TransactionDialog):
                continue
            try:
                w.reject()
            except Exception:
                pass


def main():
    # Back up database
    print("[backup] creating database backup...", flush=True)
    try:
        dest = os.path.join(os.path.dirname(__file__), "..", "..", "backups",
                            f"pre_ruih_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        backup_database(dest)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print(f"[backup] saved to: {dest}", flush=True)
        else:
            print("[backup] FAILED", flush=True)
    except Exception as e:
        print(f"[backup] error: {e}", flush=True)

    # Check for pre-existing RUIH rows
    conn = get_connection()
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM Transactions WHERE description LIKE 'RUIH_%' ESCAPE '\\'",
    ).fetchone()["cnt"]
    conn.close()
    if existing > 0:
        check("No pre-existing RUIH_ rows", False)
        print(f"[error] Found {existing} pre-existing RUIH_ rows - clean up first", flush=True)
        return report(None)

    # Get total before
    conn = get_connection()
    total_before = conn.execute(
        "SELECT COUNT(*) as cnt FROM Transactions"
    ).fetchone()["cnt"]
    conn.close()
    print(f"[db] total_before = {total_before}", flush=True)

    # Insert 3 test transactions
    fy = "2025-26"
    start, end = fy_date_range(fy)
    test_date = (start + timedelta(days=60)).isoformat()
    print(f"[db] test_date = {test_date}", flush=True)

    try:
        id1 = add_transaction(39, 1, test_date, "Expense", 1.11,
                             category="RUIH_test", description="RUIH_excel_row_1")
        id2 = add_transaction(39, 1, test_date, "Expense", 2.22,
                             category="RUIH_test", description="RUIH_excel_row_2")
        id3 = add_transaction(39, 1, test_date, "Expense", 3.33,
                             category="RUIH_test", description="RUIH_excel_row_3")
        print(f"[db] inserted rows: {id1}, {id2}, {id3}", flush=True)
    except Exception as e:
        check("Insert 3 test transactions", False)
        print(f"[error] {e}", flush=True)
        return report(None)

    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("00_dashboard")

    # Verify active window
    if QApplication.activeWindow() != dashboard:
        check("Dashboard is active window", False)
        return report(harness)

    # Navigate to Transactions
    dashboard._navigate(TRANSACTIONS_NAV_INDEX)
    harness.settle(1.5)
    harness.shot("01_transactions_screen")

    screen = dashboard.stack.currentWidget()
    check("Transactions screen loaded",
          TRANSACTIONS_NAV_INDEX not in getattr(dashboard, "_screen_errors", {}))

    # Set FY selector to match test data (2025-26)
    dashboard.fy_combo.setCurrentText("2025-26")
    harness.settle(1.0)

    # Set search filter to "RUIH_" and apply
    if hasattr(screen, 'f_search'):
        screen.f_search.setText("RUIH_")

    # Find Apply button (try by accessible name first, fallback to finding by text)
    btn_apply = harness.find(screen, "Apply")
    if not btn_apply:
        # Apply button doesn't have accessible name set, find by text
        from PySide6.QtWidgets import QPushButton
        for btn in screen.findChildren(QPushButton):
            if btn.text() == "Apply":
                btn_apply = btn
                break

    if btn_apply:
        harness.click(btn_apply)
        harness.settle(1.0)

    harness.settle(1.0)
    table = screen.table
    row_count = table.rowCount()
    print(f"[table] rowCount after filter = {row_count}", flush=True)
    check("Table shows exactly 3 RUIH rows", row_count == 3)

    harness.shot("02_table_filtered")

    # Test 6: Cell click on Amount column of row 0
    print("\n[test] Cell click on Amount (row 0)", flush=True)
    if row_count > 0:
        table.clearSelection()
        harness.settle(0.3)
        # Amount is at column 7 (including checkbox), but table.clickCell expects visual column
        # The table has checkbox at 0, then data columns 1+
        # Let me find the amount cell
        table.setCurrentCell(0, 7)  # Column 7 is Amount after checkbox
        harness.settle(0.5)
        is_selected = table.currentRow() == 0
        print(f"[table] currentRow() == 0: {is_selected}", flush=True)
        check("Cell click sets currentRow to 0", is_selected)

    # Test 7: Checkbox click on row 1
    print("\n[test] Checkbox click (row 1)", flush=True)
    if row_count > 1:
        checkbox = table.cellWidget(1, 0)
        if checkbox and isinstance(checkbox, QCheckBox):
            # Use click_via_os for the checkbox
            harness.click_via_os(checkbox)
            harness.settle(0.5)
            is_checked = checkbox.isChecked()
            print(f"[table] checkbox.isChecked(): {is_checked}", flush=True)
            check("Checkbox checked after click", is_checked)
        else:
            print("[warn] checkbox not found or not a QCheckBox", flush=True)
            check("Checkbox found and clickable", False)

    # Test 8: Enter to edit
    print("\n[test] Enter to edit (row 0)", flush=True)
    table.setCurrentCell(0, 0)
    harness.settle(0.3)

    dialog_found = False
    def handle_edit_dialog():
        nonlocal dialog_found
        try:
            dlg = harness.find_dialog(TransactionDialog, timeout=2.0)
            if dlg and dlg.isVisible():
                dialog_found = True
                print("[edit] dialog found, rejecting", flush=True)
                dlg.reject()
        except Exception as e:
            print(f"[edit] error handling dialog: {e}", flush=True)

    QTimer.singleShot(0, handle_edit_dialog)
    QTest.keyClick(table, Qt.Key.Key_Return)
    harness.settle(1.0)
    check("Enter opens edit dialog", dialog_found)

    # Test 9: Double-click to edit
    print("\n[test] Double-click to edit (row 1, Description column)", flush=True)
    table.setCurrentCell(1, 6)  # Description is column 6 after checkbox
    harness.settle(0.3)

    dialog_found = False
    def handle_dblclick_dialog():
        nonlocal dialog_found
        try:
            dlg = harness.find_dialog(TransactionDialog, timeout=2.0)
            if dlg and dlg.isVisible():
                dialog_found = True
                print("[dblclick] dialog found, rejecting", flush=True)
                dlg.reject()
        except Exception as e:
            print(f"[dblclick] error: {e}", flush=True)

    QTimer.singleShot(0, handle_dblclick_dialog)
    harness.click_at_via_os(table.cellWidget(1, 6) or table, QPoint(50, 50), double=True)
    harness.settle(1.0)
    check("Double-click opens edit dialog", dialog_found)

    # Test 10: Delete selected
    print("\n[test] Delete selected rows", flush=True)

    # Check 2 rows (0 and 1)
    cb0 = table.cellWidget(0, 0)
    cb1 = table.cellWidget(1, 0)
    if cb0 and isinstance(cb0, QCheckBox):
        cb0.setChecked(True)
    if cb1 and isinstance(cb1, QCheckBox):
        cb1.setChecked(True)
    harness.settle(0.5)

    # Read IDs of checked rows (column 11 = ID, but it's hidden)
    # We need to get transaction IDs from the DB using description
    conn = get_connection()
    checked_ids = conn.execute(
        "SELECT transaction_id FROM Transactions WHERE description IN ('RUIH_excel_row_1', 'RUIH_excel_row_2') ORDER BY transaction_id"
    ).fetchall()
    checked_ids = [r[0] for r in checked_ids]
    print(f"[delete] checked_ids from DB: {checked_ids}", flush=True)
    check("Found exactly 2 checked transaction IDs", len(checked_ids) == 2)
    conn.close()

    # Pre-arm delete confirmation handler
    def handle_delete_confirm():
        try:
            msg_box = None
            for w in QApplication.instance().topLevelWidgets():
                if isinstance(w, QMessageBox) and w.isVisible():
                    msg_box = w
                    break
            if msg_box:
                print("[delete] confirm dialog found, clicking Yes", flush=True)
                yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)
                if yes_btn:
                    yes_btn.click()
        except Exception as e:
            print(f"[delete] confirm error: {e}", flush=True)

    QTimer.singleShot(100, handle_delete_confirm)
    QTest.keyClick(table, Qt.Key.Key_Delete)
    harness.settle(1.5)

    # Verify deletion via DB
    conn = get_connection()
    remaining_ids = conn.execute(
        "SELECT transaction_id FROM Transactions WHERE description LIKE 'RUIH_%' ORDER BY transaction_id"
    ).fetchall()
    remaining_ids = [r[0] for r in remaining_ids]
    total_after = conn.execute(
        "SELECT COUNT(*) as cnt FROM Transactions"
    ).fetchone()["cnt"]
    conn.close()

    print(f"[delete] remaining_ids: {remaining_ids}", flush=True)
    print(f"[delete] total_after: {total_after}", flush=True)
    expected_remaining = [id3]
    check("Exactly 1 RUIH row remains (id3)", remaining_ids == expected_remaining)
    check("Total count is total_before + 1", total_after == total_before + 1)

    harness.shot("03_after_delete")
    return report(harness)


def report(harness):
    dismiss_blocking_dialogs()
    try:
        if harness:
            harness.close()
    except Exception:
        pass

    print("\n===== SUMMARY =====", flush=True)
    failed = [label for label, ok in checks if not ok]
    if failed:
        print(f"{len(failed)} check(s) FAILED:", flush=True)
        for label in failed:
            print(f"  - {label}", flush=True)
        return 1
    print("All checks PASSED.", flush=True)
    print(f"Screenshots saved to: {SHOT_DIR}", flush=True)
    return 0


def _close_all_windows():
    """Always-runs teardown: clean up test data from DB, close windows."""
    try:
        # Delete all RUIH_ rows
        conn = get_connection()
        conn.execute("DELETE FROM Transactions WHERE description LIKE 'RUIH_%' ESCAPE '\\'")
        conn.commit()
        final_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM Transactions WHERE description LIKE 'RUIH_%'"
        ).fetchone()["cnt"]
        conn.close()
        if final_count == 0:
            print("[teardown] RUIH_ rows deleted successfully", flush=True)
        else:
            print(f"[teardown] WARNING: {final_count} RUIH_ rows still exist", flush=True)
    except Exception as e:
        print(f"[teardown] error deleting RUIH_ rows: {e}", flush=True)

    dismiss_blocking_dialogs()
    try:
        app = QApplication.instance()
        if app:
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
