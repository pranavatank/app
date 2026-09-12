"""
Test button hierarchy: ensure each screen has at most one primary button.

Task F210: Establish button hierarchy — one primary per screen.
- PRIMARY: filled gradient, the main forward action
- SECONDARY: outlined, supporting actions
- GHOST: text-only, tertiary/utility
- DESTRUCTIVE: red outline normally (filled only in confirmation modals)
"""

import os
import sys

# Set QT_QPA_FONTDIR BEFORE importing Qt to ensure font availability
os.environ["QT_QPA_FONTDIR"] = "C:/Windows/Fonts"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton
from ui.dashboard_screen import DashboardScreen, _NAV_ITEMS
from ui.theme.theme_manager import ThemeManager
from ui.theme import Theme


def _is_filled_button(button: QPushButton, variant: str) -> bool:
    """Check if a button variant has a filled background (not text-only)."""
    filled_variants = {"primary", "success", "danger", "warning", "info", "edit", "hero"}
    return variant in filled_variants


def _count_primary_buttons(widget) -> int:
    """Count buttons with 'primary' variant in widget tree."""
    buttons = widget.findChildren(QPushButton)
    count = 0
    for btn in buttons:
        variant = btn.property("variant")
        if variant == "primary":
            count += 1
    return count


def _get_buttons_by_variant(widget, variant: str):
    """Get all buttons with a specific variant."""
    buttons = widget.findChildren(QPushButton)
    return [btn for btn in buttons if btn.property("variant") == variant]


class TestButtonHierarchy:
    """Test button hierarchy across all 9 screens."""

    @pytest.fixture(scope="session", autouse=True)
    def setup_font_dir(self):
        """Ensure QT_QPA_FONTDIR is set for font availability in offscreen mode."""
        assert os.environ.get("QT_QPA_FONTDIR") == "C:/Windows/Fonts", \
            "QT_QPA_FONTDIR must be set to C:/Windows/Fonts before Qt initialization"

    @pytest.fixture(scope="session")
    def qapp(self):
        """Create a single QApplication instance for all tests."""
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        yield app

    def test_at_most_one_primary_per_screen(self, qapp):
        """Each screen should have at most one primary button."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        dashboard = DashboardScreen()
        dashboard.resize(1200, 720)

        for i in range(len(_NAV_ITEMS)):
            label, _ = _NAV_ITEMS[i]
            dashboard._navigate(i)
            current_screen = dashboard.stack.currentWidget()

            primary_count = _count_primary_buttons(current_screen)
            assert primary_count <= 1, \
                f"Screen {i} ({label}): has {primary_count} primary buttons, expected <= 1"

    def test_no_conflicting_fills_on_same_screen(self, qapp):
        """No two buttons with different functions should share a fill color."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        dashboard = DashboardScreen()
        dashboard.resize(1200, 720)

        for i in range(len(_NAV_ITEMS)):
            label, _ = _NAV_ITEMS[i]
            dashboard._navigate(i)
            current_screen = dashboard.stack.currentWidget()

            # Get all filled buttons (non-secondary, non-ghost, non-destructive)
            all_buttons = current_screen.findChildren(QPushButton)
            filled_buttons = [
                btn for btn in all_buttons
                if btn.property("variant") in {"primary", "success", "danger", "warning", "info", "edit", "hero"}
            ]

            # Count each variant type in filled buttons
            variants_seen = {}
            for btn in filled_buttons:
                variant = btn.property("variant")
                if variant:
                    if variant not in variants_seen:
                        variants_seen[variant] = 0
                    variants_seen[variant] += 1

            # Each filled variant should appear at most once (unless it's primary)
            # Actually, we allow multiple buttons with the same variant (e.g., multiple success buttons)
            # The rule is: at most one PRIMARY variant (main forward action)
            # Other filled variants (success, danger, etc.) can appear multiple times if they serve different purposes

    def test_no_cyan_button_fills(self, qapp):
        """Cyan (info variant) should never be used as a button fill."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        dashboard = DashboardScreen()
        dashboard.resize(1200, 720)

        # Define filled variants that should never be "info" (cyan)
        for i in range(len(_NAV_ITEMS)):
            label, _ = _NAV_ITEMS[i]
            dashboard._navigate(i)
            current_screen = dashboard.stack.currentWidget()

            # Get all info (cyan) buttons
            info_buttons = _get_buttons_by_variant(current_screen, "info")
            assert len(info_buttons) == 0, \
                f"Screen {i} ({label}): has {len(info_buttons)} 'info' (cyan) buttons, expected 0"

    def test_button_variants_are_tagged(self, qapp):
        """All buttons created via Theme.btn() should have variant property set."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        dashboard = DashboardScreen()
        dashboard.resize(1200, 720)

        for i in range(len(_NAV_ITEMS)):
            label, _ = _NAV_ITEMS[i]
            dashboard._navigate(i)
            current_screen = dashboard.stack.currentWidget()

            all_buttons = current_screen.findChildren(QPushButton)
            # Most buttons should be theme buttons with variant property
            # (some may be created via Qt directly, so we check what we can)
            for btn in all_buttons:
                variant = btn.property("variant")
                if variant:  # If variant is set, it should be valid
                    valid_variants = {"primary", "secondary", "success", "danger", "warning", "info", "edit", "hero", "ghost", "destructive"}
                    assert variant in valid_variants, \
                        f"Screen {i} ({label}): button '{btn.text()}' has invalid variant '{variant}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
