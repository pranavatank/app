"""
tests/test_money_label.py — Unit tests for MoneyLabel widget and format_inr function.

Tests:
- Indian digit grouping formatting
- Positive/negative amounts
- Decimal values
- Edge cases
"""

import pytest
from ui.widgets.money_label import format_inr, MoneyLabel


class TestFormatInr:
    """Test cases for the format_inr function."""

    def test_simple_thousands(self):
        """Test basic thousands formatting."""
        assert format_inr(1000) == "₹1,000"
        assert format_inr(10000) == "₹10,000"

    def test_indian_grouping_basic(self):
        """Test Indian grouping: last 3 digits, then pairs."""
        assert format_inr(256642) == "₹2,56,642"
        assert format_inr(1234567) == "₹12,34,567"

    def test_indian_grouping_crores(self):
        """Test formatting for crore-scale numbers."""
        assert format_inr(10000000) == "₹1,00,00,000"
        assert format_inr(123456789) == "₹12,34,56,789"

    def test_less_than_thousand(self):
        """Test numbers less than 1000."""
        assert format_inr(100) == "₹100"
        assert format_inr(1) == "₹1"
        assert format_inr(999) == "₹999"

    def test_exact_thousand(self):
        """Test exact thousands."""
        assert format_inr(1000) == "₹1,000"
        assert format_inr(100000) == "₹1,00,000"

    def test_negative_amounts(self):
        """Test negative amount formatting."""
        assert format_inr(-1000) == "₹-1,000"
        assert format_inr(-256642) == "₹-2,56,642"
        assert format_inr(-1234567) == "₹-12,34,567"

    def test_zero(self):
        """Test zero value."""
        assert format_inr(0) == "₹0"

    def test_decimal_values(self):
        """Test amounts with decimal places."""
        assert format_inr(1000.50) == "₹1,000.50"
        assert format_inr(256642.75) == "₹2,56,642.75"
        assert format_inr(1234567.99) == "₹12,34,567.99"

    def test_decimal_with_negative(self):
        """Test negative amounts with decimals."""
        assert format_inr(-1000.50) == "₹-1,000.50"
        assert format_inr(-256642.25) == "₹-2,56,642.25"

    def test_lakhs(self):
        """Test lakh-scale formatting."""
        assert format_inr(100000) == "₹1,00,000"  # 1 lakh
        assert format_inr(1256000) == "₹12,56,000"  # 12.56 lakhs


class TestMoneyLabelWidget:
    """Test cases for the MoneyLabel widget."""

    def test_initialization_default(self):
        """Test MoneyLabel initialization with default amount."""
        label = MoneyLabel()
        assert label.amount == 0
        assert label.text() == "₹0"

    def test_initialization_with_amount(self):
        """Test MoneyLabel initialization with a specific amount."""
        label = MoneyLabel(256642)
        assert label.amount == 256642
        assert label.text() == "₹2,56,642"

    def test_set_amount(self):
        """Test set_amount method."""
        label = MoneyLabel()
        label.set_amount(1234567)
        assert label.amount == 1234567
        assert label.text() == "₹12,34,567"

    def test_set_amount_negative(self):
        """Test set_amount with negative value."""
        label = MoneyLabel()
        label.set_amount(-50000)
        assert label.text() == "₹-50,000"

    def test_set_masked(self):
        """Test set_masked method."""
        label = MoneyLabel(1000000)
        label.set_masked(True)
        assert label.text() == "₹ ****"

        label.set_masked(False)
        assert label.text() == "₹10,00,000"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
