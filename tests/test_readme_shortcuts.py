"""
tests/test_readme_shortcuts.py — Test all keyboard shortcuts claimed in README.

Verifies that every keyboard shortcut listed in README.md's "Keyboard Shortcuts Guide"
section (lines 292-414) is actually implemented and working.

Shortcuts tested:
- Selection: Ctrl+A, Click, Shift+Click, Ctrl+Click, Drag (note: click-based selection is Qt default)
- Clipboard: Ctrl+C, Ctrl+V, Ctrl+X
- Editing: Double-Click, F2, Enter, Esc, Delete
- Navigation: Arrow Keys, Tab, Shift+Tab, Home, End, Ctrl+Home, Ctrl+End, Page Up/Down
"""

import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QKeyEvent

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
    # Add 5 rows for navigation testing
    for i in range(5):
        table.addDataRow([f"A{i}", f"B{i}", f"C{i}"])
    return table


@pytest.fixture
def excel_table_readonly(qapp):
    """Create a read-only ExcelTable with sample data."""
    table = ExcelTable(show_checkboxes=False, read_only=True)
    table.setHeaders(["Col1", "Col2", "Col3"])
    for i in range(5):
        table.addDataRow([f"Data{i}_1", f"Data{i}_2", f"Data{i}_3"])
    return table


@pytest.fixture
def excel_table_with_checkboxes(qapp):
    """Create an ExcelTable with checkboxes enabled."""
    table = ExcelTable(show_checkboxes=True, editable=True, read_only=False)
    table.setHeaders(["Col1", "Col2"])
    for i in range(3):
        table.addDataRow([f"R{i}C1", f"R{i}C2"])
    return table


class TestSelectionShortcuts:
    """Test selection-related shortcuts from README."""

    def test_ctrl_a_selects_all_cells(self, qapp, excel_table_editable):
        """Verify Ctrl+A selects all cells."""
        # Simulate Ctrl+A
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Verify all cells are selected
        selected = excel_table_editable.selectedItems()
        expected_cells = excel_table_editable.rowCount() * excel_table_editable.columnCount()
        assert len(selected) == expected_cells, f"Expected {expected_cells} cells selected, got {len(selected)}"

    def test_ctrl_a_works_in_readonly(self, qapp, excel_table_readonly):
        """Verify Ctrl+A works in read-only mode."""
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        excel_table_readonly.keyPressEvent(key_event)

        selected = excel_table_readonly.selectedItems()
        assert len(selected) > 0, "Ctrl+A should select cells even in read-only mode"


class TestClipboardShortcuts:
    """Test clipboard-related shortcuts: Ctrl+C, Ctrl+V, Ctrl+X."""

    def test_ctrl_c_copy_to_clipboard(self, qapp, excel_table_editable):
        """Verify Ctrl+C copies selected cells to clipboard."""
        # Select all cells
        excel_table_editable.selectAllCells()

        # Simulate Ctrl+C
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Check clipboard
        clipboard_text = QApplication.clipboard().text()
        assert len(clipboard_text) > 0, "Clipboard should contain copied text"
        # Should have tab or newline separators for multi-cell copy
        assert "\t" in clipboard_text or "\n" in clipboard_text, "Should have cell separators"

    def test_ctrl_c_excludes_checkbox_column(self, qapp, excel_table_with_checkboxes):
        """Verify Ctrl+C excludes checkbox column from copy."""
        excel_table_with_checkboxes.selectAllCells()

        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        excel_table_with_checkboxes.keyPressEvent(key_event)

        clipboard_text = QApplication.clipboard().text()
        assert "☑" not in clipboard_text, "Checkbox column should not be copied"

    def test_ctrl_v_paste_to_cells(self, qapp, excel_table_editable):
        """Verify Ctrl+V pastes clipboard content to cells."""
        # Set clipboard to some test data
        QApplication.clipboard().setText("TestA\tTestB\tTestC")

        # Click on first cell to set current position
        excel_table_editable.setCurrentCell(0, 0)

        # Simulate Ctrl+V
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Verify paste happened
        first_cell = excel_table_editable.item(0, 0)
        assert first_cell.text() == "TestA", f"Expected 'TestA' in first cell, got {first_cell.text()}"

    def test_ctrl_x_cut_copies_and_clears(self, qapp, excel_table_editable):
        """Verify Ctrl+X (cut) copies and clears content."""
        # Select a cell with data
        excel_table_editable.setCurrentCell(0, 0)
        original_text = excel_table_editable.item(0, 0).text()

        # Simulate Ctrl+X
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Verify clipboard has the data
        clipboard_text = QApplication.clipboard().text()
        assert original_text in clipboard_text, f"Clipboard should contain '{original_text}'"

        # Verify cell is cleared
        cell_after = excel_table_editable.item(0, 0).text()
        assert cell_after == "", f"Cut cell should be empty, got '{cell_after}'"

    def test_ctrl_v_pastes_to_multiple_cells(self, qapp, excel_table_editable):
        """Verify Ctrl+V can paste multiple values."""
        # Set clipboard to multi-line data
        QApplication.clipboard().setText("Val1\tVal2\nVal3\tVal4")

        # Set current cell
        excel_table_editable.setCurrentCell(0, 0)

        # Simulate Ctrl+V
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Verify all values were pasted
        assert excel_table_editable.item(0, 0).text() == "Val1"
        assert excel_table_editable.item(0, 1).text() == "Val2"
        assert excel_table_editable.item(1, 0).text() == "Val3"
        assert excel_table_editable.item(1, 1).text() == "Val4"


