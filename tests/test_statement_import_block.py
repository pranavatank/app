"""
tests/test_statement_import_block.py — Test import blocking based on balance validation.

Tests that:
1. _import_blocked is set correctly based on direction_errors and confidence
2. _import_transactions respects _import_blocked flag
3. When no balance_after data exists (confidence = 0.0), import is not blocked
"""

import os
import sys

os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication, QMessageBox

from ui.statement_import_screen_modern import StatementImportScreen
from models.person import get_all_persons, add_person
from models.bank_account import add_account, delete_account


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
    return add_person("Test Person", "test@example.com", "active")


@pytest.fixture
def test_account_id(test_person_id):
    """Create a temporary test bank account."""
    account_id = add_account(
        person_id=test_person_id,
        bank_name="Test Bank",
        account_type="Savings",
        account_number_masked="XXXX0001",
        account_number_full="TEST_FULL_001",
        account_opening_date="2020-01-01",
        opening_balance=100000.0,
        interest_rate=4.0,
        currency="INR",
    )
    yield account_id
    try:
        delete_account(account_id)
    except Exception:
        pass


class TestStatementImportBlocking:
    """Test _import_blocked flag and import blocking behavior."""

    def test_import_blocked_when_tied_rows_and_low_confidence(self, qapp, test_person_id, test_account_id):
        """
        Test 1: When balance_after exists with tied rows and confidence < 0.9,
        _import_blocked should be True and _import_transactions should show warning.

        Rows:
        - (2025-04-01, Income, 100, balance_after 1000, desc A)
        - (2025-04-02, Income, 100, balance_after 900, desc B)  <- direction wrong (balance decreased but Income)
        - (2025-04-03, Income, 50, balance_after 850, desc C)

        This creates tied rows with direction mismatches, triggering low confidence.
        """
        screen = StatementImportScreen(None)
        screen.selected_person_id = test_person_id
        screen.selected_account_id = test_account_id

        warnings_shown = []
        infos_shown = []
        successes_shown = []

        def mock_warning(msg):
            warnings_shown.append(msg)

        def mock_info(msg):
            infos_shown.append(msg)

        def mock_success(msg):
            successes_shown.append(msg)

        def mock_critical(parent, title, text, *args, **kwargs):
            pytest.fail(f"QMessageBox.critical should not be called: {title}: {text}")

        loader_runs = []

        def mock_loader_run(widget, **kwargs):
            loader_runs.append({"widget": widget, "kwargs": kwargs})

        # Prepare test rows with balance_after
        rows = [
            {
                "transaction_date": "2025-04-01",
                "transaction_type": "Income",
                "amount": 100.0,
                "balance_after": 1000.0,
                "description": "A",
                "mode": "Transfer",
                "category": "Salary",
                "reference_no": None,
            },
            {
                "transaction_date": "2025-04-02",
                "transaction_type": "Income",
                "amount": 100.0,
                "balance_after": 900.0,  # decreased, but Income (wrong direction)
                "description": "B",
                "mode": "Transfer",
                "category": "Salary",
                "reference_no": None,
            },
            {
                "transaction_date": "2025-04-03",
                "transaction_type": "Income",
                "amount": 50.0,
                "balance_after": 850.0,  # decreased, but Income (wrong direction)
                "description": "C",
                "mode": "Transfer",
                "category": "Salary",
                "reference_no": None,
            },
        ]

        with patch("ui.statement_import_screen_modern.show_warning", side_effect=mock_warning), \
             patch("ui.statement_import_screen_modern.show_info", side_effect=mock_info), \
             patch("ui.statement_import_screen_modern.show_success", side_effect=mock_success), \
             patch("ui.statement_import_screen_modern.QMessageBox.critical", side_effect=mock_critical), \
             patch("ui.statement_import_screen_modern.validate_transactions") as mock_validate, \
             patch("ui.statement_import_screen_modern.Loader.run", side_effect=mock_loader_run):

            mock_validate.return_value = (rows, [])

            screen._process_parsed_statement(rows)

            assert screen._import_blocked, "_import_blocked should be True for tied rows with low confidence"
            assert len(warnings_shown) > 0, "show_warning should have been called"
            assert "blocked" in warnings_shown[0].lower(), "Warning should mention 'blocked'"

        with patch("ui.statement_import_screen_modern.show_warning", side_effect=mock_warning), \
             patch("ui.statement_import_screen_modern.Loader.run", side_effect=mock_loader_run):
            loader_runs.clear()
            screen._import_transactions()
            assert len(loader_runs) == 0, "Loader.run should not be called when import is blocked"
            assert any("blocked" in w.lower() for w in warnings_shown), \
                "Warning containing 'blocked' should be shown in _import_transactions"

    def test_import_not_blocked_without_balance_after(self, qapp, test_person_id, test_account_id):
        """
        Test 2: When no balance_after exists (Excel without balance column),
        confidence() returns 0.0, but _import_blocked should be False
        because there are no tied_count rows (direction_errors returns 0).

        Rows without balance_after:
        - (2025-04-01, Income, 100, no balance_after, desc A)
        - (2025-04-02, Income, 100, no balance_after, desc B)
        - (2025-04-03, Income, 50, no balance_after, desc C)
        """
        screen = StatementImportScreen(None)
        screen.selected_person_id = test_person_id
        screen.selected_account_id = test_account_id

        warnings_shown = []
        infos_shown = []

        def mock_warning(msg):
            warnings_shown.append(msg)

        def mock_info(msg):
            infos_shown.append(msg)

        def mock_critical(parent, title, text, *args, **kwargs):
            pytest.fail(f"QMessageBox.critical should not be called: {title}: {text}")

        loader_runs = []

        def mock_loader_run(widget, **kwargs):
            loader_runs.append({"widget": widget, "kwargs": kwargs})

        rows = [
            {
                "transaction_date": "2025-04-01",
                "transaction_type": "Income",
                "amount": 100.0,
                "description": "A",
                "mode": "Transfer",
                "category": "Salary",
                "reference_no": None,
            },
            {
                "transaction_date": "2025-04-02",
                "transaction_type": "Income",
                "amount": 100.0,
                "description": "B",
                "mode": "Transfer",
                "category": "Salary",
                "reference_no": None,
            },
            {
                "transaction_date": "2025-04-03",
                "transaction_type": "Income",
                "amount": 50.0,
                "description": "C",
                "mode": "Transfer",
                "category": "Salary",
                "reference_no": None,
            },
        ]

        with patch("ui.statement_import_screen_modern.show_warning", side_effect=mock_warning), \
             patch("ui.statement_import_screen_modern.show_info", side_effect=mock_info), \
             patch("ui.statement_import_screen_modern.QMessageBox.critical", side_effect=mock_critical), \
             patch("ui.statement_import_screen_modern.validate_transactions") as mock_validate, \
             patch("ui.statement_import_screen_modern.check_duplicate") as mock_check_dup, \
             patch("ui.statement_import_screen_modern.Loader.run", side_effect=mock_loader_run):

            mock_validate.return_value = (rows, [])
            mock_check_dup.return_value = False

            screen._process_parsed_statement(rows)

            assert not screen._import_blocked, "_import_blocked should be False when no balance_after (no tied rows)"
            assert screen.parse_confidence == 0.0, "confidence should be 0.0 without balance_after"

        checked_rows = [0, 1, 2]
        with patch("ui.statement_import_screen_modern.show_warning", side_effect=mock_warning), \
             patch.object(screen.preview_table, "getCheckedRows", return_value=checked_rows), \
             patch("ui.statement_import_screen_modern.Loader.run", side_effect=mock_loader_run):
            loader_runs.clear()
            screen._import_transactions()
            assert len(loader_runs) == 1, "Loader.run should be called once when import is not blocked"

    def test_import_blocked_with_balances_but_no_tied_rows(self, qapp, test_person_id, test_account_id):
        """
        Test 3: When balance_after exists but NO tied rows (tied==0) with different amounts
        that don't match a pattern, _import_blocked should be True.

        Rows:
        - (2025-04-01, Expense, 7, balance_after 1000)
        - (2025-04-02, Expense, 8, balance_after 1500)  <- balance increased but Expense (not tied)
        - (2025-04-03, Expense, 9, balance_after 900)   <- balance decreased but wrong

        When has_balances=True and tied==0, should block because no row correlations exist.
        """
        screen = StatementImportScreen(None)
        screen.selected_person_id = test_person_id
        screen.selected_account_id = test_account_id

        warnings_shown = []

        def mock_warning(msg):
            warnings_shown.append(msg)

        def mock_info(msg):
            pass

        def mock_critical(parent, title, text, *args, **kwargs):
            pytest.fail(f"QMessageBox.critical should not be called: {title}: {text}")

        loader_runs = []

        def mock_loader_run(widget, **kwargs):
            loader_runs.append({"widget": widget, "kwargs": kwargs})

        rows = [
            {
                "transaction_date": "2025-04-01",
                "transaction_type": "Expense",
                "amount": 7.0,
                "balance_after": 1000.0,
                "description": "A",
                "mode": "Transfer",
                "category": "Other",
                "reference_no": None,
            },
            {
                "transaction_date": "2025-04-02",
                "transaction_type": "Expense",
                "amount": 8.0,
                "balance_after": 1500.0,  # balance increased but Expense (not a direction error, just wrong amount)
                "description": "B",
                "mode": "Transfer",
                "category": "Other",
                "reference_no": None,
            },
            {
                "transaction_date": "2025-04-03",
                "transaction_type": "Expense",
                "amount": 9.0,
                "balance_after": 900.0,  # balance decreased (could be correct but not matching amounts)
                "description": "C",
                "mode": "Transfer",
                "category": "Other",
                "reference_no": None,
            },
        ]

        with patch("ui.statement_import_screen_modern.show_warning", side_effect=mock_warning), \
             patch("ui.statement_import_screen_modern.show_info", side_effect=mock_info), \
             patch("ui.statement_import_screen_modern.QMessageBox.critical", side_effect=mock_critical), \
             patch("ui.statement_import_screen_modern.validate_transactions") as mock_validate, \
             patch("ui.statement_import_screen_modern.Loader.run", side_effect=mock_loader_run):

            mock_validate.return_value = (rows, [])

            screen._process_parsed_statement(rows)

            assert screen._import_blocked, "_import_blocked should be True when has_balances=True and tied==0"
            assert len(warnings_shown) > 0, "show_warning should have been called"
            assert "blocked" in warnings_shown[0].lower(), "Warning should mention 'blocked'"
