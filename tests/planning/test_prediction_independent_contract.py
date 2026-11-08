"""Independent hand-ledger acceptance for the prediction orchestration."""
from datetime import date

import pytest

from core.database import get_connection
from engines.prediction_engine import (
    _deposit_accounts_match,
    _matched_realised_fd_interest,
    _project_fd_interest_data,
    compare_our_data_to_itr,
    get_prediction_summary,
    project_fy_income,
)
from models.bank_account import add_account
from models.person import add_person
from models.transaction import add_transaction
from engines.fd_allocation_engine import normalize_bank_key


FY = "2025-26"
FY_START = date(2025, 4, 1)
FY_END = date(2026, 3, 31)
# Hand calculation from the documented full-year FD accrual branch:
# int(100,000 * ((1 + 8/400)^4 - 1)) = 8,243.
FD_FY_INTEREST = 8_243
OTHER_BANK_FD_FY_INTEREST = 2_030


@pytest.fixture
def independent_ledger():
    person_id = add_person("Synthetic prediction acceptance", first_name="Synthetic")
    account_id = add_account(person_id, "Synthetic Bank", "Savings", interest_rate=0.0)
    other_bank_account_id = add_account(person_id, "Other Synthetic Bank", "Savings", interest_rate=0.0)

    transactions = [
        ("2025-04-01", 10_000, "Salary", None),
        ("2025-09-30", 2_000, "Professional Fees", None),
        # This credit matches the tracked FD after normalization and is already
        # represented by that FD's full-year interest estimate.
        ("2025-09-30", 2_000, "FD Interest", "765432109876"),
        # This credit has no tracked FD association and must remain additive.
        ("2025-09-30", 3_000, "FD Interest", "OTHER-FD-99"),
        ("2026-03-31", 100, "Savings Interest", None),
        # Principal is not taxable interest or salary.
        ("2026-03-31", 100_000, "FD Maturity", None),
        ("2025-05-01", 50_000, "Other Income", None),
        ("2026-04-01", 8_000, "Salary", None),
    ]
    for txn_date, amount, category, deposit_account_no in transactions:
        add_transaction(
            account_id, person_id, txn_date, "Income", amount,
            category=category, deposit_account_no=deposit_account_no,
        )

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE Transactions SET is_internal_transfer = 1 "
            "WHERE person_id = ? AND category = 'Other Income'",
            (person_id,),
        )
        conn.execute(
            """INSERT INTO FixedDeposit
               (account_id, person_id, principal_amount, start_date, interest_rate,
                compounding_type, maturity_date, deposit_account_no, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')""",
            (account_id, person_id, 100_000, "2025-04-01", 8.0, "Quarterly", "2026-03-31", "FD765432109876"),
        )
        # Same deposit-number token at another bank must remain a separate FD.
        conn.execute(
            """INSERT INTO FixedDeposit
               (account_id, person_id, principal_amount, start_date, interest_rate,
                compounding_type, maturity_date, deposit_account_no, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')""",
            (other_bank_account_id, person_id, 50_000, "2025-04-01", 4.0, "Quarterly", "2026-03-31", "765432109876"),
        )
        conn.commit()
    finally:
        conn.close()

    yield person_id

    conn = get_connection()
    try:
        conn.execute("DELETE FROM FixedDeposit WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM Transactions WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM AccountHolder WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM BankAccount WHERE person_id = ?", (person_id,))
        conn.execute("DELETE FROM Person WHERE person_id = ?", (person_id,))
        conn.commit()
    finally:
        conn.close()


def test_projection_as_of_and_summary_match_independent_ledger(independent_ledger):
    person_id = independent_ledger

    at_start = project_fy_income(person_id, FY, FY_START)
    start_summary = get_prediction_summary(person_id, FY, FY_START)
    assert at_start["projected_total"] == 10_000 + FD_FY_INTEREST + OTHER_BANK_FD_FY_INTEREST
    assert start_summary["realised_income"]["taxable"] == 10_000
    assert start_summary["realised_income"]["non_taxable"] == 0
    assert start_summary["fy_income"]["projected_total"] == 10_000 + FD_FY_INTEREST + OTHER_BANK_FD_FY_INTEREST
    assert start_summary["timeline"]["months"][-1]["cumulative_projected"] == start_summary["fy_income"]["projected_total"]

    at_end = project_fy_income(person_id, FY, FY_END)
    end_summary = get_prediction_summary(person_id, FY, FY_END)
    assert end_summary["realised_income"]["taxable"] == 10_000 + 2_000 + 2_000 + 3_000 + 100
    assert end_summary["realised_income"]["non_taxable"] == 100_000 + 50_000
    assert at_end["projected_total"] == (
        10_000 + 2_000 + 100 + FD_FY_INTEREST + OTHER_BANK_FD_FY_INTEREST + 3_000
    )
    assert end_summary["fy_income"]["projected_total"] == at_end["projected_total"]
    timeline_sum = sum(month["monthly_projected"] for month in end_summary["timeline"]["months"])
    assert abs(timeline_sum - at_end["projected_total"]) <= 0.06
    assert end_summary["timeline"]["months"][-1]["cumulative_projected"] == at_end["projected_total"]


def test_itr_comparison_exposes_interest_without_counting_fd_principal(independent_ledger):
    person_id = independent_ledger
    comparison = compare_our_data_to_itr(person_id, FY, FY_END)
    rows = {row["label"]: row for row in comparison["rows"]}

    assert comparison["has_itr_data"] is False
    assert rows["FD Interest"]["our_value"] == FD_FY_INTEREST + OTHER_BANK_FD_FY_INTEREST + 3_000
    assert rows["Savings Interest"]["our_value"] == 100
    assert rows["Total Interest"]["our_value"] == FD_FY_INTEREST + OTHER_BANK_FD_FY_INTEREST + 3_000 + 100
    assert rows["Total Interest"]["our_value"] < 100_000


def test_deposit_account_normalization_and_bank_scoped_association(independent_ledger):
    person_id = independent_ledger
    assert _deposit_accounts_match("FD765432109876", "765432109876")
    assert not _deposit_accounts_match("FD765432109876", "300014105383")

    _, projected_accounts = _project_fd_interest_data(person_id, FY, FY_END)
    matched = _matched_realised_fd_interest(person_id, FY, FY_END, projected_accounts)
    assert len(projected_accounts) == 2
    assert len(matched) == 1
    (matched_bank, _), matched_amount = next(iter(matched.items()))
    assert matched_bank == normalize_bank_key("Synthetic Bank")
    assert matched_amount == 2_000
