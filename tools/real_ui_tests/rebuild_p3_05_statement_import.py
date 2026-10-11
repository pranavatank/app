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
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type, os_type_widget, native_file_dialog,
    answer_modal_dialog, wait_until, toast_texts,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QInputDialog, QAbstractSpinBox,
)
import openpyxl


PDATA = Path(__file__).resolve().parent.parent.parent / "data" / "PersonalData" / "Pranav"
STATEMENT_DIR = PDATA / "Statement"
RUIH_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"
EXPECTATIONS_PATH = RUIH_DIR / "P0_expectations.json"

JANA_SAVINGS_LABEL = "Jana — Savings"
JANA_CURRENT_LABEL = "Jana — Current"
JANA_BANK_NAME = "Jana Small Finance Bank"

# Native QFileDialogs are answered by an external typer process; the modal
# watchdog must not reject them (rejecting a native dialog kills the process).
NATIVE_DIALOG_TITLES = {"Select File", "Export Debug Report"}


def run_r(p):
    p.checks.check("R part", True, "n/a")


def run_s(p):
    p.expected_titles.update(NATIVE_DIALOG_TITLES)
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


def _jana_expectations():
    try:
        expectations = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
        return expectations.get("statements", {}).get("Jana", {})
    except Exception:
        return {}


def _account_id(p, bank_name, account_type):
    rows = p.sql(
        "SELECT account_id FROM BankAccount WHERE bank_name=? AND account_type=? ORDER BY account_id LIMIT 1",
        (bank_name, account_type),
    )
    return rows[0][0] if rows else None


def _transaction_count(p, account_id):
    return p.sql("SELECT COUNT(*) FROM Transactions WHERE account_id=?", (account_id,))[0][0]


def _select_account(p, nav_page, account_label, file_format="PDF"):
    os_click(p.harness, nav_page, "Select person: Pranav", wait=0.8)
    os_click(p.harness, nav_page, f"Select account: {account_label}", wait=0.8)
    os_click(p.harness, nav_page, f"Select {file_format} format", wait=0.6)


def _choose_file(p, nav_page, path, check_name):
    """Pick a file through the native dialog. The path is verified first: a
    missing file leaves the native dialog open on a 'File not found' box."""
    if not path.exists():
        p.checks.check(check_name, False, f"file not found: {path}")
        return False
    native_file_dialog(
        lambda: os_click(p.harness, nav_page, "File drop zone", wait=1.0), str(path), timeout=30
    )
    ok = wait_until(
        p.harness,
        lambda: nav_page.selected_file is not None and Path(nav_page.selected_file).resolve() == path.resolve(),
        timeout=10,
    )
    p.checks.check(check_name, ok, f"selected_file={nav_page.selected_file!r}")
    return ok


def _parse_to_preview(p, nav_page, check_name):
    """The preview table keeps rows from an earlier import, so wait for the
    wizard to actually switch to the preview step, not just for rows."""
    os_click(p.harness, nav_page, "Next button", wait=2.0)
    ok = wait_until(
        p.harness,
        lambda: nav_page.stack.currentIndex() == 1 and nav_page.preview_table.rowCount() > 0,
        timeout=180,
        interval=0.5,
    )
    p.checks.check(check_name, ok, "")
    return ok


def _tick_rows(p, nav_page, rows):
    """Clear all row checkboxes, then OS-click the checkbox of each given row.
    With no table cells selected, the screen's row operations act on the
    checked rows."""
    os_click(p.harness, nav_page, "Clear transaction selection", wait=0.5)
    table = nav_page.preview_table
    for row in rows:
        table.scrollToItem(table.item(row, 1))
        p.harness.settle(0.2)
        os_click_widget(p.harness, table.cellWidget(row, 0).findChild(QCheckBox), wait=0.3)
    p.harness.settle(0.3)
    return nav_page._selected_preview_rows()


def _fill_input_dialog(p, text):
    def fill(dlg):
        spin_box = next(s for s in dlg.findChildren(QAbstractSpinBox) if s.isVisible())
        os_type_widget(p.harness, spin_box, text)
        ok_button = dlg.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        os_click_widget(p.harness, ok_button, wait=0.5)
    return fill


def _prearm_ok(prearm):
    """True if the prearmed handler ran without error; always disarms it."""
    ran = prearm.done
    prearm.done = True
    return ran and prearm.error is None and prearm.info.get("error") is None


