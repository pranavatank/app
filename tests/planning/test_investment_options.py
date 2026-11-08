"""
tests/test_investment_options.py — Tests for government-backed investment option projections
"""

from datetime import date

import pytest

from engines.interest_engine import calculate_fd_maturity
from engines.investment_options import (
    INVESTMENT_OPTIONS,
    best_overflow_option,
    eligible_options,
    format_lock_in,
    project_option,
    schemes_outdated,
)


def _option_named(name: str) -> dict:
    return next(option for option in INVESTMENT_OPTIONS if option["name"] == name)


POTD_1Y = _option_named("Post Office Time Deposit – 1 year")
POTD_3Y = _option_named("Post Office Time Deposit – 3 years")
NSC = _option_named("National Savings Certificate (NSC)")
KVP = _option_named("Kisan Vikas Patra (KVP)")
SCSS = _option_named("Senior Citizens Savings Scheme (SCSS)")


def test_investment_options_have_expected_keys():
    expected_keys = {"name", "rate", "tenure_months", "compounding", "payout",
                     "max_amount", "eligibility", "tax", "notes", "source_url"}

    assert len(INVESTMENT_OPTIONS) == 11
    for option in INVESTMENT_OPTIONS:
        assert set(option) == expected_keys


@pytest.mark.parametrize("tenure_months, expected", [
    (12, "1 year"),
    (24, "2 years"),
    (115, "9 years 7 months"),
    (7, "7 months"),
    (13, "1 year 1 month"),
])
def test_format_lock_in(tenure_months, expected):
    assert format_lock_in(tenure_months) == expected


def test_kvp_roughly_doubles_money():
    maturity_value = project_option(KVP, 100000)["maturity_value"]

    assert abs(maturity_value - 200000) <= 500


def test_payout_option_caps_amount_and_pays_simple_interest():
    result = project_option(SCSS, 4000000)

    assert result["invested"] == 3000000
    assert result["capped"] is True
    assert result["interest"] == round(3000000 * 8.2 / 100 * 5, 2)


def test_nsc_maturity_matches_annual_compounding():
    result = project_option(NSC, 100000)

    assert result["maturity_value"] == calculate_fd_maturity(100000, 7.7, 60, "Annual")


def test_eligible_options_hides_senior_only_schemes_for_non_seniors():
    assert SCSS not in eligible_options(False)
    assert SCSS in eligible_options(True)


@pytest.mark.parametrize("tenure_months, is_senior, amount, expected", [
    (12, False, 500000, POTD_1Y),
    (36, False, 500000, POTD_3Y),
    (60, False, 500000, NSC),
    (60, True, 500000, SCSS),
    (60, True, 5000000, NSC),
    (6, False, 1, None),
])
def test_best_overflow_option(tenure_months, is_senior, amount, expected):
    assert best_overflow_option(tenure_months, is_senior, amount) == expected


def test_schemes_outdated_after_valid_until():
    assert schemes_outdated(date(2026, 10, 12)) is False
    assert schemes_outdated(date(2027, 1, 1)) is True
