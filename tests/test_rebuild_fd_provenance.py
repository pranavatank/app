"""Synthetic checks of rebuild provenance against production FD semantics."""
import copy
import sqlite3

import pytest

from tools.real_ui_tests.rebuild_p2_8_fd_origin import validate_fd_provenance


@pytest.fixture
def validate():
    from ui.statement_import_screen_modern import _TransactionImportWorker
    from models.fixed_deposit import _extract_actual_fd_no

    def check(txns, fds):
        return validate_fd_provenance(
            txns, fds,
            lambda txn: _TransactionImportWorker._is_fd_opening_transaction(None, txn),
            _extract_actual_fd_no,
        )
    return check


def opening():
    txn = dict(transaction_id=1, account_id=1, person_id=1, transaction_type="Expense",
               category="FD Principal", description="INITIAL PAYIN FD", amount=100000,
               transaction_date="2025-04-01", reference_no=None)
    fd = dict(fd_id=1, account_id=1, person_id=1, source_transaction_id=1,
              principal_amount=100000, start_date="2025-04-01", status="Pending Details",
              linked_transaction_id=None, fd_reference_no=None, maturity_date=None,
              actual_interest_amount=None)
    return txn, fd


def redemption():
    txn = dict(transaction_id=2, account_id=1, person_id=1, transaction_type="Income",
               category="FD Principal", description="PRINC AND INT AUTO REDEEM 4522000012345678/1",
               amount=100000, transaction_date="2025-05-01", reference_no=None)
    fd = dict(fd_id=2, account_id=1, person_id=1, source_transaction_id=2,
              linked_transaction_id=2, principal_amount=100000, start_date=None,
              status="Matured", fd_reference_no="4522000012345678/1",
              maturity_date="2025-05-01", actual_interest_amount=None)
    return txn, fd


def test_openings_and_redemption_placeholders_are_distinct_valid_origins(validate):
    debit, dated = opening()
    credit, undated = redemption()
    assert validate([debit, credit], [dated, undated]) == (
        {"opening": 1, "redemption_only": 1}, [],
    )


@pytest.mark.parametrize("field,value", [
    ("source_transaction_id", None), ("source_transaction_id", 999),
    ("account_id", 2), ("person_id", 2), ("principal_amount", 99999),
    ("principal_amount", float("nan")), ("start_date", "2025-04-02"),
    ("start_date", None),
])
def test_invalid_opening_provenance_cannot_hide_as_redemption(validate, field, value):
    txn, fd = opening()
    fd[field] = value
    assert validate([txn], [fd])[1]


def test_missing_and_duplicate_opening_links_fail(validate):
    txn, fd = opening()
    assert any("missing opening" in error for error in validate([txn], [])[1])
    duplicate = dict(fd, fd_id=3)
    assert any("duplicate" in error for error in validate([txn], [fd, duplicate])[1])


def test_nonopening_debit_is_rejected_even_with_matching_date_amount(validate):
    txn, fd = opening()
    txn.update(category="Food", description="groceries")
    assert any("not an opening debit" in error for error in validate([txn], [fd])[1])


@pytest.mark.parametrize("field,value", [
    ("source_transaction_id", None), ("linked_transaction_id", None),
    ("linked_transaction_id", 999), ("status", "Pending Details"),
    ("account_id", 2), ("person_id", 2), ("principal_amount", 90000),
    ("actual_interest_amount", 10000), ("actual_interest_amount", float("inf")),
    ("fd_reference_no", "9999000012345678/1"), ("maturity_date", "2025-05-02"),
    ("start_date", "2025-05-01"),
])
def test_invalid_redemption_provenance_fails(validate, field, value):
    txn, fd = redemption()
    fd[field] = value
    assert validate([txn], [fd])[1]


@pytest.mark.parametrize("change", [
    {"transaction_type": "Expense"}, {"description": "salary"},
    {"amount": -100000}, {"amount": float("inf")},
])
def test_redemption_requires_real_finite_credit(validate, change):
    txn, fd = redemption()
    txn.update(change)
    assert validate([txn], [fd])[1]


@pytest.mark.parametrize("interest_first", [False, True])
def test_separate_interest_credit_and_principal_credit(validate, interest_first):
    principal_txn, fd = redemption()
    interest_txn = dict(principal_txn, transaction_id=3, amount=12000,
                        description="INT AUTO REDEEM 4522000012345678/1")
    fd["actual_interest_amount"] = 12000
    if interest_first:
        fd["source_transaction_id"] = 3
    assert validate([principal_txn, interest_txn], [fd])[1] == []