def run_part_a(p, nav_page):
    """Idempotency: Jana—Savings existing account, verify no change."""
    p.log.log("=== PART A: Idempotency ===")

    _select_account(p, nav_page, JANA_SAVINGS_LABEL)

    pdf_path = STATEMENT_DIR / _jana_expectations().get("file", "Jana - Pranav.pdf")
    if not _choose_file(p, nav_page, pdf_path, "part_a select Jana PDF"):
        return

    if not _parse_to_preview(p, nav_page, "part_a preview loaded"):
        return

    n_preview = nav_page.preview_table.rowCount()
    all_flags_true = len(nav_page.preview_duplicate_flags) == n_preview and all(nav_page.preview_duplicate_flags)
    p.checks.check("part_a all duplicate_flags True", all_flags_true,
                   f"count={n_preview} flags={len(nav_page.preview_duplicate_flags)}")

    account_id = _account_id(p, JANA_BANK_NAME, "Savings")
    count_before = _transaction_count(p, account_id)
    p.log.log(f"Jana transaction count before: {count_before}")
    expected = _jana_expectations().get("count", 65)
    p.checks.check("part_a Jana count matches expectation", count_before == expected, f"got {count_before}, expected {expected}")

    os_click(p.harness, nav_page, "Select all new transactions", wait=1.0)
    p.checks.check("part_a no rows selected (all duplicates)", nav_page.preview_table.getCheckedRows() == [],
                   f"checked={nav_page.preview_table.getCheckedRows()}")

    os_click(p.harness, nav_page, "Next button", wait=1.5)
    toasts = toast_texts()
    p.observe("part_a import with nothing selected: toasts", " | ".join(toasts))
    refused = nav_page.stack.currentIndex() == 1
    p.checks.check("part_a import with nothing selected stays on preview", refused,
                   f"stack_index={nav_page.stack.currentIndex()}")

    os_click(p.harness, nav_page, "Back button", wait=1.0)
    p.harness.settle(1.0)
    p.checks.check("part_a back returns to selection", nav_page.stack.currentIndex() == 0, "")

    count_final = _transaction_count(p, account_id)
    p.checks.check("part_a Jana count unchanged after all operations", count_before == count_final,
                   f"before={count_before} after={count_final}")


