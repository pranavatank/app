"""
tests/test_tax_baseline.py — Tax engine regression tests (no fixtures).

These tests do NOT skip when document fixtures are missing; they validate
the tax calculation engine against known ground-truth values.

Ground truth from spec:
  - calculate_tax_by_slabs(1_500_000, NEW_REGIME_SLABS) == 105000.0 (baseline 150000.0)
  - calculate_new_regime_tax(1_275_000)["total_tax"] == 0.0 (baseline 93600.0)
    Note: 12,75,000 is the headline tax-free salary figure for the regime.
"""

import pytest
from engines.tax_engine import calculate_tax_by_slabs, NEW_REGIME_SLABS, calculate_new_regime_tax


class TestTaxEngine:
    """Tax engine regression tests."""

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 150000.0 vs true 105000.0 — fixed by T027-T029"
    )
    def test_calculate_tax_by_slabs_new_regime(self):
        """Tax calculation on 1.5M under NEW_REGIME_SLABS should be 105000."""
        result = calculate_tax_by_slabs(1_500_000, NEW_REGIME_SLABS)
        assert result == 105000.0

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 93600.0 vs true 0.0 — fixed by T027-T029; 12,75,000 is tax-free threshold"
    )
    def test_calculate_new_regime_tax_threshold(self):
        """Tax on 1,275,000 (tax-free threshold) should be 0.0 under new regime."""
        result = calculate_new_regime_tax(1_275_000)
        assert result["total_tax"] == 0.0
