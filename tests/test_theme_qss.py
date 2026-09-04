"""
Tests for theme QSS stylesheet validity and accessibility features.
Validates that focus rings and press behaviors meet accessibility standards.
"""

import pytest
from ui.theme.theme import Theme
from ui.theme.theme_manager import ThemeManager


class TestThemeFocusRings:
    """Verify that all themes have proper focus ring styling."""

    def test_all_themes_have_focus_rules(self):
        """Each registered theme's stylesheet must contain focus rules with FOCUS_RING."""
        for theme_name in ThemeManager.theme_names():
            # Apply the theme to get its colors
            ThemeManager.apply(theme_name, save=False, notify=False)

            # Get the generated stylesheet
            qss = Theme.get_stylesheet()

            # Verify focus rules exist and reference the FOCUS_RING token
            assert ":focus" in qss, f"Theme {theme_name} missing :focus rules"
            assert Theme.FOCUS_RING in qss, f"Theme {theme_name} FOCUS_RING not in stylesheet"

            # Count focus rules to ensure multiple interactive elements have focus styling
            focus_count = qss.count(":focus")
            assert focus_count >= 8, (
                f"Theme {theme_name} has only {focus_count} focus rules; "
                "expected at least 8 for QPushButton, QLineEdit, QComboBox, QSpinBox, "
                "QDateEdit, QCheckBox, QRadioButton, QTabBar::tab"
            )

    def test_pressed_rules_no_padding_margin(self):
        """No :pressed rule should change padding or margin."""
        for theme_name in ThemeManager.theme_names():
            ThemeManager.apply(theme_name, save=False, notify=False)
            qss = Theme.get_stylesheet()

            # Split QSS into blocks separated by closing braces
            lines = qss.split('\n')
            in_pressed_block = False
            pressed_line_buffer = []

            for line in lines:
                # Detect start of :pressed rule
                if ":pressed" in line:
                    in_pressed_block = True
                    pressed_line_buffer = [line]
                elif in_pressed_block:
                    pressed_line_buffer.append(line)
                    # End of block when we hit closing brace
                    if "}}" in line or "}" in line:
                        pressed_block = '\n'.join(pressed_line_buffer)

                        # Check for padding/margin in this :pressed block
                        assert "padding" not in pressed_block.lower(), (
                            f"Theme {theme_name} has :pressed rule with padding: "
                            f"{pressed_block}"
                        )
                        assert "margin" not in pressed_block.lower(), (
                            f"Theme {theme_name} has :pressed rule with margin: "
                            f"{pressed_block}"
                        )

                        in_pressed_block = False
                        pressed_line_buffer = []

    def test_focus_ring_covers_major_widgets(self):
        """Verify focus ring styling exists for major interactive widgets."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        qss = Theme.get_stylesheet()

        required_widgets = [
            "QPushButton:focus",
            "QLineEdit:focus",
            "QComboBox:focus",
            "QSpinBox:focus",
            "QDateEdit:focus",
            "QCheckBox:focus",
            "QRadioButton:focus",
            "QTabBar::tab:focus",
        ]

        for widget in required_widgets:
            assert widget in qss, (
                f"Missing focus rule for {widget}"
            )

    def test_focus_ring_contrast(self):
        """Verify FOCUS_RING token exists and is defined for all themes."""
        for theme_name in ThemeManager.theme_names():
            ThemeManager.apply(theme_name, save=False, notify=False)

            # FOCUS_RING should be a valid color
            focus_ring = Theme.FOCUS_RING
            assert focus_ring is not None, (
                f"Theme {theme_name} has FOCUS_RING = None"
            )

            # It should be a string (hex color)
            assert isinstance(focus_ring, str), (
                f"Theme {theme_name} FOCUS_RING is not a string: {type(focus_ring)}"
            )

            # Basic format check (hex color)
            assert focus_ring.startswith("#") or focus_ring.startswith("rgb"), (
                f"Theme {theme_name} FOCUS_RING has invalid format: {focus_ring}"
            )


class TestThemeScrollbars:
    """Verify scrollbars meet size requirements."""

    def test_scrollbar_size(self):
        """Scrollbars should be 12px with 24px effective hit area."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        qss = Theme.get_stylesheet()

        # Check vertical scrollbar
        assert "width: 16px" in qss or "width:16px" in qss, (
            "Vertical scrollbar track should be 16px wide (12px handle + 2px padding each side)"
        )

        # Check horizontal scrollbar
        assert "height: 16px" in qss or "height:16px" in qss, (
            "Horizontal scrollbar track should be 16px tall (12px handle + 2px padding each side)"
        )

        # Check handle sizes
        assert "min-height: 12px" in qss or "min-height:12px" in qss, (
            "Vertical scrollbar handle should have min-height: 12px"
        )
        assert "min-width: 12px" in qss or "min-width:12px" in qss, (
            "Horizontal scrollbar handle should have min-width: 12px"
        )


class TestThemeSpinbox:
    """Verify spinbox buttons meet size requirements."""

    def test_spinbox_button_size(self):
        """Spinbox up/down buttons should be sized appropriately."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        qss = Theme.get_stylesheet()

        # Spinbox buttons should be 24px wide and 12px tall each
        assert "width: 24px" in qss or "width:24px" in qss, (
            "Spinbox buttons should have width: 24px"
        )
        assert "height: 12px" in qss or "height:12px" in qss, (
            "Spinbox buttons should have height: 12px"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