def run_part_b(p, nav_page):
    """New account: create Jana Current, import, test row operations."""
    p.log.log("=== PART B: New Account & Row Operations ===")

    opening_balance = _jana_expectations().get("opening_balance", 0)
    p.log.log(f"Jana opening balance: {opening_balance}")

    from models.bank_account import add_account
    acc_id = _account_id(p, JANA_BANK_NAME, "Current")
    if acc_id is None:
        try:
            acc_id = add_account(
                person_id=1,
                bank_name=JANA_BANK_NAME,
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
    rows_before_import = _transaction_count(p, acc_id)

    _select_account(p, nav_page, JANA_CURRENT_LABEL)

    pdf_path = STATEMENT_DIR / _jana_expectations().get("file", "Jana - Pranav.pdf")
    if not _choose_file(p, nav_page, pdf_path, "part_b file selected"):
        return
    if not _parse_to_preview(p, nav_page, "part_b preview loaded"):
        return

    n_preview = nav_page.preview_table.rowCount()
    p.log.log(f"Preview has {n_preview} rows")
    if n_preview < 5:
        p.checks.check("part_b enough preview rows for row operations", False, f"rows={n_preview}")
        return

    _check_merge(p, nav_page)
    _check_split(p, nav_page)
    _check_shift(p, nav_page)
    _check_bulk_edit(p, nav_page)

    p.observe("part_b delete row", "not reachable: statement import preview has no delete control")

    os_click(p.harness, nav_page, "Clear transaction selection", wait=0.5)
    os_click(p.harness, nav_page, "Select all new transactions", wait=1.0)
    expected_rows = len(nav_page.preview_table.getCheckedRows())
    os_click(p.harness, nav_page, "Next button", wait=2.0)

    ok = wait_until(p.harness, lambda: nav_page.person_cards_container.isVisible(), timeout=180, interval=0.5)
    p.checks.check("part_b import complete", ok, "")

    imported = _transaction_count(p, acc_id) - rows_before_import
    p.log.log(f"Imported transaction count for new Jana Current: {imported}")
    p.checks.check("part_b imported row count equals selected rows", imported == expected_rows,
                   f"imported={imported} selected={expected_rows}")


def _check_merge(p, nav_page):
    rows = [0, 1]
    selected = _tick_rows(p, nav_page, rows)
    p.checks.check("part_b merge selection", selected == rows, f"selected={selected}")
    before = _snapshot_preview(nav_page)
    os_click(p.harness, nav_page, "Merge selected transactions", wait=1.0)
    p.harness.settle(0.5)
    after = _snapshot_preview(nav_page)
    p.checks.check("part_b merge rows", len(after) == len(before) - 1, f"before={len(before)} after={len(after)}")
    merged_amount = round(sum(float(before[r]["amount"]) for r in rows), 2)
    p.checks.check("part_b merge sums amounts", float(after[0]["amount"]) == merged_amount,
                   f"got={after[0]['amount']} expected={merged_amount}")
    p.checks.check("part_b merge keeps unselected rows",
                   _unselected_rows(after, {rows[0]}) == _unselected_rows(before, set(rows)), f"selected={rows}")
    p.checks.check("part_b merge snapshot matches table", len(after) == nav_page.preview_table.rowCount(),
                   f"rows={nav_page.preview_table.rowCount()} snapshot_len={len(after)}")


def _check_split(p, nav_page):
    transactions = nav_page.preview_transactions
    row = next((i for i in range(min(5, len(transactions))) if float(transactions[i]["amount"]) >= 1), 0)
    split_amount = round(float(transactions[row]["amount"]) / 4, 2)
    selected = _tick_rows(p, nav_page, [row])
    p.checks.check("part_b split selection", selected == [row], f"selected={selected}")
    before = _snapshot_preview(nav_page)
    prearm = answer_modal_dialog(p.harness, p.app, QInputDialog, "Split Row", _fill_input_dialog(p, f"{split_amount:.2f}"))
    os_click(p.harness, nav_page, "Split selected transaction", wait=1.0)
    p.harness.settle(0.5)
    # APP BUG if the dialog never opens: getDouble() is called with min=/max= keywords
    # (statement_import_screen_modern.py:1857), which PySide6 rejects (minValue/maxValue).
    p.checks.check("part_b split dialog handled", _prearm_ok(prearm), str(prearm.info))
    after = _snapshot_preview(nav_page)
    p.checks.check("part_b split row", len(after) == len(before) + 1, f"before={len(before)} after={len(after)}")
    p.checks.check("part_b split amounts",
                   float(after[row + 1]["amount"]) == split_amount
                   and float(after[row]["amount"]) == round(float(before[row]["amount"]) - split_amount, 2),
                   f"new={after[row + 1]['amount']} kept={after[row]['amount']} split={split_amount}")
    p.checks.check("part_b split keeps unselected rows",
                   _unselected_rows(after, {row, row + 1}) == _unselected_rows(before, {row}), f"selected={[row]}")
    p.checks.check("part_b split snapshot matches table", len(after) == nav_page.preview_table.rowCount(),
                   f"rows={nav_page.preview_table.rowCount()} snapshot_len={len(after)}")


def _check_shift(p, nav_page):
    rows = [1]
    days = 2
    selected = _tick_rows(p, nav_page, rows)
    p.checks.check("part_b shift selection", selected == rows, f"selected={selected}")
    before = _snapshot_preview(nav_page)
    prearm = answer_modal_dialog(p.harness, p.app, QInputDialog, "Shift Dates", _fill_input_dialog(p, str(days)))
    os_click(p.harness, nav_page, "Shift selected transaction dates", wait=0.8)
    p.harness.settle(1.5)
    # APP BUG if the dialog never opens: getInt() is called with min=/max= keywords
    # (statement_import_screen_modern.py:1833), which PySide6 rejects (minValue/maxValue).
    p.checks.check("part_b shift dialog handled", _prearm_ok(prearm), str(prearm.info))
    after = _snapshot_preview(nav_page)
    expected_date = (date.fromisoformat(before[rows[0]]["transaction_date"]) + timedelta(days=days)).isoformat()
    p.checks.check("part_b shift moves selected date", after[rows[0]]["transaction_date"] == expected_date,
                   f"got={after[rows[0]]['transaction_date']} expected={expected_date}")
    p.checks.check("part_b shift keeps unselected rows",
                   len(after) == len(before) and _unselected_rows(after, set(rows)) == _unselected_rows(before, set(rows)),
                   f"selected={rows}")


def _check_bulk_edit(p, nav_page):
    rows = [2, 3]
    selected = _tick_rows(p, nav_page, rows)
    p.checks.check("part_b bulk edit selection", selected == rows, f"selected={selected}")
    before = _snapshot_preview(nav_page)

    def bulk_fill(dlg):
        os_type(p.harness, dlg, "Transaction description", "RUIH_TEST", wait=0.3)
        os_click(p.harness, dlg, "Save transaction edit", wait=0.5)

    prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Bulk Edit Selected Rows", bulk_fill)
    os_click(p.harness, nav_page, "Bulk edit selected transactions", wait=0.8)
    p.harness.settle(1.5)
    p.checks.check("part_b bulk edit dialog handled", _prearm_ok(prearm), str(prearm.info))
    after = _snapshot_preview(nav_page)
    p.checks.check("part_b bulk edit sets description on selected rows",
                   all(after[r]["description"] == "RUIH_TEST" for r in rows), "")
    p.checks.check("part_b bulk edit keeps unselected rows",
                   len(after) == len(before) and _unselected_rows(after, set(rows)) == _unselected_rows(before, set(rows)),
                   f"selected={rows}")
    # APP BUG if this fails: the screen applies every dialog field (date, type,
    # amount, balance, ...) taken from the first selected row to all selected rows.
    unchanged = all(
        after[r][key] == before[r][key] for r in rows for key in ("transaction_date", "amount", "balance_after")
    )
    p.checks.check("part_b bulk edit leaves other fields of selected rows unchanged", unchanged,
                   f"before={[(before[r]['transaction_date'], before[r]['amount']) for r in rows]} "
                   f"after={[(after[r]['transaction_date'], after[r]['amount']) for r in rows]}")


def _snapshot_preview(page):
    """Copy each preview row dict; handlers mutate the dicts in place, so a list() copy is not enough."""
    return [dict(txn) for txn in page.preview_transactions]


def _unselected_rows(rows, selected_indices):
    return [txn for idx, txn in enumerate(rows) if idx not in selected_indices]


def run_part_c(p, nav_page):
    """Debug report: copy and export."""
    p.log.log("=== PART C: Debug Reports ===")

    _select_account(p, nav_page, JANA_SAVINGS_LABEL)

    pdf_path = STATEMENT_DIR / _jana_expectations().get("file", "Jana - Pranav.pdf")
    if not _choose_file(p, nav_page, pdf_path, "part_c file selected"):
        return
    if not _parse_to_preview(p, nav_page, "part_c preview loaded"):
        return

    QApplication.clipboard().clear()
    os_click(p.harness, nav_page, "Copy debug report", wait=0.8)
    clipboard_text = QApplication.clipboard().text()
    p.checks.check("part_c copy debug non-empty", len(clipboard_text) > 0, f"len={len(clipboard_text)}")

    export_path = RUIH_DIR / "test_debug_export.txt"
    if export_path.exists():
        export_path.unlink()
    native_file_dialog(
        lambda: os_click(p.harness, nav_page, "Export debug report", wait=1.0), str(export_path), timeout=30
    )
    p.harness.settle(1.0)
    file_exists = export_path.exists()
    p.checks.check("part_c export debug file exists", file_exists, "")
    if file_exists:
        p.checks.check("part_c export debug file has report text", "Parser used" in export_path.read_text(encoding="utf-8"), "")
        export_path.unlink()

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

    try:
        _select_account(p, nav_page, JANA_SAVINGS_LABEL, file_format="Excel")

        if not _choose_file(p, nav_page, xlsx_path, "part_d file selected"):
            return

        p.checks.check("part_d map columns button visible", nav_page.map_columns_btn.isVisible(), "")
        if nav_page.map_columns_btn.isVisible():
            from ui.dialogs.column_mapping_dialog import ColumnMappingDialog

            def mapping_fill_fn(dlg):
                os_click(p.harness, dlg, "Save column mapping", wait=0.5)

            mapping_prearm = answer_modal_dialog(p.harness, p.app, ColumnMappingDialog, "Map Columns", mapping_fill_fn)
            os_click(p.harness, nav_page, "Map Excel columns", wait=0.8)
            p.harness.settle(1.0)
            p.checks.check("part_d column mapping saved", _prearm_ok(mapping_prearm),
                           str(mapping_prearm.info))

        if _parse_to_preview(p, nav_page, "part_d excel preview loaded"):
            n_excel = nav_page.preview_table.rowCount()
            p.checks.check("part_d excel row count is 3", n_excel == 3, f"got {n_excel}")
            os_click(p.harness, nav_page, "Back button", wait=1.0)
    finally:
        if xlsx_path.exists():
            xlsx_path.unlink()


if __name__ == "__main__":
    main_wrapper("05", "statement_import", run_r, run_s)
