"""
Tests for lazy screen loading and error isolation in DashboardScreen.
T043: Build screens lazily; wrap screen construction in try/except.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Set offscreen platform before importing Qt
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from ui.dashboard_screen import DashboardScreen, _NAV_ITEMS
import core.database as db


@pytest.fixture(scope="session", autouse=True)
def setup_app():
    """Initialize database and QApplication once for all tests."""
    db.initialise_database()
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield
    # Don't quit the app, let pytest handle it


def test_dashboard_lazy_loading():
    """Test that screens are lazy-loaded on first navigation."""
    dash = DashboardScreen()

    # Overview should be loaded immediately (index 0)
    assert dash._screen_pages[0] is not None, "Overview page should be preloaded"

    # Other screens should start as placeholders (None)
    for i in range(1, len(_NAV_ITEMS)):
        # Check that the initial widget is a placeholder
        initial_widget = dash.stack.widget(i)
        assert initial_widget is not None
        # After first navigate, screen should be loaded
        assert dash._screen_pages[i] is None, f"Screen {i} should not be preloaded"

    # Navigate to Accounts (index 1) and verify it's loaded
    dash._navigate(1)
    assert dash._screen_pages[1] is not None, "Accounts page should be loaded after navigation"

    # Verify navigation to all other screens works
    for i in range(2, len(_NAV_ITEMS)):
        dash._navigate(i)
        assert dash._screen_pages[i] is not None, f"Screen {i} should be loaded after navigation"


def test_screen_construction_failure_isolation():
    """Test that a screen construction failure shows inline error and doesn't break other screens."""
    dash = DashboardScreen()

    # Monkeypatch one screen class to raise during construction
    # We'll patch the Accounts screen
    with patch('ui.accounts_screen.AccountsScreen') as MockAccountsScreen:
        MockAccountsScreen.side_effect = RuntimeError("Simulated construction error")

        # Try to navigate to Accounts (index 1)
        dash._navigate(1)

        # Verify error page is displayed
        screen = dash._screen_pages[1]
        assert screen is not None, "Error page should be created"

        # Verify the error message is stored
        assert 1 in dash._screen_errors, "Error should be recorded"
        assert "Accounts" in dash._screen_errors[1], "Error message should contain screen name"
        assert "RuntimeError" in dash._screen_errors[1], "Error message should contain exception type"

        # Verify other screens still work
        dash._navigate(2)  # Navigate to Transactions
        assert dash._screen_pages[2] is not None, "Other screens should still load successfully"


def test_sidebar_expansion_persistence():
    """Test that sidebar expansion state persists across instances."""
    import os
    import json
    from core.session import Session, _CONFIG_FILE, _CONFIG_DIR

    # Clean up any existing state
    if os.path.exists(_CONFIG_FILE):
        os.remove(_CONFIG_FILE)

    # First instance - should default to expanded
    session1 = Session()
    assert session1.is_sidebar_open() is True, "First run should default to expanded"

    # Simulate collapsing
    session1.set_sidebar_open(False)

    # Create new instance - should load persisted state
    session2 = Session()
    assert session2.is_sidebar_open() is False, "State should persist from previous instance"

    # Set back to expanded
    session2.set_sidebar_open(True)

    # Verify it persists again
    session3 = Session()
    assert session3.is_sidebar_open() is True, "Updated state should persist"


def test_nav_button_tooltips_and_accessible_names():
    """Test that all nav buttons have tooltips and accessible names."""
    dash = DashboardScreen()

    for i, btn in enumerate(dash._nav_buttons):
        label, _ = _NAV_ITEMS[i]
        tooltip = btn.toolTip()
        accessible_name = btn.accessibleName()

        assert tooltip == label, f"Nav button {i} should have tooltip '{label}', got '{tooltip}'"
        assert f"Navigate to {label}" in accessible_name, \
            f"Nav button {i} should have accessible name containing 'Navigate to {label}'"


def test_construction_performance():
    """Test that dashboard construction completes in under 800ms."""
    import time

    start = time.perf_counter()
    dash = DashboardScreen()
    elapsed = time.perf_counter() - start

    elapsed_ms = elapsed * 1000
    assert elapsed_ms < 800, f"Construction took {elapsed_ms:.0f}ms, should be < 800ms"


def test_initial_widget_count():
    """Test that initial widget count is under 300."""
    dash = DashboardScreen()
    widget_count = len(dash.findChildren(QWidget))

    assert widget_count < 300, f"Initial widget count {widget_count}, should be < 300"
