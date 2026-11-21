"""Regression tests for bank ledger links and their downstream totals."""

from datetime import date

import pytest

from engines.prediction_engine import realised_income_to_date
from engines.statement_metadata_extractor import extract_account_metadata
from engines.statement_parser import validate_transactions
from models.bank_account import add_account
from models.income_expectation import (
    add_income_expectation,
    auto_link_income_expectations,
    get_income_expectations,
    link_actual_transaction,
)
from models.person import add_person
from models.transaction import (
    add_transaction,
    delete_transaction,
    get_expense_total,
    get_income_total,
    get_transaction,
    link_internal_transfer,
    reprocess_internal_transfers,
    update_transaction,
)


@pytest.fixture
def household():
    payer = add_person("Ledger test payer")
    receiver = add_person("Ledger test receiver")
    return payer, receiver, add_account(payer, "Test Bank A", "Savings"), add_account(
        receiver, "Test Bank B", "Savings",
    )


def test_confirmed_family_transfer_preserves_balances_and_clears_expectation(household):
    payer, receiver, source, destination = household
    debit = add_transaction(source, payer, "2025-04-11", "Expense", 1800, balance_after=2200)
    credit = add_transaction(destination, receiver, "2025-04-12", "Income", 1800, category="Salary", balance_after=1900)
    expectation, = add_income_expectation(receiver, destination, "Salary", 1800, "2025-04-12", "One-Time", "2025-26")
    link_actual_transaction(expectation, credit)

    link_internal_transfer(debit, credit)
    assert get_transaction(debit)["linked_transaction_id"] == credit
    assert get_transaction(credit)["linked_transaction_id"] == debit
    assert get_transaction(credit)["balance_after"] == 1900
    assert get_income_total(receiver, "2025-26") == 0
    assert get_expense_total(payer, "2025-26") == 0
    assert not realised_income_to_date(receiver, "2025-26", as_of=date(2025, 4, 30))["by_category"]
    assert get_income_expectations(receiver, "2025-26")[0]["actual_transaction_id"] is None
    assert auto_link_income_expectations(receiver, destination, "2025-26") == 0
    with pytest.raises(ValueError):
        link_actual_transaction(expectation, credit)

    reprocess_internal_transfers(person_id=payer)
    assert get_transaction(credit)["linked_transaction_id"] == debit
    update_transaction(debit, "2025-04-11", "Expense", 1700)
    assert not get_transaction(debit)["is_internal_transfer"]
    assert not get_transaction(credit)["is_internal_transfer"]


def test_detection_requires_shared_reference_across_accounts(household):
    payer, receiver, source, destination = household
    debit = add_transaction(source, payer, "2025-04-12", "Expense", 2700, reference_no="UTR921632745")
    credit = add_transaction(destination, receiver, "2025-04-13", "Income", 2700)

    assert reprocess_internal_transfers(person_id=payer) == (0, 0)
    update_transaction(credit, "2025-04-13", "Income", 2700, reference_no="UTR921632745")
    assert reprocess_internal_transfers(person_id=payer) == (1, 2)
    delete_transaction(debit)
    assert not get_transaction(credit)["is_internal_transfer"]
    assert get_transaction(credit)["linked_transaction_id"] is None


def test_transaction_screen_links_selected_family_transfer(qapp, household, monkeypatch):
    from PySide6.QtCore import QDate

    from core.session import session
    from ui import transactions_screen as ui

    payer, receiver, source, destination = household
    debit = add_transaction(source, payer, "2025-04-11", "Expense", 4600)
    credit = add_transaction(destination, receiver, "2025-04-11", "Income", 4600)
    older = add_transaction(source, payer, "2025-03-30", "Expense", 125)
    monkeypatch.setattr(session, "selected_person_id", payer)
    monkeypatch.setattr(session, "selected_account_id", source)
    monkeypatch.setattr(session, "selected_fy", "2025-26")
    monkeypatch.setattr(ui.TransactionsScreen, "_choose_transfer_counterpart", lambda self, txn, candidates: candidates[0]["transaction_id"])
    screen = ui.TransactionsScreen()
    screen._fetch_and_display()
    assert [row["transaction_id"] for row in screen._current_rows] == [debit]
    screen.ledger_dates.enabled.setChecked(True)
    screen.ledger_dates.start.setDate(QDate(2025, 3, 29))
    screen.ledger_dates.end.setDate(QDate(2025, 3, 31))
    screen._fetch_and_display()
    assert [row["transaction_id"] for row in screen._current_rows] == [older]
    screen._clear_filters()
    screen.table.setCurrentCell(0, 1)

    assert screen.btn_link_transfer.isEnabled()
    screen.btn_link_transfer.click()
    assert get_transaction(debit)["linked_transaction_id"] == credit
    assert screen.table.item(0, 2).text() == "Transfer (Out)"
    screen.close()


def test_expectation_auto_match_requires_category_and_manual_link_is_unique(household):
    _, receiver, _, destination = household
    first, = add_income_expectation(receiver, destination, "Salary", 1800, "2025-04-11", "One-Time", "2025-26")
    second, = add_income_expectation(receiver, destination, "Salary", 1900, "2025-04-12", "One-Time", "2025-26")
    credit = add_transaction(destination, receiver, "2025-04-12", "Income", 1900, category="Other Income")
    assert auto_link_income_expectations(receiver, destination, "2025-26") == 0
    link_actual_transaction(second, credit)
    with pytest.raises(ValueError):
        link_actual_transaction(first, credit)


def test_header_metadata_does_not_read_transaction_names():
    header = extract_account_metadata(
        "Account Number: 123456780001\nCustomer Name: Test Holder\n"
        "Branch Name: Example Main\nDate Description Debit Credit Balance\n"
        "2025-04-01 Account Number: 123456780002 Customer Name: Another Holder",
    )
    assert header["account_number_full"] == "123456780001"
    assert header["account_holder_name"] == "Test Holder"
    assert header["branch_name"] == "Example Main"


def test_clear_narration_enriches_generic_statement_categories():
    rows, errors = validate_transactions([
        {
            "transaction_date": "2025-04-01", "amount": 500, "transaction_type": "Income",
            "description": "NEFT PENSION APRIL", "category": "Other Income",
        },
        {
            "transaction_date": "2025-04-02", "amount": 500, "transaction_type": "Income",
            "description": "UPI TRANSFER", "category": "Other Income",
        },
    ])
    assert not errors
    assert [row["category"] for row in rows] == ["Pension", "Other Income"]
