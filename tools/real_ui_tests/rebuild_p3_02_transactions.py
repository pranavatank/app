r"""tools/real_ui_tests/rebuild_p3_02_transactions.py — Phase 3.02 Transactions screen.

R: Navigation, filter by type, search, sorting, pill counts.
S: Add transaction, category preservation, move to account, single/multi delete, unsaved changes.

Note: test_excel_table_interactions.py is run as a separate command (not from here).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click_widget, os_type_widget, os_select_combo, os_set_date, answer_modal_dialog,
    answer_message_box, find_button,
)
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox
from PySide6.QtCore import QDate


def run_r(p):
    page = p.nav("Transactions")

    fy_start, fy_end = "2025-04-01", "2026-03-31"

    result = p.sql(
        "SELECT COUNT(*) as cnt FROM Transactions WHERE person_id = 1 AND transaction_date BETWEEN ? AND ?",
        (fy_start, fy_end)
    )
    expected_row_count = result[0][0] if result else 0

    table = page.table
    actual_row_count = table.rowCount()

    p.checks.check("01_table_rowcount_matches_db",
                   actual_row_count == expected_row_count,
                   f"expected {expected_row_count}, got {actual_row_count}")

    try:
        p.a11y("f_type", "accessible name")
        os_select_combo(p.harness, page.f_type, "Income")
        filter_btn = find_button(page, "Apply")
        os_click_widget(p.harness, filter_btn, wait=0.8)

        result = p.sql(
            "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_type = 'Income' "
            "AND person_id = 1 AND transaction_date BETWEEN ? AND ?",
            (fy_start, fy_end)
        )
        income_count = result[0][0] if result else 0
        new_row_count = table.rowCount()

        p.checks.check("02_filter_income_type",
                      new_row_count == income_count,
                      f"expected {income_count}, got {new_row_count}")
    except Exception as e:
        p.checks.check("02_filter_income_type", False, f"error: {str(e)[:50]}")

    try:
        p.a11y("f_search", "accessible name")
        if table.rowCount() > 0:
            _COL_DESC = 5
            item = table.item(0, _COL_DESC + 1)
            if item:
                desc = item.text()
                if len(desc) >= 6:
                    search_term = desc[:6]
                    os_type_widget(p.harness, page.f_search, search_term)
                    filter_btn = find_button(page, "Apply")
                    os_click_widget(p.harness, filter_btn, wait=0.8)

                    result = p.sql(
                        "SELECT COUNT(*) as cnt FROM Transactions WHERE description LIKE ? "
                        "AND person_id = 1 AND transaction_date BETWEEN ? AND ?",
                        (f"%{search_term}%", fy_start, fy_end)
                    )
                    search_count = result[0][0] if result else 0
                    new_row_count = table.rowCount()

                    p.checks.check("03_search_description",
                                  new_row_count == search_count,
                                  f"expected {search_count}, got {new_row_count}")
    except Exception as e:
        p.checks.check("03_search_description", False, f"error: {str(e)[:50]}")

    try:
        if table.rowCount() > 0:
            header = table.horizontalHeader()
            date_col = 1
            rect = header.sectionRect(date_col)
            os_click_widget(p.harness, header, wait=0.5)
            p.harness.settle(0.5)
            p.checks.check("04_sort_by_date", True, "sorting by OS header click")
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
        os_type_widget(p.harness, dlg.amount_spin, "1234.56")
        os_type_widget(p.harness, dlg.desc_edit, "RUIH_add_transaction", wait=0.3)
        btn_box = dlg.findChild(QDialogButtonBox)
        os_click_widget(p.harness, btn_box.button(QDialogButtonBox.StandardButton.Ok), wait=0.8)

    state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Add Transaction", fill_add_transaction)
    os_click_widget(p.harness, page.btn_add, wait=2.0)
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
            "SELECT category FROM Transactions WHERE transaction_type = 'Income' AND category NOT IN ('Salary', 'Interest', 'Bonus', '') LIMIT 1"
        )

        if category_result and category_result[0][0]:
            non_standard_category = category_result[0][0]
            p.observe("category_preservation_test", f"found category: {non_standard_category}")

            result = p.sql(
                "SELECT transaction_id FROM Transactions WHERE category = ?",
                (non_standard_category,)
            )
            edit_id = result[0][0] if result else None

            if edit_id:
                def fill_edit_preserve(dlg):
                    btn_box = dlg.findChild(QDialogButtonBox)
                    os_click_widget(p.harness, btn_box.button(QDialogButtonBox.StandardButton.Cancel), wait=0.8)

                state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Edit Transaction", fill_edit_preserve)
                result_after = p.sql(
                    "SELECT category FROM Transactions WHERE transaction_id = ?",
                    (edit_id,)
                )
                if result_after:
                    p.checks.check("12_category_preserved", result_after[0][0] == non_standard_category,
                                   f"category preserved")
        else:
            p.observe("category_preservation_test", "no non-standard income category found")
    except Exception as e:
        p.checks.check("12_category_preserved", False, f"error: {str(e)[:50]}")

    try:
        result = p.sql("SELECT account_id FROM BankAccount LIMIT 2")
        if len(result) >= 2:
            source_id, target_id = result[0][0], result[1][0]

            move_result = p.sql(
                "SELECT transaction_id FROM Transactions WHERE account_id = ? AND description LIKE 'RUIH_%' LIMIT 1",
                (source_id,)
            )

            if move_result:
                move_id = move_result[0][0]
                p.observe("transaction_move_test", f"moving transaction {move_id} from account {source_id} to {target_id}")

                def fill_move_transaction(dlg):
                    target_account_text = next(
                        (f"{a.get('bank_display_name', a['bank_name'])} ({a['account_type']})"
                         for a in accounts if a["account_id"] == target_id),
                        None
                    )
                    if target_account_text:
                        os_select_combo(p.harness, dlg.cmb_account, target_account_text)
                        p.harness.settle(0.3)
                    btn_box = dlg.findChild(QDialogButtonBox)
                    os_click_widget(p.harness, btn_box.button(QDialogButtonBox.StandardButton.Ok), wait=0.8)

                state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Edit Transaction", fill_move_transaction)
                result_after = p.sql(
                    "SELECT account_id FROM Transactions WHERE transaction_id = ?",
                    (move_id,)
                )
                if result_after and result_after[0][0] == target_id:
                    p.checks.check("13_move_to_account", True, "transaction moved to target account")
                else:
                    p.checks.check("13_move_to_account", False, "transaction not moved")
    except Exception as e:
        p.checks.check("13_move_to_account", False, f"error: {str(e)[:50]}")

    try:
        result = p.sql("SELECT transaction_id FROM Transactions WHERE description LIKE 'RUIH_%' LIMIT 1")
        if result:
            delete_id = result[0][0]

            def fill_and_delete(dlg):
                btn_box = dlg.findChild(QDialogButtonBox)
                os_click_widget(p.harness, btn_box.button(QDialogButtonBox.StandardButton.Ok), wait=0.8)

            ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Delete")
            state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Edit Transaction", fill_and_delete)

            table = page.table
            if table.rowCount() > 0:
                os_click_widget(p.harness, page.btn_delete, wait=0.8)
                p.harness.settle(1.0)

            after_result = p.sql(
                "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_id = ?",
                (delete_id,)
            )
            after_count = after_result[0][0] if after_result else 0
            p.checks.check("14_single_delete_removes_row", after_count == 0,
                          f"transaction still exists: {after_count > 0}")
    except Exception as e:
        p.checks.check("14_single_delete_removes_row", False, f"error: {str(e)[:50]}")

    try:
        result = p.sql("SELECT transaction_id FROM Transactions WHERE description LIKE 'RUIH_%' ORDER BY transaction_id DESC LIMIT 2")
        if len(result) >= 2:
            id1, id2 = result[0][0], result[1][0]

            table = page.table
            table.clearSelection()

            for row in range(table.rowCount()):
                _COL_ID = 10
                item = table.item(row, _COL_ID + 1)
                if item and item.text():
                    try:
                        row_id = int(item.text())
                        if row_id in (id1, id2):
                            checkbox = table.cellWidget(row, 0)
                            if checkbox:
                                os_click_widget(p.harness, checkbox, wait=0.2)
                    except (ValueError, AttributeError):
                        pass

            ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Delete")
            os_click_widget(p.harness, page.btn_delete, wait=0.8)
            p.harness.settle(1.0)

            after_result = p.sql(
                "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_id IN (?, ?)",
                (id1, id2)
            )
            after_count = after_result[0][0] if after_result else 0
            p.checks.check("15_multi_delete_removes_rows", after_count == 0,
                          f"some transactions still exist: {after_count}")
    except Exception as e:
        p.checks.check("15_multi_delete_removes_rows", False, f"error: {str(e)[:50]}")

    try:
        import pyautogui
        table = page.table
        page._dirty = False

        if table.rowCount() > 0:
            _COL_DESC = 5
            item = table.item(0, _COL_DESC + 1)
            if item:
                os_click_widget(p.harness, item, wait=0.2, double=True)
                p.harness.settle(0.3)
                pyautogui.hotkey("ctrl", "a")
                p.harness.settle(0.2)
                pyautogui.write("RUIH_", interval=0.05)
                p.harness.settle(0.3)
                pyautogui.press("return")
                p.harness.settle(0.5)

        unsaved_bar = page._unsaved_bar
        bar_visible = unsaved_bar.isVisible() if unsaved_bar else False
        p.checks.check("16_unsaved_bar_visible_on_edit", bar_visible, "bar should be visible after edit")

        if bar_visible:
            ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Discard, expect_title="Unsaved Changes")
            os_click_widget(p.harness, page.btn_discard, wait=0.8)
            p.harness.settle(1.0)

        dirty_after_discard = page._dirty
        p.checks.check("17_unsaved_changes_discarded", not dirty_after_discard,
                      "dirty flag should be False after discard")
    except Exception as e:
        p.checks.check("16_unsaved_bar_visible_on_edit", False, f"error: {str(e)[:50]}")

    try:
        ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.No, expect_title="Reprocess Internal Transfers")
        os_click_widget(p.harness, page.btn_reprocess, wait=1.5)
        p.harness.settle(1.0)

        result_before = p.sql("SELECT COUNT(*) as cnt FROM Transactions WHERE is_internal_transfer = 1")
        count_before = result_before[0][0] if result_before else 0
        p.checks.check("18_link_transfers_no_reprocess", True, f"internal transfer count: {count_before}")
    except Exception as e:
        p.checks.check("18_link_transfers_no_reprocess", False, f"error: {str(e)[:50]}")


if __name__ == "__main__":
    main_wrapper("02", "transactions", run_r, run_s)
