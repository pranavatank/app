"""
tests/test_excel_table_enter_key.py — Test Enter/Return key behavior in ExcelTable.

Verifies:
1. Enter key emits doubleClicked signal when not in edit mode
2. Enter key commits cell edits when in edit mode (default Qt behavior)
3. F2 still works correctly and is unaffected by Enter key changes
4. Checkbox column toggling and select-all functionality works
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from ui.widgets.excel_table import ExcelTable, ExcelTableWithStats


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def excel_table_editable(qapp):
    """Create an editable ExcelTable with sample data."""
    table = ExcelTable(show_checkboxes=False, editable=True, read_only=False)
    table.setHeaders(["Col1", "Col2", "Col3"])
    table.addDataRow(["A1", "B1", "C1"])
    table.addDataRow(["A2", "B2", "C2"])
    table.addDataRow(["A3", "B3", "C3"])
    return table


@pytest.fixture
def excel_table_readonly(qapp):
    """Create a read-only ExcelTable with sample data."""
    table = ExcelTable(show_checkboxes=False, read_only=True)
    table.setHeaders(["Col1", "Col2", "Col3"])
    table.addDataRow(["Data1", "Data2", "Data3"])
    table.addDataRow(["Data4", "Data5", "Data6"])
    return table


@pytest.fixture
def excel_table_with_checkboxes(qapp):
    """Create an ExcelTable with checkboxes."""
    table = ExcelTable(show_checkboxes=True, editable=False, read_only=True)
    table.setHeaders(["Col1", "Col2", "Col3"])
    table.addDataRow(["A1", "B1", "C1"], checked=False)
    table.addDataRow(["A2", "B2", "C2"], checked=False)
    table.addDataRow(["A3", "B3", "C3"], checked=False)
    return table


class TestEnterKeyBasics:
    """Test Enter/Return key basic behavior."""

    def test_enter_key_emits_double_clicked_readonly(self, qapp, excel_table_readonly):
        """Verify Enter key emits doubleClicked signal in read-only mode."""
        # Set current cell
        excel_table_readonly.setCurrentCell(0, 0)

        # Create a spy for doubleClicked signal
        signal_spy = MagicMock()
        excel_table_readonly.doubleClicked.connect(signal_spy)

        # Simulate Enter key press
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        excel_table_readonly.keyPressEvent(key_event)

        # Verify event was accepted
        assert key_event.isAccepted(), "Enter key should be accepted"

        # Verify doubleClicked was emitted
        assert signal_spy.called, "doubleClicked signal should have been emitted"

    def test_enter_key_emits_double_clicked_editable_not_editing(self, qapp, excel_table_editable):
        """Verify Enter key emits doubleClicked in editable table when NOT in edit mode."""
        excel_table_editable.setCurrentCell(0, 0)

        signal_spy = MagicMock()
        excel_table_editable.doubleClicked.connect(signal_spy)

        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Should emit doubleClicked because we're not currently editing
        assert signal_spy.called, "doubleClicked should be emitted when not in edit mode"

    def test_enter_key_ignored_when_no_current_cell(self, qapp, excel_table_readonly):
        """Verify Enter key does nothing if there's no valid current cell."""
        # Don't set a current cell
        excel_table_readonly.setCurrentCell(-1, -1)

        signal_spy = MagicMock()
        excel_table_readonly.doubleClicked.connect(signal_spy)

        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        excel_table_readonly.keyPressEvent(key_event)

        # Should still accept the event, but not emit doubleClicked
        assert key_event.isAccepted()
        assert not signal_spy.called, "doubleClicked should not emit if currentIndex is invalid"

    def test_key_enter_same_as_key_return(self, qapp, excel_table_readonly):
        """Verify Key_Enter behaves the same as Key_Return."""
        excel_table_readonly.setCurrentCell(0, 0)

        signal_spy = MagicMock()
        excel_table_readonly.doubleClicked.connect(signal_spy)

        # Test with Key_Enter
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Enter, Qt.KeyboardModifier.NoModifier)
        excel_table_readonly.keyPressEvent(key_event)

        assert key_event.isAccepted()
        assert signal_spy.called, "Key_Enter should behave like Key_Return"


