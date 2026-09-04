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


def test_nav_labels_not_clipped_when_expanded():
    """Regression test for sidebar nav label and icon clipping bug.

    When the sidebar is expanded to 248px, both nav icons and labels should have
    enough space and not be clipped. This test verifies that nav buttons have a
    proper expanding size policy, icons get natural width (24px), and labels
    expand to fill remaining space.

    Previously, nav labels were clipped when sidebar was 248px (buttons were too
    narrow), and nav icons were clipped when set to 6px for a 22px icon.
    """
    from core.session import session
    from PyQt6.QtWidgets import QToolButton

    # Ensure sidebar is expanded
    session.set_sidebar_open(True)
    dash = DashboardScreen()
    dash.resize(1280, 720)
    dash.show()

    # Get sidebar and verify its width
    sidebar = dash.findChild(QWidget, 'sidebar')
    assert sidebar is not None, "Sidebar widget not found"
    assert sidebar.width() == 248, f"Expanded sidebar should be 248px, got {sidebar.width()}"

    # Get all nav buttons and verify they expand with the sidebar
    nav_buttons = [b for b in dash.findChildren(QToolButton) if b.property('nav_item')]
    assert len(nav_buttons) == 9, f"Should have 9 nav buttons, got {len(nav_buttons)}"

    # Verify each nav button fills the sidebar width
    for btn in nav_buttons:
        assert btn.width() > 200, \
            f"Nav button should fill expanded sidebar (>{200}px), but is {btn.width()}px"

    # Verify no nav labels are clipped
    clipped_labels = 0
    for btn in nav_buttons:
        label = btn.findChild(QLabel, 'nav_label')
        if label and label.isVisible():
            label_width = label.width()
            label_required = label.sizeHint().width()
            # Allow 2px tolerance for rounding errors in Qt's layout engine
            if label_required > label_width + 2:
                clipped_labels += 1

    assert clipped_labels == 0, f"{clipped_labels} nav labels are clipped"

    # Verify no nav icons are clipped
    clipped_icons = 0
    for btn in nav_buttons:
        icon = btn.findChild(QLabel, 'navIcon')
        if icon and icon.isVisible():
            icon_width = icon.width()
            icon_required = icon.sizeHint().width()
            # Allow 2px tolerance for rounding errors
            if icon_required > icon_width + 2:
                clipped_icons += 1

    assert clipped_icons == 0, f"{clipped_icons} nav icons are clipped"


def test_nav_labels_hidden_when_collapsed():
    """Regression test: nav labels should be hidden when sidebar is collapsed.

    This ensures the collapse path properly hides labels and the labels
    remain hidden (not clipped) in the 76px rail mode.
    """
    from core.session import session
    from PyQt6.QtWidgets import QToolButton

    # Start expanded, then collapse
    session.set_sidebar_open(True)
    dash = DashboardScreen()
    dash.resize(1280, 720)
    dash.show()

    # Collapse the sidebar
    dash._toggle_sidebar()

    # Verify sidebar width is collapsed
    sidebar = dash.findChild(QWidget, 'sidebar')
    assert sidebar.width() == 76, f"Collapsed sidebar should be 76px, got {sidebar.width()}"

    # Verify all nav labels are hidden (not just clipped)
    visible_count = 0
    for btn in dash.findChildren(QToolButton):
        if btn.property('nav_item'):
            label = btn.findChild(QLabel, 'nav_label')
            if label and label.isVisible():
                visible_count += 1

    assert visible_count == 0, f"{visible_count} nav labels should be hidden in collapsed mode"
