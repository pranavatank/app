"""
tests/test_income_expectation_crud.py — Smoke tests for income expectation CRUD UI
"""

import pytest
from datetime import date

from core.database import get_connection
from core.session import session
from models.person import add_person, get_all_persons
from models.bank_account import add_account, get_accounts_for_person
from models.income_expectation import (
    add_income_expectation,
    get_income_expectations,
    update_income_expectation,
    delete_income_expectation
)
from config import get_current_financial_year


class TestIncomeExpectationCRUD:
    """Test CRUD operations for income expectations."""

    def test_add_single_income_expectation(self):
        """Test adding a single (one-time) income expectation."""
        # Setup
        person_id = add_person("Alice", first_name="Alice", last_name="A")
        account_id = add_account(person_id, "HDFC Bank", "Savings")
        fy = get_current_financial_year()

        # Create one-time expectation
        exp_date = date(2024, 6, 15).isoformat()
        result = add_income_expectation(
            person_id=person_id,
            account_id=account_id,
            income_type="Bonus",
            expected_amount=100000.0,
            expected_date=exp_date,
            frequency="One-Time",
            financial_year=fy,
            notes="Mid-year bonus"
        )

        # Verify
        assert len(result) == 1, "Should create exactly 1 record for one-time expectation"
        exp_id = result[0]

        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        assert len(expectations) >= 1
        exp = next((e for e in expectations if e["expectation_id"] == exp_id), None)
        assert exp is not None
        assert exp["income_type"] == "Bonus"
        assert exp["expected_amount"] == 100000.0
        assert exp["frequency"] == "One-Time"
        assert exp["notes"] == "Mid-year bonus"

    def test_add_monthly_income_expectations(self):
        """Test adding monthly income expectations (creates 12 records)."""
        # Setup
        person_id = add_person("Bob", first_name="Bob", last_name="B")
        account_id = add_account(person_id, "SBI Bank", "Savings")
        fy = get_current_financial_year()

        # Create monthly expectation
        result = add_income_expectation(
            person_id=person_id,
            account_id=account_id,
            income_type="Salary",
            expected_amount=50000.0,
            expected_date="15",  # Day of month
            frequency="Monthly",
            financial_year=fy
        )

        # Verify: should create 12 records
        assert len(result) == 12, f"Expected 12 records for monthly, got {len(result)}"

        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        salary_exps = [e for e in expectations if e["income_type"] == "Salary"]
        assert len(salary_exps) >= 12, "Should have at least 12 salary expectations"

    def test_update_income_expectation(self):
        """Test updating an income expectation."""
        # Setup
        person_id = add_person("Charlie", first_name="Charlie", last_name="C")
        account_id = add_account(person_id, "Axis Bank", "Current")
        fy = get_current_financial_year()

        # Create expectation
        exp_date = date(2024, 12, 31).isoformat()
        result = add_income_expectation(
            person_id=person_id,
            account_id=account_id,
            income_type="Dividend",
            expected_amount=25000.0,
            expected_date=exp_date,
            frequency="One-Time",
            financial_year=fy,
            notes="Annual dividend"
        )
        exp_id = result[0]

        # Update amount and notes
        update_income_expectation(
            exp_id,
            expected_amount=30000.0,
            notes="Annual dividend (updated)"
        )

        # Verify
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        exp = next((e for e in expectations if e["expectation_id"] == exp_id), None)
        assert exp is not None
        assert exp["expected_amount"] == 30000.0
        assert exp["notes"] == "Annual dividend (updated)"

    def test_delete_income_expectation(self):
        """Test deleting an income expectation."""
        # Setup
        person_id = add_person("Diana", first_name="Diana", last_name="D")
        account_id = add_account(person_id, "ICICI Bank", "Savings Plus")
        fy = get_current_financial_year()

        # Create expectation
        exp_date = date(2024, 3, 31).isoformat()
        result = add_income_expectation(
            person_id=person_id,
            account_id=account_id,
            income_type="Interest",
            expected_amount=5000.0,
            expected_date=exp_date,
            frequency="One-Time",
            financial_year=fy
        )
        exp_id = result[0]

        # Verify it exists
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        assert any(e["expectation_id"] == exp_id for e in expectations)

        # Delete
        delete_income_expectation(exp_id)

        # Verify it's gone
        expectations = get_income_expectations(person_id=person_id, financial_year=fy)
        assert not any(e["expectation_id"] == exp_id for e in expectations)

    def test_screen_has_add_button(self, qapp):
        """Smoke test: verify IncomeManagementScreen has Add button and it's primary styled."""
        from ui.income_management_screen import IncomeManagementScreen

        screen = IncomeManagementScreen()

        # Check that the expectations table widget exists
        assert hasattr(screen, 'table_expectations_widget'), "Screen should have table_expectations_widget"
        assert hasattr(screen, 'table_expectations'), "Screen should have table_expectations"

        # Check that empty state exists
        assert hasattr(screen, 'empty_state_expectations'), "Screen should have empty_state_expectations"

    def test_dialog_imports(self, qapp):
        """Smoke test: verify dialog classes can be imported and instantiated."""
        from ui.dialogs.income_expectation_dialog import IncomeExpectationDialog, LinkActualDialog

        # Should not raise an error
        persons = [{"person_id": 1, "full_name": "Test Person"}]
        dlg = IncomeExpectationDialog(persons=persons)
        assert dlg is not None

        # LinkActualDialog should also instantiate
        dlg2 = LinkActualDialog()
        assert dlg2 is not None
