import math

import pytest

from engines.fd_allocation_engine import (
    COVERAGE_NEAR,
    COVERAGE_OK,
    COVERAGE_OVER,
    SMALL_FINANCE_BANK,
    get_coverage_report,
    get_savings_total,
    max_principal_within_limit,
    normalize_bank_key,
    suggest_fd_allocation,
    suggest_household_allocation,
)
from engines.interest_engine import calculate_fd_maturity


def _bank(name, r1, r3, r5, senior=0.5, bank_type="Bank"):
    rates = [rate for rate in (r1, r3, r5) if rate is not None]
    return {
        "bank_name": name,
        "bank_type": bank_type,
        "highest_rate": max(rates),
        "rate_1y": r1,
        "rate_3y": r3,
        "rate_5y": r5,
        "senior_extra": senior,
    }


def _floored_cap(headroom, rate):
    return math.floor(max_principal_within_limit(headroom, rate, 12) / 1000) * 1000


@pytest.mark.parametrize("bank_name, expected", [
    ("HDFC Bank Ltd", "hdfc"),
    ("State Bank of India", "state india"),
    ("SBI", "state india"),
    ("Bank of India", "india"),
    ("BOI", "india"),
    ("Ujjivan SFB", "ujjivan small finance"),
    ("UJJIVAN SMALL FINANCE BANK LIMITED", "ujjivan small finance"),
    ("Induslnd Bank", "indusind"),
    ("IndusInd Bank", "indusind"),
])
def test_normalize_bank_key(bank_name, expected):
    assert normalize_bank_key(bank_name) == expected


def test_max_principal_keeps_maturity_within_limit():
    principal = max_principal_within_limit(500000, 7.0, 12)
    assert principal < 500000
    assert calculate_fd_maturity(principal, 7.0, 12, "Quarterly") <= 500000.01


def test_max_principal_without_interest_counts_principal_only():
    assert max_principal_within_limit(500000, 7.0, 12, count_interest=False) == 500000.0


@pytest.mark.parametrize("headroom", [0, -5000])
def test_max_principal_is_zero_without_headroom(headroom):
    assert max_principal_within_limit(headroom, 7.0, 12) == 0.0


def test_allocation_fills_highest_rate_banks_first():
    banks = [_bank("A", 8.0, None, None), _bank("B", 7.5, None, None), _bank("C", 7.0, None, None)]

    result = suggest_fd_allocation(1_200_000, banks, "rate_1y")

    rows = result["rows"]
    assert [row["bank_name"] for row in rows] == ["A", "B", "C"]
    assert rows[0]["amount"] == _floored_cap(500000, 8.0)
    assert rows[1]["amount"] == _floored_cap(500000, 7.5)
    assert rows[2]["amount"] == round(1_200_000 - rows[0]["amount"] - rows[1]["amount"], 2)
    assert result["unallocated"] == 0
    assert all(row["fully_insured"] for row in rows)


def test_max_banks_limits_rows_and_leaves_remainder():
    banks = [_bank("A", 8.0, None, None), _bank("B", 7.5, None, None), _bank("C", 7.0, None, None)]

    result = suggest_fd_allocation(1_200_000, banks, "rate_1y", max_banks=1)

    assert len(result["rows"]) == 1
    assert result["unallocated"] > 0


def test_existing_exposure_reduces_bank_headroom():
    banks = [_bank("A Bank", 8.0, None, None), _bank("B Bank", 7.0, None, None)]
    exposure = {"a": {"total": 450000, "annual_fd_interest": 0}}

    result = suggest_fd_allocation(100_000, banks, "rate_1y", exposure=exposure, min_per_bank=10_000)

    rows = {row["bank_name"]: row for row in result["rows"]}
    assert rows["A Bank"]["amount"] == _floored_cap(50000, 8.0)
    assert rows["B Bank"]["amount"] == round(100_000 - _floored_cap(50000, 8.0), 2)


def test_bank_at_insurance_limit_is_skipped():
    banks = [_bank("A Bank", 8.0, None, None), _bank("B Bank", 7.0, None, None)]
    exposure = {"a": {"total": 495000, "annual_fd_interest": 0}}

    result = suggest_fd_allocation(100_000, banks, "rate_1y", exposure=exposure, min_per_bank=10_000)

    assert "A Bank" in result["skipped_full"]
    assert [row["bank_name"] for row in result["rows"]] == ["B Bank"]


def test_small_finance_banks_can_be_excluded():
    banks = [
        _bank("Ujjivan SFB", 9.0, None, None, bank_type=SMALL_FINANCE_BANK),
        _bank("HDFC", 7.0, None, None),
    ]

    result = suggest_fd_allocation(100_000, banks, "rate_1y", include_small_finance=False)

    assert [row["bank_name"] for row in result["rows"]] == ["HDFC"]


def test_senior_rate_adds_senior_extra():
    banks = [_bank("A", 7.0, None, None, senior=0.5)]

    result = suggest_fd_allocation(100_000, banks, "rate_1y", is_senior=True)

    assert result["rows"][0]["rate"] == 7.5


def test_excluded_banks_are_skipped_by_exact_name():
    banks = [_bank("A", 8.0, None, None), _bank("B", 7.0, None, None)]

    result = suggest_fd_allocation(100_000, banks, "rate_1y", excluded_banks=("A",))

    assert [row["bank_name"] for row in result["rows"]] == ["B"]