class TestEnterKeyEditMode:
    """Test Enter key behavior during cell editing."""

    def test_enter_key_in_edit_mode_uses_default_behavior(self, qapp, excel_table_editable):
        """Verify Enter in edit mode lets Qt handle it (commits edit)."""
        excel_table_editable.setCurrentCell(0, 0)

        # Mock the super().keyPressEvent to verify it's called
        original_super = type(excel_table_editable).__bases__[0].keyPressEvent
        with patch.object(type(excel_table_editable).__bases__[0], 'keyPressEvent') as mock_super:
            # Set table to EditingState to simulate being in edit mode
            excel_table_editable.setState(excel_table_editable.State.EditingState)

            key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
            excel_table_editable.keyPressEvent(key_event)

            # Verify super().keyPressEvent was called to let Qt handle the edit commit
            assert mock_super.called, "super().keyPressEvent should be called when in edit mode"


class TestCheckboxColumnClicking:
    """Test checkbox column click behavior."""

    def test_checkbox_cell_toggle_on_click(self, qapp, excel_table_with_checkboxes):
        """Verify clicking a checkbox cell toggles the checkbox."""
        # Initial state: row 0 unchecked
        initial_state = excel_table_with_checkboxes.getCheckedRows()
        assert 0 not in initial_state, "Row 0 should be unchecked initially"

        # Simulate clicking checkbox column of row 0
        excel_table_with_checkboxes._on_cell_clicked(0, 0)

        # Verify it's now checked
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert 0 in checked_rows, "Row 0 should be checked after clicking"

        # Click again to uncheck
        excel_table_with_checkboxes._on_cell_clicked(0, 0)
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert 0 not in checked_rows, "Row 0 should be unchecked after second click"

    def test_checkbox_column_not_affected_by_data_cell_click(self, qapp, excel_table_with_checkboxes):
        """Verify clicking a data cell (non-checkbox) doesn't toggle checkbox."""
        # Click column 1 (data column, not checkbox column)
        excel_table_with_checkboxes._on_cell_clicked(0, 1)

        # Checkbox state should not change
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert 0 not in checked_rows, "Clicking data cell should not toggle checkbox"


class TestCheckboxHeaderSelectAll:
    """Test select-all functionality via checkbox column header."""

    def test_header_click_checks_all_unchecked_rows(self, qapp, excel_table_with_checkboxes):
        """Verify clicking header when rows are unchecked checks all rows."""
        # All rows initially unchecked
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert len(checked_rows) == 0, "All rows should be unchecked initially"

        # Click header to select all
        excel_table_with_checkboxes._on_header_section_clicked(0)

        # All rows should now be checked
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert len(checked_rows) == excel_table_with_checkboxes.rowCount(), "All rows should be checked"

    def test_header_click_unchecks_all_checked_rows(self, qapp, excel_table_with_checkboxes):
        """Verify clicking header when rows are checked unchecks all rows."""
        # Check all rows
        excel_table_with_checkboxes._select_all_checkboxes(True)
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert len(checked_rows) == 3, "All rows should be checked"

        # Click header to uncheck all
        excel_table_with_checkboxes._on_header_section_clicked(0)

        # All rows should now be unchecked
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert len(checked_rows) == 0, "All rows should be unchecked"

    def test_header_click_checks_all_when_partially_checked(self, qapp, excel_table_with_checkboxes):
        """Verify clicking header when some rows are checked checks all rows."""
        # Check only row 0
        excel_table_with_checkboxes.setRowChecked(0, True)
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert len(checked_rows) == 1, "Only row 0 should be checked"

        # Click header (should check all since not all are checked)
        excel_table_with_checkboxes._on_header_section_clicked(0)

        # All rows should be checked
        checked_rows = excel_table_with_checkboxes.getCheckedRows()
        assert len(checked_rows) == 3, "All rows should be checked"


