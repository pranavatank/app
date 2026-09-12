"""
tests/test_statement_import_flow.py — Integration test for statement import flow

Tests the complete parse → preview → import pipeline, including error handling.
Verifies that worker threads correctly return results and handle exceptions.
"""

import os
import sys
import time

# Set QT_QPA_FONTDIR BEFORE importing Qt
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QTest

from ui.dashboard_screen import DashboardScreen, _NAV_ITEMS
from ui.statement_import_screen_modern import StatementImportScreen
from models.person import get_all_persons
from models.bank_account import add_account, delete_account, get_accounts_for_person


@pytest.fixture(scope="session", autouse=True)
def setup_font_dir():
    """Ensure QT_QPA_FONTDIR is set before Qt initialization."""
    assert os.environ.get("QT_QPA_FONTDIR") == "C:/Windows/Fonts", \
        "QT_QPA_FONTDIR must be set to C:/Windows/Fonts before Qt initialization"


@pytest.fixture(scope="session")
def qapp():
    """Create a single QApplication instance for all tests."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app


@pytest.fixture
def test_person_id():
    """Get or create a test person."""
    persons = get_all_persons()
    if persons:
        return persons[0]["person_id"]
    # If no persons exist, the test will skip
    pytest.skip("No persons available in test database")


@pytest.fixture
def test_account_id(test_person_id):
    """Create a temporary test bank account."""
    account_id = add_account(
        person_id=test_person_id,
        bank_name="Jana Small Finance Bank",
        account_type="Savings",
        account_number="TEST_ACCT_001",
        account_number_masked="XXXX1001",
        opening_date="2020-01-01",
        opening_balance=100000.0,
        current_balance=100000.0,
        interest_rate=4.0,
        currency="INR",
        is_archived=False,
    )
    yield account_id
    # Cleanup
    try:
        delete_account(account_id)
    except Exception:
        pass


class TestStatementImportFlow:
    """Integration tests for statement import pipeline."""

    def test_statement_parse_success(self, qapp, test_person_id, test_account_id):
        """
        Test successful statement parsing:
        1. Navigate to Statement Import screen
        2. Select person, account, and valid Jana statement file
        3. Verify parsing completes and transitions to preview
        4. Assert correct transaction count (65 for Jana)
        """
        # Monkeypatch QMessageBox.critical to prevent blocking
        QMessageBox.critical = staticmethod(lambda parent, title, text, *a, **kw: None)

        # Build dashboard and navigate to Statement Import
        dashboard = DashboardScreen()
        dashboard.resize(1200, 720)

        # Find Statement Import index
        statement_import_index = None
        for i, (label, _) in enumerate(_NAV_ITEMS):
            if label == "Statement Import":
                statement_import_index = i
                break

        assert statement_import_index is not None, "Statement Import screen not found in _NAV_ITEMS"

        # Navigate to Statement Import
        dashboard._navigate(statement_import_index)
        qapp.processEvents()

        screen = dashboard.stack.currentWidget()
        assert isinstance(screen, StatementImportScreen), "Current screen is not StatementImportScreen"

        # Select person
        for i in range(screen.person_combo.count()):
            if screen.person_combo.itemData(i) == test_person_id:
                screen.person_combo.setCurrentIndex(i)
                break
        qapp.processEvents()

        # Select account
        accounts = get_accounts_for_person(test_person_id)
        for i in range(screen.account_combo.count()):
            if screen.account_combo.itemData(i) == test_account_id:
                screen.account_combo.setCurrentIndex(i)
                break
        qapp.processEvents()

        # Verify Parse button is enabled
        assert screen.btn_next.isEnabled(), "Parse button should be enabled after selecting person and account"

        # Find the Jana test statement file
        fixture_dir = Path(__file__).resolve().parent.parent / "data" / "PersonalData" / "Pranav" / "Statement"
        jana_file = fixture_dir / "Jana - Pranav.pdf"

        if not jana_file.exists():
            pytest.skip(f"Test file not found: {jana_file}")

        # Set the file
        screen._set_selected_file(str(jana_file))
        qapp.processEvents()

        # Click Parse button
        screen.btn_next.click()

        # Pump event loop with timeout to allow parsing to complete
        start = time.time()
        max_wait = 15
        while time.time() - start < max_wait:
            qapp.processEvents()
            QTest.qWait(100)
            # Check if we've moved to the preview screen (stack index 1)
            if screen.stack.currentIndex() == 1:
                break

        # Assert we moved to preview screen
        assert screen.stack.currentIndex() == 1, \
            f"Did not transition to preview screen. Current index: {screen.stack.currentIndex()}"

        # Assert transaction count
        assert len(screen.preview_transactions) == 65, \
            f"Expected 65 transactions from Jana statement, got {len(screen.preview_transactions)}"

        # Verify that parsing actually happened (debug info was populated)
        assert screen.import_debug_info, "Debug info should be populated after parsing"

    def test_statement_parse_error_handling(self, qapp, test_person_id, test_account_id):
        """
        Test error handling in statement parsing:
        1. Navigate to Statement Import screen
        2. Select person, account, and a nonexistent file
        3. Attempt to parse
        4. Verify the screen handles error gracefully (does not crash/hang)
        5. Assert Parse button becomes enabled again (allowing retry)
        """
        # Monkeypatch QMessageBox.critical to prevent blocking
        original_critical = QMessageBox.critical
        critical_calls = []

        def mock_critical(parent, title, text, *a, **kw):
            critical_calls.append({"title": title, "text": text})
            return None

        QMessageBox.critical = staticmethod(mock_critical)

        try:
            # Build dashboard and navigate to Statement Import
            dashboard = DashboardScreen()
            dashboard.resize(1200, 720)

            # Find Statement Import index
            statement_import_index = None
            for i, (label, _) in enumerate(_NAV_ITEMS):
                if label == "Statement Import":
                    statement_import_index = i
                    break

            assert statement_import_index is not None

            # Navigate to Statement Import
            dashboard._navigate(statement_import_index)
            qapp.processEvents()

            screen = dashboard.stack.currentWidget()
            assert isinstance(screen, StatementImportScreen)

            # Select person
            for i in range(screen.person_combo.count()):
                if screen.person_combo.itemData(i) == test_person_id:
                    screen.person_combo.setCurrentIndex(i)
                    break
            qapp.processEvents()

            # Select account
            for i in range(screen.account_combo.count()):
                if screen.account_combo.itemData(i) == test_account_id:
                    screen.account_combo.setCurrentIndex(i)
                    break
            qapp.processEvents()

            # Set a nonexistent file
            screen._set_selected_file("/nonexistent/fake_statement.pdf")
            qapp.processEvents()

            # Click Parse button
            initial_stack_index = screen.stack.currentIndex()
            screen.btn_next.click()

            # Pump event loop with timeout
            start = time.time()
            max_wait = 15
            while time.time() - start < max_wait:
                qapp.processEvents()
                QTest.qWait(100)
                # If we transition to preview, break (should not happen for bad file)
                if screen.stack.currentIndex() != initial_stack_index:
                    break

            # Verify we're still on selection screen (not transitioned)
            assert screen.stack.currentIndex() == initial_stack_index, \
                "Should remain on selection screen when parse fails"

            # Verify Parse button is enabled again (to allow retry)
            assert screen.btn_next.isEnabled(), \
                "Parse button should be re-enabled after error to allow retry"

            # Verify that an error was reported (critical was called)
            # This verifies the error path worked instead of silently hanging
            assert len(critical_calls) > 0, \
                "Error should have been reported via QMessageBox.critical"

        finally:
            # Restore original QMessageBox.critical
            QMessageBox.critical = original_critical
