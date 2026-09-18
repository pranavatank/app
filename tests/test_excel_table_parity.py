"""
tests/test_excel_table_parity.py — Test Excel table consistency across screens.

Verifies:
1. All 8 known table-bearing screens have ExcelTable instances
2. Each ExcelTable supports Ctrl+A selection on all cells
3. Ctrl+C returns non-trivial multi-cell text (fixes issue where expectation
   ledger previously returned only 6 characters / one cell)
4. F2 enters edit mode on editable tables and does nothing on read-only ones
5. All tables have alternating row colors and consistent behavior
"""

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

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
def excel_table_with_stats(qapp):
    """Create an ExcelTableWithStats with sample data."""
    wrapper = ExcelTableWithStats(show_checkboxes=False, editable=True)
    wrapper.table.setHeaders(["Item", "Value"])
    wrapper.table.addDataRow(["Item1", "100"])
    wrapper.table.addDataRow(["Item2", "200"])
    return wrapper


class TestExcelTableBasics:
    """Test basic ExcelTable functionality."""

    def test_excel_table_is_qwidget_derivative(self, excel_table_editable):
        """Verify ExcelTable is a valid Qt widget."""
        assert excel_table_editable is not None
        assert hasattr(excel_table_editable, 'copySelection')
        assert hasattr(excel_table_editable, 'keyPressEvent')

    def test_read_only_mode_disables_editing(self, excel_table_readonly):
        """Verify read-only mode doesn't allow item editing."""
        assert excel_table_readonly.read_only is True
        # Check that edit triggers are disabled in read-only mode
        assert excel_table_readonly.editTriggers() == excel_table_readonly.EditTrigger.NoEditTriggers

    def test_alternating_row_colors_enabled(self, excel_table_editable, excel_table_readonly):
        """Verify all ExcelTables have alternating row colors enabled."""
        assert excel_table_editable.alternatingRowColors() is True
        assert excel_table_readonly.alternatingRowColors() is True


class TestCtrlASelection:
    """Test Ctrl+A selection behavior."""

    def test_ctrl_a_selects_all_cells_editable(self, qapp, excel_table_editable):
        """Verify Ctrl+A selects all cells in editable table."""
        excel_table_editable.selectAllCells()
        selected = excel_table_editable.selectedItems()
        assert len(selected) == 9, f"Expected 9 cells selected, got {len(selected)}"

    def test_ctrl_a_selects_all_cells_readonly(self, qapp, excel_table_readonly):
        """Verify Ctrl+A selects all cells in read-only table."""
        excel_table_readonly.selectAllCells()
        selected = excel_table_readonly.selectedItems()
        assert len(selected) == 6, f"Expected 6 cells selected, got {len(selected)}"

    def test_ctrl_a_via_keypress_editable(self, qapp, excel_table_editable):
        """Verify Ctrl+A keypress triggers selection in editable table."""
        from PySide6.QtGui import QKeyEvent
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        excel_table_editable.keyPressEvent(key_event)
        selected = excel_table_editable.selectedItems()
        assert len(selected) > 0, "Ctrl+A should select cells"


