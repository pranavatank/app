"""
tests/test_fd_redemption.py — Tests for FD redemption event handling
"""

import pytest
from datetime import date
from core.database import get_connection
from models.person import add_person
from models.bank_account import add_account
from models.transaction import add_transaction
from models.fixed_deposit import (
    add_fd_from_statement,
    apply_statement_redemption_event,
    get_fd,
    _extract_actual_fd_no,
)


class TestExtractActualFdNo:
    """Test _extract_actual_fd_no pattern matching."""

    def test_extract_fd_no_with_space_before_slash(self):
        """Test extraction from narration like '123456784414 /1'."""
        result = _extract_actual_fd_no("INT AUTO REDEEM NAME 123456784414 /1 - NAME", None)
        assert result == "123456784414"


class TestFdRedemptionDifferentNumber:
    """Test applying redemption event to FD with different reference number."""

    def test_different_fd_number_creates_new_matured_fd(self):
        """When redemption narration names a different FD number, create a new Matured FD."""
        pid = add_person("Test User", first_name="Test", last_name="User")
        aid = add_account(pid, "Equitas Small Finance Bank", "Savings")

        open_tx = add_transaction(
            account_id=aid,
            person_id=pid,
            transaction_date="2025-10-04",
            transaction_type="Debit",
            amount=100000.0,
            category="FD Opened",
            mode="Transfer",
            description="FD Opened",
            balance_after=None,
        )

        fd_open = add_fd_from_statement(
            account_id=aid,
            person_id=pid,
            principal_amount=100000.0,
            start_date="2025-10-04",
            fd_reference_no="123456785662",
            source_transaction_id=open_tx,
        )
        assert fd_open > 0

        opening_fd = get_fd(fd_open)
        assert opening_fd["status"] == "Pending Details"
        assert opening_fd["fd_reference_no"] == "123456785662"

        interest_tx = add_transaction(
            account_id=aid,
            person_id=pid,
            transaction_date="2025-12-15",
            transaction_type="Credit",
            amount=10775.0,
            category="FD Interest",
            mode="Transfer",
            description="INT AUTO REDEEM NAME 123456782394 /1 - NAME",
            balance_after=None,
        )

        apply_statement_redemption_event(
            account_id=aid,
            person_id=pid,
            transaction_id=interest_tx,
            transaction_date="2025-12-15",
            amount=10775.0,
            description="INT AUTO REDEEM NAME 123456782394 /1 - NAME",
            reference_no=None,
        )

        principal_tx = add_transaction(
            account_id=aid,
            person_id=pid,
            transaction_date="2025-12-15",
            transaction_type="Credit",
            amount=100000.0,
            category="FD Maturity",
            mode="Transfer",
            description="PRINC AND INT AUTO REDEEM NAME 123456782394 /1 - NAME",
            balance_after=None,
        )

        fd_id = apply_statement_redemption_event(
            account_id=aid,
            person_id=pid,
            transaction_id=principal_tx,
            transaction_date="2025-12-15",
            amount=100000.0,
            description="PRINC AND INT AUTO REDEEM NAME 123456782394 /1 - NAME",
            reference_no=None,
        )

        assert fd_id > 0

        opening_fd_after = get_fd(fd_open)
        assert opening_fd_after["status"] == "Pending Details"
        assert opening_fd_after["fd_reference_no"] == "123456785662"

        redeemed_fd = get_fd(fd_id)
        assert redeemed_fd["status"] == "Matured"
        assert redeemed_fd["fd_reference_no"] == "123456782394"
        assert redeemed_fd["principal_amount"] == 100000.0
        assert redeemed_fd["actual_interest_amount"] == 10775.0
        assert redeemed_fd["linked_transaction_id"] == principal_tx


class TestFdRedemptionSameNumber:
    """Test applying redemption event to FD with same reference number."""

    def test_same_fd_number_updates_existing_fd(self):
        """When redemption narration matches the FD number, update the existing FD."""
        pid = add_person("Test User", first_name="Test", last_name="User")
        aid = add_account(pid, "Equitas Small Finance Bank", "Savings")

        open_tx = add_transaction(
            account_id=aid,
            person_id=pid,
            transaction_date="2025-10-04",
            transaction_type="Debit",
            amount=100000.0,
            category="FD Opened",
            mode="Transfer",
            description="FD Opened",
            balance_after=None,
        )

        fd_open = add_fd_from_statement(
            account_id=aid,
            person_id=pid,
            principal_amount=100000.0,
            start_date="2025-10-04",
            fd_reference_no="123456787861",
            source_transaction_id=open_tx,
        )
        assert fd_open > 0

        opening_fd = get_fd(fd_open)
        assert opening_fd["status"] == "Pending Details"
        assert opening_fd["fd_reference_no"] == "123456787861"

        principal_tx = add_transaction(
            account_id=aid,
            person_id=pid,
            transaction_date="2025-12-15",
            transaction_type="Credit",
            amount=100000.0,
            category="FD Maturity",
            mode="Transfer",
            description="PRINC AND INT AUTO REDEEM NAME 123456787861 /1 - NAME",
            balance_after=None,
        )

        fd_id = apply_statement_redemption_event(
            account_id=aid,
            person_id=pid,
            transaction_id=principal_tx,
            transaction_date="2025-12-15",
            amount=100000.0,
            description="PRINC AND INT AUTO REDEEM NAME 123456787861 /1 - NAME",
            reference_no=None,
        )

        assert fd_id == fd_open

        redeemed_fd = get_fd(fd_id)
        assert redeemed_fd["status"] == "Matured"
        assert redeemed_fd["fd_reference_no"] == "123456787861"
        assert redeemed_fd["principal_amount"] == 100000.0
        assert redeemed_fd["linked_transaction_id"] == principal_tx


