"""
tests/test_interest_baseline.py — Interest engine regression tests (no fixtures).

These tests do NOT skip when document fixtures are missing; they validate
the FD maturity calculation engine against known ground-truth values.

Test case: FD with principal 100,000, rate 8%, start 2025-04-01, Quarterly compounding, 201 days.

Ground truth from spec:
  - Bank-style and formula maturity must DIFFER (currently both return 104458.54, inert).
  - Formula interest (owner's spreadsheet): 4455 within +/-1
  - Bank-style interest: 4496 within +/-1

Baseline from spec:
  - Both methods return 104458.54 (identical, proving bank-style is inert)
  - This should be fixed by T023-T024
"""

from datetime import date, timedelta
import pytest
from engines.interest_engine import calculate_fd_maturity_flexible, calculate_fd_maturity_bank_style


class TestInterestEngine:
    """FD maturity calculation regression tests."""

    @pytest.mark.xfail(
        strict=True,
        reason="baseline: both return 104458.54 (inert) vs true: should differ — fixed by T023-T024"
    )
    def test_fd_201_days_flexible_vs_bank_style_differ(self):
        """Bank-style and formula maturity must DIFFER for a 201-day FD.

        Currently both return 104458.54, proving the bank-style branch is inert.
        When fixed, they should produce different results.
        """
        principal = 100000.0
        rate = 8.0
        start_date = date(2025, 4, 1)
        maturity_date = start_date + timedelta(days=201)
        compounding = "Quarterly"

        flexible = calculate_fd_maturity_flexible(
            principal=principal,
            rate=rate,
            start_date=start_date,
            maturity_date=maturity_date,
            compounding=compounding,
            tenure_years=0,
            tenure_months=0,
            tenure_days=201,
        )

        bank_style = calculate_fd_maturity_bank_style(
            principal=principal,
            rate=rate,
            start_date=start_date,
            maturity_date=maturity_date,
            compounding=compounding,
            tenure_years=0,
            tenure_months=0,
            tenure_days=201,
        )

        # Currently both are equal; when fixed, they must differ
        assert (
            bank_style != flexible
        ), f"Bank-style ({bank_style}) and flexible ({flexible}) are identical; bank-style branch is inert"

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 104458.54 (interest 4458.54) vs true 104455.0 (interest 4455) — fixed by T023-T024"
    )
    def test_fd_201_days_formula_interest(self):
        """Formula interest for 201-day FD should be 4455 (owner's spreadsheet value)."""
        principal = 100000.0
        rate = 8.0
        start_date = date(2025, 4, 1)
        maturity_date = start_date + timedelta(days=201)
        compounding = "Quarterly"

        maturity = calculate_fd_maturity_flexible(
            principal=principal,
            rate=rate,
            start_date=start_date,
            maturity_date=maturity_date,
            compounding=compounding,
            tenure_years=0,
            tenure_months=0,
            tenure_days=201,
        )

        interest = maturity - principal
        # Owner's spreadsheet: 4455 within +/-1
        assert abs(interest - 4455) <= 1, f"Formula interest {interest} != 4455 within +/-1"

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 104458.54 (interest 4458.54) vs true 104496.0 (interest 4496) — fixed by T023-T024"
    )
    def test_fd_201_days_bank_style_interest(self):
        """Bank-style interest for 201-day FD should be 4496."""
        principal = 100000.0
        rate = 8.0
        start_date = date(2025, 4, 1)
        maturity_date = start_date + timedelta(days=201)
        compounding = "Quarterly"

        maturity = calculate_fd_maturity_bank_style(
            principal=principal,
            rate=rate,
            start_date=start_date,
            maturity_date=maturity_date,
            compounding=compounding,
            tenure_years=0,
            tenure_months=0,
            tenure_days=201,
        )

        interest = maturity - principal
        # Bank-style: 4496 within +/-1
        assert abs(interest - 4496) <= 1, f"Bank-style interest {interest} != 4496 within +/-1"
