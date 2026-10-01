r"""tools/real_ui_tests/rebuild_p3_01_accounts.py — Phase 3.01 Accounts screen.

R: Navigation, view toggle, card widget counting, inline detail panel.
S: Add account with AccountDialog, validation errors, edit, delete.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type, os_select_combo,
    answer_modal_dialog, answer_message_box, find_button, toast_texts,
)
from tools.real_ui_test_harness import find_by_accessible_name
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMessageBox


def run_r(p):
    page = p.nav("Accounts")

    os_click(p.harness, page, "Toggle account view", wait=0.6)
    p.checks.check("01_toggle_from_card_to_list", page.view_mode == "list", f"view_mode={page.view_mode}")

    os_click(p.harness, page, "Toggle account view", wait=0.6)
    p.checks.check("02_toggle_from_list_to_card", page.view_mode == "card", f"view_mode={page.view_mode}")

    accounts = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    expected_count = accounts[0][0]
    card_count = len([w for w in page.container.findChildren(QFrame)
                      if w.objectName() == "accountCard"])
    p.checks.check("03_card_count_matches_db", card_count == expected_count,
                   f"expected {expected_count}, got {card_count}")

    if expected_count > 0 and page.view_mode == "card":
        cards = [w for w in page.container.findChildren(QFrame)
                 if w.objectName() == "accountCard"]
        if cards:
            card = cards[0]
            p.a11y("first_account_card", "first account card (card view)")
            os_click_widget(p.harness, card, wait=0.5)
            p.checks.check("04_detail_panel_opens",
                          page.detail_frame.maximumWidth() > 0,
                          f"detail_frame.maximumWidth()={page.detail_frame.maximumWidth()}")

            labels = [w.text() for w in page.detail_panel.findChildren(QLabel)
                     if hasattr(w, 'text') and callable(w.text)]
            bank_in_detail = any("bank" in t.lower() or "account" in t.lower() for t in labels)
            p.checks.check("05_detail_panel_shows_account_info", bank_in_detail,
                          f"labels: {labels[:3]}")

            try:
                close_btn = find_button(page.detail_panel, "Close")
                os_click_widget(p.harness, close_btn, wait=0.3)
                p.checks.check("06_detail_panel_closes", page.detail_frame.maximumWidth() == 0)
            except Exception as e:
                p.checks.check("06_detail_panel_closes", False, repr(e))


def run_s(p):
    from ui.dialogs.account_dialog import AccountDialog
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

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

    answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_add_dialog)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(0.8)

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount WHERE account_holder_name = 'RUIH_Holder'")
    added_count = result[0][0]
    p.checks.check("10_account_added_to_db", added_count > 0, f"count={added_count}")

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
            bank_tab_rect = inner_tabs.tabBar().tabRect(1)
            QTest.mouseClick(inner_tabs.tabBar(), Qt.MouseButton.LeftButton, pos=bank_tab_rect.center())
            p.harness.settle(0.3)
        except Exception:
            pass

        os_type(p.harness, dlg, "IFSC code", "ABC")
        os_click(p.harness, dlg, "Save account", wait=0.5)
        try:
            os_click(p.harness, dlg, "Cancel account dialog", wait=0.5)
        except Exception:
            pass

    answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_invalid_ifsc)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    toasts = toast_texts()
    has_error_toast = any("invalid" in t.lower() or "ifsc" in t.lower() for t in toasts)
    p.checks.check("11_invalid_ifsc_shows_error", has_error_toast,
                   f"toasts={toasts}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    before_micr_count = result[0][0]

    def fill_invalid_micr(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")
        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")
        os_type(p.harness, dlg, "Account holder name", "RUIH_InvalidMICR")
        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        try:
            inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
            bank_tab_rect = inner_tabs.tabBar().tabRect(1)
            QTest.mouseClick(inner_tabs.tabBar(), Qt.MouseButton.LeftButton, pos=bank_tab_rect.center())
            p.harness.settle(0.3)
            os_type(p.harness, dlg, "MICR code", "12345")
        except Exception:
            pass

        os_click(p.harness, dlg, "Save account", wait=0.5)
        try:
            os_click(p.harness, dlg, "Cancel account dialog", wait=0.5)
        except Exception:
            pass

    answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_invalid_micr)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    toasts = toast_texts()
    has_micr_error = any("micr" in t.lower() or "invalid" in t.lower() for t in toasts)
    p.checks.check("12_invalid_micr_shows_error", has_micr_error, f"toasts={toasts}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    after_micr_count = result[0][0]
    p.checks.check("13_micr_error_blocks_save", before_micr_count == after_micr_count,
                   f"before={before_micr_count}, after={after_micr_count}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    before_email_count = result[0][0] if result else 0

    def fill_invalid_email(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")
        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")
        os_type(p.harness, dlg, "Account holder name", "RUIH_InvalidEmail")
        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
        contact_tab_rect = inner_tabs.tabBar().tabRect(2)
        p.harness.click_at_via_os(inner_tabs.tabBar(), contact_tab_rect.center(), wait=0.3)
        p.harness.settle(0.3)
        os_type(p.harness, dlg, "Email address", "bad@")

        os_click(p.harness, dlg, "Save account", wait=0.5)
        try:
            os_click(p.harness, dlg, "Cancel account dialog", wait=0.5)
        except Exception:
            pass

    answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_invalid_email)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    toasts = toast_texts()
    has_email_error = any("email" in t.lower() or "invalid" in t.lower() for t in toasts)
    p.checks.check("14_invalid_email_shows_error", has_email_error, f"toasts={toasts}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    after_email_count = result[0][0] if result else 0
    p.checks.check("14b_email_error_blocks_save", before_email_count == after_email_count,
                   f"before={before_email_count}, after={after_email_count}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    before_phone_count = result[0][0] if result else 0

    def fill_invalid_phone(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")
        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")
        os_type(p.harness, dlg, "Account holder name", "RUIH_InvalidPhone")
        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
        contact_tab_rect = inner_tabs.tabBar().tabRect(2)
        p.harness.click_at_via_os(inner_tabs.tabBar(), contact_tab_rect.center(), wait=0.3)
        p.harness.settle(0.3)
        os_type(p.harness, dlg, "Phone number", "12345")

        os_click(p.harness, dlg, "Save account", wait=0.5)
        try:
            os_click(p.harness, dlg, "Cancel account dialog", wait=0.5)
        except Exception:
            pass

    answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_invalid_phone)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    toasts = toast_texts()
    has_phone_error = any("phone" in t.lower() or "invalid" in t.lower() for t in toasts)
    p.checks.check("15_invalid_phone_shows_error", has_phone_error, f"toasts={toasts}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    after_phone_count = result[0][0] if result else 0
    p.checks.check("15b_phone_error_blocks_save", before_phone_count == after_phone_count,
                   f"before={before_phone_count}, after={after_phone_count}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    before_tan_count = result[0][0] if result else 0

    def fill_invalid_tan(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")
        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")
        os_type(p.harness, dlg, "Account holder name", "RUIH_InvalidTAN")
        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
        bank_tab_rect = inner_tabs.tabBar().tabRect(1)
        p.harness.click_at_via_os(inner_tabs.tabBar(), bank_tab_rect.center(), wait=0.3)
        p.harness.settle(0.3)
        os_type(p.harness, dlg, "TAN code", "ABC")

        os_click(p.harness, dlg, "Save account", wait=0.5)
        try:
            os_click(p.harness, dlg, "Cancel account dialog", wait=0.5)
        except Exception:
            pass

    answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_invalid_tan)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    toasts = toast_texts()
    has_tan_error = any("tan" in t.lower() or "invalid" in t.lower() for t in toasts)
    p.checks.check("16_invalid_tan_shows_error", has_tan_error, f"toasts={toasts}")

    result = p.sql("SELECT COUNT(*) as cnt FROM BankAccount")
    after_tan_count = result[0][0] if result else 0
    p.checks.check("16b_tan_error_blocks_save", before_tan_count == after_tan_count,
                   f"before={before_tan_count}, after={after_tan_count}")

    def fill_valid_ruih_account(dlg):
        person_combo = find_by_accessible_name(dlg, "Person selector")
        os_select_combo(p.harness, person_combo, "Pranav")
        bank_combo = find_by_accessible_name(dlg, "Bank selector")
        os_select_combo(p.harness, bank_combo, "Jana Small Finance Bank")
        os_type(p.harness, dlg, "Account holder name", "RUIH")
        type_combo = find_by_accessible_name(dlg, "Account type")
        os_select_combo(p.harness, type_combo, "Current")

        inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
        bank_tab_rect = inner_tabs.tabBar().tabRect(1)
        p.harness.click_at_via_os(inner_tabs.tabBar(), bank_tab_rect.center(), wait=0.3)
        p.harness.settle(0.3)
        os_type(p.harness, dlg, "IFSC code", "JSFB0000001")

        os_click(p.harness, dlg, "Save account", wait=1.0)

    answer_modal_dialog(p.harness, p.app, AccountDialog, "Add Account", fill_valid_ruih_account)
    os_click(p.harness, page, "Add account", wait=2.0)
    p.harness.settle(1.0)

    result = p.sql("SELECT account_id FROM BankAccount WHERE account_holder_name = 'RUIH' LIMIT 1")
    ruih_account_id = None
    if result:
        ruih_account_id = result[0][0]

    p.checks.check("17_ruih_account_created", ruih_account_id is not None,
                   f"account_id={ruih_account_id}")

    if ruih_account_id:
        result = p.sql("SELECT ifsc_code FROM BankAccount WHERE account_id = ?", (ruih_account_id,))
        if result:
            ifsc = result[0][0]
            p.checks.check("18_ruih_ifsc_set_correctly", ifsc == "JSFB0000001", f"ifsc={ifsc}")

    # Test Edit IFSC
    if ruih_account_id:
        try:
            p.harness.settle(0.5)
            page.refresh()
            p.harness.settle(1.0)

            ruih_cards = [w for w in page.container.findChildren(QFrame)
                         if w.objectName() == "accountCard"]
            ruih_card = None
            for card in ruih_cards:
                labels = [l.text() for l in card.findChildren(QLabel)]
                if any("RUIH" in str(l) for l in labels):
                    ruih_card = card
                    break

            if ruih_card:
                os_click_widget(p.harness, ruih_card, wait=0.5)
                p.harness.settle(0.5)

                def fill_edit_ifsc(dlg):
                    inner_tabs = find_by_accessible_name(dlg, "Account details tabs")
                    bank_tab_rect = inner_tabs.tabBar().tabRect(1)
                    p.harness.click_at_via_os(inner_tabs.tabBar(), bank_tab_rect.center(), wait=0.3)
                    p.harness.settle(0.3)
                    os_type(p.harness, dlg, "IFSC code", "JSFB0000002", retries=2)
                    os_click(p.harness, dlg, "Save account", wait=1.0)

                prearm = answer_modal_dialog(p.harness, p.app, AccountDialog, "Edit Account", fill_edit_ifsc)
                try:
                    edit_btn = find_button(page.detail_panel, "Edit")
                    os_click_widget(p.harness, edit_btn, wait=0.5)
                except Exception:
                    pass
                ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
                if not ok or prearm.error:
                    p.checks.check("edit account IFSC", False, f"{prearm.error}")
                else:
                    p.harness.settle(0.5)
                    result = p.sql("SELECT ifsc_code FROM BankAccount WHERE account_id = ?", (ruih_account_id,))
                    if result and result[0][0] == "JSFB0000002":
                        p.checks.check("edit account IFSC", True)
                    else:
                        p.checks.check("edit account IFSC", False, f"ifsc={result[0][0] if result else None}")
        except Exception as e:
            p.checks.check("edit account IFSC", False, repr(e))

    # Test Delete
    if ruih_account_id:
        try:
            p.harness.settle(0.5)
            page.refresh()
            p.harness.settle(1.0)

            ruih_cards = [w for w in page.container.findChildren(QFrame)
                         if w.objectName() == "accountCard"]
            ruih_card = None
            for card in ruih_cards:
                labels = [l.text() for l in card.findChildren(QLabel)]
                if any("RUIH" in str(l) for l in labels):
                    ruih_card = card
                    break

            if ruih_card:
                os_click_widget(p.harness, ruih_card, wait=0.5)
                p.harness.settle(0.5)

                prearm = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes,
                    expect_title="Confirm Delete")
                try:
                    delete_btn = find_button(page.detail_panel, "Delete")
                    os_click_widget(p.harness, delete_btn, wait=0.5)
                except Exception:
                    pass
                ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
                if not ok or prearm.error:
                    p.checks.check("delete account", False, f"{prearm.error}")
                else:
                    p.harness.settle(1.0)
                    result = p.sql("SELECT COUNT(*) FROM BankAccount WHERE account_id = ?", (ruih_account_id,))
                    row_count = result[0][0] if result else 0
                    p.checks.check("delete account", row_count == 0, f"account still exists")
        except Exception as e:
            p.checks.check("delete account", False, repr(e))


if __name__ == "__main__":
    main_wrapper("01", "accounts", run_r, run_s)