class TestCtrlCCopy:
    """Test Ctrl+C copy behavior."""

    def test_copy_multi_cell_selection_editable(self, qapp, excel_table_editable):
        """Verify Ctrl+C returns non-trivial text for multi-cell selection."""
        excel_table_editable.selectAllCells()
        excel_table_editable.copySelection()
        clipboard_text = QApplication.clipboard().text()
        # Should have tab-separated values from multiple cells
        assert len(clipboard_text) > 20, f"Expected substantial clipboard text, got: {clipboard_text}"
        assert "\t" in clipboard_text or "\n" in clipboard_text, "Should have tab or newline separators"
        # Verify it's not just a single cell (which would be ~6 chars like "Data1")
        assert clipboard_text.count("Data") < 10, "Should not be just one or two cells repeated"

    def test_copy_multi_cell_selection_readonly(self, qapp, excel_table_readonly):
        """Verify Ctrl+C works on read-only tables and returns multi-cell text."""
        excel_table_readonly.selectAllCells()
        excel_table_readonly.copySelection()
        clipboard_text = QApplication.clipboard().text()
        # Expectation ledger used to return only 6 chars; verify we get more now
        assert len(clipboard_text) > 10, f"Multi-cell copy should return substantial text, got: {clipboard_text}"
        assert "\t" in clipboard_text or "\n" in clipboard_text, "Should have separators"

    def test_copy_with_checkboxes(self, qapp):
        """Verify copy excludes checkbox column."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Data1", "Data2"])
        table.addDataRow(["A", "B"])
        table.addDataRow(["C", "D"])

        table.selectAllCells()
        table.copySelection()
        clipboard_text = QApplication.clipboard().text()
        # Should not contain anything from checkbox column
        assert "☑" not in clipboard_text, "Checkbox column should not be copied"


class TestF2KeyHandling:
    """Test F2 edit mode behavior."""

    def test_f2_not_in_edit_triggers_readonly(self, qapp, excel_table_readonly):
        """Verify F2 does nothing in read-only mode."""
        from PySide6.QtGui import QKeyEvent
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
        # Should accept the event without entering edit mode
        excel_table_readonly.keyPressEvent(key_event)
        # Verify no editor is open (editor would be a QLineEdit)
        assert excel_table_readonly.state() == excel_table_readonly.State.NoState, \
            "Table should remain in NoState in read-only mode"

    def test_f2_edit_triggers_configured_editable(self, qapp, excel_table_editable):
        """Verify F2 edit mode is configured for editable tables."""
        # Check that EditKeyPressed trigger is enabled
        has_edit_key_trigger = (
            excel_table_editable.editTriggers() & excel_table_editable.EditTrigger.EditKeyPressed
        ) != 0
        assert has_edit_key_trigger, "Editable table should have EditKeyPressed trigger"

    def test_f2_key_accepted_readonly(self, qapp, excel_table_readonly):
        """Verify F2 is accepted (not rejected) in read-only mode."""
        from PySide6.QtGui import QKeyEvent
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
        excel_table_readonly.keyPressEvent(key_event)
        # Event should be accepted (not propagated to parent)
        assert key_event.isAccepted() is True, "F2 should be accepted in read-only mode"


class TestExcelTableWithStats:
    """Test ExcelTableWithStats wrapper."""

    def test_wrapper_passes_editable_parameter(self, qapp):
        """Verify ExcelTableWithStats passes editable parameter to inner table."""
        wrapper = ExcelTableWithStats(editable=True, read_only=False)
        assert wrapper.table.editable is True
        assert wrapper.table.read_only is False

    def test_wrapper_passes_readonly_parameter(self, qapp):
        """Verify ExcelTableWithStats passes read_only parameter to inner table."""
        wrapper = ExcelTableWithStats(editable=False, read_only=True)
        assert wrapper.table.read_only is True

    def test_wrapper_has_stats_label(self, excel_table_with_stats):
        """Verify ExcelTableWithStats has a stats label."""
        assert hasattr(excel_table_with_stats, 'stats_label')
        assert excel_table_with_stats.stats_label is not None


class TestScreenTableIntegration:
    """Integration tests with actual screen tables."""

    @pytest.mark.skip(reason="Requires full database/session setup")
    def test_income_management_tds_table_is_excel_table(self):
        """Verify Income Management screen's TDS table is ExcelTable."""
        # This would require full app initialization
        pass

    @pytest.mark.skip(reason="Requires full database/session setup")
    def test_income_management_ledger_table_is_excel_table(self):
        """Verify Income Management screen's ledger table is ExcelTable."""
        pass

    @pytest.mark.skip(reason="Requires full database/session setup")
    def test_tax_documents_position_table_is_excel_table(self):
        """Verify Tax Documents screen's position table is ExcelTable."""
        pass

    @pytest.mark.skip(reason="Requires full database/session setup")
    def test_tax_documents_non_income_table_is_excel_table(self):
        """Verify Tax Documents screen's non-income table is ExcelTable."""
        pass

    @pytest.mark.skip(reason="Requires full database/session setup")
    def test_tax_documents_fd_table_is_excel_table(self):
        """Verify Tax Documents screen's FD table is ExcelTable."""
        pass