class TestCheckboxColumnWidth:
    """Test checkbox column width management."""

    def test_checkbox_column_width_on_init(self, qapp):
        """Verify checkbox column is set to 40px on initialization."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2"])

        # Check column 0 width
        width = table.columnWidth(0)
        assert width == 40, f"Checkbox column should be 40px, got {width}px"

    def test_checkbox_column_width_after_column_sizing(self, qapp):
        """Verify checkbox column remains 40px even after setColumnSizing is called."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2", "Col3"])

        # Apply column sizing (intentionally not specifying column 0)
        table.setColumnSizing({1: {"mode": "FIXED", "width": 100}, 2: {"mode": "STRETCH"}})

        # Column 0 should still be 40px
        width = table.columnWidth(0)
        assert width == 40, f"Checkbox column should remain 40px after setColumnSizing, got {width}px"

    def test_checkbox_column_not_affected_by_no_checkboxes_mode(self, qapp):
        """Verify checkbox column handling doesn't break when checkboxes are disabled."""
        table = ExcelTable(show_checkboxes=False, read_only=True)
        table.setHeaders(["Col1", "Col2", "Col3"])

        # Should not crash and should work normally
        assert table.columnCount() == 3
        assert table._checkbox_col == -1


class TestF2KeyUnaffected:
    """Verify F2 key behavior is unaffected by Enter key changes."""

    def test_f2_still_enters_edit_mode_editable(self, qapp, excel_table_editable):
        """Verify F2 still enters edit mode on editable tables."""
        excel_table_editable.setCurrentCell(0, 0)

        # Check that EditKeyPressed trigger is enabled
        has_edit_key_trigger = (
            excel_table_editable.editTriggers() & excel_table_editable.EditTrigger.EditKeyPressed
        ) != 0
        assert has_edit_key_trigger, "Editable table should have EditKeyPressed trigger for F2"

    def test_f2_ignored_in_readonly(self, qapp, excel_table_readonly):
        """Verify F2 is still ignored in read-only mode."""
        excel_table_readonly.setCurrentCell(0, 0)

        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
        excel_table_readonly.keyPressEvent(key_event)

        assert key_event.isAccepted(), "F2 should be accepted in read-only mode"
        assert excel_table_readonly.state() != excel_table_readonly.State.EditingState, \
            "F2 should not enter edit mode in read-only mode"

    def test_other_shortcuts_still_work(self, qapp, excel_table_editable):
        """Verify other keyboard shortcuts are unaffected."""
        excel_table_editable.selectAllCells()
        selected = excel_table_editable.selectedItems()
        assert len(selected) == 9, "Ctrl+A should still work"

        excel_table_editable.copySelection()
        clipboard_text = QApplication.clipboard().text()
        assert len(clipboard_text) > 0, "Ctrl+C should still work"


class TestEnterKeyIntegration:
    """Integration tests for Enter key with doubleClicked signal."""

    def test_enter_key_handler_receives_correct_index(self, qapp, excel_table_editable):
        """Verify doubleClicked is emitted with the correct row/column index."""
        excel_table_editable.setCurrentCell(1, 2)

        emitted_indices = []
        def capture_index(index):
            emitted_indices.append((index.row(), index.column()))

        excel_table_editable.doubleClicked.connect(capture_index)

        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        assert len(emitted_indices) == 1, "Should emit exactly one index"
        assert emitted_indices[0] == (1, 2), f"Should emit correct index (1, 2), got {emitted_indices[0]}"

    def test_enter_key_multiple_handlers(self, qapp, excel_table_readonly):
        """Verify multiple doubleClicked handlers all receive the signal."""
        excel_table_readonly.setCurrentCell(0, 0)

        handler1_called = []
        handler2_called = []

        excel_table_readonly.doubleClicked.connect(lambda idx: handler1_called.append(True))
        excel_table_readonly.doubleClicked.connect(lambda idx: handler2_called.append(True))

        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        excel_table_readonly.keyPressEvent(key_event)

        assert len(handler1_called) == 1, "First handler should be called"
        assert len(handler2_called) == 1, "Second handler should be called"
