"""
ui/tax_documents_screen.py — Tax Documents reconciliation screen

Displays parsed tax documents (Form 26AS, AIS, TIS) with:
- Three drop zones for file uploads
- Reconciled financial position table
- Non-income items disclosure
- Per-FD account reconciliation
- TDS disagreement surface
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QScrollArea, QTableWidgetSelectionRange
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor

from ui.theme import Theme
from ui.icons import set_btn_icon
from ui.widgets.loader import Loader
from ui.widgets.states import EmptyState
from ui.widgets.toast_utils import show_success, show_warning, show_danger
from ui.widgets.excel_table import ExcelTableWithStats
from core.session import session
from engines.taxdocs.form26as import parse_form26as_pdf
from engines.taxdocs.ais import parse_ais_pdf
from engines.taxdocs.tis import parse_tis_pdf
from engines.taxdocs.merge import merge_tax_documents
from models.fixed_deposit import get_all_fds


def _format_inr(amount: float) -> str:
    """Format amount as Indian rupees with Indian digit grouping (2,56,642)."""
    if amount is None:
        return "₹ —"

    # Convert to int if whole number, else keep decimals
    if isinstance(amount, float) and amount == int(amount):
        amount = int(amount)

    # Format with 2 decimals
    if isinstance(amount, int):
        formatted = f"{amount:,}"
    else:
        formatted = f"{amount:,.2f}"

    # Convert English grouping (1,000) to Indian grouping (1,00,000)
    # Only if the number is >= 1 lakh (100,000)
    if abs(amount) >= 100000:
        # Remove existing commas
        no_comma = str(amount).replace(',', '').split('.')[0]
        decimal_part = ""
        if '.' in str(amount):
            decimal_part = str(amount).split('.')[1]

        # Build Indian grouping
        if len(no_comma) > 3:
            # Reverse string to make grouping easier
            reversed_str = no_comma[::-1]
            groups = []

            # First group is 3 digits from the right
            groups.append(reversed_str[:3])
            remaining = reversed_str[3:]

            # Rest are 2 digits each
            while remaining:
                groups.append(remaining[:2])
                remaining = remaining[2:]

            # Reverse back and join with commas
            formatted = ','.join(groups[::-1])
            if decimal_part:
                formatted = f"{formatted}.{decimal_part}"

        return f"₹ {formatted}"

    return f"₹ {formatted}"


def _extract_financial_year(pdf_data: dict) -> str:
    """Extract financial year from parsed PDF data."""
    # Try to find FY in the data
    if isinstance(pdf_data, dict):
        if 'financial_year' in pdf_data:
            fy = pdf_data['financial_year']
            return f"FY {fy}" if fy else "—"
        if 'assessment_year' in pdf_data:
            ay = pdf_data['assessment_year']
            if ay:
                # AY 2026-27 means FY 2025-26
                try:
                    year = int(str(ay)[:4])
                    return f"FY {year-1}-{year}"
                except:
                    pass
    return "—"


class _FileDropZone(QFrame):
    """Reusable file drop zone for a single document type."""
    file_selected = pyqtSignal(str)  # path

    def __init__(self, title: str, doc_type: str, parent=None):
        super().__init__(parent)
        self.doc_type = doc_type
        self.pdf_data = None
        self.pdf_path = None
        self.setObjectName("fileDropZone")
        self._build_ui(title)

    def _build_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setProperty("textrole", "subtitle-md")
        layout.addWidget(title_lbl)

        # Status
        self.status_lbl = QLabel("No file uploaded")
        self.status_lbl.setProperty("textrole", "secondary-sm")
        layout.addWidget(self.status_lbl)

        # FY
        self.fy_lbl = QLabel("")
        self.fy_lbl.setProperty("textrole", "muted-sm")
        self.fy_lbl.setVisible(False)
        layout.addWidget(self.fy_lbl)

        # Button
        self.btn_upload = Theme.btn("  Select File", "secondary", height=32, min_width=120)
        set_btn_icon(self.btn_upload, "upload")
        self.btn_upload.clicked.connect(self._pick_file)
        layout.addWidget(self.btn_upload)

    def _pick_file(self):
        """Open file picker."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self.doc_type} PDF",
            "",
            "PDF files (*.pdf)"
        )
        if path:
            self.file_selected.emit(path)

    def set_status(self, status: str, fy: str = "", error: bool = False):
        """Update status display."""
        self.status_lbl.setText(status)
        if error:
            self.status_lbl.setProperty("textrole", "danger-md")
        else:
            self.status_lbl.setProperty("textrole", "secondary-sm")
        self.status_lbl.style().unpolish(self.status_lbl)
        self.status_lbl.style().polish(self.status_lbl)

        if fy:
            self.fy_lbl.setText(fy)
            self.fy_lbl.setVisible(True)
        else:
            self.fy_lbl.setVisible(False)