def test_tds_risk_when_new_fd_crosses_non_senior_threshold():
    banks = [_bank("A", 7.0, None, None)]
    exposure = {"a": {"total": 0, "annual_fd_interest": 45000}}

    result = suggest_fd_allocation(200_000, banks, "rate_1y", exposure=exposure)

    assert result["rows"][0]["tds_risk"] is True


def test_no_tds_risk_under_senior_threshold():
    banks = [_bank("A", 7.0, None, None)]
    exposure = {"a": {"total": 0, "annual_fd_interest": 45000}}

    result = suggest_fd_allocation(200_000, banks, "rate_1y", is_senior=True, exposure=exposure)

    assert result["rows"][0]["tds_risk"] is False


def test_banks_without_rate_for_tenure_are_skipped():
    banks = [_bank("A", None, 9.0, 9.0), _bank("B", 7.0, None, None)]

    result = suggest_fd_allocation(100_000, banks, "rate_1y")

    assert [row["bank_name"] for row in result["rows"]] == ["B"]


def test_zero_amount_allocates_nothing():
    result = suggest_fd_allocation(0, [_bank("A", 7.0, None, None)], "rate_1y")

    assert result["rows"] == []
    assert result["unallocated"] == 0


def test_single_depositor_rows_have_blank_person_name():
    result = suggest_fd_allocation(100_000, [_bank("A", 7.0, None, None)], "rate_1y")

    assert [row["person_name"] for row in result["rows"]] == [""]


def test_household_depositors_each_take_the_top_bank_within_max_banks():
    banks = [_bank("A", 8.0, None, None), _bank("B", 7.5, None, None)]
    depositors = [
        {"name": "Asha", "is_senior": False, "exposure": {}},
        {"name": "Ravi", "is_senior": False, "exposure": {}},
    ]

    result = suggest_household_allocation(1_500_000, banks, "rate_1y", depositors, max_banks=1)

    assert [(row["person_name"], row["bank_name"]) for row in result["rows"]] == [("Asha", "A"), ("Ravi", "A")]
    assert result["unallocated"] > 0


def test_household_senior_depositor_gets_senior_extra_only():
    banks = [_bank("A", 7.0, None, None, senior=0.5)]
    depositors = [
        {"name": "Senior", "is_senior": True, "exposure": {}},
        {"name": "Junior", "is_senior": False, "exposure": {}},
    ]

    result = suggest_household_allocation(1_000_000, banks, "rate_1y", depositors)

    assert {row["person_name"]: row["rate"] for row in result["rows"]} == {"Senior": 7.5, "Junior": 7.0}


def test_household_skipped_label_names_the_full_depositor():
    banks = [_bank("A Bank", 8.0, None, None), _bank("B Bank", 7.0, None, None)]
    depositors = [
        {"name": "Asha", "is_senior": False, "exposure": {"a": {"total": 495000, "annual_fd_interest": 0}}},
        {"name": "Ravi", "is_senior": False, "exposure": {}},
    ]

    result = suggest_household_allocation(100_000, banks, "rate_1y", depositors)

    assert result["skipped_full"] == ["A Bank (Asha)"]
    assert [row["person_name"] for row in result["rows"]] == ["Ravi"]


def test_get_savings_total_counts_joint_accounts_once(monkeypatch):
    accounts_by_person = {
        1: [
            {"account_id": 10, "account_type": "Savings", "current_balance": 200000},
            {"account_id": 11, "account_type": "FD-linked", "current_balance": 999},
        ],
        2: [
            {"account_id": 10, "account_type": "Savings", "current_balance": 200000},
            {"account_id": 12, "account_type": "Salary", "current_balance": 50000, "account_status": "Closed"},
            {"account_id": 13, "account_type": "Current", "current_balance": -500},
        ],
    }
    monkeypatch.setattr("engines.fd_allocation_engine.get_accounts_for_person",
                        lambda person_id: accounts_by_person[person_id])

    assert get_savings_total([1, 2]) == 200000.0


def test_coverage_report_flags_banks_by_limit_usage(monkeypatch):
    exposures = {
        1: {
            "hdfc": {"bank_name": "HDFC Bank", "savings_amount": 20000.0, "fd_amount": 500000.0, "total": 520000.0},
            "sbi": {"bank_name": "SBI", "savings_amount": 0.0, "fd_amount": 0.0, "total": 0.0},
        },
        2: {
            "icici": {"bank_name": "ICICI Bank", "savings_amount": 60000.0, "fd_amount": 400000.0, "total": 460000.0},
            "axis": {"bank_name": "Axis Bank", "savings_amount": 100000.0, "fd_amount": 0.0, "total": 100000.0},
        },
    }
    monkeypatch.setattr("engines.fd_allocation_engine.get_existing_exposure", lambda person_id: exposures[person_id])
    persons = [{"person_id": 1, "full_name": "Ravi"}, {"person_id": 2, "full_name": "Asha"}]

    rows = get_coverage_report(persons)

    assert [(row["person_name"], row["bank_name"], row["status"]) for row in rows] == [
        ("Asha", "ICICI Bank", COVERAGE_NEAR),
        ("Asha", "Axis Bank", COVERAGE_OK),
        ("Ravi", "HDFC Bank", COVERAGE_OVER),
    ]
    assert rows[2]["headroom"] == 0
    assert rows[2]["used_pct"] == 104.0
