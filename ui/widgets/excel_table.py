"""
ui/widgets/excel_table.py — Excel-like table with copy/paste, selection, stats.
"""

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QCheckBox, QWidget,
    QHBoxLayout, QLabel, QHeaderView, QApplication, QMessageBox,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QKeyEvent
from ui.theme import Theme


class NoFocusRectDelegate(QStyledItemDelegate):
    """
    1) Strips the native focus-rectangle state before painting a
       selected/non-editing cell — QSS alone (`outline: none` / `border:
       none` on `::item:selected:focus`) doesn't reliably suppress the
       platform style's own dotted/solid focus border.
    2) Gives the actual in-place editor (a QLineEdit Qt spawns on top of
       the cell while typing) a borderless, zero-radius, minimal-padding
       style instead of letting it inherit the app's global QLineEdit QSS
       (1.5-2px border + 10px radius + 8-12px padding) — in a normal-width
       table cell that border/padding eats into the text, which is the
       "cursor shows but the border hides the text" bug.
    """

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        if opt.state & QStyle.StateFlag.State_HasFocus:
            opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, opt, index)

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Theme.SURFACE};
                    color: {Theme.TEXT_PRIMARY};
                    border: 1px solid {Theme.PRIMARY};
                    border-radius: 0px;
                    padding: 0px 8px;
                    selection-background-color: {Theme.PRIMARY_LIGHT};
                    selection-color: {Theme.PRIMARY_DARK};
                }}
            """)
        return editor


class ExcelTable(QTableWidget):
    """Table with Excel-like features: cell/row selection, copy/paste, checkboxes, stats."""
    
    selectionStatsChanged = pyqtSignal(str)  # Emits stats text
    cellDataChanged = pyqtSignal()  # Emits when data is pasted/changed
    deleteRequested = pyqtSignal()  # Emits when Delete key pressed
    
    def __init__(self, parent=None, show_checkboxes=True, editable=False):
        super().__init__(parent)
        self.show_checkboxes = show_checkboxes
        self.editable = editable
        self._checkbox_col = 0 if show_checkboxes else -1
        self._numeric_cols: set[int] = set()
        self._setup_table()

    def setNumericColumns(self, cols) -> None:
        """Restrict which column indices (post-checkbox-offset) must contain
        a numeric value when pasted into. Non-numeric pasted text into these
        columns is rejected (cell left unchanged) instead of silently
        accepted as text. Default is empty — no restriction, unchanged
        behavior for any screen that doesn't opt in."""
        self._numeric_cols = set(cols or [])

    def _paste_allowed(self, col: int, cleaned_value: str) -> bool:
        """Whether a cleaned pasted value may be written into this column."""
        if col not in self._numeric_cols:
            return True
        if cleaned_value == "":
            return True  # blank always allowed — clears the cell
        try:
            float(cleaned_value)
            return True
        except ValueError:
            return False
        
    def _setup_table(self):
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setItemDelegate(NoFocusRectDelegate(self))
        self.itemSelectionChanged.connect(self._update_stats)
        
    def setHeaders(self, headers: list[str]):
        """Set headers with optional checkbox column."""
        if self.show_checkboxes:
            self.setColumnCount(len(headers) + 1)
            self.setHorizontalHeaderLabels(["☑"] + headers)
            self.setColumnWidth(0, 40)
        else:
            self.setColumnCount(len(headers))
            self.setHorizontalHeaderLabels(headers)
            
    def addDataRow(self, row_data: list, user_data=None, checked=False, editable_cols=None):
        """Add row with optional checkbox and user data.
        
        Args:
            row_data: List of cell values
            user_data: Data to store in first data column
            checked: Initial checkbox state
            editable_cols: List of column indices that should be editable (None = all editable if self.editable)
        """
        r = self.rowCount()
        self.insertRow(r)
        
        col_offset = 1 if self.show_checkboxes else 0
        
        if self.show_checkboxes:
            cb = QCheckBox()
            cb.setChecked(checked)
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(r, 0, cb_widget)
            
        for col, value in enumerate(row_data):
            item = QTableWidgetItem(str(value) if value is not None else "—")
            if user_data is not None and col == 0:
                item.setData(Qt.ItemDataRole.UserRole, user_data)
            
            # Set editable flag
            if self.editable:
                if editable_cols is None or col in editable_cols:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
            self.setItem(r, col + col_offset, item)
            
    def getCheckedRows(self) -> list[int]:
        """Return list of checked row indices."""
        if not self.show_checkboxes:
            return []
        checked = []
        for r in range(self.rowCount()):
            widget = self.cellWidget(r, 0)
            if widget:
                cb = widget.findChild(QCheckBox)
                if cb and cb.isChecked():
                    checked.append(r)
        return checked
    
    def setRowChecked(self, row: int, checked: bool):
        """Set checkbox state for a row."""
        if not self.show_checkboxes or row >= self.rowCount():
            return
        widget = self.cellWidget(row, 0)
        if widget:
            cb = widget.findChild(QCheckBox)
            if cb:
                cb.setChecked(checked)
                
    def selectAllRows(self):
        """Select all rows."""
        self.selectAll()
        
    def selectAllCells(self):
        """Select all cells (Ctrl+A)."""
        self.selectAll()
        
    def deleteSelectedRows(self):
        """Delete selected rows."""
        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            return
            
        reply = QMessageBox.question(
            self,
            "Delete Rows",
            f"Delete {len(selected_rows)} selected row(s)?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for row in sorted(selected_rows, reverse=True):
                self.removeRow(row)
            self.deleteRequested.emit()
        
    def copySelection(self):
        """Copy selected cells to clipboard (TSV format)."""
        selection = self.selectedRanges()
        if not selection:
            return
            
        rows_data = {}
        for rng in selection:
            for row in range(rng.topRow(), rng.bottomRow() + 1):
                if row not in rows_data:
                    rows_data[row] = {}
                for col in range(rng.leftColumn(), rng.rightColumn() + 1):
                    if self.show_checkboxes and col == 0:
                        continue
                    item = self.item(row, col)
                    rows_data[row][col] = item.text() if item else ""
                    
        if not rows_data:
            return
            
        lines = []
        for row in sorted(rows_data.keys()):
            cols = rows_data[row]
            line = "\t".join(cols.get(c, "") for c in sorted(cols.keys()))
            lines.append(line)
            
        QApplication.clipboard().setText("\n".join(lines))
        
    def pasteSelection(self):
        """Paste from clipboard to selected cells with smart data cleaning.
        
        Supports two modes:
        1. Single value to multiple cells: If clipboard has one value and multiple cells selected,
           paste that value to all selected cells
        2. Range paste: If clipboard has multiple values, paste starting from current cell
        """
        clipboard = QApplication.clipboard().text()
        if not clipboard:
            return
        
        # Get selected cells
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        # Check if clipboard contains single value or multiple values
        lines = [line for line in clipboard.split("\n") if line.strip()]
        
        # Mode 1: Single value to multiple selected cells
        if len(lines) == 1 and "\t" not in lines[0]:
            # Single value - paste to all selected editable cells
            cleaned_value = self._clean_paste_value(lines[0])
            pasted_count = 0
            rejected = 0

            for item in selected_items:
                if self.show_checkboxes and item.column() == 0:
                    continue
                if item and (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    if not self._paste_allowed(item.column(), cleaned_value):
                        rejected += 1
                        continue
                    item.setText(cleaned_value)
                    pasted_count += 1

            if pasted_count > 0:
                self.cellDataChanged.emit()
            if rejected > 0:
                QMessageBox.warning(self, "Paste Skipped",
                    f"{rejected} cell(s) skipped — that column requires a numeric value.")
            return
        
        # Mode 2: Range paste (original behavior)
        current = self.currentItem()
        if not current:
            return
            
        start_row = current.row()
        start_col = current.column()
        
        if self.show_checkboxes and start_col == 0:
            start_col = 1
            
        pasted_count = 0
        rejected = 0

        for r_offset, line in enumerate(lines):
            if not line.strip():
                continue
            cells = line.split("\t")
            for c_offset, value in enumerate(cells):
                row = start_row + r_offset
                col = start_col + c_offset
                if row >= self.rowCount() or col >= self.columnCount():
                    continue
                if self.show_checkboxes and col == 0:
                    continue
                item = self.item(row, col)
                if item and (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    # Clean the value
                    cleaned_value = self._clean_paste_value(value)
                    if not self._paste_allowed(col, cleaned_value):
                        rejected += 1
                        continue
                    item.setText(cleaned_value)
                    pasted_count += 1

        if pasted_count > 0:
            self.cellDataChanged.emit()
        if rejected > 0:
            QMessageBox.warning(self, "Paste Skipped",
                f"{rejected} cell(s) skipped — that column requires a numeric value.")
            
    def _clean_paste_value(self, value: str) -> str:
        """Clean pasted value by removing common formatting."""
        if not value:
            return ""
        
        # Remove common currency symbols and formatting
        cleaned = value.strip()
        
        # Remove currency symbols
        cleaned = cleaned.replace("₹", "").replace("$", "").replace("€", "").replace("£", "")
        
        # Remove percentage sign (but keep the number)
        if "%" in cleaned:
            cleaned = cleaned.replace("%", "").strip()
        
        # Remove commas from numbers
        if cleaned.replace(",", "").replace(".", "").replace("-", "").isdigit():
            cleaned = cleaned.replace(",", "")
        
        # Handle special markers
        if cleaned in ["—", "–", "-", "N/A", "n/a", "NA", "na"]:
            return ""
            
        return cleaned.strip()
            
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts."""
        # Ctrl+C - Copy
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copySelection()
            event.accept()
        # Ctrl+V - Paste
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.pasteSelection()
            event.accept()
        # Ctrl+A - Select All
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            self.selectAllCells()
            event.accept()
        # Delete - Delete selected rows
        elif event.key() == Qt.Key.Key_Delete:
            self.deleteSelectedRows()
            event.accept()
        # Ctrl+X - Cut (copy then delete content)
        elif event.matches(QKeySequence.StandardKey.Cut):
            self.copySelection()
            for item in self.selectedItems():
                if item and (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    item.setText("")
            self.cellDataChanged.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
            
    def _update_stats(self):
        """Calculate and emit stats for selected numeric cells."""
        selection = self.selectedItems()
        if not selection:
            self.selectionStatsChanged.emit("")
            return
            
        numeric_values = []
        for item in selection:
            if self.show_checkboxes and item.column() == 0:
                continue
            text = item.text().replace("₹", "").replace(",", "").replace("%", "").strip()
            if text and text != "—":
                try:
                    numeric_values.append(float(text))
                except ValueError:
                    pass
                    
        if not numeric_values:
            stats = f"Selected: {len(selection)} cells"
        else:
            total = sum(numeric_values)
            avg = total / len(numeric_values)
            stats = f"Selected: {len(selection)} cells | Count: {len(numeric_values)} | Total: ₹{total:,.2f} | Avg: ₹{avg:,.2f}"
            
        self.selectionStatsChanged.emit(stats)


class ExcelTableWithStats(QWidget):
    """Excel table with stats bar at bottom."""
    
    def __init__(self, parent=None, show_checkboxes=True):
        super().__init__(parent)
        self.table = ExcelTable(parent=self, show_checkboxes=show_checkboxes)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        from PyQt6.QtWidgets import QVBoxLayout
        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(4)
        
        v_layout.addWidget(self.table)
        
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(self._stats_label_css())
        self.stats_label.setMinimumHeight(24)
        v_layout.addWidget(self.stats_label)
        
        layout.addLayout(v_layout)
        
        self.table.selectionStatsChanged.connect(self._on_stats_changed)

    @staticmethod
    def _stats_label_css() -> str:
        return f"""
            color: {Theme.TEXT_SECONDARY};
            font-size: 11px;
            padding: 4px 8px;
            background: {Theme.SURFACE_ALT};
            border-top: 1px solid {Theme.BORDER};
        """

    def refresh_theme(self):
        """Call after a live theme switch — the stats bar's colors are baked
        in at construction and won't update via the global QSS alone."""
        self.stats_label.setStyleSheet(self._stats_label_css())

    def _on_stats_changed(self, stats: str):
        self.stats_label.setText(stats if stats else "No selection")


# ══════════════════════════════════════════════════════════════════════════════
# Copy-only shortcut for read-only / reference tables
# ══════════════════════════════════════════════════════════════════════════════

def _copy_table_selection(table: QTableWidget, checkbox_col: int) -> None:
    """Build a TSV of the current selection and put it on the clipboard —
    same format ExcelTable.copySelection() uses, so pasting elsewhere (e.g.
    Excel) works identically."""
    selection = table.selectedRanges()
    if not selection:
        return
    rows_data: dict[int, dict[int, str]] = {}
    for rng in selection:
        for row in range(rng.topRow(), rng.bottomRow() + 1):
            rows_data.setdefault(row, {})
            for col in range(rng.leftColumn(), rng.rightColumn() + 1):
                if col == checkbox_col:
                    continue
                item = table.item(row, col)
                rows_data[row][col] = item.text() if item else ""
    if not rows_data:
        return
    lines = []
    for row in sorted(rows_data.keys()):
        cols = rows_data[row]
        lines.append("\t".join(cols.get(c, "") for c in sorted(cols.keys())))
    QApplication.clipboard().setText("\n".join(lines))


def enable_copy_shortcut(table: QTableWidget, checkbox_col: int = -1) -> None:
    """Attach Ctrl+C (copy-to-clipboard, TSV) to a plain read-only QTableWidget.
    Use this for reference/view-only tables that don't need the full
    ExcelTable editing feature set — e.g. AIS/TIS comparison tables,
    reconciliation results, master-data list dialogs."""
    base_keypress = table.keyPressEvent

    def _keypress(event: QKeyEvent):
        if event.matches(QKeySequence.StandardKey.Copy):
            _copy_table_selection(table, checkbox_col)
            event.accept()
        else:
            base_keypress(event)

    table.keyPressEvent = _keypress