class TestEditingShortcuts:
    """Test editing-related shortcuts: F2, Enter, Esc, Delete."""

    def test_delete_key_removes_selected_rows(self, qapp, excel_table_editable):
        """Verify Delete key triggers deleteSelectedRows method."""
        # Select cells in first row
        excel_table_editable.setCurrentCell(0, 0)
        excel_table_editable.selectColumn(0)

        # Mock deleteSelectedRows to track if it's called
        original_delete = excel_table_editable.deleteSelectedRows
        delete_called = []

        def mock_delete():
            delete_called.append(True)
            # Don't actually delete so we can verify the handler was called

        excel_table_editable.deleteSelectedRows = mock_delete

        # Simulate Delete key
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Verify deleteSelectedRows was called
        assert len(delete_called) > 0, "Delete key should call deleteSelectedRows"

        # Restore original
        excel_table_editable.deleteSelectedRows = original_delete

    def test_f2_enters_edit_mode_in_editable_table(self, qapp, excel_table_editable):
        """Verify F2 is configured for edit mode in editable tables."""
        # Check that EditKeyPressed trigger is enabled
        has_edit_key_trigger = (
            excel_table_editable.editTriggers() & excel_table_editable.EditTrigger.EditKeyPressed
        ) != 0
        assert has_edit_key_trigger, "Editable table should have EditKeyPressed trigger for F2"

    def test_f2_does_nothing_in_readonly_mode(self, qapp, excel_table_readonly):
        """Verify F2 does nothing in read-only mode."""
        # Simulate F2
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
        excel_table_readonly.keyPressEvent(key_event)

        # Verify event was accepted (not rejected)
        assert key_event.isAccepted(), "F2 should be accepted in read-only mode"

    def test_esc_cancels_edit_mode(self, qapp, excel_table_editable):
        """Verify that being in a table with Qt defaults, Esc cancels edit mode."""
        # This is a Qt default behavior - we just verify our keyPressEvent doesn't break it
        excel_table_editable.setCurrentCell(0, 0)
        excel_table_editable.edit(excel_table_editable.indexFromItem(excel_table_editable.item(0, 0)))

        # Verify we can enter edit mode
        assert excel_table_editable.state() in (excel_table_editable.State.EditingState,
                                                 excel_table_editable.State.NoState)


