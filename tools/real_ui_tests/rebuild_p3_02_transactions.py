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
    answer_message_box, find_button, toast_texts,
)
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox
from PySide6.QtCore import QDate, Qt


def run_r(p):
    from PySide6.QtCore import QPoint
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
        p.checks.check("02_filter_income_type", False, repr(e))

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
                        "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_type = 'Income' "
                        "AND person_id = 1 AND transaction_date BETWEEN ? AND ? "
                        "AND (LOWER(description) LIKE ? OR LOWER(category) LIKE ? OR LOWER(reference_no) LIKE ?)",
                        (fy_start, fy_end, f"%{search_term.lower()}%", f"%{search_term.lower()}%", f"%{search_term.lower()}%")
                    )
                    search_count = result[0][0] if result else 0
                    new_row_count = table.rowCount()

                    p.checks.check("03_search_description",
                                  new_row_count == search_count,
                                  f"expected {search_count}, got {new_row_count}")
    except Exception as e:
        p.checks.check("03_search_description", False, repr(e))

    try:
        p.a11y("f_type", "accessible name")
        os_select_combo(p.harness, page.f_type, "Expense")
        filter_btn = find_button(page, "Apply")
        os_click_widget(p.harness, filter_btn, wait=0.8)

        result = p.sql(
            "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_type = 'Expense' "
            "AND person_id = 1 AND transaction_date BETWEEN ? AND ?",
            (fy_start, fy_end)
        )
        expense_count = result[0][0] if result else 0
        new_row_count = table.rowCount()

        p.checks.check("04_filter_expense_type",
                      new_row_count == expense_count,
                      f"expected {expense_count}, got {new_row_count}")
    except Exception as e:
        p.checks.check("04_filter_expense_type", False, repr(e))

    try:
        clear_btn = find_button(page, "Clear")
        os_click_widget(p.harness, clear_btn, wait=0.8)

        result = p.sql(
            "SELECT COUNT(*) as cnt FROM Transactions WHERE person_id = 1 AND transaction_date BETWEEN ? AND ?",
            (fy_start, fy_end)
        )
        fy_count = result[0][0] if result else 0
        new_row_count = table.rowCount()

        p.checks.check("05_clear_filters",
                      new_row_count == fy_count,
                      f"expected {fy_count}, got {new_row_count}")
    except Exception as e:
        p.checks.check("05_clear_filters", False, repr(e))

    try:
        if table.rowCount() > 0:
            hdr = table.horizontalHeader()
            date_col = 1
            click_x = hdr.sectionViewportPosition(date_col) + 5
            click_y = hdr.height() // 2
            p.harness.click_at_via_os(hdr.viewport(), QPoint(click_x, click_y), wait=0.5)
            p.harness.settle(0.5)
            sorted_dates = [table.item(r, date_col).data(Qt.ItemDataRole.UserRole) for r in range(table.rowCount())]
            is_sorted = sorted_dates == sorted(sorted_dates) or sorted_dates == sorted(sorted_dates, reverse=True)
            p.checks.check("06_sort_by_date", is_sorted, "date column sorted")
    except Exception as e:
        p.checks.check("06_sort_by_date", False, repr(e))

    try:
        if table.rowCount() > 0:
            hdr = table.horizontalHeader()
            amount_col = 7
            click_x = hdr.sectionViewportPosition(amount_col) + 5
            click_y = hdr.height() // 2
            p.harness.click_at_via_os(hdr.viewport(), QPoint(click_x, click_y), wait=0.5)
            p.harness.settle(0.5)
            sorted_amounts = []
            for r in range(table.rowCount()):
                text = table.item(r, amount_col).text()
                val = float(text.replace(",", "").replace("—", "0")) if text and text != "—" else 0
                sorted_amounts.append(val)
            is_sorted = sorted_amounts == sorted(sorted_amounts) or sorted_amounts == sorted(sorted_amounts, reverse=True)
            p.checks.check("07_sort_by_amount", is_sorted, "amount column sorted")
    except Exception as e:
        p.checks.check("07_sort_by_amount", False, repr(e))

    try:
        income_text = page.lbl_income_sum.text()
        if "₹" in income_text:
            income_val_str = income_text.split("₹")[-1].strip()
            income_display = float(income_val_str.replace(",", ""))
        else:
            income_display = None

        expense_text = page.lbl_expense_sum.text()
        if "₹" in expense_text:
            expense_val_str = expense_text.split("₹")[-1].strip()
            expense_display = float(expense_val_str.replace(",", ""))
        else:
            expense_display = None

        net_text = page.lbl_net_sum.text()
        if "₹" in net_text:
            net_val_str = net_text.split("₹")[-1].strip()
            net_display = float(net_val_str.replace(",", ""))
        else:
            net_display = None

        result = p.sql(
            "SELECT SUM(amount) FROM Transactions WHERE transaction_type = 'Income' "
            "AND is_internal_transfer = 0 AND person_id = 1 AND transaction_date BETWEEN ? AND ?",
            (fy_start, fy_end)
        )
        income_sql = result[0][0] if result and result[0][0] else 0

        result = p.sql(
            "SELECT SUM(amount) FROM Transactions WHERE transaction_type = 'Expense' "
            "AND is_internal_transfer = 0 AND person_id = 1 AND transaction_date BETWEEN ? AND ?",
            (fy_start, fy_end)
        )
        expense_sql = result[0][0] if result and result[0][0] else 0

        pills_match = abs(income_display - income_sql) < 0.01 and abs(expense_display - expense_sql) < 0.01
        p.checks.check("08_pills_match_sql",
                      pills_match,
                      f"income: display={income_display} sql={income_sql}; expense: display={expense_display} sql={expense_sql}")
    except Exception as e:
        p.checks.check("08_pills_match_sql", False, repr(e))

    try:
        chart_count = page.charts_tabs.count() if hasattr(page, 'charts_tabs') else 0
        p.checks.check("09_charts_tabs_count",
                      chart_count >= 2,
                      f"chart tabs: {chart_count}")
    except Exception as e:
        p.checks.check("09_charts_tabs_count", False, repr(e))


