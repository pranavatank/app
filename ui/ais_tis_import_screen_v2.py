"""
ui/ais_tis_import_screen_v2.py — Enhanced AIS/TIS Import Screen with dual tabs.

Supports both Form 26AS and AIS/TIS imports with intelligent TAN matching.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QTabWidget, QDialog, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import set_btn_icon, tab_icon
from ui.widgets.excel_table import ExcelTableWithStats, enable_copy_shortcut, NoFocusRectDelegate
from ui.widgets.loader import Loader
from ui.widgets.toast_utils import show_success, show_warning, show_info
from core.session import session
from models.person import get_person, get_ais_tis_password, set_ais_tis_password
from models.form26as import save_form26as_import, get_form26as_import, get_form26as_records
from models.ais_tis_import import (
    save_ais_tis_data, get_ais_tis_data, save_ais_tis_records,
    get_ais_tis_records, save_ais_tis_pdf_lines,
)
from models.income_source import (
    get_income_source_by_tan, save_income_source, get_all_income_sources,
    SOURCE_TYPES, SOURCE_TYPE_EMPLOYER, SOURCE_TYPE_BANK
)
from engines.form26as_parser import parse_form26as_pdf, parse_form26as_text_simple, extract_financial_year_from_ay
from engines.ais_tis_parser import (
    parse_ais_json, parse_tis_json, parse_ais_pdf_text, parse_tis_pdf_text,
)
from engines.pdf_extractor import extract_pdf_text, PDFExtractionError
from ui.dialogs.password_dialog import PasswordDialog
import json

_BUCKET_KEYS = ["salary_income", "fd_interest", "savings_interest", "other_interest",
                "dividend_income", "rental_income", "other_income"]


# ══════════════════════════════════════════════════════════════════════════════
# Worker classes for parsing AIS/TIS/26AS PDFs in background thread
# ══════════════════════════════════════════════════════════════════════════════

class _AISTISParseWorker(QObject):
    """Worker that parses AIS/TIS PDF text in a background thread."""
    finished = pyqtSignal(dict)  # Emits parsed result dict
    error = pyqtSignal(object)   # Emits exception
    progress = pyqtSignal(str)   # Emits progress message

    def __init__(self, pdf_text: str, source_type: str):
        super().__init__()
        self.pdf_text = pdf_text
        self.source_type = source_type

    def run(self):
        """Parse AIS/TIS PDF text in background thread."""
        try:
            self.progress.emit(f"Parsing {self.source_type} PDF...")
            parser = parse_ais_pdf_text if self.source_type == "AIS" else parse_tis_pdf_text
            parsed = parser(self.pdf_text)
            self.finished.emit(parsed)
        except Exception as e:
            self.error.emit(e)


class _Form26ASParseWorker(QObject):
    """Worker that parses Form 26AS PDF text in a background thread."""
    finished = pyqtSignal(dict)  # Emits parsed result dict
    error = pyqtSignal(object)   # Emits exception
    progress = pyqtSignal(str)   # Emits progress message

    def __init__(self, pdf_text: str):
        super().__init__()
        self.pdf_text = pdf_text

    def run(self):
        """Parse Form 26AS PDF text in background thread."""
        try:
            self.progress.emit("Parsing Form 26AS PDF...")
            parsed = parse_form26as_pdf(self.pdf_text)
            if not parsed["records"]:
                parsed["records"] = parse_form26as_text_simple(self.pdf_text)
            self.finished.emit(parsed)
        except Exception as e:
            self.error.emit(e)


def _bucket_for_json_type(type_str: str) -> str:
    """Classify a JSON-parsed AIS/TIS detail record (which carries a plain
    'type' label, not the PDF parser's 'bucket' field) into the same
    aggregate buckets engines.ais_tis_parser uses."""
    t = (type_str or "").lower()
    if "salary" in t:
        return "salary_income"
    if "fd" in t or "fixed deposit" in t:
        return "fd_interest"
    if "savings" in t:
        return "savings_interest"
    if "interest" in t:
        return "other_interest"
    if "dividend" in t:
        return "dividend_income"
    if "rental" in t:
        return "rental_income"
    return "other_income"


def _recompute_aggregates_from_records(records: list[dict]) -> dict:
    """
    Re-derive the salary/interest/dividend/... bucket totals and total TDS
    from the FINAL user-approved (edited/filtered) record list, instead of
    trusting the totals the parser computed before the user had a chance to
    fix mis-parsed amounts or drop bad rows.

    Mirrors engines.ais_tis_parser's own accounting rule for PDF-sourced
    records: 'summary' rows carry the bucket amount, 'detail' rows carry
    the TDS breakdown, so both are counted (not double-counted). Records
    without a record_type (the JSON import path, which has no
    summary/detail split) are counted once for both amount and TDS.
    """
    totals = {k: 0.0 for k in _BUCKET_KEYS}
    tds_total = 0.0
    for rec in records:
        bucket = rec.get("bucket") or "other_income"
        if bucket not in totals:
            bucket = "other_income"
        rtype = rec.get("record_type")
        if rtype == "summary":
            totals[bucket] += float(rec.get("amount") or 0)
        elif rtype == "detail":
            tds_total += float(rec.get("tds_deducted") or 0)
        else:
            totals[bucket] += float(rec.get("amount") or 0)
            tds_total += float(rec.get("tds_deducted") or 0)
    totals["tds_deducted"] = tds_total
    return totals


class AISTISImportScreenV2(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)

        # Compact Header
        header = self._build_header()
        layout.addWidget(header)

        # Tab widget with 3 tabs — relies entirely on the global QSS
        # (QTabWidget::pane / QTabBar::tab in ui/theme/theme.py) rather than
        # an inline override, so it live-refreshes on a theme switch like
        # every other tab widget in the app.
        self.tabs = QTabWidget()

        # Tab 1: Form 26AS
        self.tab_26as = self._build_26as_tab()
        self.tabs.addTab(self.tab_26as, "Form 26AS")
        self.tabs.setTabIcon(0, tab_icon("basic_info"))

        # Tab 2: AIS
        self.tab_ais = self._build_ais_tab()
        self.tabs.addTab(self.tab_ais, "AIS")
        self.tabs.setTabIcon(1, tab_icon("account_found"))

        # Tab 3: TIS
        self.tab_tis = self._build_tis_tab()
        self.tabs.addTab(self.tab_tis, "TIS")
        self.tabs.setTabIcon(2, tab_icon("chart_overview"))

        layout.addWidget(self.tabs, 1)
        
        # Debug panel at bottom (collapsible)
        self._build_debug_panel(layout)

    def _build_header(self) -> QFrame:
        self._header_frame = header = QFrame()
        header.setObjectName("aisTisHeaderFrame")
        header.setGraphicsEffect(Theme.shadow_card())
        h_layout = QHBoxLayout(header)
        h_layout.setSpacing(12)

        self._title_lbl = title = QLabel("Income Tax Data Import")
        title.setObjectName("aisTisTitle")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        h_layout.addWidget(title)

        self.person_label = QLabel("Select person")
        self.person_label.setObjectName("aisTisPersonLabel")
        h_layout.addWidget(self.person_label)
        h_layout.addStretch()

        return header

    def _build_26as_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Import button
        btn_layout = QHBoxLayout()
        btn_import = Theme.btn("Import Form 26AS PDF", "primary", height=36, min_width=200)
        btn_import.setAccessibleName("Import Form 26AS PDF")
        set_btn_icon(btn_import, "import")
        btn_import.clicked.connect(self._import_26as)
        btn_layout.addWidget(btn_import)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Table with scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table_26as = QTableWidget()
        self.table_26as.setAccessibleName("Form 26AS records table")
        self.table_26as.setColumnCount(7)
        self.table_26as.setHorizontalHeaderLabels([
            "Deductor Name", "TAN", "Section", "Date", "Amount Paid", "TDS Deducted", "Status"
        ])
        self.table_26as.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_26as.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_26as.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_26as.setItemDelegate(NoFocusRectDelegate(self.table_26as))
        enable_copy_shortcut(self.table_26as)
        table_layout.addWidget(self.table_26as)
        
        scroll.setWidget(table_container)
        layout.addWidget(scroll, 1)
        return tab

    def _build_ais_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Import buttons
        btn_layout = QHBoxLayout()
        btn_import_pdf = Theme.btn("Import AIS PDF", "primary", height=36, min_width=170)
        btn_import_pdf.setAccessibleName("Import AIS PDF")
        set_btn_icon(btn_import_pdf, "import_pdf")
        btn_import_pdf.clicked.connect(self._import_ais_pdf)
        btn_layout.addWidget(btn_import_pdf)
        btn_import_json = Theme.btn("Import AIS JSON", "success", height=36, min_width=180)
        btn_import_json.setAccessibleName("Import AIS JSON")
        set_btn_icon(btn_import_json, "import")
        btn_import_json.clicked.connect(self._import_ais)
        btn_layout.addWidget(btn_import_json)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Table
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table_ais = QTableWidget()
        self.table_ais.setAccessibleName("AIS records table")
        self.table_ais.setColumnCount(6)
        self.table_ais.setHorizontalHeaderLabels([
            "Source", "TAN", "Type", "Amount", "TDS", "Quarter"
        ])
        self.table_ais.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_ais.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_ais.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_ais.setItemDelegate(NoFocusRectDelegate(self.table_ais))
        enable_copy_shortcut(self.table_ais)
        table_layout.addWidget(self.table_ais)
        
        scroll.setWidget(table_container)
        layout.addWidget(scroll, 1)
        return tab

    def _build_tis_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Import buttons
        btn_layout = QHBoxLayout()
        btn_import_pdf = Theme.btn("Import TIS PDF", "primary", height=36, min_width=170)
        btn_import_pdf.setAccessibleName("Import TIS PDF")
        set_btn_icon(btn_import_pdf, "import_pdf")
        btn_import_pdf.clicked.connect(self._import_tis_pdf)
        btn_layout.addWidget(btn_import_pdf)
        btn_import_json = Theme.btn("Import TIS JSON", "info", height=36, min_width=180)
        btn_import_json.setAccessibleName("Import TIS JSON")
        set_btn_icon(btn_import_json, "import")
        btn_import_json.clicked.connect(self._import_tis)
        btn_layout.addWidget(btn_import_json)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Table
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table_tis = QTableWidget()
        self.table_tis.setAccessibleName("TIS records table")
        self.table_tis.setColumnCount(6)
        self.table_tis.setHorizontalHeaderLabels([
            "Source", "TAN", "Type", "Amount", "TDS", "Quarter"
        ])
        self.table_tis.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_tis.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_tis.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_tis.setItemDelegate(NoFocusRectDelegate(self.table_tis))
        enable_copy_shortcut(self.table_tis)
        table_layout.addWidget(self.table_tis)
        
        scroll.setWidget(table_container)
        layout.addWidget(scroll, 1)
        return tab

    def _build_debug_panel(self, parent_layout):
        """Collapsible debug panel at bottom."""
        self.debug_frame = QFrame()
        self.debug_frame.setObjectName("aisTisDebugFrame")
        self.debug_frame.setMaximumHeight(200)
        self.debug_frame.hide()

        debug_layout = QVBoxLayout(self.debug_frame)
        debug_layout.setContentsMargins(8, 8, 8, 8)
        debug_layout.setSpacing(4)

        debug_header = QHBoxLayout()
        debug_title = QLabel("Debug: Extracted Text")
        debug_title.setObjectName("aisTisDebugTitle")
        debug_header.addWidget(debug_title)
        debug_header.addStretch()

        btn_close_debug = QPushButton("✕")
        btn_close_debug.setObjectName("aisTisCloseDebugBtn")
        btn_close_debug.setFixedSize(20, 20)
        btn_close_debug.clicked.connect(self.debug_frame.hide)
        debug_header.addWidget(btn_close_debug)
        debug_layout.addLayout(debug_header)

        self.debug_text = QTextEdit()
        self.debug_text.setObjectName("aisTisDebugText")
        self.debug_text.setReadOnly(True)
        debug_layout.addWidget(self.debug_text)
        
        parent_layout.addWidget(self.debug_frame)
        
        # Toggle button
        self.btn_toggle_debug = Theme.btn("Show Debug", "ghost", height=28, min_width=120)
        set_btn_icon(self.btn_toggle_debug, "debug")
        self.btn_toggle_debug.clicked.connect(self._toggle_debug)
        parent_layout.addWidget(self.btn_toggle_debug)

    def refresh_theme(self):
        """Called after a live theme switch — re-apply shadow effects and
        refresh data since person_label styling depends on selection state."""
        if hasattr(self, "_header_frame"):
            self._header_frame.setGraphicsEffect(Theme.shadow_card())
        self.refresh()

    def refresh(self):
        pid = session.selected_person_id
        fy = session.selected_fy

        if not pid:
            self.person_label.setText("Please select a person from the top bar")
            self.person_label.setProperty("variant", "warning")
            self.person_label.style().unpolish(self.person_label)
            self.person_label.style().polish(self.person_label)
            self.table_26as.setRowCount(0)
            self.table_ais.setRowCount(0)
            self.table_tis.setRowCount(0)
            return

        person = get_person(pid)
        if person:
            self.person_label.setText(f"{person['full_name']} · FY {fy}")
            self.person_label.setProperty("variant", "selected")
            self.person_label.style().unpolish(self.person_label)
            self.person_label.style().polish(self.person_label)

        self._load_26as_data()
        self._load_ais_data()
        self._load_tis_data()

    def _load_tis_data(self):
        """Load TIS data separately from AIS."""
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            self.table_tis.setRowCount(0)
            return

        import_data = get_ais_tis_data(pid, fy, source_type="TIS")
        if not import_data:
            self.table_tis.setRowCount(0)
            return

        records = get_ais_tis_records(import_data["import_id"])
        self.table_tis.setRowCount(len(records))
        
        for row_idx, rec in enumerate(records):
            self.table_tis.setItem(row_idx, 0, QTableWidgetItem(rec.get("information_source") or ""))
            self.table_tis.setItem(row_idx, 1, QTableWidgetItem(rec.get("source_tan") or ""))
            self.table_tis.setItem(row_idx, 2, QTableWidgetItem(rec.get("information_code") or ""))
            
            amount = rec.get("amount") or 0
            self.table_tis.setItem(row_idx, 3, QTableWidgetItem(f"₹ {amount:,.2f}"))
            
            tds = rec.get("tds_deducted") or 0
            self.table_tis.setItem(row_idx, 4, QTableWidgetItem(f"₹ {tds:,.2f}"))
            
            self.table_tis.setItem(row_idx, 5, QTableWidgetItem(rec.get("quarter") or ""))

    def _import_26as(self):
        pid = session.selected_person_id
        fy = session.selected_fy

        if not pid:
            show_warning("Please select a person from the top bar.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Form 26AS PDF", "", "PDF Files (*.pdf)"
        )

        if not file_path:
            return

        try:
            # Extract text from PDF
            result = extract_pdf_text(file_path)
            pdf_text = result.text

            # Show debug
            self.debug_text.setPlainText(pdf_text[:5000])  # First 5000 chars
            self.debug_frame.show()
            self.btn_toggle_debug.setText("Hide Debug")

            def on_parse_done(parsed):
                """Callback on GUI thread after Form 26AS parse completes."""
                try:
                    if not parsed["records"]:
                        show_info("No TDS records found in PDF.")
                        return

                    # Determine FY
                    if parsed["assessment_year"]:
                        import_fy = extract_financial_year_from_ay(parsed["assessment_year"])
                    else:
                        import_fy = fy

                    # Preview & edit before writing anything to the database
                    preview = RecordsPreviewDialog(
                        self, "Preview Form 26AS Records", parsed["records"],
                        columns=[
                            ("Deductor Name", "deductor_name", False),
                            ("TAN", "deductor_tan", False),
                            ("Section", "section", False),
                            ("Date", "transaction_date", False),
                            ("Amount Paid", "amount_paid", True),
                            ("TDS Deducted", "tds_deducted", True),
                            ("Status", "status", False),
                        ],
                    )
                    if preview.exec() != QDialog.DialogCode.Accepted:
                        return
                    approved_records = preview.get_selected_records()
                    if not approved_records:
                        show_info("No rows were selected.")
                        return

                    # Process records and match with income sources
                    processed_records = []
                    new_sources = []

                    for rec in approved_records:
                        tan = (rec.get("deductor_tan") or "").strip().upper()
                        rec["deductor_tan"] = tan
                        if not tan:
                            continue

                        # Check if income source exists
                        source = get_income_source_by_tan(tan)

                        if not source:
                            # New TAN - ask user to link or create
                            new_sources.append(rec)

                        processed_records.append(rec)

                    # Show dialog for new sources
                    if new_sources:
                        self._handle_new_sources(new_sources)

                    # Save to database
                    import_id = save_form26as_import(
                        person_id=pid,
                        financial_year=import_fy,
                        records=processed_records,
                        source_file=file_path,
                        raw_text=pdf_text,
                    )

                    show_success(f"Imported {len(processed_records)} TDS records from Form 26AS.")

                    self._load_26as_data()

                except Exception as e:
                    QMessageBox.critical(self, "Import Error", f"Failed to import Form 26AS:\n{str(e)}")

            def on_parse_error(exc):
                """Callback if parse fails."""
                QMessageBox.critical(self, "Parse Failed", f"Could not parse PDF.\n\nError: {exc}")

            # Run parser in background thread
            worker = _Form26ASParseWorker(pdf_text)
            Loader.run(
                self,
                fn=worker.run,
                message="Parsing Form 26AS PDF…",
                subtitle="Extracting TDS records",
                on_done=on_parse_done,
                on_error=on_parse_error
            )

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import Form 26AS:\n{str(e)}")

    def _import_ais_pdf(self):
        self._import_ais_tis_pdf("AIS")

    def _import_tis_pdf(self):
        self._import_ais_tis_pdf("TIS")

    def _is_pdf_encrypted(self, file_path: str) -> bool:
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            return bool(getattr(reader, "is_encrypted", False))
        except Exception:
            return False

    def _is_password_error(self, error: Exception) -> bool:
        msg = str(error).lower()
        return "password" in msg or "encrypted" in msg

    def _prompt_ais_tis_password(self, saved_password: str | None) -> tuple[str | None, bool]:
        info_text = (
            "This PDF is encrypted. Enter the AIS/TIS password to continue."
        )
        hint_text = (
            "Common formats:\n"
            "- PAN only (e.g. ABCDE1234F)\n"
            "- PAN + DOB (e.g. ABCDE1234F01011990)\n"
            "- DOB in DDMMYYYY format"
        )
        dlg = PasswordDialog(
            self,
            title="Enter AIS/TIS Password",
            info_text=info_text,
            hint_text=hint_text,
            placeholder_text="PAN or PAN + DOB",
            prefill_password=saved_password,
            save_label="Save or update password for this person",
            save_checked=True,
            accept_label="Decrypt and Import",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None, False
        password = dlg.get_password()
        if not password:
            show_warning("Password is required to open the PDF.")
            return None, False
        return password, dlg.should_save()

    def _import_ais_tis_pdf(self, source_type: str):
        pid = session.selected_person_id
        fy = session.selected_fy

        if not pid:
            show_warning("Please select a person from the top bar.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Select {source_type} PDF", "", "PDF Files (*.pdf)"
        )

        if not file_path:
            return

        saved_password = get_ais_tis_password(pid, session.aes_key)
        password = None
        save_password = False

        if self._is_pdf_encrypted(file_path):
            password, save_password = self._prompt_ais_tis_password(saved_password)
            if not password:
                return

        while True:
            try:
                result = extract_pdf_text(file_path, password=password)
                break
            except PDFExtractionError as e:
                if self._is_password_error(e):
                    show_warning("The password did not unlock the PDF. Please try again.")
                    password, save_password = self._prompt_ais_tis_password(password or saved_password)
                    if not password:
                        return
                    continue
                QMessageBox.critical(
                    self, "PDF Extraction Failed",
                    f"Could not extract text.\n\nError: {e}")
                return

        if save_password and password:
            set_ais_tis_password(pid, password, session.aes_key)

        pdf_text = result.text
        self.debug_text.setPlainText(pdf_text[:5000])
        self.debug_frame.show()
        self.btn_toggle_debug.setText("Hide Debug")

        # Store context for later use in callback
        self._ais_tis_import_context = {
            "pdf_text": pdf_text,
            "source_type": source_type,
            "pid": pid,
            "fy": fy
        }

        def on_parse_done(parsed):
            """Callback on GUI thread after AIS/TIS parse completes."""
            try:
                details = parsed.get("details") or []
                if not details:
                    show_info(f"No {source_type} records found in the PDF.")
                    return

                # Preview & edit before writing anything to the database
                preview = RecordsPreviewDialog(
                    self, f"Preview {source_type} Records", details,
                    columns=[
                        ("Source", "information_source", False),
                        ("TAN", "source_tan", False),
                        ("Code", "information_code", False),
                        ("Amount", "amount", True),
                        ("TDS", "tds_deducted", True),
                        ("Quarter", "quarter", False),
                    ],
                )
                if preview.exec() != QDialog.DialogCode.Accepted:
                    return
                approved_details = preview.get_selected_records()
                if not approved_details:
                    show_info("No rows were selected.")
                    return
                for rec in approved_details:
                    rec["source_tan"] = (rec.get("source_tan") or "").strip().upper()

                parsed = dict(parsed)
                parsed["details"] = approved_details
                parsed.update(_recompute_aggregates_from_records(approved_details))

                existing = get_ais_tis_data(pid, fy, source_type=source_type)
                if existing:
                    merged = dict(parsed)
                    for key in _BUCKET_KEYS + ["tds_deducted"]:
                        if merged.get(key, 0) == 0 and existing.get(key, 0) not in (None, 0):
                            merged[key] = existing[key]
                    parsed = merged

                import_id = save_ais_tis_data(
                    person_id=pid,
                    financial_year=fy,
                    source_type=source_type,
                    raw_json=pdf_text,
                    data=parsed
                )
                new_sources = []
                if import_id:
                    save_ais_tis_pdf_lines(import_id, pdf_text)
                    save_ais_tis_records(import_id, approved_details)

                    for rec in approved_details:
                        tan = rec.get("source_tan") or ""
                        if tan and not get_income_source_by_tan(tan):
                            new_sources.append(rec)

                if import_id and new_sources:
                    self._handle_new_sources_ais(new_sources)

                show_success(f"Imported {len(approved_details)} {source_type} record(s) for FY {fy}.")

                if source_type == "AIS":
                    self._load_ais_data()
                else:
                    self._load_tis_data()

            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))

        def on_parse_error(exc):
            """Callback if parse fails."""
            QMessageBox.critical(self, "Parse Failed", f"Could not parse PDF.\n\nError: {exc}")

        def on_parse_progress(msg):
            """Update progress during parse."""
            pass  # Loader.run() handles progress display

        # Run parser in background thread
        worker = _AISTISParseWorker(pdf_text, source_type)
        worker.progress.connect(on_parse_progress)

        Loader.run(
            self,
            fn=worker.run,
            message=f"Parsing {source_type} PDF…",
            subtitle="Extracting income and TDS records",
            on_done=on_parse_done,
            on_error=on_parse_error
        )

    def _import_ais(self):
        pid = session.selected_person_id
        fy = session.selected_fy

        if not pid:
            show_warning("Please select a person from the top bar.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select AIS/TIS JSON", "", "JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_json = f.read()
                json_data = json.loads(raw_json)

            source_type = "AIS"
            parsed = parse_ais_json(json_data)

            self.debug_text.setPlainText(raw_json[:5000])
            self.debug_frame.show()
            self.btn_toggle_debug.setText("Hide Debug")

            records = parsed.get("details", [])
            if not records:
                show_info("No AIS records found in the JSON file.")
                return

            formatted_records = [
                {
                    "record_type": "json_detail",
                    "information_code": rec.get("section", ""),
                    "information_description": rec.get("type", ""),
                    "information_source": rec.get("source", rec.get("deductor", "")),
                    "source_tan": rec.get("tan", ""),
                    "amount": rec.get("amount", 0),
                    "tds_deducted": rec.get("tds", 0),
                    "bucket": _bucket_for_json_type(rec.get("type")),
                }
                for rec in records
            ]

            # Preview & edit before writing anything to the database.
            preview = RecordsPreviewDialog(
                self, "Preview AIS Records", formatted_records,
                columns=[
                    ("Source", "information_source", False),
                    ("TAN", "source_tan", False),
                    ("Type", "information_description", False),
                    ("Amount", "amount", True),
                    ("TDS", "tds_deducted", True),
                ],
            )
            if preview.exec() != QDialog.DialogCode.Accepted:
                return
            approved_records = preview.get_selected_records()
            if not approved_records:
                show_info("No rows were selected.")
                return
            for rec in approved_records:
                rec["source_tan"] = (rec.get("source_tan") or "").strip().upper()

            parsed = dict(parsed)
            parsed.update(_recompute_aggregates_from_records(approved_records))

            existing = get_ais_tis_data(pid, fy, source_type=source_type)
            if existing:
                merged = dict(parsed)
                for key in _BUCKET_KEYS + ["tds_deducted"]:
                    if merged.get(key, 0) == 0 and existing.get(key, 0) not in (None, 0):
                        merged[key] = existing[key]
                parsed = merged

            import_id = save_ais_tis_data(
                person_id=pid,
                financial_year=fy,
                source_type=source_type,
                raw_json=raw_json,
                data=parsed
            )

            new_sources = []
            if import_id:
                save_ais_tis_records(import_id, approved_records)
                for rec in approved_records:
                    tan = rec.get("source_tan") or ""
                    if tan and not get_income_source_by_tan(tan):
                        new_sources.append(rec)

            if new_sources:
                self._handle_new_sources_ais(new_sources)

            show_success(f"Imported {len(approved_records)} AIS record(s) for FY {fy}.")

            self._load_ais_data()

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import AIS/TIS:\n{str(e)}")

    def _handle_new_sources(self, records: list[dict]):
        """Handle new TANs found in Form 26AS."""
        dialog = NewSourceDialog(records, "26AS", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for rec, source_type in dialog.get_results():
                tan = rec.get("deductor_tan", "").strip().upper()
                name = rec.get("deductor_name", "Unknown")
                
                save_income_source(
                    source_type=source_type,
                    source_name=name,
                    tan=tan
                )

    def _handle_new_sources_ais(self, records: list[dict]):
        """Handle new TANs found in AIS/TIS."""
        dialog = NewSourceDialog(records, "AIS", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for rec, source_type in dialog.get_results():
                tan = rec.get("source_tan", "").strip().upper()
                name = rec.get("information_source", "Unknown")
                
                save_income_source(
                    source_type=source_type,
                    source_name=name,
                    tan=tan
                )

    def _load_26as_data(self):
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            self.table_26as.setRowCount(0)
            return
        
        import_data = get_form26as_import(pid, fy)
        if not import_data:
            self.table_26as.setRowCount(0)
            return
        
        records = get_form26as_records(import_data["import_id"])
        self.table_26as.setRowCount(len(records))
        
        for row, rec in enumerate(records):
            self.table_26as.setItem(row, 0, QTableWidgetItem(rec.get("deductor_name") or ""))
            self.table_26as.setItem(row, 1, QTableWidgetItem(rec.get("deductor_tan") or ""))
            self.table_26as.setItem(row, 2, QTableWidgetItem(rec.get("section") or ""))
            self.table_26as.setItem(row, 3, QTableWidgetItem(rec.get("transaction_date") or ""))
            
            amount_paid = rec.get("amount_paid") or 0
            self.table_26as.setItem(row, 4, QTableWidgetItem(f"₹ {amount_paid:,.2f}"))
            
            tds = rec.get("tds_deducted") or 0
            self.table_26as.setItem(row, 5, QTableWidgetItem(f"₹ {tds:,.2f}"))
            
            self.table_26as.setItem(row, 6, QTableWidgetItem(rec.get("status") or ""))

    def _load_ais_data(self):
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            self.table_ais.setRowCount(0)
            return

        import_data = get_ais_tis_data(pid, fy, source_type="AIS")
        if not import_data:
            self.table_ais.setRowCount(0)
            return
        
        records = get_ais_tis_records(import_data["import_id"])
        self.table_ais.setRowCount(len(records))
        
        for row, rec in enumerate(records):
            self.table_ais.setItem(row, 0, QTableWidgetItem(rec.get("information_source") or ""))
            self.table_ais.setItem(row, 1, QTableWidgetItem(rec.get("source_tan") or ""))
            self.table_ais.setItem(row, 2, QTableWidgetItem(rec.get("information_code") or ""))
            
            amount = rec.get("amount") or 0
            self.table_ais.setItem(row, 3, QTableWidgetItem(f"₹ {amount:,.2f}"))
            
            tds = rec.get("tds_deducted") or 0
            self.table_ais.setItem(row, 4, QTableWidgetItem(f"₹ {tds:,.2f}"))
            
            self.table_ais.setItem(row, 5, QTableWidgetItem(rec.get("quarter") or ""))

    def _toggle_debug(self):
        """Toggle debug panel visibility."""
        if self.debug_frame.isVisible():
            self.debug_frame.hide()
            self.btn_toggle_debug.setText("Show Debug")
        else:
            self.debug_frame.show()
            self.btn_toggle_debug.setText("Hide Debug")

    def _import_tis(self):
        """Import TIS JSON - similar to AIS but separate storage."""
        pid = session.selected_person_id
        fy = session.selected_fy

        if not pid:
            show_warning("Please select a person from the top bar.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select TIS JSON", "", "JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_json = f.read()
                json_data = json.loads(raw_json)

            parsed = parse_tis_json(json_data)

            self.debug_text.setPlainText(raw_json[:5000])
            self.debug_frame.show()
            self.btn_toggle_debug.setText("Hide Debug")

            records = parsed.get("details", [])
            if not records:
                show_info("No TIS records found in the JSON file.")
                return

            formatted_records = [
                {
                    "record_type": "json_detail",
                    "information_code": rec.get("section", ""),
                    "information_description": rec.get("type", ""),
                    "information_source": rec.get("source", rec.get("deductor", "")),
                    "source_tan": rec.get("tan", ""),
                    "amount": rec.get("amount", 0),
                    "tds_deducted": rec.get("tds", 0),
                    "bucket": _bucket_for_json_type(rec.get("type")),
                }
                for rec in records
            ]

            # Preview & edit before writing anything to the database.
            preview = RecordsPreviewDialog(
                self, "Preview TIS Records", formatted_records,
                columns=[
                    ("Source", "information_source", False),
                    ("TAN", "source_tan", False),
                    ("Type", "information_description", False),
                    ("Amount", "amount", True),
                    ("TDS", "tds_deducted", True),
                ],
            )
            if preview.exec() != QDialog.DialogCode.Accepted:
                return
            approved_records = preview.get_selected_records()
            if not approved_records:
                show_info("No rows were selected.")
                return
            for rec in approved_records:
                rec["source_tan"] = (rec.get("source_tan") or "").strip().upper()

            parsed = dict(parsed)
            parsed.update(_recompute_aggregates_from_records(approved_records))

            # Save to database with TIS source type
            import_id = save_ais_tis_data(
                person_id=pid,
                financial_year=fy,
                source_type="TIS",
                raw_json=raw_json,
                data=parsed
            )

            new_sources = []
            if import_id:
                save_ais_tis_records(import_id, approved_records)
                for rec in approved_records:
                    tan = rec.get("source_tan") or ""
                    if tan and not get_income_source_by_tan(tan):
                        new_sources.append(rec)

            if new_sources:
                self._handle_new_sources_ais(new_sources)

            show_success(f"Imported {len(approved_records)} TIS record(s) for FY {fy}.")

            self._load_tis_data()

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import TIS:\n{str(e)}")


class RecordsPreviewDialog(QDialog):
    """
    Editable preview of parsed records before they're written to the
    database — mirrors the statement-import wizard's "Preview & Import"
    step (ui/statement_import_screen_modern.py) so 26AS/AIS/TIS imports get
    the same review-and-fix-before-insert safety net instead of inserting
    whatever the regex/PDF parser produced, unseen and uneditable.
    """

    def __init__(self, parent, title: str, records: list[dict],
                 columns: list[tuple[str, str, bool]], subtitle: str = ""):
        """
        columns: list of (header_label, record_dict_key, is_numeric) in
        display order. Every visible column is editable; rows default to
        checked (included) and can be unchecked to exclude them from import.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(860, 500)
        self._records = [dict(r) for r in records]
        self._columns = columns
        self._build_ui(title, subtitle)
        self._populate()

    def _build_ui(self, title: str, subtitle: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 16)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        t.setProperty("textrole", "title-sm")
        layout.addWidget(t)

        sub_text = subtitle or (
            f"Review the {len(self._records)} extracted record(s) below. "
            "Double-click any cell to fix a parsing mistake, uncheck a row "
            "to skip it, then confirm to save."
        )
        s = QLabel(sub_text)
        s.setWordWrap(True)
        s.setProperty("textrole", "muted-md")
        layout.addWidget(s)

        self.table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.table = self.table_widget.table
        self.table.setHeaders([c[0] for c in self._columns])
        numeric_cols = [i for i, c in enumerate(self._columns) if c[2]]
        self.table.setNumericColumns(numeric_cols)
        enable_copy_shortcut(self.table)
        layout.addWidget(self.table_widget, 1)

        btn_row = QHBoxLayout()
        self.count_lbl = QLabel("")
        self.count_lbl.setProperty("textrole", "muted-sm")
        btn_row.addWidget(self.count_lbl)
        btn_row.addStretch()
        btn_cancel = Theme.btn("Cancel", "secondary", height=38, min_width=110)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_confirm = Theme.btn("Confirm & Save", "primary", height=38, min_width=170)
        set_btn_icon(btn_confirm, "save")
        btn_confirm.clicked.connect(self.accept)
        btn_row.addWidget(btn_confirm)
        layout.addLayout(btn_row)

    def _populate(self):
        self.table.blockSignals(True)
        for rec in self._records:
            row_values = [self._fmt(rec.get(key), numeric) for _, key, numeric in self._columns]
            self.table.addDataRow(row_values, checked=True)
        self.table.blockSignals(False)
        self.count_lbl.setText(f"{len(self._records)} record(s) parsed")

    @staticmethod
    def _fmt(value, numeric: bool) -> str:
        if value is None or value == "":
            return ""
        if numeric:
            try:
                return f"{float(value):,.2f}"
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    def get_selected_records(self) -> list[dict]:
        """Read back the (possibly edited) checked rows as record dicts."""
        checked = set(self.table.getCheckedRows())
        results = []
        for row in sorted(checked):
            rec = dict(self._records[row])
            for col, (_, key, numeric) in enumerate(self._columns):
                item = self.table.item(row, col + 1)
                text = (item.text() if item else "").strip()
                if numeric:
                    cleaned = text.replace("₹", "").replace(",", "").strip()
                    try:
                        rec[key] = float(cleaned) if cleaned else 0.0
                    except ValueError:
                        rec[key] = rec.get(key, 0.0)
                else:
                    rec[key] = text or None
            results.append(rec)
        return results


class NewSourceDialog(QDialog):
    """Dialog to handle new income sources found during import."""
    
    def __init__(self, records: list[dict], source_type: str, parent=None):
        super().__init__(parent)
        self.records = records
        self.source_type = source_type
        self.combos = []
        self.setWindowTitle("New Income Sources Found")
        self.setMinimumWidth(600)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel(f"New TANs found in {self.source_type}")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setProperty("textrole", "title-sm")
        layout.addWidget(title)
        
        info = QLabel(
            "The following TANs are not in your database. "
            "Please select the type of income source for each:"
        )
        info.setWordWrap(True)
        info.setProperty("textrole", "body-sm")
        layout.addWidget(info)
        
        # Form for each record
        form_frame = QFrame()
        form_frame.setStyleSheet(Theme.card_style(radius=10, padding=12))
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(12)
        
        for rec in self.records[:10]:  # Limit to 10
            if self.source_type == "26AS":
                tan = rec.get("deductor_tan", "")
                name = rec.get("deductor_name", "Unknown")
            else:
                tan = rec.get("source_tan", "")
                name = rec.get("information_source", "Unknown")
            
            label = QLabel(f"{name}\n{tan}")
            label.setProperty("textrole", "muted-sm")
            
            combo = QComboBox()
            combo.addItems(SOURCE_TYPES)
            combo.setCurrentText(SOURCE_TYPE_EMPLOYER)
            combo.setMinimumHeight(32)
            
            self.combos.append((rec, combo))
            form_layout.addRow(label, combo)
        
        layout.addWidget(form_frame)
        
        if len(self.records) > 10:
            note = QLabel(f"Note: Showing first 10 of {len(self.records)} new sources.")
            note.setProperty("textrole", "muted-sm")
            layout.addWidget(note)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = Theme.btn("Cancel", "secondary", height=36, min_width=100)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_save = Theme.btn("Save", "primary", height=36, min_width=100)
        btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
    
    def get_results(self) -> list[tuple]:
        """Returns list of (record, source_type) tuples."""
        return [(rec, combo.currentText()) for rec, combo in self.combos]
