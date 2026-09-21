"""
ui/dialogs/fd_bulk_rate_dialog.py — Bulk rate-entry dialog for FDs.

Enter the real interest rate and tenure for every FD still on default
projections, in one pass.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QComboBox, QPushButton, QTableWidget, QHeaderView, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.theme import Theme
from ui.widgets.excel_table import ExcelTableWithStats
from ui.widgets.toast_utils import show_success, show_warning
from ui.widgets.states import EmptyState
from core.session import session
from config import COMPOUNDING_TYPES
from models.fixed_deposit import get_all_fds, apply_fd_details


class FDBulkRateDialog(QDialog):
    """Enter the real interest rate and tenure for every FD still on default
    projections, in one pass."""

    COL_CHECK, COL_BANK, COL_FD_NO, COL_PRINCIPAL, COL_START, \
        COL_RATE, COL_YEARS, COL_MONTHS, COL_DAYS, COL_COMPOUNDING = range(10)

    def __init__(self, parent=None, person_id: int | None = None):
        super().__init__(parent)
        self._person_id = person_id
        self._saved = 0
        self._fd_id_map = {}  # Maps row index to fd_id
        self.table = None
        self.table_widget = None
        self.setWindowTitle("Enter Real FD Rates")
        self.setModal(True)
        self.setMinimumWidth(920)
        self._build_ui()
        self._load_pending()

    def _build_ui(self) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Title
        title = QLabel("Enter Real FD Rates")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Rates entered here replace the default projection for these deposits.")
        subtitle.setProperty("textrole", "muted-sm")
        layout.addWidget(subtitle)

        # Fill row: rate, tenure, compounding, apply button
        fill_layout = QHBoxLayout()
        fill_layout.setSpacing(10)

        # Rate spinbox
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.01, 100.00)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setSuffix(" %")
        self.rate_spin.setAccessibleName("Bulk interest rate")
        fill_layout.addWidget(QLabel("Rate:"))
        fill_layout.addWidget(self.rate_spin)

        # Years spinbox
        self.years_spin = QSpinBox()
        self.years_spin.setRange(0, 20)
        fill_layout.addWidget(QLabel("Years:"))
        fill_layout.addWidget(self.years_spin)

        # Months spinbox
        self.months_spin = QSpinBox()
        self.months_spin.setRange(0, 11)
        fill_layout.addWidget(QLabel("Months:"))
        fill_layout.addWidget(self.months_spin)

        # Days spinbox
        self.days_spin = QSpinBox()
        self.days_spin.setRange(0, 364)
        fill_layout.addWidget(QLabel("Days:"))
        fill_layout.addWidget(self.days_spin)

        # Compounding combo
        self.compounding_combo = QComboBox()
        for comp_type in COMPOUNDING_TYPES:
            self.compounding_combo.addItem(comp_type)
        fill_layout.addWidget(QLabel("Compounding:"))
        fill_layout.addWidget(self.compounding_combo)

        # Apply button with left-align wrapper
        apply_btn = Theme.btn("Apply to Checked", "secondary", height=Theme.HEIGHT_MD, min_width=150)
        apply_btn.clicked.connect(self._on_apply_to_checked)
        apply_wrapper = QWidget()
        apply_wrapper_layout = QHBoxLayout(apply_wrapper)
        apply_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        apply_wrapper_layout.setSpacing(0)
        apply_wrapper_layout.addWidget(apply_btn)
        apply_wrapper_layout.addStretch()
        fill_layout.addWidget(apply_wrapper)

        layout.addLayout(fill_layout)

        # Placeholder for table or empty state (will be filled in _load_pending)
        self.table_placeholder_index = layout.count()
        layout.addSpacing(1)  # Placeholder

        # Footer buttons
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.btn_cancel = Theme.btn("Cancel", "secondary", height=Theme.HEIGHT_MD)
        self.btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(self.btn_cancel)

        self.btn_save = Theme.btn("Save Rates", "primary", height=Theme.HEIGHT_MD)
        self.btn_save.clicked.connect(self._on_save)
        footer_layout.addWidget(self.btn_save)

        layout.addLayout(footer_layout)

    def _load_pending(self) -> None:
        """Load FDs with missing rate or maturity date."""
        fds = get_all_fds(person_id=self._person_id)

        # Filter for FDs that are estimated (missing rate or maturity_date)
        pending_fds = [
            fd for fd in fds
            if not fd.get("interest_rate") or not fd.get("maturity_date")
        ]

        layout = self.layout()

        if not pending_fds:
            # Show empty state
            empty = EmptyState(
                icon_name="piggy-bank",
                headline="All deposits have real rates",
                explanation="Nothing to enter."
            )
            # Replace the placeholder with empty state
            layout.removeItem(layout.itemAt(self.table_placeholder_index))
            layout.insertWidget(self.table_placeholder_index, empty, stretch=1)

            self.table = None
            self.btn_save.setEnabled(False)
            return

        # Build the table
        table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.table_widget = table_widget
        self.table = table_widget.table
        self.table.setAccessibleName("Bulk rate entry table")
        self.table.editable = True
        self.table.setHeaders([
            "Bank", "FD No", "Principal", "Start Date", "Rate %",
            "Years", "Months", "Days", "Compounding"
        ])
        self.table.setNumericColumns({self.COL_RATE, self.COL_YEARS, self.COL_MONTHS, self.COL_DAYS})

        # Column sizing keyed by real column indices (1-9, skipping checkbox at 0)
        col_specs = {
            1: {"mode": "FIXED", "width": 120},      # Bank
            2: {"mode": "FIXED", "width": 120},      # FD No
            3: {"mode": "FIXED", "width": 100},      # Principal
            4: {"mode": "FIXED", "width": 100},      # Start Date
            5: {"mode": "FIXED", "width": 80},       # Rate %
            6: {"mode": "FIXED", "width": 60},       # Years
            7: {"mode": "FIXED", "width": 70},       # Months
            8: {"mode": "FIXED", "width": 60},       # Days
            9: {"mode": "FIXED", "width": 110},      # Compounding
        }
        self.table.setColumnSizing(col_specs)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed
        )

        # Populate table rows
        for row, fd in enumerate(pending_fds):
            bank_name = fd.get("bank_name", "—")
            fd_no = fd.get("fd_reference_no", "—")
            principal = session.mask(fd.get("principal_amount", 0.0))
            start_date = fd.get("start_date", "—")
            compounding = fd.get("compounding_type") or "Quarterly"

            row_data = [
                bank_name,
                fd_no,
                principal,
                start_date,
                "",  # Rate (empty)
                0,   # Years
                0,   # Months
                0,   # Days
                compounding
            ]

            # Add row with editable columns
            self.table.addDataRow(
                row_data,
                editable_cols={self.COL_RATE, self.COL_YEARS, self.COL_MONTHS, self.COL_DAYS, self.COL_COMPOUNDING}
            )

            # Store fd_id in mapping
            self._fd_id_map[row] = fd["fd_id"]

        # Replace placeholder with table
        layout.removeItem(layout.itemAt(self.table_placeholder_index))
        layout.insertWidget(self.table_placeholder_index, table_widget, stretch=1)

    def _on_apply_to_checked(self) -> None:
        """Apply fill-row values to checked rows (or all if none checked)."""
        if not self.table:
            return

        checked_rows = self.table.getCheckedRows()
        rows_to_update = checked_rows if checked_rows else list(range(self.table.rowCount()))

        if not checked_rows and self.table.rowCount() > 0:
            show_warning("No rows checked - applying to all rows.")

        # Block signals while updating
        self.table.blockSignals(True)

        rate = self.rate_spin.value()
        years = self.years_spin.value()
        months = self.months_spin.value()
        days = self.days_spin.value()
        compounding = self.compounding_combo.currentText()

        try:
            for row in rows_to_update:
                # Set rate
                rate_item = self.table.item(row, self.COL_RATE)
                if rate_item:
                    rate_item.setText(f"{rate:.2f}")

                # Set years
                years_item = self.table.item(row, self.COL_YEARS)
                if years_item:
                    years_item.setText(str(years))

                # Set months
                months_item = self.table.item(row, self.COL_MONTHS)
                if months_item:
                    months_item.setText(str(months))

                # Set days
                days_item = self.table.item(row, self.COL_DAYS)
                if days_item:
                    days_item.setText(str(days))

                # Set compounding
                comp_item = self.table.item(row, self.COL_COMPOUNDING)
                if comp_item:
                    comp_item.setText(compounding)
        finally:
            self.table.blockSignals(False)

    def _on_save(self) -> None:
        """Save all filled rates to the database."""
        if not self.table:
            return

        errors = []
        self._saved = 0

        for row in range(self.table.rowCount()):
            fd_id = self._fd_id_map.get(row)
            if fd_id is None:
                continue

            rate_item = self.table.item(row, self.COL_RATE)
            if not rate_item:
                continue

            rate_text = rate_item.text().strip()

            # Skip empty or "—" rate
            if not rate_text or rate_text == "—":
                continue

            years_item = self.table.item(row, self.COL_YEARS)
            months_item = self.table.item(row, self.COL_MONTHS)
            days_item = self.table.item(row, self.COL_DAYS)
            compounding_item = self.table.item(row, self.COL_COMPOUNDING)

            try:
                rate_value = float(rate_text.replace("%", "").strip())
                years = int(years_item.text()) if years_item else 0
                months = int(months_item.text()) if months_item else 0
                days = int(days_item.text()) if days_item else 0
                compounding_text = compounding_item.text() if compounding_item else ""
                compounding = (compounding_text.strip() or "Quarterly") if compounding_text != "—" else "Quarterly"

                # Call apply_fd_details
                apply_fd_details(fd_id, rate_value, years, months, days, compounding)
                self._saved += 1
            except ValueError as e:
                errors.append(f"Row {row + 1}: {e}")

        # Show result
        if self._saved > 0:
            if errors:
                error_msg = "\n".join(errors[:10])
                show_warning(
                    f"Saved {self._saved} deposit(s). {len(errors)} row(s) need attention:\n{error_msg}"
                )
            else:
                show_success(f"Saved real rates for {self._saved} deposit(s).")
            self.accept()
        else:
            if errors:
                error_msg = "\n".join(errors[:10])
                show_warning(f"Could not save any rates:\n{error_msg}")
            # Stay open if nothing was saved

    def saved_count(self) -> int:
        """Return the number of FDs saved."""
        return self._saved
