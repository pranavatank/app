"""
Tests for FD categorisation pattern matching.
Verifies that longer, more specific patterns always take precedence over shorter substrings.
"""

from engines.parser_utils import _guess_fd_category


class TestFDCategorisation:
    """Test FD category detection with longest-pattern-first matching."""

    def test_int_auto_redeem_income_is_fd_interest_not_maturity(self):
        """INT AUTO REDEEM should be FD Interest, not FD Maturity (AUTO REDEEM)."""
        result = _guess_fd_category("INT AUTO REDEEM", "Income")
        assert result == "FD Interest", f"Expected 'FD Interest', got {result}"

    def test_princ_and_int_auto_redeem_income_is_fd_maturity(self):
        """PRINC AND INT AUTO REDEEM should be FD Maturity (most specific)."""
        result = _guess_fd_category("PRINC AND INT AUTO REDEEM", "Income")
        assert result == "FD Maturity", f"Expected 'FD Maturity', got {result}"

    def test_auto_redeem_income_is_fd_maturity(self):
        """AUTO REDEEM alone should be FD Maturity."""
        result = _guess_fd_category("AUTO REDEEM", "Income")
        assert result == "FD Maturity", f"Expected 'FD Maturity', got {result}"

    def test_closure_proceeds_income_is_fd_maturity(self):
        """CLOSURE PROCEEDS (Ujjivan) should be FD Maturity."""
        result = _guess_fd_category("CLOSURE PROCEEDS", "Income")
        assert result == "FD Maturity", f"Expected 'FD Maturity', got {result}"

    def test_initial_payin_expense_is_fd_principal(self):
        """INITIAL PAYIN (Equitas) should be FD Principal."""
        result = _guess_fd_category("INITIAL PAYIN", "Expense")
        assert result == "FD Principal", f"Expected 'FD Principal', got {result}"

    def test_credit_interest_capitalised_british_spelling(self):
        """CREDIT INTEREST CAPITALISED (British spelling) should be Savings Interest."""
        result = _guess_fd_category("CREDIT INTEREST CAPITALISED", "Income")
        assert result == "Savings Interest", f"Expected 'Savings Interest', got {result}"

    def test_credit_interest_capitalized_american_spelling(self):
        """CREDIT INTEREST CAPITALIZED (American spelling) should be Savings Interest."""
        result = _guess_fd_category("CREDIT INTEREST CAPITALIZED", "Income")
        assert result == "Savings Interest", f"Expected 'Savings Interest', got {result}"

    def test_sms_alerts_charges_expense_is_bank_charges(self):
        """SMS ALERTS CHARGES should be Bank Charges."""
        result = _guess_fd_category("SMS ALERTS CHARGES", "Expense")
        assert result == "Bank Charges", f"Expected 'Bank Charges', got {result}"

    def test_goods_and_services_tax_expense_is_bank_charges(self):
        """GOODS AND SERVICES TAX should be Bank Charges."""
        result = _guess_fd_category("GOODS AND SERVICES TAX", "Expense")
        assert result == "Bank Charges", f"Expected 'Bank Charges', got {result}"

    def test_unrelated_narration_returns_none(self):
        """Unrelated narrations like UPI PAYMENT TO MERCHANT should return None."""
        result = _guess_fd_category("UPI PAYMENT TO MERCHANT", "Expense")
        assert result is None, f"Expected None, got {result}"

    def test_fd_booking_expense(self):
        """FD BOOKING should be FD Principal."""
        result = _guess_fd_category("FD BOOKING", "Expense")
        assert result == "FD Principal", f"Expected 'FD Principal', got {result}"

    def test_amb_charges_expense(self):
        """AMB CHARGES should be Bank Charges."""
        result = _guess_fd_category("AMB CHARGES", "Expense")
        assert result == "Bank Charges", f"Expected 'Bank Charges', got {result}"

    def test_fd_interest_income(self):
        """FD INTEREST should be FD Interest."""
        result = _guess_fd_category("FD INTEREST", "Income")
        assert result == "FD Interest", f"Expected 'FD Interest', got {result}"

    def test_casa_credit_interest_savings_interest(self):
        """CASA CREDIT INTEREST should be Savings Interest."""
        result = _guess_fd_category("CASA CREDIT INTEREST", "Income")
        assert result == "Savings Interest", f"Expected 'Savings Interest', got {result}"

    def test_interest_on_deposit_fd_interest(self):
        """INTEREST ON DEPOSIT should be FD Interest."""
        result = _guess_fd_category("INTEREST ON DEPOSIT", "Income")
        assert result == "FD Interest", f"Expected 'FD Interest', got {result}"

    def test_generic_interest_with_fd_keyword(self):
        """Generic INTEREST with FD keyword should be FD Interest."""
        result = _guess_fd_category("INTEREST FD ACCT", "Income")
        assert result == "FD Interest", f"Expected 'FD Interest', got {result}"

    def test_maturity_keyword(self):
        """MATURITY keyword should be FD Maturity."""
        result = _guess_fd_category("FD MATURITY", "Income")
        assert result == "FD Maturity", f"Expected 'FD Maturity', got {result}"

    def test_fd_cr_is_fd_maturity(self):
        """FD CR should be FD Maturity."""
        result = _guess_fd_category("FD CR", "Income")
        assert result == "FD Maturity", f"Expected 'FD Maturity', got {result}"