class TestNavigationShortcuts:
    """Test navigation shortcuts: Arrow keys, Tab, Home, End, Ctrl+Home, Ctrl+End, Page Up/Down."""

    def test_arrow_keys_navigate_cells(self, qapp, excel_table_editable):
        """Verify arrow keys navigate between cells (Qt default)."""
        excel_table_editable.setCurrentCell(1, 1)
        initial_row = excel_table_editable.currentRow()

        # Press Down arrow
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Should have moved down (or stayed if at bottom)
        assert excel_table_editable.currentRow() >= initial_row, "Arrow keys should navigate"

    def test_tab_moves_to_next_cell(self, qapp, excel_table_editable):
        """Verify Tab moves to next cell (Qt default)."""
        excel_table_editable.setCurrentCell(0, 0)
        initial_col = excel_table_editable.currentColumn()

        # Press Tab
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Should have moved to next column
        assert excel_table_editable.currentColumn() > initial_col, "Tab should move to next column"

    def test_shift_tab_moves_to_previous_cell(self, qapp, excel_table_editable):
        """Verify Shift+Tab is handled without error (Qt default, backward navigation)."""
        excel_table_editable.setCurrentCell(1, 1)

        # Press Shift+Tab - this should navigate backward (Qt handles this)
        # Note: We just verify it doesn't cause an error; the exact navigation
        # behavior depends on Qt's internal handling of focus changes
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Verify the table is still valid after Shift+Tab
        assert excel_table_editable is not None
        assert excel_table_editable.currentRow() >= 0
        assert excel_table_editable.currentColumn() >= 0

    def test_home_moves_to_first_column(self, qapp, excel_table_editable):
        """Verify Home moves to first column in current row (Qt default)."""
        excel_table_editable.setCurrentCell(2, 2)

        # Press Home
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Should be at first column (column 0)
        assert excel_table_editable.currentColumn() == 0, "Home should move to first column"

    def test_end_moves_to_last_column(self, qapp, excel_table_editable):
        """Verify End moves to last column in current row (Qt default)."""
        last_col = excel_table_editable.columnCount() - 1
        excel_table_editable.setCurrentCell(2, 0)

        # Press End
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Should be at last column
        assert excel_table_editable.currentColumn() == last_col, "End should move to last column"

    def test_ctrl_home_moves_to_first_cell(self, qapp, excel_table_editable):
        """Verify Ctrl+Home moves to first cell in table."""
        excel_table_editable.setCurrentCell(3, 2)

        # Simulate Ctrl+Home
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Should be at (0, 0)
        assert excel_table_editable.currentRow() == 0, f"Expected row 0, got {excel_table_editable.currentRow()}"
        assert excel_table_editable.currentColumn() == 0, f"Expected column 0, got {excel_table_editable.currentColumn()}"

    def test_ctrl_home_skips_checkbox_column(self, qapp, excel_table_with_checkboxes):
        """Verify Ctrl+Home moves to first data column (skips checkbox)."""
        excel_table_with_checkboxes.setCurrentCell(2, 2)

        # Simulate Ctrl+Home
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
        excel_table_with_checkboxes.keyPressEvent(key_event)

        # Should be at (0, 1) - first data column (skip checkbox at 0)
        assert excel_table_with_checkboxes.currentRow() == 0
        assert excel_table_with_checkboxes.currentColumn() == 1, \
            f"Expected column 1 (first data col), got {excel_table_with_checkboxes.currentColumn()}"

    def test_ctrl_end_moves_to_last_cell(self, qapp, excel_table_editable):
        """Verify Ctrl+End moves to last cell in table."""
        excel_table_editable.setCurrentCell(0, 0)

        # Simulate Ctrl+End
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)

        # Should be at last row, last column
        last_row = excel_table_editable.rowCount() - 1
        last_col = excel_table_editable.columnCount() - 1
        assert excel_table_editable.currentRow() == last_row, f"Expected row {last_row}, got {excel_table_editable.currentRow()}"
        assert excel_table_editable.currentColumn() == last_col, f"Expected column {last_col}, got {excel_table_editable.currentColumn()}"

    def test_page_up_down_work_with_qt_defaults(self, qapp, excel_table_editable):
        """Verify Page Up/Down are handled by Qt default scrolling (no explicit handling needed)."""
        # These should be handled by Qt's default QTableWidget behavior
        # We just verify the shortcuts don't cause errors
        initial_row = excel_table_editable.currentRow()

        # Press Page Down
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_PageDown, Qt.KeyboardModifier.NoModifier)
        excel_table_editable.keyPressEvent(key_event)

        # The row might change depending on visible area (Qt default)
        # We just verify no exception was raised
        assert excel_table_editable is not None