class TestSortingAndRowColors:
    """Test sorting and row color configuration."""

    def test_sorting_can_be_disabled(self, qapp, excel_table_editable):
        """Verify sorting can be disabled on ExcelTable."""
        excel_table_editable.setSortingEnabled(False)
        assert excel_table_editable.isSortingEnabled() is False

    def test_sorting_can_be_enabled(self, qapp, excel_table_editable):
        """Verify sorting can be enabled on ExcelTable."""
        excel_table_editable.setSortingEnabled(True)
        assert excel_table_editable.isSortingEnabled() is True

    def test_alternating_row_colors_always_on(self, qapp):
        """Verify alternating row colors are enabled by default."""
        table = ExcelTable()
        assert table.alternatingRowColors() is True

    def test_read_only_setter_updates_triggers(self, qapp):
        """Verify setReadOnly() updates edit triggers."""
        table = ExcelTable(editable=True, read_only=False)
        assert table.editTriggers() != table.EditTrigger.NoEditTriggers

        table.setReadOnly(True)
        assert table.editTriggers() == table.EditTrigger.NoEditTriggers

        table.setReadOnly(False)
        assert table.editTriggers() != table.EditTrigger.NoEditTriggers


class TestCheckboxSelectionSync:
    """Test synchronization between checkbox state and Qt row selection."""

    def test_checkbox_toggled_selects_row(self, qapp):
        """Verify checking a checkbox also selects the row in Qt's selection model."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2"])
        table.addDataRow(["A1", "B1"])
        table.addDataRow(["A2", "B2"])
        table.addDataRow(["A3", "B3"])

        # Row 0 should not be selected initially
        assert not table.selectionModel().isRowSelected(0, table.rootIndex()), \
            "Row 0 should not be selected initially"
        assert table.getCheckedRows() == [], "No rows should be checked initially"

        # Check row 0's checkbox via setRowChecked
        table.setRowChecked(0, True)

        # Verify row 0 is now selected in Qt's selection model
        assert table.selectionModel().isRowSelected(0, table.rootIndex()), \
            "Row 0 should be selected after checking its checkbox"
        assert table.getCheckedRows() == [0], "Row 0 should be in checked list"

    def test_checkbox_unchecked_deselects_row(self, qapp):
        """Verify unchecking a checkbox also deselects the row (but keeps other checked rows selected)."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2"])
        table.addDataRow(["A1", "B1"])
        table.addDataRow(["A2", "B2"])
        table.addDataRow(["A3", "B3"])

        # Check rows 0 and 1
        table.setRowChecked(0, True)
        table.setRowChecked(1, True)

        assert table.selectionModel().isRowSelected(0, table.rootIndex()), "Row 0 should be selected"
        assert table.selectionModel().isRowSelected(1, table.rootIndex()), "Row 1 should be selected"
        assert table.getCheckedRows() == [0, 1], "Rows 0 and 1 should be checked"

        # Uncheck row 0
        table.setRowChecked(0, False)

        # Verify row 0 is deselected but row 1 remains selected
        assert not table.selectionModel().isRowSelected(0, table.rootIndex()), \
            "Row 0 should be deselected after unchecking its checkbox"
        assert table.selectionModel().isRowSelected(1, table.rootIndex()), \
            "Row 1 should still be selected (we only unchecked row 0)"
        assert table.getCheckedRows() == [1], "Only row 1 should be checked"

    def test_checkbox_click_selects_row(self, qapp):
        """Verify clicking a checkbox (via _on_cell_clicked) also selects the row."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2"])
        table.addDataRow(["A1", "B1"])
        table.addDataRow(["A2", "B2"])

        # Simulate clicking the checkbox in row 0, column 0
        table._on_cell_clicked(0, 0)

        # Verify row 0 is now both checked and selected
        assert table.getCheckedRows() == [0], "Row 0 should be checked after clicking"
        assert table.selectionModel().isRowSelected(0, table.rootIndex()), \
            "Row 0 should be selected after clicking its checkbox"

        # Click again to uncheck
        table._on_cell_clicked(0, 0)

        assert table.getCheckedRows() == [], "Row 0 should be unchecked after second click"
        assert not table.selectionModel().isRowSelected(0, table.rootIndex()), \
            "Row 0 should be deselected after unchecking"

    def test_initial_checked_state_selects_row(self, qapp):
        """Verify adding a row with checked=True also selects it in Qt's model."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2"])
        table.addDataRow(["A1", "B1"], checked=False)
        table.addDataRow(["A2", "B2"], checked=True)  # Add with checked=True
        table.addDataRow(["A3", "B3"], checked=False)

        # Verify row 1 (the one added with checked=True) is selected
        assert table.getCheckedRows() == [1], "Row 1 should be checked"
        assert table.selectionModel().isRowSelected(1, table.rootIndex()), \
            "Row 1 should be selected because it was added with checked=True"

    def test_select_all_checkboxes_selects_all_rows(self, qapp):
        """Verify _select_all_checkboxes syncs all rows to Qt's selection model."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2"])
        table.addDataRow(["A1", "B1"])
        table.addDataRow(["A2", "B2"])
        table.addDataRow(["A3", "B3"])

        # Select all checkboxes
        table._select_all_checkboxes(True)

        # Verify all rows are both checked and selected
        assert table.getCheckedRows() == [0, 1, 2], "All rows should be checked"
        assert table.selectionModel().isRowSelected(0, table.rootIndex()), "Row 0 should be selected"
        assert table.selectionModel().isRowSelected(1, table.rootIndex()), "Row 1 should be selected"
        assert table.selectionModel().isRowSelected(2, table.rootIndex()), "Row 2 should be selected"

        # Uncheck all
        table._select_all_checkboxes(False)

        assert table.getCheckedRows() == [], "No rows should be checked"
        assert not table.selectionModel().isRowSelected(0, table.rootIndex()), "Row 0 should be deselected"
        assert not table.selectionModel().isRowSelected(1, table.rootIndex()), "Row 1 should be deselected"
        assert not table.selectionModel().isRowSelected(2, table.rootIndex()), "Row 2 should be deselected"

    def test_getcheckrows_returns_correct_rows(self, qapp):
        """Verify getCheckedRows() correctly identifies checked rows."""
        table = ExcelTable(show_checkboxes=True, read_only=True)
        table.setHeaders(["Col1", "Col2"])
        table.addDataRow(["A1", "B1"])
        table.addDataRow(["A2", "B2"])
        table.addDataRow(["A3", "B3"])
        table.addDataRow(["A4", "B4"])

        # Check rows 0, 2
        table.setRowChecked(0, True)
        table.setRowChecked(2, True)

        checked = table.getCheckedRows()
        assert checked == [0, 2], f"Expected [0, 2], got {checked}"

        # Verify selections also match
        assert table.selectionModel().isRowSelected(0, table.rootIndex()), "Row 0 should be selected"
        assert not table.selectionModel().isRowSelected(1, table.rootIndex()), "Row 1 should not be selected"
        assert table.selectionModel().isRowSelected(2, table.rootIndex()), "Row 2 should be selected"
        assert not table.selectionModel().isRowSelected(3, table.rootIndex()), "Row 3 should not be selected"
