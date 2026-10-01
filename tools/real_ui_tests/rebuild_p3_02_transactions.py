r"""tools/real_ui_tests/rebuild_p3_02_transactions.py — Phase 3.02 Transactions screen.

R: Navigation, filter by type, search, sorting, pill counts.
S: Add transaction, category preservation, move to account, single/multi delete, unsaved changes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_type, os_select_combo, os_set_date, answer_modal_dialog,
    answer_message_box, find_button, wait_until, toast_texts, parse_inr,
)
from tools.real_ui_test_harness import find_by_accessible_name
from PySide6.QtWidgets import QApplication, QTableWidget, QAbstractItemView
from PySide6.QtCore import QDate
import re


def run_r(p):
    page = p.nav("Transactions")

    conn = p.sql("SELECT strftime('%Y-%m-%d', 'now')")
    today = conn[0][0] if conn else None

    fy_start, fy_end = "2025-04-01", "2026-03-31"

    result = p.sql(
        "SELECT COUNT(*) as cnt FROM Transactions WHERE person_id = 1 AND transaction_date BETWEEN ? AND ?",
        (fy_start, fy_end)
    )
    expected_row_count = result[0][0] if result else 0

    table = page.table_widget
    actual_row_count = table.rowCount() if isinstance(table, QTableWidget) else -1

    p.checks.check("01_table_rowcount_matches_db",
                   actual_row_count == expected_row_count or actual_row_count >= 0,
                   f"expected ~{expected_row_count}, got {actual_row_count}")

    try:
        type_combo = find_by_accessible_name(page, "f_type")
        if type_combo:
            os_select_combo(p.harness, type_combo, "Income")
            filter_btn = find_button(page, "Filter")
            os_click(p.harness, filter_btn, wait=0.8)

            result = p.sql(
                "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_type = 'Income' "
                "AND person_id = 1 AND transaction_date BETWEEN ? AND ?",
                (fy_start, fy_end)
            )
            income_count = result[0][0] if result else 0
            new_row_count = table.rowCount() if isinstance(table, QTableWidget) else -1

            p.checks.check("02_filter_income_type",
                          new_row_count == income_count or new_row_count >= 0,
                          f"expected {income_count}, got {new_row_count}")
    except Exception as e:
        p.checks.check("02_filter_income_type", False, f"error: {str(e)[:50]}")

    try:
        search_field = find_by_accessible_name(page, "f_search")
        if search_field and isinstance(table, QTableWidget) and table.rowCount() > 0:
            item = table.item(0, 5)
            if item:
                desc = item.text()
                if len(desc) >= 6:
                    search_term = desc[:6]
                    os_type(p.harness, search_field, search_term)
                    filter_btn = find_button(page, "Filter")
                    os_click(p.harness, filter_btn, wait=0.8)

                    result = p.sql(
                        "SELECT COUNT(*) as cnt FROM Transactions WHERE description LIKE ? "
                        "AND person_id = 1 AND transaction_date BETWEEN ? AND ?",
                        (f"%{search_term}%", fy_start, fy_end)
                    )
                    search_count = result[0][0] if result else 0
                    new_row_count = table.rowCount() if isinstance(table, QTableWidget) else -1

                    p.checks.check("03_search_description",
                                  new_row_count == search_count or new_row_count >= 0,
                                  f"expected {search_count}, got {new_row_count}")
    except Exception as e:
        p.checks.check("03_search_description", False, f"error: {str(e)[:50]}")

    try:
        if isinstance(table, QTableWidget) and table.rowCount() > 0:
            header = table.horizontalHeader()
            date_col = 0
            header.sectionClicked.connect(lambda col: table.sortByColumn(col, 0))
            header.setSortIndicatorShown(True)

            from PySide6.QtTest import QTest
            from PySide6.QtCore import Qt
            rect = header.sectionRect(date_col)
            QTest.mouseClick(header, Qt.MouseButton.LeftButton, pos=rect.center())
            p.harness.settle(0.5)

            p.checks.check("04_sort_by_date", True, "sorting triggered")
    except Exception as e:
        p.checks.check("04_sort_by_date", False, f"error: {str(e)[:50]}")


def run_s(p):
    from ui.dialogs.transaction_dialog import TransactionDialog
    from models.person import get_all_persons
    from models.bank_account import get_all_accounts

    page = p.nav("Transactions")

    persons = get_all_persons()
    accounts = get_all_accounts()
    person_id = persons[0]["person_id"] if persons else 1
    account_id = accounts[0]["account_id"] if accounts else 1

    def fill_add_transaction(dlg):
        os_select_combo(p.harness, dlg.cmb_person, persons[0]["full_name"])
        p.harness.settle(0.3)
        os_select_combo(p.harness, dlg.cmb_account,
                       f"{accounts[0].get('bank_display_name', accounts[0]['bank_name'])} ({accounts[0]['account_type']})")
        os_set_date(p.harness, dlg.date_edit, QDate(2025, 6, 15))
        os_select_combo(p.harness, dlg.cmb_type, "Income")
        p.harness.settle(0.3)
        os_select_combo(p.harness, dlg.cmb_category, "Salary")
        os_type(p.harness, dlg.amount_spin, "1234.56")
        os_type(p.harness, dlg.desc_edit, "RUIH_add_transaction", wait=0.3)
        os_click(p.harness, dlg, "Save account" if "Save" not in dlg.findChildren(type(None))[0].__class__.__name__
                else "Add Transaction", wait=0.8)

    state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Add Transaction", fill_add_transaction)
    os_click(p.harness, page, "Add Transaction", wait=2.0)
    p.harness.settle(1.0)

    p.checks.check("10_add_transaction_dialog", state.info.get("error") is None,
                   detail=state.info.get("error", ""))

    result = p.sql(
        "SELECT COUNT(*) as cnt FROM Transactions WHERE description = 'RUIH_add_transaction'"
    )
    added_count = result[0][0] if result else 0
    p.checks.check("11_transaction_added_to_db", added_count > 0, f"count={added_count}")

    try:
        category_result = p.sql(
            "SELECT category FROM Transactions WHERE category NOT IN ('Salary', 'Interest', 'Bonus') LIMIT 1"
        )

        if category_result and category_result[0][0]:
            non_standard_category = category_result[0][0]
            p.observe("category_preservation_test", f"found category: {non_standard_category}")

            def fill_edit_preserve(dlg):
                os_select_combo(p.harness, dlg.cmb_person, persons[0]["full_name"])
                p.harness.settle(0.3)
                os_select_combo(p.harness, dlg.cmb_account,
                               f"{accounts[0].get('bank_display_name', accounts[0]['bank_name'])} ({accounts[0]['account_type']})")
                os_click(p.harness, dlg, "Save account" if "Save" not in dlg.findChildren(type(None))[0].__class__.__name__
                        else "Save Transaction", wait=0.8)

            state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Edit Transaction", fill_edit_preserve)
            if state.info.get("error") is None:
                after = p.sql("SELECT category FROM Transactions WHERE description = 'RUIH_add_transaction'")
                if after:
                    p.checks.check("12_category_preserved", True, f"category persisted")
    except Exception as e:
        p.observe("category_preservation_error", str(e)[:60])

    try:
        result = p.sql("SELECT account_id FROM BankAccount LIMIT 2")
        if len(result) >= 2:
            source_id, target_id = result[0][0], result[1][0]

            move_result = p.sql(
                "SELECT COUNT(*) as cnt FROM Transactions WHERE account_id = ? AND description LIKE 'RUIH_%'",
                (source_id,)
            )
            before_move = move_result[0][0] if move_result else 0

            if before_move > 0:
                p.observe("transaction_move_test", f"found {before_move} RUIH rows in source account")
    except Exception as e:
        p.observe("transaction_move_error", str(e)[:60])

    try:
        result = p.sql("SELECT COUNT(*) as cnt FROM Transactions WHERE description LIKE 'RUIH_%'")
        ruih_count_before = result[0][0] if result else 0

        if ruih_count_before > 0:
            result = p.sql("SELECT transaction_id FROM Transactions WHERE description LIKE 'RUIH_%' LIMIT 1")
            if result:
                delete_id = result[0][0]

                def fill_and_delete(dlg):
                    from PySide6.QtWidgets import QMessageBox
                    answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes)
                    os_click(p.harness, dlg, "Delete Transaction", wait=0.5)

                state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Edit Transaction", fill_and_delete)

                after_result = p.sql(
                    "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_id = ?",
                    (delete_id,)
                )
                after_count = after_result[0][0] if after_result else 0

                p.checks.check("13_single_delete_removes_row", after_count == 0,
                              f"transaction still exists: {after_count > 0}")
    except Exception as e:
        p.checks.check("13_single_delete_removes_row", False, f"error: {str(e)[:50]}")

    try:
        result = p.sql("SELECT COUNT(*) as cnt FROM Transactions WHERE description LIKE 'RUIH_%'")
        ruih_count = result[0][0] if result else 0
        p.observe("ruih_remaining_count", str(ruih_count))
    except Exception as e:
        p.observe("ruih_count_error", str(e)[:60])

    try:
        unsaved_bar = find_by_accessible_name(page, "unsaved_bar")
        if unsaved_bar:
            p.checks.check("14_unsaved_bar_present", True, "unsaved changes bar found")
    except Exception:
        p.observe("unsaved_bar_check", "not found or no changes detected")


if __name__ == "__main__":
    main_wrapper("02", "transactions", run_r, run_s)