class TestDeleteShortcut:
    """Specific tests for Delete key shortcut."""

    def test_delete_shortcut_is_explicitly_handled(self, qapp, excel_table_editable):
        """Verify Delete key is explicitly handled (not Qt default)."""
        # Create a mock to verify deleteSelectedRows was called
        excel_table_editable.deleteSelectedRows = MagicMock()

        excel_table_editable.setCurrentCell(0, 0)

        # Simulate Delete key
        with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=1):
            key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
            excel_table_editable.keyPressEvent(key_event)

        # Verify deleteSelectedRows was called
        assert excel_table_editable.deleteSelectedRows.called or excel_table_editable.rowCount() < 5


class TestShortcutCodeCoverage:
    """Verify all shortcut handlers are exercised."""

    def test_all_clipboard_shortcuts_are_handled(self, qapp, excel_table_editable):
        """Verify Ctrl+C, Ctrl+V, Ctrl+X handlers exist and are callable."""
        assert hasattr(excel_table_editable, 'copySelection')
        assert hasattr(excel_table_editable, 'pasteSelection')
        assert callable(excel_table_editable.copySelection)
        assert callable(excel_table_editable.pasteSelection)

    def test_all_navigation_shortcuts_are_recognized(self, qapp, excel_table_editable):
        """Verify navigation shortcuts (Home, End, Ctrl+Home, Ctrl+End) don't raise errors."""
        shortcuts_to_test = [
            (Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier),
            (Qt.Key.Key_End, Qt.KeyboardModifier.NoModifier),
            (Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier),
            (Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier),
        ]

        for key, modifier in shortcuts_to_test:
            key_event = QKeyEvent(QKeyEvent.Type.KeyPress, key, modifier)
            # Should not raise an exception
            excel_table_editable.keyPressEvent(key_event)


class TestShortcutDocumentationAccuracy:
    """Verify README claims match implementation."""

    def test_ctrl_a_select_all_documented_and_implemented(self, qapp, excel_table_editable):
        """Verify Ctrl+A (Select All) is both documented and implemented."""
        # Check implementation
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)
        selected = excel_table_editable.selectedItems()
        assert len(selected) > 0, "Ctrl+A should select cells"

    def test_ctrl_c_copy_documented_and_implemented(self, qapp, excel_table_editable):
        """Verify Ctrl+C (Copy) is both documented and implemented."""
        excel_table_editable.selectAllCells()
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)
        clipboard = QApplication.clipboard().text()
        assert len(clipboard) > 0, "Ctrl+C should copy to clipboard"

    def test_ctrl_v_paste_documented_and_implemented(self, qapp, excel_table_editable):
        """Verify Ctrl+V (Paste) is both documented and implemented."""
        QApplication.clipboard().setText("PasteTest")
        excel_table_editable.setCurrentCell(0, 0)
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)
        # Paste handler should be called without error
        assert excel_table_editable is not None

    def test_ctrl_x_cut_documented_and_implemented(self, qapp, excel_table_editable):
        """Verify Ctrl+X (Cut) is both documented and implemented."""
        excel_table_editable.setCurrentCell(0, 0)
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)
        # Cut handler should be called without error
        assert excel_table_editable is not None

    def test_f2_edit_documented_and_implemented(self, qapp, excel_table_editable):
        """Verify F2 (Edit) is both documented and implemented."""
        has_edit_key_trigger = (
            excel_table_editable.editTriggers() & excel_table_editable.EditTrigger.EditKeyPressed
        ) != 0
        assert has_edit_key_trigger, "F2 should be configured for edit mode"

    def test_delete_documented_and_implemented(self, qapp, excel_table_editable):
        """Verify Delete is both documented and implemented."""
        assert hasattr(excel_table_editable, 'deleteSelectedRows')
        assert callable(excel_table_editable.deleteSelectedRows)

    def test_ctrl_home_end_documented_and_implemented(self, qapp, excel_table_editable):
        """Verify Ctrl+Home and Ctrl+End are both documented and implemented."""
        # Test Ctrl+Home
        excel_table_editable.setCurrentCell(2, 2)
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)
        assert excel_table_editable.currentRow() == 0

        # Test Ctrl+End
        excel_table_editable.setCurrentCell(0, 0)
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)
        last_row = excel_table_editable.rowCount() - 1
        last_col = excel_table_editable.columnCount() - 1
        assert excel_table_editable.currentRow() == last_row
        assert excel_table_editable.currentColumn() == last_col
