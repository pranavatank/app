"""
ui/tax_documents_screen.py — Tax Documents reconciliation screen

Displays parsed tax documents (Form 26AS, AIS, TIS) with:
- Three drop zones for file uploads
- Reconciled financial position table
- Non-income items disclosure
- Per-FD account reconciliation
- TDS disagreement surface
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QScrollArea, QTableWidgetSelectionRange
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QColor

from PySide6.QtWidgets import QDialog, QMessageBox
from ui.theme import Theme
from ui.icons import set_btn_icon
from ui.widgets.loader import Loader
from ui.widgets.states import EmptyState
from ui.widgets.toast_utils import show_success, show_warning, show_danger
from ui.widgets.excel_table import ExcelTableWithStats, ExcelTable
from ui.widgets.drop_zone import DropZone
from ui.dialogs.password_dialog import PasswordDialog
from core.session import session
from engines.taxdocs.form26as import parse_form26as_pdf
from engines.taxdocs.ais import parse_ais_pdf
from engines.taxdocs.tis import parse_tis_pdf
from engines.taxdocs.merge import merge_tax_documents
from engines.taxdocs.persist import (
    persist_form26as, persist_ais_tis,
    SOURCE_TYPE_AIS, SOURCE_TYPE_TIS,
)
from engines.statement_parser import is_pdf_encrypted
from models.fixed_deposit import get_all_fds, find_fd_by_account_no
from models.ais_tis_import import get_ais_tis_data
from models.form26as import get_form26as_import
from models.person import get_ais_tis_password, get_all_persons, set_ais_tis_password
import json
import os


def _format_inr(amount: float) -> str:
    """Format amount as Indian rupees with Indian digit grouping (2,56,642)."""
    if amount is None:
        return "₹ —"
    from ui.widgets.money_label import format_inr
    s = format_inr(round(float(amount), 2))
    return s.replace("₹", "₹ ", 1)


def _selected_person_id() -> int | None:
    if session.selected_person_id is not None:
        return session.selected_person_id
    people = get_all_persons()
    return people[0]["person_id"] if len(people) == 1 else None


def _saved_ais_tis(person_id: int, financial_year: str, source_type: str) -> dict | None:
    row = get_ais_tis_data(person_id, financial_year, source_type)
    if row is None:
        return None
    try:
        parsed = json.loads(row.get("raw_json") or "{}")
    except (TypeError, ValueError):
        parsed = {}
    return {
        "dividend": row.get("dividend_income") or 0.0,
        "savings_interest": row.get("savings_interest") or 0.0,
        "fd_interest": row.get("fd_interest") or 0.0,
        "business_receipts": row.get("other_income") or 0.0,
        "tds": row.get("tds_deducted") or 0.0,
        **(parsed if isinstance(parsed, dict) else {}),
    }


class TaxDocumentsScreen(QWidget):
    """Screen for uploading and reconciling tax documents."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.merge_result = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        """Build the screen layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(16)

        # Title
        title = QLabel("Tax Documents Reconciliation")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setProperty("textrole", "title-md")
        layout.addWidget(title)

        self.person_prompt = QLabel("Select a person to view or import their tax documents.")
        self.person_prompt.setProperty("textrole", "secondary-md")
        self.person_prompt.setWordWrap(True)
        layout.addWidget(self.person_prompt)

        # Upload zones
        upload_frame = QFrame()
        upload_frame.setObjectName("panelFrame")
        upload_layout = QHBoxLayout(upload_frame)
        upload_layout.setContentsMargins(0, 0, 0, 0)
        upload_layout.setSpacing(16)

        self.zone_26as = DropZone(
            title="Form 26AS",
            subtitle="Drag PDF here or click to browse",
            accepted_extensions=[".pdf"],
            filter_text="PDF files (*.pdf)",
            parent=self
        )
        self.zone_ais = DropZone(
            title="AIS",
            subtitle="Drag PDF here or click to browse",
            accepted_extensions=[".pdf"],
            filter_text="PDF files (*.pdf)",
            parent=self
        )
        self.zone_tis = DropZone(
            title="TIS",
            subtitle="Drag PDF here or click to browse",
            accepted_extensions=[".pdf"],
            filter_text="PDF files (*.pdf)",
            parent=self
        )

        upload_layout.addWidget(self.zone_26as)
        upload_layout.addWidget(self.zone_ais)
        upload_layout.addWidget(self.zone_tis)

        self.zone_26as.fileSelected.connect(self._on_26as_selected)
        self.zone_ais.fileSelected.connect(self._on_ais_selected)
        self.zone_tis.fileSelected.connect(self._on_tis_selected)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setObjectName("transparentSurface")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        inner.setObjectName("transparentSurface")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(16)
        inner_layout.addWidget(upload_frame)

        # Empty state
        self.empty_state = EmptyState(
            icon_name="document",
            headline="Reconciliation needs all three documents",
            explanation="Add the missing Form 26AS, AIS, or TIS PDF for this financial year.",
            action_text="Browse Form 26AS"
        )
        self.empty_state.action_clicked.connect(self.zone_26as._on_browse_click)
        inner_layout.addWidget(self.empty_state)

        # Position table (hidden until data loaded)
        self.position_frame = self._build_position_frame()
        self.position_frame.setVisible(False)
        inner_layout.addWidget(self.position_frame)

        # Non-income items panel (hidden until data loaded)
        self.non_income_frame = self._build_non_income_frame()
        self.non_income_frame.setVisible(False)
        inner_layout.addWidget(self.non_income_frame)

        # FD reconciliation panel (hidden until data loaded)
        self.fd_frame = self._build_fd_frame()
        self.fd_frame.setVisible(False)
        inner_layout.addWidget(self.fd_frame)

        inner_layout.addStretch()

        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

    def refresh(self):
        """Show the saved documents for the current person and financial year."""
        person_id = _selected_person_id()
        fy = session.selected_fy
        self.person_prompt.setVisible(person_id is None)
        self.merge_result = None
        self.position_frame.hide()
        self.non_income_frame.hide()
        self.fd_frame.hide()
        self.empty_state.setVisible(person_id is not None)

        form26as = get_form26as_import(person_id, fy) if person_id is not None else None
        ais = _saved_ais_tis(person_id, fy, SOURCE_TYPE_AIS) if person_id is not None else None
        tis = _saved_ais_tis(person_id, fy, SOURCE_TYPE_TIS) if person_id is not None else None
        for zone, data in ((self.zone_26as, form26as), (self.zone_ais, ais), (self.zone_tis, tis)):
            zone.setEnabled(person_id is not None)
            zone.pdf_data = data
            zone.pdf_path = None
            saved = data is not None
            zone.icon_label.setVisible(not saved)
            zone.setMinimumHeight(76 if saved else 120)
            vertical_padding = 8 if saved else 20
            zone.layout().setContentsMargins(20, vertical_padding, 20, vertical_padding)
            zone.layout().setSpacing(4 if saved else 12)
            zone.set_status(f"{zone.title_text} · Saved" if data is not None else zone.title_text,
                            fy=f"FY {fy}" if data is not None else "")
        self._try_merge(person_id)

    def _build_position_frame(self) -> QFrame:
        """Build the reconciled position table."""
        frame = QFrame()
        frame.setObjectName("panelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title = QLabel("Reconciled Financial Position")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setProperty("textrole", "subtitle-md")
        layout.addWidget(title)

        # Table (read-only)
        self.position_table_widget = ExcelTableWithStats(show_checkboxes=False, read_only=True)
        self.position_table = self.position_table_widget.table
        self.position_table.setHeaders([
            "Category", "TIS", "AIS", "26AS", "In App", "Status"
        ])
        self.position_table.setAccessibleName("Reconciled financial position table")
        self.position_table.setAccessibleDescription("Shows the comparison of financial data across TIS, AIS, Form 26AS, and in-app records.")
        self.position_table.setSortingEnabled(False)
        layout.addWidget(self.position_table_widget)

        return frame

    def _build_non_income_frame(self) -> QFrame:
        """Build the non-income items disclosure panel."""
        frame = QFrame()
        frame.setObjectName("panelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title = QLabel("Reported, Not Income")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setProperty("textrole", "subtitle-md")

        subtitle = QLabel("Transactions that are disclosed but not counted as taxable income")
        subtitle.setProperty("textrole", "secondary-sm")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Table (read-only)
        self.non_income_table_widget = ExcelTableWithStats(show_checkboxes=False, read_only=True)
        self.non_income_table = self.non_income_table_widget.table
        self.non_income_table.setHeaders(["Category", "Amount"])
        self.non_income_table.setAccessibleName("Non-income items disclosure table")
        self.non_income_table.setAccessibleDescription("Lists transactions that are disclosed but not counted as taxable income.")
        self.non_income_table.setSortingEnabled(False)
        layout.addWidget(self.non_income_table_widget)

        return frame

    def _build_fd_frame(self) -> QFrame:
        """Build the FD account reconciliation panel."""
        frame = QFrame()
        frame.setObjectName("panelFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title = QLabel("Fixed Deposit Reconciliation")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setProperty("textrole", "subtitle-md")

        subtitle = QLabel("Matching AIS account numbers to Fixed Deposit records")
        subtitle.setProperty("textrole", "secondary-sm")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Table (read-only)
        self.fd_table_widget = ExcelTableWithStats(show_checkboxes=False, read_only=True)
        self.fd_table = self.fd_table_widget.table
        self.fd_table.setHeaders([
            "Account Number", "AIS Amount", "FD Record", "Status"
        ])
        self.fd_table.setAccessibleName("Fixed deposit reconciliation table")
        self.fd_table.setAccessibleDescription("Shows matching between AIS account numbers and Fixed Deposit records.")
        self.fd_table.setSortingEnabled(False)
        layout.addWidget(self.fd_table_widget)

        return frame

    def _on_26as_selected(self, path: str):
        """Handle 26AS file selection."""
        person_id = _selected_person_id()
        if person_id is None:
            show_warning("Select a person before importing tax documents.")
            return
        self.zone_26as.set_status("Parsing...", error=False)

        def parse_26as():
            parsed = parse_form26as_pdf(path, password=None, debug={})
            info = persist_form26as(person_id, parsed,
                                    source_file=os.path.basename(path))
            return info

        def on_done(info):
            self.refresh()
            show_success(f"Form 26AS imported — {info['record_count']} records, FY {info['financial_year']}")

        def on_error(exc):
            self.zone_26as.set_status(f"Error: {str(exc)[:50]}", error=True)
            show_danger(f"Failed to parse 26AS: {str(exc)}")

        Loader.run(self, fn=parse_26as, message="Parsing Form 26AS…",
                  on_done=on_done, on_error=on_error)

    def _on_ais_selected(self, path: str):
        """Handle AIS file selection."""
        person_id = _selected_person_id()
        if person_id is None:
            show_warning("Select a person before importing tax documents.")
            return
        self.zone_ais.set_status("Parsing...", error=False)

        # Check if encrypted and prompt for password on GUI thread BEFORE starting background parse
        password = None
        if is_pdf_encrypted(path):
            # Try saved password first
            saved_password = get_ais_tis_password(person_id, session.aes_key)

            # Prompt for password
            dlg = PasswordDialog(
                self, title="Enter AIS Password",
                info_text="This AIS file is password-protected. Enter the password to continue.",
                hint_text="Check your AIS document or email for the password.",
                placeholder_text="AIS password",
                prefill_password=saved_password,
                save_label="Save password for AIS/TIS documents",
                save_checked=False,
                accept_label="Continue"
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self.zone_ais.set_status("Cancelled", error=False)
                return
            password = dlg.get_password()
            if not password:
                show_warning("Password is required to open the encrypted file.")
                self.zone_ais.set_status("Password required", error=True)
                return

            # Remember if user wants to save password
            should_save = dlg.should_save()
        else:
            should_save = False

        def parse_ais():
            parsed = parse_ais_pdf(path, password=password)
            info = persist_ais_tis(person_id, parsed, SOURCE_TYPE_AIS,
                                   source_file=os.path.basename(path))
            return info

        def on_done(info):
            # Save password if requested
            if should_save and password:
                set_ais_tis_password(person_id, password, session.aes_key)

            self.refresh()
            show_success(f"AIS imported — {info['record_count']} records, FY {info['financial_year']}")

        def on_error(exc):
            self.zone_ais.set_status(f"Error: {str(exc)[:50]}", error=True)
            show_danger(f"Failed to parse AIS: {str(exc)}")

        Loader.run(self, fn=parse_ais, message="Parsing AIS…",
                  on_done=on_done, on_error=on_error)

    def _on_tis_selected(self, path: str):
        """Handle TIS file selection."""
        person_id = _selected_person_id()
        if person_id is None:
            show_warning("Select a person before importing tax documents.")
            return
        self.zone_tis.set_status("Parsing...", error=False)

        # Check if encrypted and prompt for password on GUI thread BEFORE starting background parse
        password = None
        if is_pdf_encrypted(path):
            # Try saved password first
            saved_password = get_ais_tis_password(person_id, session.aes_key)

            # Prompt for password
            dlg = PasswordDialog(
                self, title="Enter TIS Password",
                info_text="This TIS file is password-protected. Enter the password to continue.",
                hint_text="Check your TIS document or email for the password.",
                placeholder_text="TIS password",
                prefill_password=saved_password,
                save_label="Save password for AIS/TIS documents",
                save_checked=False,
                accept_label="Continue"
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self.zone_tis.set_status("Cancelled", error=False)
                return
            password = dlg.get_password()
            if not password:
                show_warning("Password is required to open the encrypted file.")
                self.zone_tis.set_status("Password required", error=True)
                return

            # Remember if user wants to save password
            should_save = dlg.should_save()
        else:
            should_save = False

        def parse_tis():
            parsed = parse_tis_pdf(path, password=password)
            info = persist_ais_tis(person_id, parsed, SOURCE_TYPE_TIS,
                                   source_file=os.path.basename(path))
            return info

        def on_done(info):
            # Save password if requested
            if should_save and password:
                set_ais_tis_password(person_id, password, session.aes_key)

            self.refresh()
            show_success(f"TIS imported — {info['record_count']} records, FY {info['financial_year']}")

        def on_error(exc):
            self.zone_tis.set_status(f"Error: {str(exc)[:50]}", error=True)
            show_danger(f"Failed to parse TIS: {str(exc)}")

        Loader.run(self, fn=parse_tis, message="Parsing TIS…",
                  on_done=on_done, on_error=on_error)

    def _try_merge(self, person_id: int | None):
        """Try to merge if all three documents are loaded."""
        if (person_id is not None and
            self.zone_26as.pdf_data and
            self.zone_ais.pdf_data and
            self.zone_tis.pdf_data):
            self._on_all_loaded(person_id)

    def _on_all_loaded(self, person_id: int):
        """Called when all three documents are loaded."""
        try:
            # Build FD lookup function
            lookup_fd = lambda acct: find_fd_by_account_no(acct, person_id)

            # Merge documents
            self.merge_result = merge_tax_documents(
                tis_data=self.zone_tis.pdf_data,
                ais_data=self.zone_ais.pdf_data,
                form26as_data=self.zone_26as.pdf_data,
                fd_by_account_no_lookup=lookup_fd,
                financial_year=session.selected_fy,
            )

            # Display results
            self.empty_state.setVisible(False)
            self.position_frame.setVisible(True)
            self.non_income_frame.setVisible(True)
            self.fd_frame.setVisible(True)

            self._render_position_table()
            self._render_non_income_table()
            self._render_fd_table()

        except Exception as e:
            show_danger(f"Merge failed: {str(e)}")

    def _render_position_table(self):
        """Render the reconciled position table."""
        if not self.merge_result:
            return

        fp = self.merge_result.get('financial_position', {})
        iv = self.merge_result.get('income_variance', {})
        tds_recon = self.merge_result.get('tds_reconciliation', {})

        self.position_table.setRowCount(0)

        # Income rows
        categories = [
            ('dividend', 'Dividend Income'),
            ('savings_interest', 'Savings Interest'),
            ('fd_interest', 'FD Interest'),
            ('business_receipts', 'Business Receipts'),
            ('total_income', 'Total Income'),
            ('presumptive_profit', 'Presumptive Profit'),
        ]

        for key, label in categories:
            if key in iv:
                row_data = iv[key]
                self._add_position_row(
                    label,
                    _format_inr(row_data.get('tis', 0)),
                    _format_inr(row_data.get('ais', 0)),
                    "—",  # 26AS doesn't have income detail
                    _format_inr(fp.get(key, 0)) if key in fp else "—",
                    "✓" if row_data.get('difference', 0) == 0 else "⚠"
                )
            elif key in fp:
                self._add_position_row(
                    label,
                    "—", "—", "—",
                    _format_inr(fp.get(key, 0)),
                    "✓"
                )

        # TDS rows
        self._add_position_row(
            "TDS Deducted (26AS)",
            "—",
            _format_inr(tds_recon.get('ais_tds', 0)),
            _format_inr(tds_recon.get('form26as_tds', 0)),
            _format_inr(fp.get('tds_deducted', 0)),
            "✓" if tds_recon.get('difference', 0) == 0 else "⚠"
        )

        # TDS difference row
        diff = tds_recon.get('difference', 0)
        if diff != 0:
            self._add_position_row(
                "TDS Difference",
                "—",
                "—",
                _format_inr(diff),
                "—",
                "⚠"
            )

        # Refund row
        self._add_position_row(
            "Refund Due",
            "—", "—", "—",
            _format_inr(fp.get('refund_due', 0)),
            "✓"
        )

        self._fit_result_table(self.position_table)

    @staticmethod
    def _fit_result_table(table):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.ensurePolished()
        rows_height = sum(table.rowHeight(row) for row in range(table.rowCount()))
        # Keep every row in the page scroll and reserve room for a horizontal scrollbar.
        table.setFixedHeight(
            header.sizeHint().height() + rows_height
            + 2 * table.frameWidth() + table.horizontalScrollBar().sizeHint().height()
        )

    def _add_position_row(self, category: str, tis: str, ais: str, form26as: str, in_app: str, status: str):
        """Add a row to the position table."""
        row_data = [category, tis, ais, form26as, in_app, status]
        self.position_table.addDataRow(row_data)

    def _render_non_income_table(self):
        """Render the non-income items table."""
        if not self.merge_result:
            return

        non_income = self.merge_result.get('non_income_items', {})

        self.non_income_table.setRowCount(0)

        for category, amount in sorted(non_income.items()):
            if amount > 0:
                # Format category name
                category_display = category.replace('_', ' ').title()
                if category == 'purchase_of_time_deposits':
                    category_display = 'Purchase of Time Deposits'
                elif category.startswith('SFT-'):
                    category_display = f"{category} Disclosure"

                row_data = [category_display, _format_inr(amount)]
                self.non_income_table.addDataRow(row_data)
        self._fit_result_table(self.non_income_table)

    def _render_fd_table(self):
        """Render the FD reconciliation table."""
        if not self.merge_result:
            return

        fd_matches = self.merge_result.get('fd_matches', {})
        fd_not_in_app = self.merge_result.get('fd_not_in_app', [])

        self.fd_table.setRowCount(0)

        # Matched FDs
        for account_no, match_data in sorted(fd_matches.items()):
            fd_id = match_data.get('fd_id', '—')
            ais_amount = match_data.get('ais_amount', 0)

            row_data = [account_no, _format_inr(ais_amount), str(fd_id), "✓ Matched"]
            self.fd_table.addDataRow(row_data)

        # Unmatched FDs
        for account_no in sorted(fd_not_in_app):
            row_data = [account_no, "—", "—", "⚠ Not in App"]
            self.fd_table.addDataRow(row_data)

            # Apply warning color to status
            row = self.fd_table.rowCount() - 1
            status_item = self.fd_table.item(row, 3)
            if status_item:
                status_item.setForeground(QColor(Theme.WARNING))
        self._fit_result_table(self.fd_table)

