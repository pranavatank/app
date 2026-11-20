"""Accounts UI identity and action routing tests use the isolated test DB fixture."""

from PySide6.QtWidgets import QPushButton

import ui.accounts_screen as accounts_module


def _account(account_id, bank, person_id=1):
    return {
        "account_id": account_id,
        "person_id": person_id,
        "bank_name": bank,
        "bank_display_name": bank,
        "account_type": "Savings",
        "person_name": f"Person {person_id}",
        "account_number_masked": f"XXXX{account_id:04d}",
        "current_balance": 1000.0,
        "opening_balance": 900.0,
        "interest_rate": 3.0,
        "account_status": "Active",
    }


def test_selected_account_and_detail_actions_keep_exact_id(qapp, monkeypatch):
    accounts = {11: _account(11, "Shared Bank"), 22: _account(22, "Shared Bank", 2)}
    visible_ids = [11, 22]
    monkeypatch.setattr(accounts_module, "get_all_accounts", lambda: [accounts[i] for i in visible_ids])
    monkeypatch.setattr(accounts_module, "get_account", lambda account_id: accounts.get(int(account_id)))

    screen = accounts_module.AccountsScreen()
    screen._on_card_clicked(accounts[22])
    screen.view_mode = "list"
    screen._load_accounts()
    screen.set_fy_filter("2025-26")
    screen.refresh_theme()

    assert screen.selected_account_id == 22
    assert screen.detail_panel.account["account_id"] == 22

    transactions = []
    imports = []
    screen.view_transactions_requested.connect(transactions.append)
    screen.import_statement_requested.connect(imports.append)
    buttons = {button.text(): button for button in screen.detail_panel.findChildren(QPushButton)}
    buttons["Transactions"].click()
    buttons["Import"].click()
    assert transactions == [22]
    assert imports == [22]
    screen.set_person_filter(1)
    assert screen.selected_account_id is None
    assert screen.detail_panel.account is None
    screen.close()
