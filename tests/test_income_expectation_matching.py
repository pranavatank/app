"""
tests/test_income_expectation_matching.py — Tests for income expectation matching (F202)
"""

import pytest
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from core.database import get_connection
from models.person import add_person
from models.bank_account import add_account
from models.income_expectation import (
    add_income_expectation,
    auto_link_income_expectations,
    get_income_expectations,
    link_actual_transaction,
    unlink_actual_transaction
)
from models.transaction import add_transaction
from config import get_current_financial_year, fy_date_range


class TestIncomeExpectationMatching:
    """Test automatic matching of income expectations with transactions."""

    def test_auto_link_income_expectations_basic_match(self):
        """Test basic matching of a salary expectation with a salary transaction."""
        # Setup: create person and account
        person_id = add_person("Alice", first_name="Alice", last_name="A")
        account_id = add_account(person_id, "HDFC Bank", "Savings")

        # Get current FY
        fy = get_current_financial_year()
        fy_start, fy_end = fy_date_range(fy)

        # Create a monthly salary expectation of ₹50,000 for the first month
        exp_date = fy_start.replace(day=15)  # 15th of FY start month
        add_income_expectation(
            person_id, account_id, "Salary", 50000.0,
            exp_date.strftime("%Y-%m-%d"), "One-Time", fy
        )

        # Create a matching transaction (same amount, same month)
        txn_date = fy_start.replace(day=14)  # 14th (close to expected 15th)
        txn_id = add_transaction(
            account_id, person_id, txn_date.strftime("%Y-%m-%d"), "Income", 50000.0, category="Salary"
        )

        # Run auto-match
        linked_count = auto_link_income_expectations(person_id, account_id, fy)

        # Verify: exactly 1 expectation was matched
        assert linked_count == 1, f"Expected 1 link, got {linked_count}"

        # Verify: expectation now has actual_transaction_id set
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        assert len(expectations) == 1
        exp = expectations[0]
        assert exp["actual_transaction_id"] == txn_id
        assert exp["actual_amount"] == 50000.0

    def test_auto_link_income_expectations_multiple_monthly(self):
        """Test matching of multiple monthly salary expectations with transactions."""
        # Setup: create person and account
        person_id = add_person("Bob", first_name="Bob", last_name="B")
        account_id = add_account(person_id, "SBI Bank", "Savings")

        fy = get_current_financial_year()
        fy_start, fy_end = fy_date_range(fy)

        # Create 4 monthly salary expectations
        salary_amount = 60000.0
        day_of_month = 15

        add_income_expectation(
            person_id, account_id, "Salary", salary_amount,
            day_of_month, "Monthly", fy
        )

        # This creates 12 monthly records. Create 4 matching transactions.
        txn_ids = []
        for month_offset in range(4):
            txn_date = (fy_start + relativedelta(months=month_offset)).replace(day=15)
            if txn_date <= fy_end:
                txn_id = add_transaction(
                    account_id, person_id, txn_date.strftime("%Y-%m-%d"), "Income", salary_amount, category="Salary"
                )
                txn_ids.append(txn_id)

        # Run auto-match
        linked_count = auto_link_income_expectations(person_id, account_id, fy)

        # Verify: 4 expectations were matched
        assert linked_count == 4, f"Expected 4 links, got {linked_count}"

        # Verify: expectations have actual_transaction_id set
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        matched = [e for e in expectations if e["actual_transaction_id"]]
        assert len(matched) == 4

    def test_auto_link_idempotent(self):
        """Test that calling auto_link twice does not create duplicate links."""
        # Setup
        person_id = add_person("Charlie", first_name="Charlie", last_name="C")
        account_id = add_account(person_id, "ICICI Bank", "Savings")

        fy = get_current_financial_year()
        fy_start, fy_end = fy_date_range(fy)

        # Create expectation and transaction
        exp_date = fy_start.replace(day=10)
        add_income_expectation(
            person_id, account_id, "Salary", 55000.0,
            exp_date.strftime("%Y-%m-%d"), "One-Time", fy
        )

        txn_date = fy_start.replace(day=10)
        add_transaction(
            account_id, person_id, txn_date.strftime("%Y-%m-%d"), "Income", 55000.0, category="Salary"
        )

        # First match
        linked_count_1 = auto_link_income_expectations(person_id, account_id, fy)
        assert linked_count_1 == 1

        # Second match (should be idempotent - no more links)
        linked_count_2 = auto_link_income_expectations(person_id, account_id, fy)
        assert linked_count_2 == 0, "Second match should return 0 (already linked)"

        # Verify: still exactly 1 link
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        matched = [e for e in expectations if e["actual_transaction_id"]]
        assert len(matched) == 1

    def test_auto_link_amount_within_50_percent(self):
        """Test matching prioritizes amounts within 50% of expected."""
        person_id = add_person("Diana", first_name="Diana", last_name="D")
        account_id = add_account(person_id, "Axis Bank", "Savings")

        fy = get_current_financial_year()
        fy_start, fy_end = fy_date_range(fy)

        exp_date = fy_start.replace(day=15)
        expected_amount = 50000.0

        # Create one expectation
        add_income_expectation(
            person_id, account_id, "Salary", expected_amount,
            exp_date.strftime("%Y-%m-%d"), "One-Time", fy
        )

        # Create two transactions in same month:
        # - One exact match: 50000
        # - One within 50%: 40000 (80% of expected)
        txn_date_1 = exp_date.replace(day=10)
        txn_id_1 = add_transaction(
            account_id, person_id, txn_date_1.strftime("%Y-%m-%d"), "Income", 40000.0, category="Salary"
        )

        txn_date_2 = exp_date.replace(day=15)
        txn_id_2 = add_transaction(
            account_id, person_id, txn_date_2.strftime("%Y-%m-%d"), "Income", 50000.0, category="Salary"
        )

        # Auto-match should pick the exact match (score = 0) over the close one
        linked_count = auto_link_income_expectations(person_id, account_id, fy)
        assert linked_count == 1

        # Verify the exact match was picked
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        exp = expectations[0]
        assert exp["actual_transaction_id"] == txn_id_2
        assert exp["actual_amount"] == 50000.0

    def test_received_to_date_reflects_matched_transactions(self):
        """Test that 'Received to Date' KPI reflects matched transactions."""
        person_id = add_person("Eve", first_name="Eve", last_name="E")
        account_id = add_account(person_id, "HDFC Bank", "Savings")

        fy = get_current_financial_year()
        fy_start, fy_end = fy_date_range(fy)

        # Create 3 monthly salary expectations
        salary_amount = 75000.0
        add_income_expectation(
            person_id, account_id, "Salary", salary_amount,
            15, "Monthly", fy
        )

        # Create 3 matching transactions
        for month_offset in range(3):
            txn_date = (fy_start + relativedelta(months=month_offset)).replace(day=15)
            if txn_date <= fy_end:
                add_transaction(
                    account_id, person_id, txn_date.strftime("%Y-%m-%d"), "Income", salary_amount, category="Salary"
                )

        # Run auto-match
        auto_link_income_expectations(person_id, account_id, fy)

        # Fetch expectations and compute "Received to Date"
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)

        # Calculate received (sum of actual amounts where actual_transaction_id is set)
        total_received = sum(
            e.get("actual_amount", 0) for e in expectations
            if e["actual_transaction_id"]
        )

        # Verify: should be 3 * 75000 = 225000
        expected_received = 3 * salary_amount
        assert total_received == expected_received, \
            f"Expected {expected_received}, got {total_received}"
        assert total_received > 0, "Received to Date should be non-zero"

    def test_no_match_when_no_transactions(self):
        """Test that no matches occur when there are no transactions."""
        person_id = add_person("Frank", first_name="Frank", last_name="F")
        account_id = add_account(person_id, "Kotak Bank", "Savings")

        fy = get_current_financial_year()

        # Create expectation but no transactions
        exp_date = fy_date_range(fy)[0].replace(day=15)
        add_income_expectation(
            person_id, account_id, "Salary", 50000.0,
            exp_date.strftime("%Y-%m-%d"), "One-Time", fy
        )

        # Auto-match should return 0
        linked_count = auto_link_income_expectations(person_id, account_id, fy)
        assert linked_count == 0

        # Verify: expectation still unlinked
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        assert expectations[0]["actual_transaction_id"] is None

    def test_no_match_when_no_expectations(self):
        """Test that no matches occur when there are no expectations."""
        person_id = add_person("Grace", first_name="Grace", last_name="G")
        account_id = add_account(person_id, "Yes Bank", "Savings")

        fy = get_current_financial_year()
        fy_start, fy_end = fy_date_range(fy)

        # Create transaction but no expectations
        txn_date = fy_start.replace(day=15)
        add_transaction(
            account_id, person_id, txn_date.strftime("%Y-%m-%d"), "Income", 50000.0, category="Salary"
        )

        # Auto-match should return 0
        linked_count = auto_link_income_expectations(person_id, account_id, fy)
        assert linked_count == 0

    def test_match_different_accounts_separately(self):
        """Test that expectations are matched to correct accounts only."""
        person_id = add_person("Henry", first_name="Henry", last_name="H")
        account_1 = add_account(person_id, "HDFC Bank", "Savings")
        account_2 = add_account(person_id, "SBI Bank", "Checking")

        fy = get_current_financial_year()
        fy_start, fy_end = fy_date_range(fy)

        exp_date = fy_start.replace(day=15)

        # Create expectations for both accounts
        add_income_expectation(
            person_id, account_1, "Salary", 50000.0,
            exp_date.strftime("%Y-%m-%d"), "One-Time", fy
        )
        add_income_expectation(
            person_id, account_2, "Salary", 50000.0,
            exp_date.strftime("%Y-%m-%d"), "One-Time", fy
        )

        # Create transactions only for account_1
        txn_date = exp_date
        add_transaction(
            account_1, person_id, txn_date.strftime("%Y-%m-%d"), "Income", 50000.0, category="Salary"
        )

        # Match for account_1 only
        linked_count_1 = auto_link_income_expectations(person_id, account_1, fy)
        assert linked_count_1 == 1

        # Match for account_2 (should find nothing)
        linked_count_2 = auto_link_income_expectations(person_id, account_2, fy)
        assert linked_count_2 == 0

        # Verify account_1 expectation is linked, account_2 is not
        exp_1 = get_income_expectations(person_id=person_id, financial_year=fy)
        for e in exp_1:
            if e["account_id"] == account_1:
                assert e["actual_transaction_id"] is not None
            elif e["account_id"] == account_2:
                assert e["actual_transaction_id"] is None