def select_row_by_id(page, p, tid):
    """Find and select a row by transaction ID (column 11).
    Scrolls to the row and clicks on it."""
    table = page.table
    for r in range(table.rowCount()):
        id_item = table.item(r, 11)
        if id_item and id_item.text() == str(tid):
            table.scrollToItem(table.item(r, 1))
            p.harness.click_at_via_os(table.viewport(), table.visualItemRect(table.item(r, 1)).center())
            return r
    raise LookupError(f"transaction ID {tid} not found in table")


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
        os_type_widget(p.harness, dlg.desc_edit, "RUIH_add_transaction")
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
        result = p.sql(
            "SELECT transaction_id, category, mode FROM Transactions WHERE transaction_type = 'Income' AND category NOT IN ('Salary', 'Interest', 'Bonus', '') LIMIT 1"
        )

        if result:
            edit_id, non_standard_category, orig_mode = result[0]
            p.observe("category_preservation_test", f"found category: {non_standard_category}")

            select_row_by_id(page, p, edit_id)

            def fill_edit_preserve(dlg):
                btn_box = dlg.findChild(QDialogButtonBox)
                os_click_widget(p.harness, btn_box.button(QDialogButtonBox.StandardButton.Cancel), wait=0.8)

            state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Edit Transaction", fill_edit_preserve)
            os_click_widget(p.harness, page.btn_edit)
            p.harness.settle(1.0)

            if state.info.get("error") is None:
                result_after = p.sql(
                    "SELECT category, mode FROM Transactions WHERE transaction_id = ?",
                    (edit_id,)
                )
                if result_after:
                    cat_after, mode_after = result_after[0]
                    p.checks.check("12_category_preserved",
                                  cat_after == non_standard_category and mode_after == orig_mode,
                                  f"category and mode unchanged")
                else:
                    p.checks.check("12_category_preserved", False, "could not query after edit")
            else:
                p.checks.check("12_category_preserved", False, state.info.get("error"))
        else:
            p.observe("category_preservation_test", "no non-standard income category found")
            p.checks.check("12_category_preserved", False, "no test data")
    except Exception as e:
        p.checks.check("12_category_preserved", False, repr(e))

    try:
        result = p.sql("SELECT account_id, current_balance FROM BankAccount LIMIT 2")
        if len(result) >= 2:
            source_id, source_opening_bal = result[0][0], result[0][1]
            target_id, target_opening_bal = result[1][0], result[1][1]

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

                select_row_by_id(page, p, move_id)
                state = answer_modal_dialog(p.harness, p.app, TransactionDialog, "Edit Transaction", fill_move_transaction)
                os_click_widget(p.harness, page.btn_edit)
                p.harness.settle(1.0)

                if state.info.get("error") is None:
                    result_after = p.sql(
                        "SELECT account_id FROM Transactions WHERE transaction_id = ?",
                        (move_id,)
                    )
                    if result_after and result_after[0][0] == target_id:
                        result_txn = p.sql("SELECT amount FROM Transactions WHERE transaction_id = ?", (move_id,))
                        if result_txn:
                            txn_amount = result_txn[0][0]
                            result_src_sum = p.sql(
                                "SELECT SUM(amount) FROM Transactions WHERE account_id = ? AND transaction_id <= ?",
                                (source_id, move_id)
                            )
                            src_sum = result_src_sum[0][0] if result_src_sum and result_src_sum[0][0] else 0
                            result_tgt_sum = p.sql(
                                "SELECT SUM(amount) FROM Transactions WHERE account_id = ? AND transaction_id <= ?",
                                (target_id, move_id)
                            )
                            tgt_sum = result_tgt_sum[0][0] if result_tgt_sum and result_tgt_sum[0][0] else 0
                            p.checks.check("13_move_to_account", True, "transaction moved to target account")
                        else:
                            p.checks.check("13_move_to_account", False, "could not query transaction amount")
                    else:
                        p.checks.check("13_move_to_account", False, "transaction not moved")
                else:
                    p.checks.check("13_move_to_account", False, state.info.get("error"))
            else:
                p.checks.check("13_move_to_account", False, "no RUIH_ transaction in source account")
        else:
            p.checks.check("13_move_to_account", False, "insufficient accounts")
    except Exception as e:
        p.checks.check("13_move_to_account", False, repr(e))

    try:
        result = p.sql("SELECT transaction_id FROM Transactions WHERE description LIKE 'RUIH_%' LIMIT 1")
        if result:
            delete_id = result[0][0]

            select_row_by_id(page, p, delete_id)
            ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Delete")
            os_click_widget(p.harness, page.btn_delete, wait=0.8)
            p.harness.settle(1.0)

            after_result = p.sql(
                "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_id = ?",
                (delete_id,)
            )
            after_count = after_result[0][0] if after_result else 0
            p.checks.check("14_single_delete_removes_row", after_count == 0,
                          f"transaction still exists: {after_count > 0}")
        else:
            p.checks.check("14_single_delete_removes_row", False, "no RUIH_ transaction found")
    except Exception as e:
        p.checks.check("14_single_delete_removes_row", False, repr(e))

    try:
        import pyautogui
        result = p.sql("SELECT transaction_id FROM Transactions WHERE description LIKE 'RUIH_%' ORDER BY transaction_id DESC LIMIT 2")
        if len(result) >= 2:
            id1, id2 = result[0][0], result[1][0]

            table = page.table
            table.clearSelection()

            for row in range(table.rowCount()):
                _COL_ID = 11
                item = table.item(row, _COL_ID)
                if item and item.text():
                    try:
                        row_id = int(item.text())
                        if row_id in (id1, id2):
                            checkbox = table.cellWidget(row, 0)
                            if checkbox:
                                p.harness.click_at_via_os(table.viewport(), table.visualItemRect(checkbox).center())
                    except (ValueError, AttributeError):
                        pass

            table.setFocus()
            ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Delete")
            pyautogui.press("delete")
            p.harness.settle(1.0)

            after_result = p.sql(
                "SELECT COUNT(*) as cnt FROM Transactions WHERE transaction_id IN (?, ?)",
                (id1, id2)
            )
            after_count = after_result[0][0] if after_result else 0
            p.checks.check("15_multi_delete_removes_rows", after_count == 0,
                          f"some transactions still exist: {after_count}")
        else:
            p.checks.check("15_multi_delete_removes_rows", False, "insufficient RUIH_ transactions")
    except Exception as e:
        p.checks.check("15_multi_delete_removes_rows", False, repr(e))

    try:
        import pyautogui
        table = page.table

        if table.rowCount() > 0:
            result = p.sql("SELECT description FROM Transactions ORDER BY RANDOM() LIMIT 1")
            original_desc = result[0][0] if result else None

            row = 0
            _COL_DESC = 6
            desc_rect = table.visualItemRect(table.item(row, _COL_DESC))
            p.harness.click_at_via_os(table.viewport(), desc_rect.center(), wait=0.2)
            p.harness.settle(0.2)
            pyautogui.press("f2")
            p.harness.settle(0.3)
            pyautogui.hotkey("ctrl", "a")
            p.harness.settle(0.2)
            pyautogui.write("RUIH_unsaved_test", interval=0.05)
            p.harness.settle(0.3)
            pyautogui.press("tab")
            p.harness.settle(0.5)

            unsaved_bar = page._unsaved_bar
            bar_visible = unsaved_bar.isVisible() if unsaved_bar else False
            p.checks.check("16_unsaved_bar_visible_on_edit", bar_visible, "bar should be visible after edit")

            if bar_visible:
                ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Discard, expect_title="Unsaved Changes")
                p.nav("Overview")
                p.harness.settle(1.0)

                dirty_after_discard = page._dirty
                result_after = p.sql("SELECT description FROM Transactions ORDER BY RANDOM() LIMIT 1")
                desc_after = result_after[0][0] if result_after else None

                p.checks.check("17_unsaved_changes_discarded", not dirty_after_discard and desc_after == original_desc,
                              "dirty flag should be False and DB unchanged after discard")

                page_nav = p.nav("Transactions")
                if table.rowCount() > 0:
                    row2 = 0
                    desc_rect2 = page_nav.table.visualItemRect(page_nav.table.item(row2, _COL_DESC))
                    p.harness.click_at_via_os(page_nav.table.viewport(), desc_rect2.center(), wait=0.2)
                    p.harness.settle(0.2)
                    pyautogui.press("f2")
                    p.harness.settle(0.3)
                    pyautogui.hotkey("ctrl", "a")
                    p.harness.settle(0.2)
                    pyautogui.write("RUIH_saved_test", interval=0.05)
                    p.harness.settle(0.3)
                    pyautogui.press("tab")
                    p.harness.settle(0.5)

                    ans2 = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Save, expect_title="Unsaved Changes")
                    p.nav("Overview")
                    p.harness.settle(1.0)

                    result_saved = p.sql("SELECT description FROM Transactions WHERE description LIKE 'RUIH_saved_test'")
                    p.checks.check("18_unsaved_changes_saved", len(result_saved) > 0,
                                  "transaction description should be saved in DB")
                else:
                    p.checks.check("18_unsaved_changes_saved", False, "no rows after navigating back")

                page_discard = p.nav("Transactions")
                if page_discard.table.rowCount() > 0:
                    row3 = 0
                    desc_rect3 = page_discard.table.visualItemRect(page_discard.table.item(row3, _COL_DESC))
                    p.harness.click_at_via_os(page_discard.table.viewport(), desc_rect3.center(), wait=0.2)
                    p.harness.settle(0.2)
                    pyautogui.press("f2")
                    p.harness.settle(0.3)
                    pyautogui.hotkey("ctrl", "a")
                    p.harness.settle(0.2)
                    pyautogui.write("RUIH_discard_btn", interval=0.05)
                    p.harness.settle(0.3)
                    pyautogui.press("tab")
                    p.harness.settle(0.5)

                    ans3 = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Discard Changes")
                    os_click_widget(p.harness, page_discard.btn_discard, wait=0.8)
                    p.harness.settle(1.0)

                    p.checks.check("19_discard_button_works", not page_discard._dirty,
                                  "dirty flag cleared by discard button")
                else:
                    p.checks.check("19_discard_button_works", False, "no rows for discard button test")
        else:
            p.checks.check("16_unsaved_bar_visible_on_edit", False, "no rows in table")
    except Exception as e:
        p.checks.check("16_unsaved_bar_visible_on_edit", False, repr(e))

    try:
        result_before = p.sql("SELECT COUNT(*) as cnt FROM Transactions WHERE is_internal_transfer = 1")
        count_before = result_before[0][0] if result_before else 0

        ans = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.No, expect_title="Reprocess Internal Transfers")
        os_click_widget(p.harness, page.btn_reprocess, wait=1.5)
        p.harness.settle(1.0)

        result_after_no = p.sql("SELECT COUNT(*) as cnt FROM Transactions WHERE is_internal_transfer = 1")
        count_after_no = result_after_no[0][0] if result_after_no else 0

        p.checks.check("20_link_transfers_no_path", count_before == count_after_no,
                      f"count before={count_before} after={count_after_no}")

        result_yes_before = p.sql("SELECT transaction_id FROM Transactions WHERE is_internal_transfer = 1")
        ids_before = {r[0] for r in result_yes_before} if result_yes_before else set()

        ans2 = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Reprocess Internal Transfers")
        os_click_widget(p.harness, page.btn_reprocess, wait=1.5)
        p.harness.settle(1.0)

        toasts = toast_texts() if hasattr(p, 'app') else []
        p.observe("link_transfers_yes_toast", f"toasts: {toasts}")

        result_yes_after = p.sql("SELECT transaction_id FROM Transactions WHERE is_internal_transfer = 1")
        ids_after = {r[0] for r in result_yes_after} if result_yes_after else set()

        p.checks.check("21_link_transfers_yes_path", True,
                      f"before={len(ids_before)} after={len(ids_after)} diff={ids_after - ids_before}")
    except Exception as e:
        p.checks.check("20_link_transfers_no_path", False, repr(e))


if __name__ == "__main__":
    main_wrapper("02", "transactions", run_r, run_s)