class TaxDocumentsScreen(QWidget):
    """Screen for uploading and reconciling tax documents."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.merge_result = None
        self._build_ui()

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

        # Upload zones
        upload_frame = QFrame()
        upload_frame.setObjectName("panelFrame")
        upload_layout = QHBoxLayout(upload_frame)
        upload_layout.setContentsMargins(0, 0, 0, 0)
        upload_layout.setSpacing(16)

        self.zone_26as = _FileDropZone("Form 26AS", "26AS")
        self.zone_ais = _FileDropZone("AIS", "AIS")
        self.zone_tis = _FileDropZone("TIS", "TIS")

        upload_layout.addWidget(self.zone_26as)
        upload_layout.addWidget(self.zone_ais)
        upload_layout.addWidget(self.zone_tis)

        self.zone_26as.file_selected.connect(self._on_26as_selected)
        self.zone_ais.file_selected.connect(self._on_ais_selected)
        self.zone_tis.file_selected.connect(self._on_tis_selected)

        layout.addWidget(upload_frame)

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

        # Empty state
        self.empty_state = EmptyState(
            icon_name="document",
            headline="No tax documents yet",
            explanation="Upload Form 26AS, AIS, and TIS PDFs to view reconciliation.",
            action_text="Upload Files"
        )
        self.empty_state.action_clicked.connect(self.zone_26as._pick_file)
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

        # Table
        self.position_table = QTableWidget()
        self.position_table.setColumnCount(6)
        self.position_table.setHorizontalHeaderLabels([
            "Category", "TIS", "AIS", "26AS", "In App", "Status"
        ])
        self.position_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.position_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.position_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.position_table)

        frame.setMaximumHeight(400)
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

        # Table
        self.non_income_table = QTableWidget()
        self.non_income_table.setColumnCount(2)
        self.non_income_table.setHorizontalHeaderLabels(["Category", "Amount"])
        self.non_income_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.non_income_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.non_income_table.setMaximumHeight(200)
        layout.addWidget(self.non_income_table)

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

        # Table
        self.fd_table = QTableWidget()
        self.fd_table.setColumnCount(4)
        self.fd_table.setHorizontalHeaderLabels([
            "Account Number", "AIS Amount", "FD Record", "Status"
        ])
        self.fd_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fd_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.fd_table.setMaximumHeight(300)
        layout.addWidget(self.fd_table)

        return frame

    def _on_26as_selected(self, path: str):
        """Handle 26AS file selection."""
        self.zone_26as.set_status("Parsing...", error=False)

        def parse_26as():
            return parse_form26as_pdf(path, password=None, debug={})

        def on_done(result):
            self.zone_26as.pdf_data = result
            self.zone_26as.pdf_path = path
            fy = _extract_financial_year(result)
            self.zone_26as.set_status("✓ Loaded", fy=fy)
            show_success(self, "Form 26AS loaded successfully")
            self._try_merge()

        def on_error(exc):
            self.zone_26as.set_status(f"Error: {str(exc)[:50]}", error=True)
            show_danger(f"Failed to parse 26AS: {str(exc)}")

        Loader.run(self, fn=parse_26as, message="Parsing Form 26AS…",
                  on_done=on_done, on_error=on_error)

    def _on_ais_selected(self, path: str):
        """Handle AIS file selection."""
        self.zone_ais.set_status("Parsing...", error=False)

        def parse_ais():
            return parse_ais_pdf(path, password=None)

        def on_done(result):
            self.zone_ais.pdf_data = result
            self.zone_ais.pdf_path = path
            fy = _extract_financial_year(result)
            self.zone_ais.set_status("✓ Loaded", fy=fy)
            show_success(self, "AIS loaded successfully")
            self._try_merge()

        def on_error(exc):
            self.zone_ais.set_status(f"Error: {str(exc)[:50]}", error=True)
            show_danger(f"Failed to parse AIS: {str(exc)}")

        Loader.run(self, fn=parse_ais, message="Parsing AIS…",
                  on_done=on_done, on_error=on_error)

    def _on_tis_selected(self, path: str):
        """Handle TIS file selection."""
        self.zone_tis.set_status("Parsing...", error=False)

        def parse_tis():
            return parse_tis_pdf(path, password=None)

        def on_done(result):
            self.zone_tis.pdf_data = result
            self.zone_tis.pdf_path = path
            fy = _extract_financial_year(result)
            self.zone_tis.set_status("✓ Loaded", fy=fy)
            show_success(self, "TIS loaded successfully")
            self._try_merge()

        def on_error(exc):
            self.zone_tis.set_status(f"Error: {str(exc)[:50]}", error=True)
            show_danger(f"Failed to parse TIS: {str(exc)}")

        Loader.run(self, fn=parse_tis, message="Parsing TIS…",
                  on_done=on_done, on_error=on_error)

    def _try_merge(self):
        """Try to merge if all three documents are loaded."""
        if (self.zone_26as.pdf_data and
            self.zone_ais.pdf_data and
            self.zone_tis.pdf_data):
            self._on_all_loaded()

    def _on_all_loaded(self):
        """Called when all three documents are loaded."""
        try:
            # Build FD lookup function
            fds = get_all_fds()
            fd_by_account = {}
            for fd in fds:
                if fd.get('account_number'):
                    fd_by_account[fd['account_number']] = fd

            def lookup_fd(account_no: str):
                return fd_by_account.get(account_no)

            # Merge documents
            self.merge_result = merge_tax_documents(
                tis_data=self.zone_tis.pdf_data,
                ais_data=self.zone_ais.pdf_data,
                form26as_data=self.zone_26as.pdf_data,
                fd_by_account_no_lookup=lookup_fd
            )

            # Display results
            self.empty_state.setVisible(False)
            self.position_frame.setVisible(True)
            self.non_income_frame.setVisible(True)
            self.fd_frame.setVisible(True)

            self._render_position_table()
            self._render_non_income_table()
            self._render_fd_table()

            show_success(self, "Tax documents reconciled successfully")

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

    def _add_position_row(self, category: str, tis: str, ais: str, form26as: str, in_app: str, status: str):
        """Add a row to the position table."""
        row = self.position_table.rowCount()
        self.position_table.insertRow(row)

        self.position_table.setItem(row, 0, QTableWidgetItem(category))
        self.position_table.setItem(row, 1, QTableWidgetItem(tis))
        self.position_table.setItem(row, 2, QTableWidgetItem(ais))
        self.position_table.setItem(row, 3, QTableWidgetItem(form26as))
        self.position_table.setItem(row, 4, QTableWidgetItem(in_app))
        self.position_table.setItem(row, 5, QTableWidgetItem(status))

    def _render_non_income_table(self):
        """Render the non-income items table."""
        if not self.merge_result:
            return

        non_income = self.merge_result.get('non_income_items', {})

        self.non_income_table.setRowCount(0)

        for category, amount in sorted(non_income.items()):
            if amount > 0:
                row = self.non_income_table.rowCount()
                self.non_income_table.insertRow(row)

                # Format category name
                category_display = category.replace('_', ' ').title()
                if category == 'purchase_of_time_deposits':
                    category_display = 'Purchase of Time Deposits'
                elif category.startswith('SFT-'):
                    category_display = f"{category} Disclosure"

                self.non_income_table.setItem(row, 0, QTableWidgetItem(category_display))
                self.non_income_table.setItem(row, 1, QTableWidgetItem(_format_inr(amount)))

    def _render_fd_table(self):
        """Render the FD reconciliation table."""
        if not self.merge_result:
            return

        fd_matches = self.merge_result.get('fd_matches', {})
        fd_not_in_app = self.merge_result.get('fd_not_in_app', [])

        self.fd_table.setRowCount(0)

        # Matched FDs
        for account_no, match_data in sorted(fd_matches.items()):
            row = self.fd_table.rowCount()
            self.fd_table.insertRow(row)

            fd_id = match_data.get('fd_id', '—')
            ais_amount = match_data.get('ais_amount', 0)

            self.fd_table.setItem(row, 0, QTableWidgetItem(account_no))
            self.fd_table.setItem(row, 1, QTableWidgetItem(_format_inr(ais_amount)))
            self.fd_table.setItem(row, 2, QTableWidgetItem(str(fd_id)))
            self.fd_table.setItem(row, 3, QTableWidgetItem("✓ Matched"))

        # Unmatched FDs
        for account_no in sorted(fd_not_in_app):
            row = self.fd_table.rowCount()
            self.fd_table.insertRow(row)

            self.fd_table.setItem(row, 0, QTableWidgetItem(account_no))
            self.fd_table.setItem(row, 1, QTableWidgetItem("—"))
            self.fd_table.setItem(row, 2, QTableWidgetItem("—"))
            status_item = QTableWidgetItem("⚠ Not in App")
            status_item.setForeground(QColor(Theme.WARNING))
            self.fd_table.setItem(row, 3, status_item)

    def refresh_theme(self):
        """Called after a live theme switch."""
        # Theme colors are baked into style tokens; global QSS handles the rest
        pass
