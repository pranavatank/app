"""
Tests for theme border-radius scale compliance.
Validates that all border-radius values in the built QSS conform to the 4-step scale:
  RADIUS_CONTROL = 8px
  RADIUS_CARD = 12px
  RADIUS_MODAL = 16px
  RADIUS_PILL = 999px
"""

import re
import pytest
from ui.theme.theme import Theme
from ui.theme.theme_manager import ThemeManager


class TestThemeRadiusScale:
    """Verify that all themes use only the 4-step radius scale."""

    # Valid radius values in the scale (in pixels)
    VALID_RADII = {8, 12, 16, 999}

    def test_all_themes_use_radius_scale(self):
        """Each theme's stylesheet must use only the 4-step radius scale."""
        for theme_name in ThemeManager.theme_names():
            # Apply the theme to get its colors
            ThemeManager.apply(theme_name, save=False, notify=False)

            # Get the generated stylesheet
            qss = Theme.get_stylesheet()

            # Extract all border-radius values from the QSS
            # Pattern: border-radius: XXXpx
            radius_pattern = r'border-radius:\s*(\d+)px'
            matches = re.findall(radius_pattern, qss, re.IGNORECASE)

            # Verify all found values are in the valid set
            assert matches, (
                f"Theme {theme_name} has no border-radius values in stylesheet"
            )

            for match in matches:
                radius_value = int(match)
                assert radius_value in self.VALID_RADII, (
                    f"Theme {theme_name} has invalid border-radius: {radius_value}px. "
                    f"Must be one of: {sorted(self.VALID_RADII)}"
                )

    def test_radius_constants_are_defined(self):
        """Verify that all 4 radius constants are defined in Theme."""
        assert hasattr(Theme, 'RADIUS_CONTROL'), "Theme.RADIUS_CONTROL not defined"
        assert hasattr(Theme, 'RADIUS_CARD'), "Theme.RADIUS_CARD not defined"
        assert hasattr(Theme, 'RADIUS_MODAL'), "Theme.RADIUS_MODAL not defined"
        assert hasattr(Theme, 'RADIUS_PILL'), "Theme.RADIUS_PILL not defined"

        # Verify values match the expected scale
        assert Theme.RADIUS_CONTROL == 8, f"RADIUS_CONTROL should be 8, got {Theme.RADIUS_CONTROL}"
        assert Theme.RADIUS_CARD == 12, f"RADIUS_CARD should be 12, got {Theme.RADIUS_CARD}"
        assert Theme.RADIUS_MODAL == 16, f"RADIUS_MODAL should be 16, got {Theme.RADIUS_MODAL}"
        assert Theme.RADIUS_PILL == 999, f"RADIUS_PILL should be 999, got {Theme.RADIUS_PILL}"

    def test_aurora_theme_radius_distribution(self):
        """Verify Aurora theme uses all 4 radius scales appropriately."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        qss = Theme.get_stylesheet()

        # Extract all radius values and their counts
        radius_pattern = r'border-radius:\s*(\d+)px'
        matches = re.findall(radius_pattern, qss, re.IGNORECASE)
        radius_counts = {}
        for match in matches:
            r = int(match)
            radius_counts[r] = radius_counts.get(r, 0) + 1

        # Verify at least some use of each scale step
        for radius in [8, 12, 16, 999]:
            assert radius in radius_counts, (
                f"Aurora theme does not use border-radius: {radius}px"
            )

        # Log the distribution for verification
        for radius in sorted(radius_counts.keys()):
            count = radius_counts[radius]
            print(f"  Aurora theme: {count} uses of {radius}px")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