def test_interest_only_placeholder_has_no_invented_principal_or_date(validate):
    txn, fd = redemption()
    txn.update(amount=12000, description="INT AUTO REDEEM 4522000012345678/1")
    fd.update(principal_amount=0, actual_interest_amount=12000)
    assert validate([txn], [fd])[1] == []


def test_combined_redemption_excess_is_valid_interest(validate):
    source, fd = redemption()
    linked = dict(source, transaction_id=3, amount=112000, transaction_date="2025-05-02")
    fd.update(linked_transaction_id=3, actual_interest_amount=12000)
    assert validate([source, linked], [fd])[1] == []


def test_interest_evidence_cannot_come_from_another_account_or_reference(validate):
    txn, fd = redemption()
    fd["actual_interest_amount"] = 12000
    interest = dict(txn, transaction_id=3, amount=12000, account_id=2,
                    description="INT AUTO REDEEM 4522000012345678/1")
    assert validate([txn, interest], [fd])[1]
    interest.update(account_id=1, description="INT AUTO REDEEM 9999000012345678/1")
    assert validate([txn, interest], [fd])[1]


def test_separate_link_must_have_matching_owner_and_reference(validate):
    txn, fd = redemption()
    linked = dict(txn, transaction_id=3, account_id=2)
    fd["linked_transaction_id"] = 3
    assert validate([txn, linked], [fd])[1]
    linked.update(account_id=1, description="PRINC AND INT AUTO REDEEM 9999000012345678/1")
    assert validate([txn, linked], [fd])[1]


def test_production_creates_nine_valid_historical_placeholders_with_separate_interest(
    validate, tmp_path, monkeypatch,
):
    """Run the real redemption writer on synthetic data, using an isolated DB."""
    import models.fixed_deposit as model

    db_path = tmp_path / "redemptions.sqlite"
    def connect():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection
    monkeypatch.setattr(model, "get_connection", connect)
    conn = connect()
    conn.execute("CREATE TABLE Transactions (transaction_id INTEGER PRIMARY KEY, account_id, person_id, transaction_date, transaction_type, category, description, amount, reference_no)")
    conn.execute("""CREATE TABLE FixedDeposit (
        fd_id INTEGER PRIMARY KEY, account_id, person_id, principal_amount, start_date,
        fd_reference_no, tenure_years, tenure_months, tenure_days, interest_rate,
        compounding_type, maturity_date, maturity_amount, maturity_amount_formula,
        maturity_amount_bank, maturity_calc_method, expected_interest_amount,
        actual_interest_amount, linked_transaction_id, source_transaction_id,
        status, source_description)""")
    conn.commit()
    conn.close()
    # Both arrival orders occur in statements. Numbered historical FDs cannot
    # be merged into another numbered FD by the production nearest-amount logic.
    for index in range(9):
        ref = f"45220000123456{index:02d}/1"
        principal = 50000 if index == 0 else 100000
        interest = 1750 if index == 0 else 11230
        events = [(principal, "PRINC AND INT AUTO REDEEM"), (interest, "INT AUTO REDEEM")]
        if index % 2:
            events.reverse()
        for amount, narration in events:
            conn = connect()
            description = f"{narration} {ref}"
            cur = conn.execute("INSERT INTO Transactions (account_id, person_id, transaction_date, transaction_type, category, description, amount) VALUES (1, 1, '2025-05-01', 'Income', 'FD Principal', ?, ?)", (description, amount))
            transaction_id = cur.lastrowid
            conn.commit()
            conn.close()
            model.apply_statement_redemption_event(1, 1, transaction_id, "2025-05-01", amount, description)
    conn = connect()
    txns = [dict(row) for row in conn.execute("SELECT * FROM Transactions")]
    fds = [dict(row) for row in conn.execute("SELECT * FROM FixedDeposit")]
    conn.close()
    assert len(fds) == 9
    assert sum(fd["principal_amount"] for fd in fds) == 850000
    assert sum(fd["actual_interest_amount"] for fd in fds) == 91590
    assert all(fd["start_date"] is None and fd["status"] == "Matured" for fd in fds)
    assert validate(txns, fds) == ({"opening": 0, "redemption_only": 9}, [])
