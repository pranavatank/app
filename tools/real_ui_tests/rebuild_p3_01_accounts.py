r"""tools/real_ui_tests/rebuild_p3_01_accounts.py — Phase 3.01 Accounts screen.

R: Navigation, view toggle, card widget counting, inline detail panel.
S: Add account with AccountDialog, validation errors, edit, delete.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_type, os_select_combo, os_set_date, answer_modal_dialog,
    answer_message_box, find_button, wait_until, adopt_window, toast_texts,
)
from tools.real_ui_test_harness import find_by_accessible_name
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDate


def run_r(p):
    page = p.nav("Accounts")

    os_click(p.harness, page, "Toggle account view", wait=0.6)
    p.checks.check("01_toggle_from_card_to_list", page.view_mode == "list", f"view_mode={page.view_mode}")

    os_click(p.harness, page, "Toggle account view", wait=0.6)
    p.checks.check("02_toggle_from_list_to_card", page.view_mode == "card", f"view_mode={page.view_mode}")

    accounts = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    expected_count = accounts[0][0]
    card_count = len([w for w in page.container.findChildren(type(page))
                      if hasattr(w, 'accessibleName') and
                      w.accessibleName().startswith('Account card for ')])
    p.checks.check("03_card_count_matches_db", card_count == expected_count,
                   f"expected {expected_count}, got {card_count}")

    if expected_count > 0 and page.view_mode == "card":
        from PySide6.QtWidgets import QFrame
        cards = [w for w in page.container.findChildren(QFrame)
                 if hasattr(w, 'accessibleName') and
                 w.accessibleName().startswith('Account card for ')]
        if cards:
            card = cards[0]
            p.a11y(card, "first account card (card view)")
            os_click(p.harness, card, wait=0.5)
            p.checks.check("04_detail_panel_opens",
                          page.detail_frame.maximumWidth() > 0,
                          f"detail_frame.maximumWidth()={page.detail_frame.maximumWidth()}")

            labels = [w.text() for w in page.detail_panel.findChildren(type(None).__bases__[0])
                     if hasattr(w, 'text') and callable(w.text)]
            bank_in_detail = any("bank" in t.lower() or "account" in t.lower() for t in labels)
            p.checks.check("05_detail_panel_shows_account_info", bank_in_detail,
                          f"labels: {labels[:3]}")

            try:
                close_btn = find_button(page.detail_panel, "Close")
                os_click(p.harness, close_btn, wait=0.3)
            except Exception:
                pass
            p.checks.check("06_detail_panel_closes", page.detail_frame.maximumWidth() == 0)


def run_s(p):
    from ui.dialogs.account_dialog import AccountDialog

    page = p.nav("Accounts")

    def fill_add_dialog(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")

        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        bank_options = [bank_combo.itemText(i) for i in range(bank_combo.count())]
        p.observe("bank_options", str(bank_options[:5]))
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")

        os_type(p.harness, dlg, "Account holder name", "RUIH_Holder")

        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        os_click(p.harness, dlg, "Save account", wait=1.0)

    state = answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_add_dialog)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(0.8)

    p.checks.check("10_add_account_dialog_appears", state.info.get("error") is None,
                   detail=state.info.get("error", ""))

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount WHERE account_holder_name = 'RUIH_Holder'")
    added_count = result[0][0]
    p.checks.check("11_account_added_to_db", added_count > 0, f"count={added_count}")

    def fill_invalid_ifsc(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")
        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")
        os_type(p.harness, dlg, "Account holder name", "RUIH_Invalid")
        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        try:
            inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
            from PySide6.QtCore import Qt
            from PySide6.QtTest import QTest
            bank_tab_rect = inner_tabs.tabBar().tabRect(1)
            QTest.mouseClick(inner_tabs.tabBar(), Qt.MouseButton.LeftButton, pos=bank_tab_rect.center())
            p.harness.settle(0.3)
        except Exception:
            pass

        os_type(p.harness, dlg, "IFSC code", "ABC")
        os_click(p.harness, dlg, "Save account", wait=0.5)

    state = answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_invalid_ifsc)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    toasts = toast_texts()
    has_error_toast = any("invalid" in t.lower() or "ifsc" in t.lower() for t in toasts)
    p.checks.check("12_invalid_ifsc_shows_error", has_error_toast or state.info.get("error"),
                   f"toasts={toasts}")

    def fill_valid_account(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")
        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")
        os_type(p.harness, dlg, "Account holder name", "RUIH_ValidHolder")
        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        try:
            inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
            from PySide6.QtCore import Qt
            from PySide6.QtTest import QTest
            bank_tab_rect = inner_tabs.tabBar().tabRect(1)
            QTest.mouseClick(inner_tabs.tabBar(), Qt.MouseButton.LeftButton, pos=bank_tab_rect.center())
            p.harness.settle(0.3)
            os_type(p.harness, dlg, "IFSC code", "JSFB0000001")
        except Exception:
            pass

        os_click(p.harness, dlg, "Save account", wait=1.0)

    state = answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_valid_account)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    p.checks.check("13_valid_account_accepted", state.info.get("error") is None,
                   detail=state.info.get("error", ""))

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount WHERE account_holder_name = 'RUIH_ValidHolder'")
    count = result[0][0]
    p.checks.check("14_valid_account_saved_to_db", count > 0, f"count={count}")

    result = p.sql("SELECT account_id FROM BankAccount WHERE account_holder_name = 'RUIH_ValidHolder' LIMIT 1")
    if result:
        account_id = result[0][0]
        result2 = p.sql("SELECT ifsc_code FROM BankAccount WHERE account_id = ?", (account_id,))
        if result2:
            ifsc = result2[0][0]
            p.checks.check("15_ifsc_persisted", ifsc == "JSFB0000001", f"ifsc={ifsc}")


if __name__ == "__main__":
    main_wrapper("01", "accounts", run_r, run_s)
