r"""tools/real_ui_tests/rebuild_p3_05_statement_import.py — Phase 3.05 Statement Import.

S ONLY (R-mode is n/a).
Tests statement import idempotency, new account creation, transaction editing,
debug report export, and Excel format parsing.

Usage: python rebuild_p3_05_statement_import.py --env S [--part a|b|c|d]

Note: test_statement_import_flow.py and test_tax_documents_flow.py are separate
run_on_scratch commands and should be run independently.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type, os_select_combo, native_file_dialog,
    answer_password_dialog, answer_modal_dialog, label_scan, parse_inr,
    read_secret, wait_until, set_fy, find_button, toast_texts,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name
from PySide6.QtWidgets import QDialog
import openpyxl


PDATA = Path(__file__).resolve().parent.parent.parent / "data" / "PersonalData" / "Pranav"
STATEMENT_DIR = PDATA / "Statement"
RUIH_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"
EXPECTATIONS_PATH = RUIH_DIR / "P0_expectations.json"


def run_r(p):
    p.checks.check("R part", True, "n/a")


def run_s(p):
    dashboard = p.dashboard
    nav_page = p.nav("Statement Import")
    p.harness.settle(2.5)

    if p.part == "a" or p.part is None:
        run_part_a(p, nav_page)

    if p.part == "b" or p.part is None:
        run_part_b(p, nav_page)

    if p.part == "c" or p.part is None:
        run_part_c(p, nav_page)

    if p.part == "d" or p.part is None:
        run_part_d(p, nav_page)


def run_part_a(p, nav_page):
    """Idempotency: Jana—Savings existing account, verify no change."""
    p.log.log("=== PART A: Idempotency ===")

    os_click(p.harness, nav_page, "Select person: Pranav", wait=0.8)

    os_click(p.harness, nav_page, "Select account: Jana — Savings", wait=0.8)

    os_click(p.harness, nav_page, "Select PDF format", wait=0.6)

    pdf_path = STATEMENT_DIR / "Jana.pdf"
    if not pdf_path.exists():
        p.log.log(f"STOP: Jana.pdf not found at {pdf_path}")
        p.checks.check("part_a select Jana PDF", False, f"file not found: {pdf_path}")
        return

    def trigger():
        os_click(p.harness, nav_page, "File drop zone", wait=1.0)

    native_file_dialog(trigger, str(pdf_path), timeout=30)
    ok = wait_until(p.harness, lambda: nav_page.selected_file is not None, timeout=10)
    p.checks.check("part_a file selected", ok, "")

    os_click(p.harness, nav_page, "Next button", wait=2.0)
    ok = wait_until(p.harness, lambda: nav_page.preview_table.rowCount() > 0, timeout=180, interval=0.5)
    p.checks.check("part_a preview loaded", ok, "")

    if not ok:
        return

    n_preview = nav_page.preview_table.rowCount()
    all_flags_true = all(
        nav_page.preview_duplicate_flags[i] for i in range(n_preview)
    ) if len(nav_page.preview_duplicate_flags) == n_preview else False
    p.checks.check("part_a all duplicate_flags True", all_flags_true,
                   f"count={n_preview} flags={len(nav_page.preview_duplicate_flags)}")

    count_before = p.sql("SELECT COUNT(*) FROM Transactions WHERE account_id=?",
                         (1,))[0][0]
    p.log.log(f"Jana transaction count before: {count_before}")
    expected = 65
    p.checks.check("part_a Jana count is 65", count_before == expected, f"got {count_before}")

    if all_flags_true:
        select_all_btn = find_button(nav_page, "Select all new transactions")
        if select_all_btn and select_all_btn.isEnabled():
            p.log.log("Idempotency: clicking 'Select all new transactions' (should be empty since all duplicates)")
            os_click(p.harness, nav_page, "Select all new transactions", wait=1.0)
            os_click(p.harness, nav_page, "Next button", wait=2.0)
            ok_import = wait_until(p.harness, lambda: nav_page.person_cards_container.isVisible(), timeout=30, interval=0.5)
            p.checks.check("part_a idempotent import completed", ok_import, "")
            count_after_import = p.sql("SELECT COUNT(*) FROM Transactions WHERE account_id=?", (1,))[0][0]
            p.checks.check("part_a idempotent import adds 0 rows", count_after_import == count_before, f"before={count_before} after={count_after_import}")
            os_click(p.harness, nav_page, "Back button", wait=1.0)
            p.harness.settle(1.0)
        else:
            p.log.log("Idempotency: 'Select all new transactions' is disabled (expected when all duplicates)")
            p.checks.check("part_a select all button disabled when all duplicates", select_all_btn is None or not select_all_btn.isEnabled(), "")
            os_click(p.harness, nav_page, "Back button", wait=1.0)
            p.harness.settle(1.0)
    else:
        os_click(p.harness, nav_page, "Back button", wait=1.0)
        p.harness.settle(1.0)

    count_final = p.sql("SELECT COUNT(*) FROM Transactions WHERE account_id=?",
                        (1,))[0][0]
    p.checks.check("part_a Jana count unchanged after all operations", count_before == count_final, "")


def run_part_b(p, nav_page):
    """New account: create Jana Current, import, test row operations."""
    p.log.log("=== PART B: New Account & Row Operations ===")

    opening_balance = 0
    if EXPECTATIONS_PATH.exists():
        try:
            expectations = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
            opening_balance = expectations.get("statements", {}).get("Jana", {}).get("opening_balance", 0)
        except Exception:
            pass
    p.log.log(f"Jana opening balance: {opening_balance}")

    from models.bank_account import add_account
    from core.session import session
    try:
        acc_id = add_account(
            person_id=1,
            bank_name="Jana Small Finance Bank",
            account_number_masked="999_TEST_CURRENT",
            account_type="Current",
            account_holder_name="Pranav Tank",
            opening_balance=opening_balance,
        )
        p.log.log(f"Created Jana Current account: {acc_id}")
        p.observe("setup", "non-UI scratch setup: created Jana Current account")
    except Exception as e:
        p.log.log(f"Failed to create account: {e}")
        p.checks.check("part_b create account", False, str(e))
        return

    os_click(p.harness, nav_page, "Select person: Pranav", wait=0.8)
    os_click(p.harness, nav_page, "Select account: Jana — Current", wait=0.8)
    os_click(p.harness, nav_page, "Select PDF format", wait=0.6)

    pdf_path = STATEMENT_DIR / "Jana.pdf"
    def trigger():
        os_click(p.harness, nav_page, "File drop zone", wait=1.0)

    native_file_dialog(trigger, str(pdf_path), timeout=30)
    wait_until(p.harness, lambda: nav_page.selected_file is not None, timeout=10)

    os_click(p.harness, nav_page, "Next button", wait=2.0)
    ok = wait_until(p.harness, lambda: nav_page.preview_table.rowCount() > 0, timeout=180, interval=0.5)
    p.checks.check("part_b preview loaded", ok, "")

    if not ok:
        return

    n_preview = nav_page.preview_table.rowCount()
    p.log.log(f"Preview has {n_preview} rows")

    snapshot_before = list(nav_page.preview_transactions)
    snapshot_before_dup_flags = list(nav_page.preview_duplicate_flags)

    if n_preview >= 2:
        os_click_widget(p.harness, nav_page.preview_table.cellWidget(0, 0), wait=0.3)
        p.harness.settle(0.3)
        os_click_widget(p.harness, nav_page.preview_table.cellWidget(1, 0), wait=0.3)

        ok = wait_until(p.harness, lambda: find_button(nav_page, "Merge selected transactions") is not None, timeout=5)
        if ok:
            snapshot_before_merge = list(nav_page.preview_transactions)
            os_click(p.harness, nav_page, "Merge selected transactions", wait=1.0)
            p.harness.settle(0.5)
            n_after_merge = nav_page.preview_table.rowCount()
            snapshot_after_merge = list(nav_page.preview_transactions)
            p.log.log(f"After merge: {n_after_merge} rows (was {n_preview})")
            p.checks.check("part_b merge rows", n_after_merge < n_preview, "")
            merged_correctly = len(snapshot_after_merge) == n_after_merge
            p.checks.check("part_b merge snapshot updated", merged_correctly, f"rows={n_after_merge} snapshot_len={len(snapshot_after_merge)}")

    if nav_page.preview_table.rowCount() >= 1:
        n_before_split = nav_page.preview_table.rowCount()
        snapshot_before_split = list(nav_page.preview_transactions)
        os_click_widget(p.harness, nav_page.preview_table.cellWidget(0, 0), wait=0.3)
        p.harness.settle(0.3)
        os_click(p.harness, nav_page, "Split selected transaction", wait=1.0)
        p.harness.settle(0.5)
        n_after_split = nav_page.preview_table.rowCount()
        snapshot_after_split = list(nav_page.preview_transactions)
        p.log.log(f"After split: {n_after_split} rows (was {n_before_split})")
        p.checks.check("part_b split row", n_after_split > n_before_split, "")
        split_correctly = len(snapshot_after_split) == n_after_split
        p.checks.check("part_b split snapshot updated", split_correctly, f"rows={n_after_split} snapshot_len={len(snapshot_after_split)}")

    if nav_page.preview_table.rowCount() >= 1:
        os_click_widget(p.harness, nav_page.preview_table.cellWidget(0, 0), wait=0.3)
        p.harness.settle(0.3)
        def shift_fill_fn(dlg):
            dlg.reject()
        shift_prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Shift Transaction Dates", shift_fill_fn)
        os_click(p.harness, nav_page, "Shift selected transaction dates", wait=0.8)
        p.harness.settle(1.5)
        p.log.log("Shift dates dialog handled")

    def bulk_fill_fn(dlg):
        os_click(p.harness, dlg, "Cancel", wait=0.5)
    bulk_prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Bulk Edit Selected Rows", bulk_fill_fn)
    os_click(p.harness, nav_page, "Bulk edit selected transactions", wait=0.8)
    p.harness.settle(1.5)
    p.log.log("Bulk Edit dialog handled")

    os_click(p.harness, nav_page, "Clear transaction selection", wait=0.5)
    os_click(p.harness, nav_page, "Select all new transactions", wait=1.0)
    os_click(p.harness, nav_page, "Next button", wait=2.0)

    ok = wait_until(p.harness, lambda: nav_page.person_cards_container.isVisible(), timeout=180, interval=0.5)
    p.checks.check("part_b import complete", ok, "")

    final_count = p.sql("SELECT COUNT(*) FROM Transactions WHERE account_id=?", (acc_id,))[0][0]
    p.log.log(f"Final transaction count for new Jana Current: {final_count}")


def run_part_c(p, nav_page):
    """Debug report: copy and export."""
    p.log.log("=== PART C: Debug Reports ===")

    os_click(p.harness, nav_page, "Select person: Pranav", wait=0.8)

    all_accounts = p.sql(
        "SELECT DISTINCT account_id FROM BankAccount WHERE person_id=1 LIMIT 1"
    )
    if not all_accounts:
        p.checks.check("part_c account found", False, "no accounts for Pranav")
        return

    acc_id = all_accounts[0][0]
    acc = p.sql("SELECT bank_name, account_type FROM BankAccount WHERE account_id=?", (acc_id,))[0]
    account_label = f"{acc[0]} — {acc[1]}"
    os_click(p.harness, nav_page, f"Select account: {account_label}", wait=0.8)
    os_click(p.harness, nav_page, "Select PDF format", wait=0.6)

    pdf_path = STATEMENT_DIR / "Jana.pdf"
    def trigger():
        os_click(p.harness, nav_page, "File drop zone", wait=1.0)

    native_file_dialog(trigger, str(pdf_path), timeout=30)
    wait_until(p.harness, lambda: nav_page.selected_file is not None, timeout=10)
    os_click(p.harness, nav_page, "Next button", wait=2.0)
    ok = wait_until(p.harness, lambda: nav_page.preview_table.rowCount() > 0, timeout=180, interval=0.5)

    if ok:
        os_click(p.harness, nav_page, "Copy debug report", wait=0.8)
        from PySide6.QtWidgets import QApplication
        clipboard_text = QApplication.clipboard().text()
        ok_copy = len(clipboard_text) > 0
        p.checks.check("part_c copy debug non-empty", ok_copy, f"len={len(clipboard_text)}")

    export_path = RUIH_DIR / "test_debug_export.txt"
    try:
        native_file_dialog(lambda: os_click(p.harness, nav_page, "Export debug report"), str(export_path), timeout=30)
        p.harness.settle(1.0)
        file_exists = export_path.exists()
        p.checks.check("part_c export debug file exists", file_exists, "")
        if file_exists:
            export_path.unlink()
    except Exception as e:
        p.log.log(f"Export debug failed: {e}")

    os_click(p.harness, nav_page, "Back button", wait=1.0)


def run_part_d(p, nav_page):
    """Excel format: create synthetic xlsx, import, verify."""
    p.log.log("=== PART D: Excel Format ===")

    xlsx_path = RUIH_DIR / "test_synthetic.xlsx"

    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Date", "Description", "Debit", "Credit", "Balance"])
        ws.append(["2025-01-15", "RUIH_PAYMENT", 5000, None, 95000])
        ws.append(["2025-01-16", "RUIH_DEPOSIT", None, 10000, 105000])
        ws.append(["2025-01-17", "RUIH_TRANSFER", 2000, None, 103000])
        wb.save(str(xlsx_path))
        p.log.log(f"Created synthetic xlsx at {xlsx_path}")
    except Exception as e:
        p.checks.check("part_d create xlsx", False, str(e))
        return

    os_click(p.harness, nav_page, "Select person: Pranav", wait=0.8)

    all_accounts = p.sql(
        "SELECT DISTINCT account_id FROM BankAccount WHERE person_id=1 LIMIT 1"
    )
    if not all_accounts:
        p.checks.check("part_d account found", False, "no accounts")
        return

    acc_id = all_accounts[0][0]
    acc = p.sql("SELECT bank_name, account_type FROM BankAccount WHERE account_id=?", (acc_id,))[0]
    account_label = f"{acc[0]} — {acc[1]}"
    os_click(p.harness, nav_page, f"Select account: {account_label}", wait=0.8)

    os_click(p.harness, nav_page, "Select Excel format", wait=0.6)

    def trigger():
        os_click(p.harness, nav_page, "File drop zone", wait=1.0)

    native_file_dialog(trigger, str(xlsx_path), timeout=30)
    wait_until(p.harness, lambda: nav_page.selected_file is not None, timeout=10)

    if hasattr(nav_page, "map_columns_btn") and nav_page.map_columns_btn.isVisible():
        os_click(p.harness, nav_page, "Map Excel columns", wait=0.8)
        p.harness.settle(1.0)
        from ui.dialogs.column_mapping_dialog import ColumnMappingDialog
        dlg = p.app.activeModalWidget() if hasattr(p, "app") else None
        if dlg and isinstance(dlg, ColumnMappingDialog):
            os_click(p.harness, dlg, "Save column mapping", wait=0.6)
            p.harness.settle(0.5)

    os_click(p.harness, nav_page, "Next button", wait=2.0)
    ok = wait_until(p.harness, lambda: nav_page.preview_table.rowCount() > 0, timeout=180, interval=0.5)
    p.checks.check("part_d excel preview loaded", ok, "")

    if ok:
        n_excel = nav_page.preview_table.rowCount()
        p.checks.check("part_d excel row count is 3", n_excel == 3, f"got {n_excel}")

    os_click(p.harness, nav_page, "Back button", wait=1.0)

    if xlsx_path.exists():
        xlsx_path.unlink()


if __name__ == "__main__":
    main_wrapper("05", "statement_import", run_r, run_s)
