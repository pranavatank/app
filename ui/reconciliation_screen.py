"""
ui/reconciliation_screen.py — Form 26AS vs AIS TDS Reconciliation Screen.

Compare TDS records from Form 26AS and AIS/TIS imports with drill-down.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.widgets.excel_table import enable_copy_shortcut, NoFocusRectDelegate
from ui.icons import set_btn_icon
from core.session import session
from models.person import get_person
from models.form26as import get_form26as_import, get_form26as_records
from models.ais_tis_import import get_ais_tis_data, get_ais_tis_records
from engines.reconciliation_engine import reconcile_tds, get_reconciliation_summary


class ReconciliationScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.reconciliation_items = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)

        # Header
        header = self._build_header()
        layout.addWidget(header)

        # Summary cards
        summary_row = QHBoxLayout()
        summary_row.setSpacing(12)
        
        self.card_total = self._metric_card("Total Records", "0", Theme.PRIMARY)
        self.card_match = self._metric_card("Match", "0", Theme.SUCCESS)
        self.card_mismatch = self._metric_card("Mismatch", "0", Theme.DANGER)
        self.card_diff = self._metric_card("Difference", "₹ 0", Theme.WARNING)
        
        summary_row.addWidget(self.card_total)
        summary_row.addWidget(self.card_match)
        summary_row.addWidget(self.card_mismatch)
        summary_row.addWidget(self.card_diff)
        layout.addLayout(summary_row)

        # Reconciliation table
        self._table_card = table_card = QFrame()
        table_card.setStyleSheet(Theme.card_style(radius=12, padding=0))
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self._table_header = table_header = QFrame()
        table_header.setStyleSheet(f"background: {Theme.SURFACE_ALT}; border-radius: 12px 12px 0 0; padding: 12px 16px;")
        th_layout = QHBoxLayout(table_header)
        th_layout.setContentsMargins(16, 12, 16, 12)
        
        th_title = QLabel("Reconciliation Results")
        th_title.setStyleSheet(Theme.title_style(14))
        th_layout.addWidget(th_title)
        th_layout.addStretch()
        
        btn_export = Theme.btn("Export", "secondary", height=32, min_width=90)
        btn_export.setAccessibleName("Export reconciliation results")
        btn_export.clicked.connect(self._export_results)
        th_layout.addWidget(btn_export)
        
        table_layout.addWidget(table_header)

        self.table = QTableWidget()
        self.table.setAccessibleName("Reconciliation results table")
        self.table.setAccessibleDescription("Comparison of Form 26AS and AIS/TIS TDS entries.")
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Status", "Deductor Name", "TAN", "Section",
            "26AS TDS", "AIS TDS", "Difference"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setItemDelegate(NoFocusRectDelegate(self.table))
        enable_copy_shortcut(self.table)
        self.table.doubleClicked.connect(self._on_row_double_click)
        table_layout.addWidget(self.table)

        layout.addWidget(table_card, 1)

    def _build_header(self) -> QFrame:
        self._header_frame = header = QFrame()
        header.setStyleSheet(Theme.card_style(radius=12, padding=16))
        h_layout = QHBoxLayout(header)
        h_layout.setSpacing(12)

        left = QVBoxLayout()
        title = QLabel("Form 26AS vs AIS Reconciliation")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(16) + " border: none; background: transparent; padding: 0; margin: 0;")
        left.addWidget(title)

        self.person_label = QLabel("Select a person from the top bar")
        self.person_label.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_SECONDARY, size=12, weight=600)
            + " border: none; background: transparent; padding: 0; margin: 0;"
        )
        left.addWidget(self.person_label)
        h_layout.addLayout(left)
        h_layout.addStretch()

        btn_reconcile = Theme.btn(" Reconcile", "primary", height=40, min_width=140)
        set_btn_icon(btn_reconcile, "reconcile")
        btn_reconcile.setAccessibleName("Run reconciliation")
        btn_reconcile.clicked.connect(self._on_reconcile)
        h_layout.addWidget(btn_reconcile)

        return header

    def _metric_card(self, label: str, value: str, accent: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(Theme.stat_tile_style(accent, radius=12))
        card.setMinimumHeight(90)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        lbl = QLabel(label)
        lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=11, weight=600))
        layout.addWidget(lbl)

        val = QLabel(value)
        val.setObjectName("metricValue")
        val.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        val.setStyleSheet(
            Theme.text_style(color=accent, size=18, weight=700)
            + " border: none; background: transparent; padding: 0; margin: 0;"
        )
        layout.addWidget(val)
        layout.addStretch()

        return card

    def refresh_theme(self):
        """Called after a live theme switch — the header, table card, and
        4 metric cards are built once at construction, so their inline
        styling needs re-applying before the dynamic refresh() runs."""
        if hasattr(self, "_header_frame"):
            self._header_frame.setStyleSheet(Theme.card_style(radius=12, padding=16))
        if hasattr(self, "_table_card"):
            self._table_card.setStyleSheet(Theme.card_style(radius=12, padding=0))
        if hasattr(self, "_table_header"):
            self._table_header.setStyleSheet(
                f"background: {Theme.SURFACE_ALT}; border-radius: 12px 12px 0 0; padding: 12px 16px;")
        for card, accent in (
            (self.card_total, Theme.PRIMARY),
            (self.card_match, Theme.SUCCESS),
            (self.card_mismatch, Theme.DANGER),
            (self.card_diff, Theme.WARNING),
        ):
            card.setStyleSheet(Theme.stat_tile_style(accent, radius=12))
            val = card.findChild(QLabel, "metricValue")
            if val:
                val.setStyleSheet(
                    Theme.text_style(color=accent, size=18, weight=700)
                    + " border: none; background: transparent; padding: 0; margin: 0;"
                )
        # Per-row status badges are QLabel cell-widgets with Theme colors
        # baked in at construction (_populate_table) — refresh() alone only
        # updates the summary cards/person label, not these, so rebuild the
        # rows too if reconciliation results are already on screen.
        if hasattr(self, "reconciliation_items") and self.reconciliation_items:
            self._populate_table()
        self.refresh()

    def refresh(self):
        pid = session.selected_person_id
        fy = session.selected_fy

        if not pid:
            self.person_label.setText("Please select a person from the top bar")
            self.person_label.setStyleSheet(Theme.text_style(color=Theme.WARNING, size=12, weight=600))
            self._clear_table()
            return
        
        person = get_person(pid)
        if person:
            self.person_label.setText(f"Reconciliation for {person['full_name']} · FY {fy}")
            self.person_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))

    def _on_reconcile(self):
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
            return
        
        # Load Form 26AS data
        form26as_import = get_form26as_import(pid, fy)
        if not form26as_import:
            QMessageBox.information(self, "No Data", "No Form 26AS data found for selected person and FY.")
            return
        
        form26as_records = get_form26as_records(form26as_import["import_id"])
        
        # Load AIS data
        ais_import = get_ais_tis_data(pid, fy, source_type="AIS")
        if not ais_import:
            ais_import = get_ais_tis_data(pid, fy, source_type="TIS")
        if not ais_import:
            QMessageBox.information(self, "No Data", "No AIS/TIS data found for selected person and FY.")
            return
        
        ais_records = get_ais_tis_records(ais_import["import_id"])
        
        # Reconcile
        self.reconciliation_items = reconcile_tds(form26as_records, ais_records)
        summary = get_reconciliation_summary(self.reconciliation_items)
        
        # Update summary cards
        self.card_total.findChild(QLabel, "metricValue").setText(str(summary["total_records"]))
        self.card_match.findChild(QLabel, "metricValue").setText(
            f"{summary['match_count']} ({summary['reconciliation_rate']:.1f}%)"
        )
        self.card_mismatch.findChild(QLabel, "metricValue").setText(
            f"{summary['mismatch_count'] + summary['only_26as_count'] + summary['only_ais_count']}"
        )
        self.card_diff.findChild(QLabel, "metricValue").setText(f"₹ {summary['total_difference']:,.2f}")
        
        # Populate table
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self.reconciliation_items))
        
        for row, item in enumerate(self.reconciliation_items):
            # Status badge
            status_widget = QLabel(item.status)
            status_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            if item.status == "Match":
                bg, fg = Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK
            elif item.status == "Minor Diff":
                bg, fg = Theme.WARNING_LIGHT, Theme.WARNING_DARK
            elif item.status == "Mismatch":
                bg, fg = Theme.DANGER_LIGHT, Theme.DANGER_DARK
            else:
                bg, fg = Theme.INFO_LIGHT, Theme.INFO_DARK
            
            status_widget.setStyleSheet(Theme.badge_style(bg, fg, radius=8, padding="4px 8px", size=11, weight=600))
            self.table.setCellWidget(row, 0, status_widget)
            
            # Other columns
            self.table.setItem(row, 1, QTableWidgetItem(item.deductor_name))
            self.table.setItem(row, 2, QTableWidgetItem(item.deductor_tan))
            self.table.setItem(row, 3, QTableWidgetItem(item.section))
            self.table.setItem(row, 4, QTableWidgetItem(f"₹ {item.form26as_amount:,.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"₹ {item.ais_amount:,.2f}"))
            
            diff_item = QTableWidgetItem(f"₹ {item.difference:,.2f}")
            if item.status in ("Mismatch", "26AS Only", "AIS Only"):
                diff_item.setForeground(Theme.DANGER)
            self.table.setItem(row, 6, diff_item)

    def _on_row_double_click(self, index):
        """Show drill-down details for selected reconciliation item."""
        row = index.row()
        if row < 0 or row >= len(self.reconciliation_items):
            return
        
        item = self.reconciliation_items[row]
        dialog = ReconciliationDetailDialog(item, self)
        dialog.exec()

    def _export_results(self):
        if not self.reconciliation_items:
            QMessageBox.information(self, "No Data", "No reconciliation results to export.")
            return
        
        # Simple TSV export to clipboard
        lines = ["Status\tDeductor Name\tTAN\tSection\t26AS TDS\tAIS TDS\tDifference"]
        for item in self.reconciliation_items:
            lines.append(
                f"{item.status}\t{item.deductor_name}\t{item.deductor_tan}\t{item.section}\t"
                f"{item.form26as_amount:.2f}\t{item.ais_amount:.2f}\t{item.difference:.2f}"
            )
        
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Exported", "Reconciliation results copied to clipboard (TSV format).")

    def _clear_table(self):
        self.table.setRowCount(0)
        self.reconciliation_items = []
        for card in [self.card_total, self.card_match, self.card_mismatch, self.card_diff]:
            card.findChild(QLabel, "metricValue").setText("0")


class ReconciliationDetailDialog(QDialog):
    """Drill-down dialog showing detailed comparison for a single reconciliation item."""
    
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(f"Details: {item.deductor_name}")
        self.setMinimumSize(700, 500)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = QLabel(self.item.deductor_name)
        header.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.setStyleSheet(Theme.title_style(15))
        layout.addWidget(header)
        
        # Status badge
        status_label = QLabel(f"Status: {self.item.status}")
        if self.item.status == "Match":
            bg, fg = Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK
        elif self.item.status == "Minor Diff":
            bg, fg = Theme.WARNING_LIGHT, Theme.WARNING_DARK
        elif self.item.status == "Mismatch":
            bg, fg = Theme.DANGER_LIGHT, Theme.DANGER_DARK
        else:
            bg, fg = Theme.INFO_LIGHT, Theme.INFO_DARK
        status_label.setStyleSheet(Theme.badge_style(bg, fg, radius=10, padding="6px 12px", size=12, weight=600))
        layout.addWidget(status_label)
        
        # Comparison table
        info_frame = QFrame()
        info_frame.setStyleSheet(Theme.card_style(radius=10, padding=16))
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)
        
        info_layout.addWidget(self._info_row("TAN:", self.item.deductor_tan))
        info_layout.addWidget(self._info_row("Section:", self.item.section))
        info_layout.addWidget(QLabel())  # Spacer
        info_layout.addWidget(self._info_row("Form 26AS TDS:", f"₹ {self.item.form26as_amount:,.2f}"))
        info_layout.addWidget(self._info_row("AIS TDS:", f"₹ {self.item.ais_amount:,.2f}"))
        info_layout.addWidget(QLabel())  # Spacer
        
        diff_label = self._info_row("Difference:", f"₹ {self.item.difference:,.2f}")
        if self.item.status in ("Mismatch", "26AS Only", "AIS Only"):
            diff_label.findChildren(QLabel)[1].setStyleSheet(
                Theme.text_style(color=Theme.DANGER, size=13, weight=700)
            )
        info_layout.addWidget(diff_label)
        
        layout.addWidget(info_frame)
        
        # Action note
        note = QLabel("Tip: Verify source documents if there's a mismatch.")
        note.setWordWrap(True)
        note.setStyleSheet(Theme.muted_style(11))
        layout.addWidget(note)
        
        layout.addStretch()
        
        # Close button
        btn_close = Theme.btn("Close", "secondary", height=36, min_width=100)
        btn_close.setAccessibleName("Close reconciliation details")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
    
    def _info_row(self, label: str, value: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)
        
        lbl = QLabel(label)
        lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=12, weight=600))
        lbl.setFixedWidth(150)
        row_layout.addWidget(lbl)
        
        val = QLabel(value)
        val.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=400))
        row_layout.addWidget(val)
        row_layout.addStretch()
        
        return row
