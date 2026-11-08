"""Focused pure checks for fresh-rebuild source validation helpers."""
import pytest

from tools.real_ui_tests.rebuild_preflight import (
    assessment_year_fields, matching_document_year_fields,
    normalize_assessment_year, require_master_credential, validate_person_seed, validate_statement_rows,
)


def test_assessment_year_accepts_two_digit_and_full_year_headers():
    assert assessment_year_fields("Assessment Year: 2026-27") == {
        "assessment_year": "2026-27",
        "financial_year": "2025-26",
    }
    assert assessment_year_fields("FINANCIAL YEAR 2025-2026") == {
        "financial_year": "2025-26",
        "assessment_year": "2026-27",
    }


@pytest.mark.parametrize(
    "text",
    ["year 2026-27", "Assessment Year 2026-2028", "Financial Year 2025-20260"],
)
def test_assessment_year_rejects_unlabeled_or_invalid_spans(text):
    with pytest.raises(ValueError):
        assessment_year_fields(text)


def test_statement_validator_infers_opening_balance_from_first_row():
    rows = [
        {
            "transaction_date": "2025-04-01",
            "transaction_type": "Income",
            "amount": 150,
            "balance_after": 1150,
            "category": "Other Income",
            "description": "credit",
        },
        {
            "transaction_date": "2025-04-02",
            "transaction_type": "Expense",
            "amount": 50,
            "balance_after": 1100,
            "category": "Food",
            "description": "debit",
        },
    ]
    assert validate_statement_rows(rows) == 1000


@pytest.mark.parametrize("rows", [[], [{"transaction_type": "Expense", "amount": 1}]])
def test_statement_validator_rejects_empty_or_incomplete_rows(rows):
    with pytest.raises(ValueError):
        validate_statement_rows(rows)


def test_statement_validator_rejects_a_statement_without_closing_balance():
    row = {
        "transaction_date": "2025-04-01",
        "transaction_type": "Expense",
        "amount": 50,
        "balance_after": None,
        "category": "Food",
        "description": "debit",
    }
    with pytest.raises(ValueError, match="balance"):
        validate_statement_rows([row])


def statement_rows():
    return [
        dict(transaction_date=f"2025-04-{day:02d}", transaction_type="Expense",
             amount=10, balance_after=100 - day * 10, category="Food", description="debit")
        for day in range(1, 4)
    ]


@pytest.mark.parametrize("field,value,error", [
    ("amount", float("nan"), "finite"),
    ("amount", float("inf"), "finite"),
    ("amount", float("-inf"), "finite"),
    ("amount", -1, "negative"),
    ("balance_after", float("nan"), "finite"),
    ("balance_after", float("inf"), "finite"),
    ("balance_after", float("-inf"), "finite"),
    ("balance_after", 81, "running balance"),
    ("transaction_date", "2025-02-30", "ISO date"),
    ("transaction_date", "20250402", "ISO date"),
    ("transaction_date", "02/04/2025", "ISO date"),
    ("transaction_date", None, "ISO date"),
    ("transaction_date", "2025-03-31", "chronological"),
])
def test_statement_validator_rejects_invalid_middle_rows(field, value, error):
    rows = statement_rows()
    rows[1][field] = value
    with pytest.raises(ValueError, match=error):
        validate_statement_rows(rows)


def test_statement_validator_accepts_same_day_and_one_paisa_rounding():
    rows = statement_rows()
    rows[1]["transaction_date"] = rows[0]["transaction_date"]
    rows[1]["balance_after"] = 80.01
    assert validate_statement_rows(rows) == 100


def test_statement_validator_rejects_balance_error_over_one_paisa():
    rows = statement_rows()
    rows[1]["balance_after"] = 80.011
    with pytest.raises(ValueError, match="running balance"):
        validate_statement_rows(rows)


def test_internal_blank_balance_is_derived_only_between_reconciling_anchors():
    rows = statement_rows()
    rows[1]["balance_after"] = None
    audit = {}
    assert validate_statement_rows(rows, audit) == 100
    assert rows[1]["balance_after"] is None
    assert audit == {
        "reported_balance_count": 2,
        "derived_internal_balances": [{
            "index": 1, "transaction_date": "2025-04-02",
            "derived_balance_after": 80,
            "previous_reported_index": 0, "next_reported_index": 2,
        }],
    }
    rows[2]["balance_after"] = 69
    with pytest.raises(ValueError, match="running balance"):
        validate_statement_rows(rows)


@pytest.mark.parametrize("index", [0, 2])
def test_missing_boundary_balance_cannot_be_derived(index):
    rows = statement_rows()
    rows[index]["balance_after"] = None
    with pytest.raises(ValueError, match="boundary balance"):
        validate_statement_rows(rows)


def test_consecutive_blank_balances_need_a_later_reported_anchor():
    rows = statement_rows()
    rows.append(dict(rows[-1], transaction_date="2025-04-04", balance_after=60))
    rows[1]["balance_after"] = rows[2]["balance_after"] = None
    audit = {}
    assert validate_statement_rows(rows, audit) == 100
    assert [r["derived_balance_after"] for r in audit["derived_internal_balances"]] == [80, 70]
    assert all(r["next_reported_index"] == 3 for r in audit["derived_internal_balances"])


def test_person_seed_retains_legal_name_with_confirmed_first_name():
    validate_person_seed(" PRANAV Example Surname ", "ABCDE1234F")
    validate_person_seed("Pranav", "ABCDE1234F")


@pytest.mark.parametrize("name,pan", [
    ("", "ABCDE1234F"), (None, "ABCDE1234F"),
    ("Pranavi Example", "ABCDE1234F"), ("Other Pranav", "ABCDE1234F"),
    ("Pranav", ""), ("Pranav", "ABCDE1234F\n"),
])
def test_person_seed_rejects_other_identity_or_invalid_pan(name, pan):
    with pytest.raises(ValueError):
        validate_person_seed(name, pan)


@pytest.mark.parametrize("value", ["2026-27", "2026-2027", " 2026 / 27 ", "2026–27"])
def test_parsed_26as_year_normalizes_and_matches_source_fy_headers(value):
    parsed_year = normalize_assessment_year(value)
    assert parsed_year == "2026-27"
    assert matching_document_year_fields("Financial Year: 2025-26", parsed_year) == {
        "assessment_year": "2026-27", "financial_year": "2025-26",
    }


@pytest.mark.parametrize("value", [None, "", "2026-28", "2026-20260", "year 2026-27"])
def test_parsed_26as_year_rejects_missing_or_invalid_years(value):
    with pytest.raises(ValueError):
        normalize_assessment_year(value)


def test_source_year_mismatch_fails_readiness():
    with pytest.raises(ValueError, match="does not agree"):
        matching_document_year_fields("Financial Year 2024-25", "2026-27")


def test_missing_26as_year_cannot_match_a_valid_source_header():
    with pytest.raises(ValueError):
        matching_document_year_fields("Financial Year 2025-26", None)


def test_master_credential_is_required_without_exposing_a_value():
    require_master_credential(True)
    with pytest.raises(ValueError, match="master credential is unavailable"):
        require_master_credential(False)
