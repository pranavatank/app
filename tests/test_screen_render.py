"""
Regression test: Construct all 9 screens under all 4 themes.

Guards against:
- F001: Stale-cache bug where placeholders weren't swapped with real screens
- F002: Unhandled exception in reimplemented showEvent() (deleted widget refs)
- F003: Unhandled exceptions during screen construction that silently added to _screen_errors
"""

import os
import sys

# Set QT_QPA_FONTDIR BEFORE importing Qt to ensure font availability
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PyQt6.QtWidgets import QApplication, QWidget
from ui.dashboard_screen import DashboardScreen, _NAV_ITEMS
from ui.theme.theme_manager import ThemeManager


@pytest.fixture(scope="session", autouse=True)
def setup_font_dir():
    """Ensure QT_QPA_FONTDIR is set for font availability in offscreen mode."""
    assert os.environ.get("QT_QPA_FONTDIR") == "C:/Windows/Fonts", \
        "QT_QPA_FONTDIR must be set to C:/Windows/Fonts before Qt initialization"


@pytest.fixture(scope="session")
def qapp():
    """Create a single QApplication instance for all tests."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app
    # Don't quit, let pytest handle cleanup


class TestScreenRenderAllThemes:
    """Regression test: render all 9 screens under all 4 themes."""

    @pytest.mark.parametrize("theme_name", [
        "Aurora",       # Light
        "Slate",        # Light
        "Nova",         # Dark
        "Midnight Pro", # Dark
    ])
    def test_all_screens_render_under_theme(self, qapp, theme_name):
        """
        For each theme:
        1. Construct all 9 screens
        2. Assert no exception is raised
        3. Assert each screen has > 10 children (non-trivial UI)
        4. Assert after _navigate(i), stack.currentWidget() is the real screen class
        5. Assert _screen_errors is empty
        6. Exercise showEvent() on each screen
        """
        # Apply the theme
        ThemeManager.apply(theme_name, save=False, notify=False)

        # Construct the dashboard
        dashboard = DashboardScreen()
        dashboard.resize(1200, 720)

        # Verify overview is preloaded (index 0)
        assert dashboard._screen_pages[0] is not None, \
            f"[{theme_name}] Overview page should be preloaded"

        # Navigate to each screen and verify
        for i in range(len(_NAV_ITEMS)):
            label, _ = _NAV_ITEMS[i]

            # Navigate to screen i
            try:
                dashboard._navigate(i)
            except Exception as e:
                pytest.fail(
                    f"[{theme_name}] Navigation to screen {i} ({label}) raised: {type(e).__name__}: {e}"
                )

            # Get the screen that is now current in the stack
            current_widget = dashboard.stack.currentWidget()
            assert current_widget is not None, \
                f"[{theme_name}] Screen {i} ({label}): stack.currentWidget() is None"

            # Verify it's the real screen, not a placeholder
            screen_page = dashboard._screen_pages[i]
            assert screen_page is not None, \
                f"[{theme_name}] Screen {i} ({label}): _screen_pages[{i}] is None (not loaded)"

            assert current_widget is screen_page, \
                f"[{theme_name}] Screen {i} ({label}): stack.currentWidget() is not the real screen (F001 regression)"

            # Verify _screen_errors is empty (F003 regression)
            assert i not in dashboard._screen_errors, \
                f"[{theme_name}] Screen {i} ({label}): _screen_errors has entry: {dashboard._screen_errors.get(i)}"

            # Verify screen has non-trivial child count (> 10 children)
            children = current_widget.findChildren(QWidget)
            assert len(children) > 10, \
                f"[{theme_name}] Screen {i} ({label}): child count is {len(children)}, expected > 10"

            # Exercise showEvent() (F002 regression)
            # This may raise an exception if the screen has a buggy showEvent()
            try:
                current_widget.show()
                # Process events to trigger any showEvent handlers
                qapp.processEvents()
            except Exception as e:
                pytest.fail(
                    f"[{theme_name}] Screen {i} ({label}): showEvent() raised: {type(e).__name__}: {e}"
                )

        # Final check: _screen_errors should be completely empty after all navigations
        assert len(dashboard._screen_errors) == 0, \
            f"[{theme_name}] _screen_errors is not empty: {dashboard._screen_errors}"

    def test_theme_navigation_consistency(self, qapp):
        """
        Verify that switching themes and navigating still works correctly.
        This is a secondary check to ensure theme switches don't break navigation.
        """
        themes = ["Aurora", "Slate", "Nova", "Midnight Pro"]

        for theme_name in themes:
            ThemeManager.apply(theme_name, save=False, notify=False)
            dashboard = DashboardScreen()
            dashboard.resize(1200, 720)

            # Quick navigation through all screens
            for i in range(len(_NAV_ITEMS)):
                try:
                    dashboard._navigate(i)
                except Exception as e:
                    pytest.fail(
                        f"Theme switching ({theme_name}) -> navigation to screen {i} failed: {e}"
                    )

                # Verify screen is loaded and current
                assert dashboard.stack.currentWidget() is not None
                assert i not in dashboard._screen_errors


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
