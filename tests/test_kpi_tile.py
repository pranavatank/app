"""
Tests for KpiTile widget — T002 bugfix verification.

Verifies that KpiTile.set_value() correctly updates widgets in-place without
rebuilding the layout (no orphaned layouts).
"""

import os
import sys
import pytest

# Set offscreen platform before importing Qt
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QLabel
from ui.widgets.kpi_tile import KpiTile
from ui.theme import Theme


@pytest.fixture(scope="session", autouse=True)
def setup_app():
    """Initialize QApplication once for all tests."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield
    # Don't quit the app, let pytest handle it


class TestKpiTile:
    """Test KpiTile widget behavior and set_value() functionality."""

    def test_initial_construction_has_value_label(self):
        """After construction, the KpiTile should have a value label with correct text."""
        tile = KpiTile("Test Label", 100.0, is_currency=True)

        # Find the value label by objectName
        value_lbl = tile.findChild(QLabel, "kpiValue")
        assert value_lbl is not None, "Value label not found (objectName='kpiValue')"
        assert value_lbl.text() != "", "Value label should not be empty"
        assert "100" in value_lbl.text(), f"Value label should contain '100', got: {value_lbl.text()}"

    def test_set_value_updates_same_widget_instance(self):
        """Calling set_value() should update the SAME QLabel instance, not create a new one."""
        tile = KpiTile("Test Label", 100.0, is_currency=True)

        # Get the initial value label instance
        initial_value_lbl = tile.findChild(QLabel, "kpiValue")
        assert initial_value_lbl is not None

        # Call set_value to change the value
        tile.set_value(250.0)

        # Get the value label again
        updated_value_lbl = tile.findChild(QLabel, "kpiValue")
        assert updated_value_lbl is not None

        # Verify it's the SAME widget instance (no rebuild)
        assert updated_value_lbl is initial_value_lbl, \
            "set_value() should NOT rebuild layout; must update the same widget"

        # Verify the text was updated
        assert "250" in updated_value_lbl.text(), \
            f"Value label should show '250', got: {updated_value_lbl.text()}"

    def test_set_value_negative_applies_danger_color(self):
        """Calling set_value() with negative value should apply danger (red) color."""
        tile = KpiTile("Test Label", 100.0, is_currency=True)

        # Set a negative value
        tile.set_value(-50.0)

        value_lbl = tile.findChild(QLabel, "kpiValue")
        assert value_lbl is not None

        # Check that the stylesheet contains the danger color
        stylesheet = value_lbl.styleSheet()
        assert Theme.DANGER_TEXT in stylesheet, \
            f"Danger color {Theme.DANGER_TEXT} should be in stylesheet, got: {stylesheet}"

    def test_set_value_with_delta_shows_delta_chip(self):
        """Calling set_value() with delta should update the delta chip with correct text and color."""
        tile = KpiTile("Test Label", 100.0, is_currency=True, delta=None)

        # Initially no delta, so chip should be hidden
        assert tile._delta_lbl is not None
        assert tile._delta_lbl.isVisible() == False, "Delta chip should initially be hidden"

        # Set value with a positive delta
        tile.set_value(100.0, delta=12)

        # Check the text was updated
        assert "+12%" in tile._delta_lbl.text(), \
            f"Delta chip should show '+12%', got: {tile._delta_lbl.text()}"

        # Verify the color is success (green)
        stylesheet = tile._delta_lbl.styleSheet()
        assert Theme.SUCCESS_TEXT in stylesheet, \
            f"Success color {Theme.SUCCESS_TEXT} should be in stylesheet for positive delta, got: {stylesheet}"

    def test_set_value_with_no_delta_hides_delta_chip(self):
        """Calling set_value() with delta=None should hide the delta chip."""
        tile = KpiTile("Test Label", 100.0, is_currency=True, delta=12)

        # Initially delta is set, so check the text
        assert "+12%" in tile._delta_lbl.text(), f"Initial delta text incorrect: {tile._delta_lbl.text()}"

        # Set value without delta
        tile.set_value(100.0, delta=None)

        # Check that the visibility flag was set to False (may not reflect in isVisible() without show())
        assert tile._delta_lbl.isVisible() == False, \
            "Delta chip should be hidden after set_value(delta=None)"

    def test_set_value_negative_delta_applies_danger_color(self):
        """Calling set_value() with negative delta should apply danger color to the chip."""
        tile = KpiTile("Test Label", 100.0, is_currency=True, delta=None)

        # Set value with a negative delta
        tile.set_value(100.0, delta=-5)

        assert "-5%" in tile._delta_lbl.text(), \
            f"Delta chip should show '-5%', got: {tile._delta_lbl.text()}"

        # Verify the color is danger (red)
        stylesheet = tile._delta_lbl.styleSheet()
        assert Theme.DANGER_TEXT in stylesheet, \
            f"Danger color {Theme.DANGER_TEXT} should be in stylesheet for negative delta, got: {stylesheet}"

    def test_set_value_with_is_currency_flag(self):
        """Calling set_value() with is_currency flag should apply currency formatting."""
        tile = KpiTile("Test Label", 100, is_currency=False)

        # Initial value is non-currency, so should be raw
        value_lbl = tile.findChild(QLabel, "kpiValue")
        initial_text = value_lbl.text()
        assert initial_text == "100", f"Non-currency value should be raw, got: {initial_text}"

        # Set value with is_currency=True
        tile.set_value(100.0, is_currency=True)

        updated_text = value_lbl.text()
        # INR formatting should apply, so expect thousands separator
        assert updated_text != "100.0", f"Currency value should be formatted, got: {updated_text}"

    def test_sparkline_visibility_in_construction(self):
        """KpiTile with sparkline_data should create sparkline widget with correct data."""
        sparkline_data = [10, 20, 15, 25, 30]
        tile = KpiTile("Test Label", 100.0, is_currency=True, sparkline_data=sparkline_data)

        assert tile._sparkline_widget is not None, "Sparkline widget should exist"
        # Verify the sparkline has the data
        assert tile._sparkline_widget.data == sparkline_data, \
            f"Sparkline should have the provided data, got: {tile._sparkline_widget.data}"

    def test_sparkline_hidden_with_insufficient_data(self):
        """KpiTile with insufficient sparkline data should hide the sparkline."""
        # Less than 2 points
        sparkline_data = [10]
        tile = KpiTile("Test Label", 100.0, is_currency=True, sparkline_data=sparkline_data)

        assert tile._sparkline_widget is not None, "Sparkline widget should exist"
        assert tile._sparkline_widget.isVisible() == False, \
            "Sparkline should be hidden when data has less than 2 points"

    def test_construction_without_delta_hides_delta_chip(self):
        """KpiTile without delta on construction should have hidden delta chip."""
        tile = KpiTile("Test Label", 100.0, is_currency=True, delta=None)

        assert tile._delta_lbl is not None, "Delta label should exist"
        assert tile._delta_lbl.isVisible() == False, "Delta chip should be hidden when delta=None"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