class TestFdRedemptionFallbackFiltering:
    """Test the principal fallback filtering when exact match fails."""

    def test_principal_redemption_different_number_creates_new_fd(self):
        """
        Test that a principal-only redemption with a DIFFERENT fd_no creates a new Matured FD
        when the fallback filter excludes numerically different FDs.

        Scenario:
        - Existing Pending Details FD with reference "999888777001" (12-digit placeholder, no start_date)
        - Redemption narration names "111222333001" (different 12-digit number)
        - Expected: creates a new Matured FD with ref "111222333001" (fallback filtered out the different-numbered FD)
        """
        pid = add_person("Fallback Test", first_name="Fallback", last_name="Test")
        aid = add_account(pid, "SBI", "Savings")

        # Create a Pending Details FD with a specific reference number (12+ digits)
        # Note: add_fd_from_statement creates "Pending Details" status FDs
        existing_fd = add_fd_from_statement(
            account_id=aid,
            person_id=pid,
            principal_amount=100000.0,
            start_date=None,  # No start_date, like a placeholder
            fd_reference_no="999888777001",
            source_transaction_id=None,
        )
        assert existing_fd > 0

        existing = get_fd(existing_fd)
        assert existing["status"] == "Pending Details"
        assert existing["fd_reference_no"] == "999888777001"

        # Create a redemption transaction with a DIFFERENT fd_no (12+ digits)
        principal_tx = add_transaction(
            account_id=aid,
            person_id=pid,
            transaction_date="2025-12-15",
            transaction_type="Credit",
            amount=100000.0,
            category="FD Maturity",
            mode="Transfer",
            description="PRINC AND INT AUTO REDEEM NAME 111222333001 /1 - NAME",
            balance_after=None,
        )

        # Apply redemption - should create a NEW FD because the number is different
        # The fallback filter at line 564 will exclude FDs with different numeric prefixes
        fd_id = apply_statement_redemption_event(
            account_id=aid,
            person_id=pid,
            transaction_id=principal_tx,
            transaction_date="2025-12-15",
            amount=100000.0,
            description="PRINC AND INT AUTO REDEEM NAME 111222333001 /1 - NAME",
            reference_no=None,
        )

        assert fd_id != existing_fd, "Should create a NEW FD when redemption number differs (fallback filters by number)"

        # Verify the original FD is unchanged
        original_after = get_fd(existing_fd)
        assert original_after["status"] == "Pending Details"
        assert original_after["fd_reference_no"] == "999888777001"

        # Verify the new FD is Matured with the redemption number
        new_fd = get_fd(fd_id)
        assert new_fd["status"] == "Matured"
        assert new_fd["fd_reference_no"] == "111222333001"
        assert new_fd["principal_amount"] == 100000.0

    def test_non_numeric_fd_reference_matched_by_fallback(self):
        """
        Test that a Jana-style non-numeric reference ('IB123…') Active FD
        is still matched by the principal fallback (regression guard).

        Scenario:
        - Active FD with non-numeric reference "IB1234567890"
        - Redemption with principal matching the FD's principal
        - Expected: the fallback correctly matches the FD by principal, not by number
        """
        pid = add_person("Jana Test", first_name="Jana", last_name="Test")
        aid = add_account(pid, "Jana Small Finance Bank", "Savings")

        # Create an Active FD with Jana-style non-numeric reference
        jana_fd = add_fd_from_statement(
            account_id=aid,
            person_id=pid,
            principal_amount=150000.0,
            start_date="2025-05-01",
            fd_reference_no="IB1234567890",
            source_transaction_id=None,
        )
        assert jana_fd > 0

        jana_existing = get_fd(jana_fd)
        assert jana_existing["status"] in ("Active", "Pending Details")
        assert jana_existing["fd_reference_no"] == "IB1234567890"

        # Create a redemption with numeric fd_no (different from the Jana ref)
        # but matching principal amount
        principal_tx = add_transaction(
            account_id=aid,
            person_id=pid,
            transaction_date="2025-12-20",
            transaction_type="Credit",
            amount=150000.0,
            category="FD Maturity",
            mode="Transfer",
            description="PRINC AND INT AUTO REDEEM NAME 987654321 /1 - NAME",
            balance_after=None,
        )

        # Apply redemption - the fallback should still match the Jana FD by principal
        fd_id = apply_statement_redemption_event(
            account_id=aid,
            person_id=pid,
            transaction_id=principal_tx,
            transaction_date="2025-12-20",
            amount=150000.0,
            description="PRINC AND INT AUTO REDEEM NAME 987654321 /1 - NAME",
            reference_no=None,
        )

        # Should match the existing Jana FD (not create a new one)
        assert fd_id == jana_fd, "Fallback should match Jana FD by principal"

        # Verify the Jana FD is now Matured and retains its non-numeric reference
        redeemed = get_fd(fd_id)
        assert redeemed["status"] == "Matured"
        assert redeemed["fd_reference_no"] == "IB1234567890", "Should keep Jana reference"
        assert redeemed["principal_amount"] == 150000.0
        assert redeemed["linked_transaction_id"] == principal_tx
