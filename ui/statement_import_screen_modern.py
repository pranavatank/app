"""
ui/statement_import_screen_modern.py — Modern 2-screen statement import.

Screen 1: Selection (Person + Account + File in one view)
Screen 2: Preview & Import (Editable table + Import)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFrame, QCheckBox,
    QPlainTextEdit, QApplication, QDialog,
    QInputDialog,
    QStackedWidget, QScrollArea, QSizePolicy, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QMimeData
from PyQt6.QtGui import QFont, QColor, QDragEnterEvent, QDropEvent
from datetime import datetime
import json
import os
import re

from ui.widgets.excel_table import ExcelTableWithStats
from ui.widgets.loader import Loader
from ui.widgets.toast_utils import show_success, show_warning, show_info
from ui.theme import Theme
from ui.icons import icon_label, set_btn_icon, pixmap as icon_pixmap
from ui.date_utils import format_display_date
from core.session import session
from models.person import get_all_persons
from models.bank_account import (
    get_accounts_for_person, get_account, update_account,
    get_statement_password, set_statement_password
)
from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
from models.transaction import add_transaction, check_duplicate, display_transaction_type
from models.transaction import add_transactions_batch, delete_transactions_by_ids
from models.fixed_deposit import add_fd_from_statement, apply_statement_redemption_event
from models.statement_import_log import log_import
from engines.statement_parser import (
    parse_statement_with_debug, validate_transactions,
    extract_statement_text, is_pdf_encrypted, is_excel_encrypted,
    StatementPasswordError, StatementPasswordInvalidError, StatementPasswordRequiredError,

)
from engines.statement.validate import confidence, balance_walk, extract_control_totals, reconcile_totals, LowConfidenceParse
from engines.statement_metadata_extractor import extract_account_metadata
from engines.interest_engine import allocate_savings_interest_to_fy
from engines.balance_engine import recalculate_account_balance
from config import get_all_financial_years, fy_date_range
from ui.dialogs.account_dialog import AccountDialog
from ui.dialogs.account_metadata_dialog import AccountMetadataDialog
from ui.dialogs.password_dialog import PasswordDialog
from ui.dialogs.column_mapping_dialog import ColumnMappingDialog


# ══════════════════════════════════════════════════════════════════════════════
# Worker class for parsing statements in background thread
# ══════════════════════════════════════════════════════════════════════════════

class _StatementParseWorker(QObject):
    """
    Worker that parses a statement in a background thread.
    Runs parse_statement_with_debug() and emits results via signals.
    """
    finished = pyqtSignal(tuple)  # Emits (txns, debug_info)
    error = pyqtSignal(object)    # Emits exception
    progress = pyqtSignal(str)    # Emits progress message

    def __init__(self, file_path, file_type, bank_name, password, column_mapping):
        super().__init__()
        self.file_path = file_path
        self.file_type = file_type
        self.bank_name = bank_name
        self.password = password
        self.column_mapping = column_mapping

    def run(self):
        """Parse statement in background thread and emit result."""
        try:
            self.progress.emit("Parsing statement...")
            txns, debug_info = parse_statement_with_debug(
                self.file_path,
                self.file_type,
                self.bank_name,
                password=self.password,
                column_mapping=self.column_mapping,
            )
            self.finished.emit((txns, debug_info))
        except Exception as e:
            self.error.emit(e)


class _TransactionImportWorker(QObject):
    """
    Worker that imports transactions in a background thread.
    Handles database insertion, FD creation, and logging.
    Does NOT call allocate_savings_interest_to_fy or recalculate_account_balance — those run on GUI thread.
    """
    finished = pyqtSignal(dict)  # Emits result dict with keys: inserted_ids, imported, fds_created, batch_rows
    error = pyqtSignal(object)   # Emits exception
    progress = pyqtSignal(str)   # Emits progress message

    def __init__(self, selected_account_id, selected_person_id, preview_transactions,
                 preview_duplicate_flags, bank_name, selected_file, file_type, checked_rows):
        super().__init__()
        self.selected_account_id = selected_account_id
        self.selected_person_id = selected_person_id
        self.preview_transactions = preview_transactions
        self.preview_duplicate_flags = preview_duplicate_flags
        self.bank_name = bank_name
        self.selected_file = selected_file
        self.file_type = file_type
        self.checked_rows = checked_rows

    def run(self):
        """Import transactions in background thread."""
        try:
            imported = 0
            fds_created = 0
            batch_rows = []
            batch_preview_rows = []

            # Collect transactions to import
            for idx in self.checked_rows:
                if idx % 25 == 0:
                    count = len([i for i in self.checked_rows if i <= idx])
                    self.progress.emit(f"Importing... {count}/{len(self.checked_rows)} processed")

                is_duplicate = self.preview_duplicate_flags[idx] if idx < len(self.preview_duplicate_flags) else False
                if is_duplicate:
                    continue

                txn = self.preview_transactions[idx]
                batch_rows.append(txn)
                batch_preview_rows.append(idx)

            # Add transactions to database
            inserted_ids = add_transactions_batch(
                account_id=self.selected_account_id,
                person_id=self.selected_person_id,
                transactions=batch_rows,
                source="Statement Import",
            )

            try:
                for txn_id, txn in zip(inserted_ids, batch_rows):
                    imported += 1

                    # Handle FD maturity
                    if txn.get("transaction_type") == "Income":
                        apply_statement_redemption_event(
                            account_id=self.selected_account_id,
                            person_id=self.selected_person_id,
                            transaction_id=txn_id,
                            transaction_date=txn["transaction_date"],
                            amount=float(txn["amount"]),
                            description=txn.get("description") or "",
                            reference_no=txn.get("reference_no"),
                        )

                    # Handle FD opening
                    if self._is_fd_opening_transaction(txn):
                        desc = txn.get("description") or ""
                        fd_ref = self._extract_fd_reference(desc) or txn.get("reference_no")
                        maturity_amt = self._extract_maturity_amount(desc)
                        fd_id = add_fd_from_statement(
                            account_id=self.selected_account_id,
                            person_id=self.selected_person_id,
                            principal_amount=float(txn["amount"]),
                            start_date=txn["transaction_date"],
                            fd_reference_no=fd_ref,
                            tenure_months=None,
                            interest_rate=None,
                            compounding_type=None,
                            maturity_date=None,
                            maturity_amount=maturity_amt,
                            maturity_amount_formula=maturity_amt,
                            maturity_amount_bank=maturity_amt,
                            expected_interest_amount=(maturity_amt - float(txn["amount"])) if maturity_amt else None,
                            source_statement_file=os.path.basename(self.selected_file) if self.selected_file else None,
                            source_transaction_id=txn_id,
                            source_description=desc
                        )
                        if fd_id:
                            fds_created += 1
            except Exception:
                delete_transactions_by_ids(inserted_ids)
                raise

            self.progress.emit("Finalizing import log...")
            log_import(
                account_id=self.selected_account_id,
                person_id=self.selected_person_id,
                bank_name=self.bank_name,
                file_name=(self.selected_file.split("/")[-1] or self.selected_file.split("\\")[-1]),
                file_type=self.file_type,
                records_imported=imported,
                status="Success"
            )

            self.finished.emit({
                "inserted_ids": inserted_ids,
                "imported": imported,
                "fds_created": fds_created,
                "batch_rows": batch_rows
            })
        except Exception as e:
            self.error.emit(e)

    def _is_fd_opening_transaction(self, txn):
        """Check if transaction opens a fixed deposit."""
        desc = (txn.get("description") or "").lower()
        return any(phrase in desc for phrase in ["fd accepted", "opening", "fixed deposit"])

    def _extract_fd_reference(self, desc):
        """Extract FD reference number from description."""
        match = re.search(r'[Rr]ef\.?\s*[:#]?\s*(\S+)', desc)
        return match.group(1) if match else None

    def _extract_maturity_amount(self, desc):
        """Extract maturity amount from description."""
        match = re.search(r'₹?\s*([\d,]+\.?\d*)', desc)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return None


class _SelectionScreenWidget(QWidget):
    """Selection screen with drag-and-drop support"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.statement_import_screen = parent
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path:
                    self.statement_import_screen._handle_file_drop(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()


class StatementImportScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

        # State
        self.selected_person_id = None
        self.selected_account_id = None
        self.selected_file = None
        self.file_type = None
        self.parsed_transactions = []
        self.preview_transactions = []
        self.preview_duplicate_flags = []
        self.bank_name = ""
        self.import_debug_info = {}
        self.validation_errors = []
        self.duplicate_count = 0
        self.statement_text = ""
        self.fds_created_last_import = 0
        self.parse_confidence = 0.0
        self.failing_rows_balance = []
        self._loader = None
        self._preview_cell_change_lock = False
        self._selection_tab_order_ready = False
        self._preview_tab_order_ready = False
        self._parse_password = None
        self._parse_save_password = False

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Stepper only (title already in top bar)
        stepper_layout = QHBoxLayout()
        stepper_layout.addStretch()
        stepper_layout.addWidget(self._build_stepper())
        layout.addLayout(stepper_layout)

        # Stack for 2 screens
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_selection_screen())
        self.stack.addWidget(self._build_preview_screen())
        layout.addWidget(self.stack, stretch=1)

        # Navigation
        nav = QHBoxLayout()
        nav.addStretch()
        self.btn_back = Theme.btn("← Back", "secondary", height=38, min_width=100)
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._go_back)
        self.btn_back.setAccessibleName("Back button")
        self.btn_back.setAccessibleDescription("Return to the previous step in the import wizard.")
        self.btn_back.setToolTip("Return to the previous step in the import wizard.")
        nav.addWidget(self.btn_back)

        self.btn_next = Theme.btn("Parse Statement →", "primary", height=38, min_width=160)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_next.setAccessibleName("Next button")
        self.btn_next.setAccessibleDescription("Continue to parse the statement or import the selected rows.")
        self.btn_next.setToolTip("Continue to parse the statement or import the selected rows.")
        nav.addWidget(self.btn_next)
        layout.addLayout(nav)

    def _build_selection_screen(self) -> QWidget:
        """Screen 1: Person + Account + File selection in one form card"""
        container = _SelectionScreenWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Single form card containing all three selections
        form_card = self._create_card()
        form_layout = QVBoxLayout(form_card)
        form_layout.setSpacing(16)

        # Card title and subtitle
        form_layout.addWidget(self._card_title_row("browse", "Import Statement"))
        form_layout.addWidget(self._card_subtitle("Select person, account, and statement file"))

        # Form fields
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Person selection
        self.person_combo = QComboBox()
        self.person_combo.setMinimumHeight(38)
        self.person_combo.setAccessibleName("Person selection")
        self.person_combo.setAccessibleDescription("Choose the person associated with this bank statement.")
        self.person_combo.setToolTip("Choose the person associated with this bank statement.")
        self.person_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        form.addRow(self._form_label("Family Member"), self.person_combo)

        # Account selection
        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(38)
        self.account_combo.setEnabled(False)
        self.account_combo.setAccessibleName("Bank account selection")
        self.account_combo.setAccessibleDescription("Choose the bank account for the selected person.")
        self.account_combo.setToolTip("Choose the bank account for the selected person.")
        self.account_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._form_label("Account"), self.account_combo)

        # File type selection
        file_type_layout = QHBoxLayout()
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems(["PDF", "Excel"])
        self.file_type_combo.setMinimumHeight(38)
        self.file_type_combo.setMaximumWidth(150)
        self.file_type_combo.setAccessibleName("Statement file type")
        self.file_type_combo.setAccessibleDescription("Choose whether the selected file is a PDF or Excel statement.")
        self.file_type_combo.setToolTip("Choose whether the selected file is a PDF or Excel statement.")
        self.file_type_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.file_type_combo.currentTextChanged.connect(self._on_file_type_changed)
        file_type_layout.addWidget(self.file_type_combo)
        file_type_layout.addStretch()

        self._column_mapping = None
        self.map_columns_btn = Theme.btn("Map Columns", "secondary", height=32, min_width=120)
        self.map_columns_btn.clicked.connect(self._open_column_mapping_dialog)
        self.map_columns_btn.setVisible(self.file_type_combo.currentText() == "Excel")
        self.map_columns_btn.setAccessibleName("Map Excel columns")
        self.map_columns_btn.setAccessibleDescription("Open the column mapping dialog for Excel imports.")
        self.map_columns_btn.setToolTip("Open the column mapping dialog for Excel imports.")
        self.map_columns_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        file_type_layout.addWidget(self.map_columns_btn)

        form.addRow(self._form_label("Format"), file_type_layout)

        form_layout.addLayout(form)

        # File selection section (with drag-and-drop)
        form_layout.addWidget(QLabel(""))  # Spacer
        file_section = QVBoxLayout()
        file_section.setSpacing(10)

        # Drag-and-drop target
        self._drag_drop_target = self._create_drag_drop_target()
        file_section.addWidget(self._drag_drop_target)

        # Browse button row
        button_row = QHBoxLayout()
        button_row.addStretch()
        btn_browse = Theme.btn("Or Browse…", "secondary", height=36, min_width=130)
        btn_browse.clicked.connect(self._browse_file)
        btn_browse.setAccessibleName("Browse statement file")
        btn_browse.setAccessibleDescription("Open a file picker to select a bank statement file.")
        btn_browse.setToolTip("Open a file picker to select a bank statement file.")
        btn_browse.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(btn_browse, "browse")
        self.btn_browse = btn_browse
        button_row.addWidget(btn_browse)
        file_section.addLayout(button_row)

        form_layout.addLayout(file_section)
        form_layout.addStretch()

        layout.addWidget(form_card)

        # Load persons
        for p in get_all_persons():
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])

        return container

    def _build_preview_screen(self) -> QWidget:
        """Screen 2: Preview table + Import with editable table"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Header card
        self._preview_header_card = header_card = self._create_card()
        hc_layout = QVBoxLayout(header_card)
        hc_layout.setSpacing(10)
        
        title_row = QHBoxLayout()
        preview_title_widget = self._card_title_row("chart_overview", "Transaction Preview")
        title_row.addWidget(preview_title_widget)
        title_row.addStretch()
        
        self.preview_summary_label = QLabel("Total: 0 | New: 0 | Duplicates: 0 | Selected: 0")
        self.preview_summary_label.setStyleSheet(
            Theme.badge_style(Theme.INFO_LIGHT, Theme.INFO_DARK, radius=8, padding="6px 12px", size=11, weight=600)
        )
        title_row.addWidget(self.preview_summary_label)
        hc_layout.addLayout(title_row)
        
        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)
        
        btn_select_all = Theme.btn("Select All New", "success", height=34, min_width=130)
        btn_select_all.clicked.connect(lambda: self._set_preview_selection(True))
        btn_select_all.setAccessibleName("Select all new transactions")
        btn_select_all.setAccessibleDescription("Select all non-duplicate transactions for import.")
        btn_select_all.setToolTip("Select all non-duplicate transactions for import.")
        btn_select_all.setShortcut("Alt+S")
        btn_select_all.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(btn_select_all, "select_all")
        actions.addWidget(btn_select_all)
        
        btn_clear = Theme.btn("Clear Selection", "secondary", height=34, min_width=130)
        btn_clear.clicked.connect(lambda: self._set_preview_selection(False))
        btn_clear.setAccessibleName("Clear transaction selection")
        btn_clear.setAccessibleDescription("Clear all selected transactions in the preview.")
        btn_clear.setToolTip("Clear all selected transactions in the preview.")
        btn_clear.setShortcut("Alt+C")
        btn_clear.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(btn_clear, "clear_sel")
        actions.addWidget(btn_clear)
        
        actions.addStretch()
        
        self.copy_debug_btn = Theme.btn("Copy Debug", "secondary", height=34, min_width=120)
        self.copy_debug_btn.clicked.connect(self._copy_debug_report)
        self.copy_debug_btn.setAccessibleName("Copy debug report")
        self.copy_debug_btn.setAccessibleDescription("Copy the parser debug report to the clipboard.")
        self.copy_debug_btn.setToolTip("Copy the parser debug report to the clipboard.")
        self.copy_debug_btn.setShortcut("Alt+D")
        self.copy_debug_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(self.copy_debug_btn, "copy")
        actions.addWidget(self.copy_debug_btn)
        
        self.export_debug_btn = Theme.btn("Export Debug", "secondary", height=34, min_width=130)
        self.export_debug_btn.clicked.connect(self._export_debug_report)
        self.export_debug_btn.setAccessibleName("Export debug report")
        self.export_debug_btn.setAccessibleDescription("Save the parser debug report to a file.")
        self.export_debug_btn.setToolTip("Save the parser debug report to a file.")
        self.export_debug_btn.setShortcut("Alt+E")
        self.export_debug_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(self.export_debug_btn, "export")
        actions.addWidget(self.export_debug_btn)

        self.bulk_edit_btn = Theme.btn("Bulk Edit", "secondary", height=34, min_width=120)
        self.bulk_edit_btn.clicked.connect(self._bulk_edit_selected_rows)
        self.bulk_edit_btn.setAccessibleName("Bulk edit selected transactions")
        self.bulk_edit_btn.setAccessibleDescription("Edit shared fields for the selected transactions.")
        self.bulk_edit_btn.setToolTip("Edit shared fields for the selected transactions.")
        self.bulk_edit_btn.setShortcut("Alt+B")
        self.bulk_edit_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(self.bulk_edit_btn, "bulk_edit")
        actions.addWidget(self.bulk_edit_btn)

        self.shift_dates_btn = Theme.btn("Shift Dates", "secondary", height=34, min_width=120)
        self.shift_dates_btn.clicked.connect(self._shift_selected_dates)
        self.shift_dates_btn.setAccessibleName("Shift selected transaction dates")
        self.shift_dates_btn.setAccessibleDescription("Move the dates of selected transactions by a number of days.")
        self.shift_dates_btn.setToolTip("Move the dates of selected transactions by a number of days.")
        self.shift_dates_btn.setShortcut("Alt+H")
        self.shift_dates_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(self.shift_dates_btn, "shift_dates")
        actions.addWidget(self.shift_dates_btn)

        self.split_row_btn = Theme.btn("Split Row", "secondary", height=34, min_width=110)
        self.split_row_btn.clicked.connect(self._split_selected_row)
        self.split_row_btn.setAccessibleName("Split selected transaction")
        self.split_row_btn.setAccessibleDescription("Split one transaction into two rows.")
        self.split_row_btn.setToolTip("Split one transaction into two rows.")
        self.split_row_btn.setShortcut("Alt+P")
        self.split_row_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(self.split_row_btn, "split")
        actions.addWidget(self.split_row_btn)

        self.merge_rows_btn = Theme.btn("Merge Rows", "secondary", height=34, min_width=120)
        self.merge_rows_btn.clicked.connect(self._merge_selected_rows)
        self.merge_rows_btn.setAccessibleName("Merge selected transactions")
        self.merge_rows_btn.setAccessibleDescription("Combine two or more selected transactions into one row.")
        self.merge_rows_btn.setToolTip("Combine two or more selected transactions into one row.")
        self.merge_rows_btn.setShortcut("Alt+G")
        self.merge_rows_btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        set_btn_icon(self.merge_rows_btn, "merge")
        actions.addWidget(self.merge_rows_btn)
        
        hc_layout.addLayout(actions)
        layout.addWidget(header_card)

        # Editable table with double-click to edit
        self.preview_table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.preview_table = self.preview_table_widget.table
        self.preview_table.setHeaders([
            "Date", "Type", "Mode", "Category", "Amount", "Balance", "Description", "Status"
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview_table.setAccessibleName("Transaction preview table")
        self.preview_table.setAccessibleDescription("Editable preview of parsed transactions. Use the checkbox column to select rows for import.")
        self.preview_table.setToolTip("Editable preview of parsed transactions. Use the checkbox column to select rows for import.")
        self.preview_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.preview_table.doubleClicked.connect(self._on_preview_row_double_click)
        self.preview_table.itemChanged.connect(self._on_preview_item_changed)
        
        for i, w in enumerate([40, 95, 100, 110, 120, 110, 280, 95]):
            self.preview_table.setColumnWidth(i, w)
        
        layout.addWidget(self.preview_table_widget, stretch=3)

        # Debug panel (collapsible with toggle)
        self._debug_card = debug_card = self._create_card()
        debug_layout = QVBoxLayout(debug_card)
        debug_layout.setSpacing(10)
        
        debug_header = QHBoxLayout()
        debug_title_widget = self._card_title_row("search", "Import Debug Panel")
        debug_header.addWidget(debug_title_widget)
        debug_header.addStretch()
        
        self.debug_toggle_btn = Theme.btn("▼ Show", "secondary", height=28, min_width=80)
        self.debug_toggle_btn.clicked.connect(self._toggle_debug_panel)
        debug_header.addWidget(self.debug_toggle_btn)
        debug_layout.addLayout(debug_header)
        
        self.debug_output = QPlainTextEdit()
        self.debug_output.setObjectName("importDebugOutput")
        self.debug_output.setReadOnly(True)
        self.debug_output.setMinimumHeight(140)
        self.debug_output.setMaximumHeight(200)
        self.debug_output.setVisible(False)  # Hidden by default
        self.debug_output.setAccessibleName("Import debug output")
        self.debug_output.setAccessibleDescription("Shows parser attempts, validation issues, and duplicate information.")
        self.debug_output.setToolTip("Shows parser attempts, validation issues, and duplicate information.")
        debug_layout.addWidget(self.debug_output)
        layout.addWidget(debug_card, stretch=0)
        
        return container

    def _build_stepper(self) -> QWidget:
        """Two-step progress indicator: numbered dots joined by a line,
        replacing the old plain '1 of 2' text badge."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._step_dots = []
        self._step_line = None
        for i, step_label in enumerate(["Select", "Preview"], start=1):
            dot = QLabel(str(i))
            dot.setFixedSize(26, 26)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            row.addWidget(dot)
            self._step_dots.append(dot)

            txt = QLabel(step_label)
            txt.setProperty("textrole", "muted-sm")
            row.addWidget(txt)

            if i == 1:
                line = QFrame()
                line.setFixedSize(24, 2)
                row.addWidget(line)
                self._step_line = line

        self._set_step(1)
        return container

    def _set_step(self, step: int):
        """Update the stepper's visual state (1 or 2)."""
        self.screen_indicator_step = step
        for i, dot in enumerate(self._step_dots, start=1):
            active = i <= step
            bg = Theme.PRIMARY if active else Theme.SURFACE_ALT
            fg = "#FFFFFF" if active else Theme.TEXT_MUTED
            dot.setStyleSheet(f"background-color: {bg}; color: {fg}; border-radius: 13px;")
        if self._step_line is not None:
            self._step_line.setStyleSheet(
                f"background-color: {Theme.PRIMARY if step >= 2 else Theme.BORDER};"
            )

    def _create_card(self) -> QFrame:
        """Create a modern card container"""
        card = QFrame()
        card.setObjectName("ImportCard")
        card.setStyleSheet(
            Theme.card_style(
                bg=Theme.SURFACE,
                border_color=Theme.BORDER,
                radius=14,
                padding=20,
                selector="QFrame#ImportCard",
            )
        )
        card.setGraphicsEffect(Theme.shadow_card())
        return card

    def _card_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl.setProperty("textrole", "emphasis-md")
        return lbl

    def _card_title_row(self, icon_name: str, text: str) -> QWidget:
        """Card title with a registry icon instead of a plain emoji."""
        row_widget = QWidget()
        row_widget.setObjectName("transparentBg")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        icon_lbl = icon_label(icon_name, size=18, color=Theme.PRIMARY)
        row.addWidget(icon_lbl)
        row.addWidget(self._card_title(text))
        row.addStretch()
        # Icon colour is baked in at construction; keep a handle so
        # refresh_theme() can re-tint it after a live theme switch.
        if not hasattr(self, "_title_icons"):
            self._title_icons = []
        self._title_icons.append((icon_lbl, icon_name))
        return row_widget

    def _card_subtitle(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("textrole", "muted-md")
        return lbl

    def _form_label(self, text: str) -> QLabel:
        lbl = QLabel(f"{text}:")
        lbl.setProperty("textrole", "section-label")
        return lbl

    def _create_drag_drop_target(self) -> QFrame:
        """Create a drag-and-drop target frame for file selection"""
        target = QFrame()
        target.setObjectName("DragDropTarget")
        target.setCursor(Qt.CursorShape.PointingHandCursor)
        target.setMinimumHeight(100)
        target.setAccessibleName("Drag and drop target")
        target.setAccessibleDescription("Drag a statement file here, or use the Browse button below.")
        target.setToolTip("Drag a statement file here, or click 'Or Browse…' to select one")

        layout = QVBoxLayout(target)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = icon_label("upload", size=32, color=Theme.PRIMARY)
        layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        text_lbl = QLabel("Drag statement file here")
        text_lbl.setProperty("textrole", "emphasis-md")
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_lbl)

        sub_lbl = QLabel("PDF or Excel format")
        sub_lbl.setProperty("textrole", "muted-md")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_lbl)

        # Store refs for theme refresh
        self._drag_drop_icon = icon_lbl
        self._drag_drop_text = text_lbl

        return target

    def _on_person_changed(self):
        """Load accounts when person changes"""
        self.selected_person_id = self.person_combo.currentData()
        if self.selected_person_id:
            self.account_combo.setEnabled(True)
            self.account_combo.clear()
            accounts = get_accounts_for_person(self.selected_person_id)
            for acc in accounts:
                self.account_combo.addItem(
                    f"{acc.get('bank_display_name', acc['bank_name'])} — {acc['account_type']} ({acc.get('account_number_masked','') or ''})",
                    userData=acc["account_id"]
                )
        else:
            self.account_combo.setEnabled(False)
            self.account_combo.clear()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Bank Statement", "",
            "All Files (*.pdf *.xls *.xlsx);;PDF (*.pdf);;Excel (*.xls *.xlsx)")
        if path:
            self._set_selected_file(path)

    def _handle_file_drop(self, path: str):
        """Handle a file dropped onto the selection screen"""
        self._set_selected_file(path)

    def _set_selected_file(self, path: str):
        """Set the selected file and update UI"""
        if not path:
            return
        self.selected_file = path
        filename = path.split("/")[-1] or path.split("\\")[-1]
        # Update drag-drop target to show selected file
        if hasattr(self, "_drag_drop_target"):
            layout = self._drag_drop_target.layout()
            # Clear layout and rebuild with file info
            while layout.count():
                layout.takeAt(0).widget().deleteLater()
            icon = icon_label("check_circle", size=32, color=Theme.SUCCESS)
            layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
            text = QLabel(f"✓ {filename}")
            text.setProperty("textrole", "emphasis-md")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(text)
            sub = QLabel("Ready to parse")
            sub.setProperty("textrole", "muted-md")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(sub)
        # Reset mapping when file changes
        self._column_mapping = None
        show_success(f"File selected: {filename}")

    def _go_next(self):
        """Handle next button - validate and parse"""
        if self.stack.currentIndex() == 0:
            # Validate selection screen
            if not self.selected_person_id:
                show_warning("Please select a person.")
                return
            
            self.selected_account_id = self.account_combo.currentData()
            if not self.selected_account_id:
                show_warning("Please select an account.")
                return
            
            if not self.selected_file:
                show_warning("Please select a statement file.")
                return
            
            # Parse statement (will be implemented in next chunk)
            self._parse_statement()
        else:
            # Import transactions (will be implemented in next chunk)
            self._import_transactions()

    def _go_back(self):
        """Go back to selection screen"""
        if self.stack.currentIndex() == 1:
            self.stack.setCurrentIndex(0)
            self._set_step(1)
            self.btn_back.setEnabled(False)
            self.btn_next.setText("Parse Statement →")
            self.person_combo.setFocus()

    def _parse_statement(self):
        """Parse statement and show preview — running parser in background thread."""
        self.file_type = self.file_type_combo.currentText()
        acc = get_account(self.selected_account_id)
        self.bank_name = acc["bank_name"] if acc else "Unknown"

        self._parse_password = None
        self._parse_save_password = False

        # Check if encrypted
        if self._is_statement_file_encrypted(self.selected_file, self.file_type):
            saved_password = self._get_saved_statement_password()
            password, save_password = self._prompt_statement_password(saved_password)
            if not password:
                return
            self._parse_password = password
            self._parse_save_password = save_password

        # Disable controls and start parse in background thread
        self.btn_next.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.file_type_combo.setEnabled(False)

        self._start_statement_parse_worker()

    def _start_statement_parse_worker(self):
        """Start the statement parser in a background thread."""
        def on_parse_done(result):
            txns, debug_info = result
            self.import_debug_info = debug_info or {}

            # Save password if requested
            if self._parse_save_password and self._parse_password:
                set_statement_password(self.selected_account_id, self._parse_password, session.aes_key)

            # Process parsed transactions on the GUI thread
            self._process_parsed_statement(txns)

        def on_parse_error(exc):
            self._handle_parse_error(exc)

        def on_parse_progress(msg):
            self._update_loader(msg)

        # Create worker and run in Loader.run()
        worker = _StatementParseWorker(
            self.selected_file,
            self.file_type,
            self.bank_name,
            self._parse_password,
            self._column_mapping
        )
        worker.progress.connect(on_parse_progress)

        Loader.run(
            self,
            fn=worker.run,
            message="Processing Statement",
            subtitle="Reading and extracting transactions...",
            on_done=on_parse_done,
            on_error=on_parse_error
        )

    def _handle_parse_error(self, exc):
        """Handle errors from statement parsing."""
        self.btn_next.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.file_type_combo.setEnabled(True)

        if isinstance(exc, StatementPasswordRequiredError):
            saved_password = self._get_saved_statement_password()
            password, save_password = self._prompt_statement_password(saved_password)
            if not password:
                return
            self._parse_password = password
            self._parse_save_password = save_password
            self._start_statement_parse_worker()
        elif isinstance(exc, StatementPasswordInvalidError):
            show_warning("The password did not unlock the file. Please try again.")
            password, save_password = self._prompt_statement_password(self._parse_password or None)
            if not password:
                return
            self._parse_password = password
            self._parse_save_password = save_password
            self._start_statement_parse_worker()
        elif isinstance(exc, StatementPasswordError):
            QMessageBox.critical(self, "Password Error", str(exc))
        else:
            QMessageBox.critical(self, "Parse Error", str(exc))

    def _process_parsed_statement(self, txns):
        """Process parsed transactions on the GUI thread (after worker returns)."""
        self.btn_next.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.file_type_combo.setEnabled(True)

        try:
            # Extract metadata (lightweight operation, can stay on UI thread)
            try:
                self.statement_text = extract_statement_text(self.selected_file, self.file_type, password=self._parse_password)
                metadata = extract_account_metadata(self.statement_text)

                if any(metadata.values()):
                    acc = get_account(self.selected_account_id)
                    dialog = AccountMetadataDialog(
                        self,
                        account_id=self.selected_account_id,
                        account_name=(acc or {}).get('bank_name', 'Account'),
                        metadata=metadata,
                    )
                    dialog.exec()
            except Exception as e:
                print(f"Metadata extraction failed: {e}")

            # If no transactions extracted and it's Excel, suggest mapping columns and retry
            if not txns and self.file_type and self.file_type.lower().startswith("excel"):
                if not self._column_mapping:
                    try:
                        from engines.statement_parser import LocalAIStatementParser
                        ai = LocalAIStatementParser()
                        suggestion = ai.suggest_excel_mapping(self.selected_file, password=self._parse_password)
                    except Exception:
                        suggestion = {}

                    mapping_dialog = ColumnMappingDialog(self, self.selected_file, account_id=self.selected_account_id, initial_mapping=suggestion)
                    mapping_dialog.setWindowTitle("Map Columns — Excel Import")
                    if mapping_dialog.exec() == QDialog.DialogCode.Accepted:
                        self._column_mapping = mapping_dialog.get_mapping()
                        # Retry parsing with new mapping
                        self._start_statement_parse_worker()
                        return

            # Validate transactions (lightweight, can stay on UI thread)
            if not txns:
                self.parsed_transactions = []
                self.preview_transactions = []
                self.preview_duplicate_flags = []
                self.validation_errors = []
                self.duplicate_count = 0
                self._populate_preview_table()
                self._switch_to_preview()
                show_warning("Could not extract transactions. Check debug panel for details.")
                return

            valid, errors = validate_transactions(txns)
            self.validation_errors = errors
            if errors:
                show_warning(f"{len(errors)} rows were skipped. Check debug panel for details.")

            # Calculate confidence score and check for low confidence
            self.parse_confidence = confidence(valid)
            self.failing_rows_balance = balance_walk(valid)
            balance_pass_rate = 1.0 - (len(self.failing_rows_balance) / len(valid)) if valid else 0.0

            # Block import if confidence is too low (< 0.9 / 90%)
            if self.parse_confidence < 0.9 and valid:
                fail_count = sum(1 for txn in valid if any(f["index"] == valid.index(txn) for f in self.failing_rows_balance))
                reason = f"Balance validation failed for {len(self.failing_rows_balance)} row(s) (confidence: {self.parse_confidence:.0%})"
                show_warning(f"Import blocked: {reason}\n\nPlease review the statement and try again.")
                # Still show preview but prevent import
                self.preview_transactions = valid
                self.preview_duplicate_flags = [False] * len(valid)
                self.parsed_transactions = valid
                self.duplicate_count = 0
                self._populate_preview_table()
                self._switch_to_preview()
                return

            # Check duplicates (lightweight DB queries, stay on UI thread)
            self.preview_transactions = valid
            self.preview_duplicate_flags = [
                check_duplicate(
                    self.selected_account_id,
                    row["transaction_date"],
                    row["amount"],
                    row["description"],
                    row.get("transaction_type"),
                    row.get("reference_no"),
                    row.get("balance_after"),
                )
                for row in valid
            ]
            unique = [row for row, is_dup in zip(valid, self.preview_duplicate_flags) if not is_dup]
            dups = sum(1 for is_dup in self.preview_duplicate_flags if is_dup)
            self.duplicate_count = dups

            if dups > 0:
                if dups == len(valid) and valid:
                    show_info("All extracted rows already exist. Preview shows parsed rows, but duplicates are disabled for import.")
                else:
                    show_info(f"{dups} duplicate(s) will be skipped.")

            self.parsed_transactions = unique
            self._populate_preview_table()
            self._show_confidence_summary(len(valid), balance_pass_rate)
            self._switch_to_preview()

        except Exception as e:
            QMessageBox.critical(self, "Parse Error", str(e))

    def _switch_to_preview(self):
        """Switch to preview screen"""
        self.stack.setCurrentIndex(1)
        self._set_step(2)
        self.btn_back.setEnabled(True)
        self.btn_next.setText("Import Selected →")
        set_btn_icon(self.btn_next, "check")
        self.preview_table.setFocus()

    def _import_transactions(self):
        """Import selected transactions using background worker thread."""
        if not self.preview_transactions:
            show_warning("No transactions available. Please go back and choose another file.")
            return

        checked_rows = self.preview_table.getCheckedRows()
        if not checked_rows:
            show_warning("Please select at least one transaction to import.")
            return

        # Disable controls during import
        self.btn_next.setEnabled(False)
        self.btn_back.setEnabled(False)

        def on_import_done(result):
            """Callback on GUI thread after worker finishes database operations."""
            try:
                inserted_ids = result["inserted_ids"]
                imported = result["imported"]
                fds_created = result["fds_created"]
                batch_rows = result["batch_rows"]

                self._update_loader("Calculating savings interest...")

                # Recalculate savings interest for affected FYs and update running balances
                # This MUST run on the GUI thread as per task requirements
                account = get_account(self.selected_account_id)
                if account:
                    interest_rate = float(account.get("interest_rate") or 0)
                    opening_balance = float(account.get("opening_balance") or 0)

                    # Determine which FYs were affected by the import
                    for txn in batch_rows:
                        txn_date = datetime.fromisoformat(txn["transaction_date"]).date()
                        # Determine FY of transaction
                        if txn_date.month >= 4:
                            fy = f"{txn_date.year}-{str(txn_date.year + 1)[2:]}"
                        else:
                            fy = f"{txn_date.year - 1}-{str(txn_date.year)[2:]}"

                        try:
                            allocate_savings_interest_to_fy(
                                self.selected_account_id, fy, interest_rate, opening_balance
                            )
                        except Exception:
                            # Log but don't fail the import
                            pass

                # Recalculate running balances after import (ensures current_balance matches last transaction)
                # This MUST run on the GUI thread as per task requirements
                self._update_loader("Updating account balance...")
                try:
                    recalculate_account_balance(self.selected_account_id)
                except Exception:
                    # Log but don't fail the import
                    pass

                self.fds_created_last_import = fds_created

                # Show success message
                msg = f"Successfully imported {imported} transactions!"
                if fds_created > 0:
                    msg += f"\n\nAuto-created {fds_created} FD record(s)."

                if self._loader:
                    self._loader.hide()

                show_success(msg)

                if self.parent_window:
                    self.parent_window.refresh_overview()
                self.refresh()

            except Exception as e:
                if self._loader:
                    self._loader.hide()
                QMessageBox.critical(self, "Post-Import Error", str(e))
            finally:
                self.btn_next.setEnabled(True)
                self.btn_back.setEnabled(True)

        def on_import_error(exc):
            """Callback on GUI thread if worker fails."""
            if self._loader:
                self._loader.hide()
            self.btn_next.setEnabled(True)
            self.btn_back.setEnabled(True)
            QMessageBox.critical(self, "Import Failed", str(exc))

        def on_import_progress(msg):
            """Update progress message from worker."""
            self._update_loader(msg)

        # Create worker
        worker = _TransactionImportWorker(
            self.selected_account_id,
            self.selected_person_id,
            self.preview_transactions,
            self.preview_duplicate_flags,
            self.bank_name,
            self.selected_file,
            self.file_type,
            checked_rows
        )
        worker.progress.connect(on_import_progress)

        # Start import in background thread using Loader.run()
        Loader.run(
            self,
            fn=worker.run,
            message="Importing Transactions",
            subtitle="Saving transactions and creating FD entries...",
            on_done=on_import_done,
            on_error=on_import_error
        )

    def refresh(self):
        """Reset to initial state"""
        self.selected_person_id = session.selected_person_id
        self.selected_account_id = None
        self.selected_file = None
        self.file_type = None
        self.parsed_transactions = []
        self.preview_transactions = []
        self.preview_duplicate_flags = []
        self.bank_name = ""
        self.import_debug_info = {}
        self.validation_errors = []
        self.duplicate_count = 0
        self.fds_created_last_import = 0
        self.parse_confidence = 0.0
        self.failing_rows_balance = []

        # Reset UI
        self.stack.setCurrentIndex(0)
        self._set_step(1)
        self.btn_back.setEnabled(False)
        self.btn_next.setText("Parse Statement →")

        # Reset drag-drop target
        if hasattr(self, "_drag_drop_target"):
            layout = self._drag_drop_target.layout()
            while layout.count():
                layout.takeAt(0).widget().deleteLater()
            icon = icon_label("upload", size=32, color=Theme.PRIMARY)
            layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._drag_drop_icon = icon
            text = QLabel("Drag statement file here")
            text.setProperty("textrole", "emphasis-md")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(text)
            sub = QLabel("PDF or Excel format")
            sub.setProperty("textrole", "muted-md")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(sub)

        # Reload person combo
        self.person_combo.clear()
        for p in get_all_persons():
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])

        if self.selected_person_id:
            for i in range(self.person_combo.count()):
                if self.person_combo.itemData(i) == self.selected_person_id:
                    self.person_combo.setCurrentIndex(i)
                    break

    # Helper methods — use the shared branded Loader overlay (same widget
    # Settings uses for backup/restore) instead of a bespoke QProgressDialog,
    # so the import wizard's progress feedback looks consistent with the
    # rest of the app rather than a plain native-looking dialog.
    def _show_loader(self, title: str, message: str):
        if self._loader is None:
            self._loader = Loader(self, title, subtitle=message)
        else:
            self._loader.set_message(title)
            self._loader.set_subtitle(message)
        self.btn_next.setEnabled(False)
        self.btn_back.setEnabled(False)
        self._loader.show()
        QApplication.processEvents()

    def _update_loader(self, message: str):
        if self._loader is not None:
            self._loader.set_subtitle(message)
            QApplication.processEvents()

    def _hide_loader(self):
        if self._loader is not None:
            self._loader.hide()
        self.btn_next.setEnabled(True)
        self.btn_back.setEnabled(self.stack.currentIndex() == 1)

    def _show_confidence_summary(self, rows_parsed: int, balance_pass_rate: float):
        """Show confidence summary as a toast notification"""
        fail_count = len(self.failing_rows_balance)
        summary = f"Parsed {rows_parsed} rows | Balance validation: {balance_pass_rate:.0%} | Rows needing review: {fail_count}"
        show_info(summary)

    def _populate_preview_table(self):
        """Populate preview table with transactions"""
        self.preview_table.setRowCount(len(self.preview_transactions))
        self.preview_table.blockSignals(True)
        
        for idx, txn in enumerate(self.preview_transactions):
            # Checkbox
            cb = QCheckBox()
            is_duplicate = self.preview_duplicate_flags[idx] if idx < len(self.preview_duplicate_flags) else False
            cb.setChecked(not is_duplicate)
            cb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            cb.setAccessibleName(f"Select transaction row {idx + 1}")
            cb.setAccessibleDescription(
                f"Toggle whether transaction row {idx + 1} is included in the import."
            )
            cb_widget = QWidget()
            cb_widget.setAccessibleName(f"Selection control for row {idx + 1}")
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.preview_table.setCellWidget(idx, 0, cb_widget)
            
            # Data columns
            date_item = QTableWidgetItem(format_display_date(txn.get("transaction_date")))
            type_item = QTableWidgetItem(display_transaction_type(txn["transaction_type"]))
            mode_item = QTableWidgetItem(txn.get("mode", "") or "")
            cat_item = QTableWidgetItem(txn.get("category","") or "")
            amt_item = QTableWidgetItem(f"₹ {txn['amount']:,.2f}")
            bal_val = txn.get("balance_after")
            bal_item = QTableWidgetItem("—" if bal_val is None else f"₹ {bal_val:,.2f}")
            desc_item = QTableWidgetItem(txn.get("description","") or "")
            status_item = QTableWidgetItem("Duplicate" if is_duplicate else "New")

            # Apply colors
            for col, item in enumerate([date_item, type_item, mode_item, cat_item, amt_item, bal_item, desc_item, status_item]):
                if col != 7 and not is_duplicate:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if is_duplicate:
                    item.setForeground(QColor(120, 130, 145))
                elif col == 1:  # Type column
                    if txn["transaction_type"] == "Income":
                        item.setForeground(QColor(56, 161, 105))
                    elif txn["transaction_type"] == "Expense":
                        item.setForeground(QColor(220, 38, 38))
                self.preview_table.setItem(idx, col+1, item)

            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.preview_table.setRowHeight(idx, 32)
            
        self.preview_table.blockSignals(False)
        self._update_preview_summary()
        
        # Update debug output
        self.debug_output.setPlainText(self._build_debug_text())

    def _update_preview_row(self, row: int):
        """Update a single row in preview table after edit"""
        if row < 0 or row >= len(self.preview_transactions):
            return
        
        txn = self.preview_transactions[row]
        is_duplicate = self.preview_duplicate_flags[row] if row < len(self.preview_duplicate_flags) else False
        
        # Update data columns (skip checkbox at column 0)
        date_item = QTableWidgetItem(format_display_date(txn.get("transaction_date")))
        type_item = QTableWidgetItem(display_transaction_type(txn["transaction_type"]))
        mode_item = QTableWidgetItem(txn.get("mode", "") or "")
        cat_item = QTableWidgetItem(txn.get("category","") or "")
        amt_item = QTableWidgetItem(f"₹ {txn['amount']:,.2f}")
        bal_val = txn.get("balance_after")
        bal_item = QTableWidgetItem("—" if bal_val is None else f"₹ {bal_val:,.2f}")
        desc_item = QTableWidgetItem(txn.get("description","") or "")
        status_item = QTableWidgetItem("Duplicate" if is_duplicate else "New")

        self.preview_table.blockSignals(True)
        for col, item in enumerate([date_item, type_item, mode_item, cat_item, amt_item, bal_item, desc_item, status_item]):
            if col != 7 and not is_duplicate:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(item.text())
            item.setToolTip(item.text())
            if is_duplicate:
                item.setForeground(QColor(120, 130, 145))
            elif col == 1:
                if txn["transaction_type"] == "Income":
                    item.setForeground(QColor(56, 161, 105))
                elif txn["transaction_type"] == "Expense":
                    item.setForeground(QColor(220, 38, 38))
            self.preview_table.setItem(row, col+1, item)

        amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.preview_table.blockSignals(False)
        # Update debug output
        self.debug_output.setPlainText(self._build_debug_text())

    

    def _on_file_type_changed(self, text: str):
        self.map_columns_btn.setVisible(text == "Excel")

    def _open_column_mapping_dialog(self):
        if not self.selected_file:
            show_warning("Please choose a file first.")
            return
        dlg = ColumnMappingDialog(self, self.selected_file, account_id=self.selected_account_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._column_mapping = dlg.get_mapping()
            show_success("Column mapping saved for this import.")

    def _set_preview_selection(self, selected: bool):
        for idx in range(len(self.preview_transactions)):
            is_duplicate = self.preview_duplicate_flags[idx] if idx < len(self.preview_duplicate_flags) else False
            if not is_duplicate:
                self.preview_table.setRowChecked(idx, selected)
        self._update_preview_summary()

    def _update_preview_summary(self):
        if not hasattr(self, "preview_summary_label"):
            return
        total = len(self.preview_transactions)
        new_count = sum(1 for flag in self.preview_duplicate_flags if not flag)
        selected = len(self.preview_table.getCheckedRows())
        self.preview_summary_label.setText(
            f"Total: {total}  |  New: {new_count}  |  Duplicates: {self.duplicate_count}  |  Selected: {selected}"
        )

    def _build_debug_text(self) -> str:
        lines = []
        mode_requested = self.import_debug_info.get("mode_requested", "unknown")
        mode_used = self.import_debug_info.get("mode_used", "unknown")
        lines.append(f"Requested mode: {mode_requested}")
        lines.append(f"Parser used: {mode_used}")

        attempts = self.import_debug_info.get("attempts", [])
        if attempts:
            lines.append("")
            lines.append("Attempts:")
            for idx, attempt in enumerate(attempts, start=1):
                lines.append(
                    f"  {idx}. {attempt.get('mode', 'unknown')} | "
                    f"scanned={attempt.get('rows_scanned', 0)} "
                    f"extracted={attempt.get('rows_extracted', 0)} "
                    f"issues={len(attempt.get('issues', []))}"
                )

        if self.validation_errors:
            lines.append("")
            lines.append("Validation failures:")
            for err in self.validation_errors[:40]:
                lines.append(f"  - {err}")

        if self.duplicate_count > 0:
            lines.append("")
            lines.append(f"Duplicates filtered: {self.duplicate_count}")

        issues = self.import_debug_info.get("issues", [])
        if issues:
            lines.append("")
            lines.append("Extraction issues:")
            for issue in issues[:120]:
                lines.append(f"  - {issue}")

        if not issues and not self.validation_errors and self.duplicate_count == 0:
            lines.append("")
            lines.append("No extraction issues were reported.")

        return "\n".join(lines)

    def _copy_debug_report(self):
        report = self._build_debug_text()
        QApplication.clipboard().setText(report)
        show_success("Debug report copied to clipboard.")

    def _export_debug_report(self):
        default_name = "import_debug_report.json"
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Debug Report", default_name,
            "JSON Files (*.json);;Text Files (*.txt)"
        )
        if not path:
            return

        try:
            if path.lower().endswith(".txt"):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._build_debug_text())
            else:
                if not path.lower().endswith(".json"):
                    path = f"{path}.json"
                payload = {
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "file": self.selected_file,
                    "file_type": self.file_type,
                    "bank_name": self.bank_name,
                    "summary": {
                        "parsed_transactions": len(self.parsed_transactions),
                        "validation_errors": len(self.validation_errors),
                        "duplicates_filtered": self.duplicate_count,
                    },
                    "parser_debug": self.import_debug_info,
                    "validation_errors": self.validation_errors,
                    "debug_text": self._build_debug_text(),
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

            show_success(f"Debug report saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _get_saved_statement_password(self) -> str | None:
        if not self.selected_account_id:
            return None
        return get_statement_password(self.selected_account_id, session.aes_key)

    def _is_statement_file_encrypted(self, file_path: str, file_type: str) -> bool:
        if file_type.upper() == "PDF":
            return is_pdf_encrypted(file_path)
        if file_type.upper() in ["EXCEL", "XLS", "XLSX"]:
            return is_excel_encrypted(file_path)
        return False

    def _prompt_statement_password(self, saved_password: str | None) -> tuple[str | None, bool]:
        info_text = "This statement file is password-protected. Enter the password to continue."
        hint_text = "Common formats depend on your bank and may include account number, DOB, or a custom bank-provided format."
        dlg = PasswordDialog(
            self, title="Enter Statement Password",
            info_text=info_text, hint_text=hint_text,
            placeholder_text="Statement password",
            prefill_password=saved_password,
            save_label="Save or update password for this account",
            save_checked=True, accept_label="Continue",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None, False
        password = dlg.get_password()
        if not password:
            show_warning("Password is required to open the file.")
            return None, False
        return password, dlg.should_save()

    def _is_fd_opening_transaction(self, txn: dict) -> bool:
        if txn.get("transaction_type") != "Expense":
            return False
        if (txn.get("category") or "").strip().upper() == "FD PRINCIPAL":
            return True
        desc = (txn.get("description") or "").upper()
        patterns = [
            r"\bINITIAL\s+PAYIN\s+FD\b", r"\bFD\d{6,}\b", r"\bTD/\d+\b",
            r"\bTD\.?\s+GENERIC\s+PAYIN\b", r"\bPAYIN\s+DEBIT\b",
            r"\bTERM\s+DEPOSIT\b", r"\bFIXED\s+DEPOSIT\b", r"\b\d+\s*FD\b",
        ]
        return any(re.search(p, desc) for p in patterns)

    def _extract_fd_reference(self, description: str) -> str | None:
        text = (description or "").upper()
        patterns = [
            r"\bFD\s*(?:NO|NUMBER|A/C|ACCOUNT)?\s*[:\-]?\s*([A-Z0-9\-/]{5,})\b",
            r"\bTD\s*(?:NO|NUMBER|A/C|ACCOUNT)?\s*[:\-]?\s*([A-Z0-9\-/]{5,})\b",
            r"\bTERM\s*DEPOSIT\s*(?:NO|NUMBER|A/C|ACCOUNT)?\s*[:\-]?\s*([A-Z0-9\-/]{5,})\b",
            r"\bTD/([A-Z0-9\-/]{5,})\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip("-/ ")[:50]
        return None

    def _extract_maturity_amount(self, description: str) -> float | None:
        text = (description or "")
        patterns = [
            r"(?i)MATURITY\s*(?:AMT|AMOUNT|VALUE)?\s*[:\-]?\s*\₹?\s*([\d,]+(?:\.\d{1,2})?)",
            r"(?i)MAT\s*AMT\s*[:\-]?\s*\₹?\s*([\d,]+(?:\.\d{1,2})?)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    return None
        return None

    def _toggle_debug_panel(self):
        """Toggle debug panel visibility"""
        is_visible = self.debug_output.isVisible()
        self.debug_output.setVisible(not is_visible)
        self.debug_toggle_btn.setText("▲ Hide" if not is_visible else "▼ Show")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._selection_tab_order_ready:
            self._setup_selection_tab_order()
            self._selection_tab_order_ready = True
        if not self._preview_tab_order_ready:
            self._setup_preview_tab_order()
            self._preview_tab_order_ready = True

    def _setup_selection_tab_order(self):
        self.setTabOrder(self.person_combo, self.account_combo)
        self.setTabOrder(self.account_combo, self.file_type_combo)
        self.setTabOrder(self.file_type_combo, self.btn_browse)
        self.setTabOrder(self.btn_browse, self.btn_ai_check)
        self.setTabOrder(self.btn_ai_check, self.map_columns_btn)
        self.setTabOrder(self.map_columns_btn, self.btn_next)
        self.setTabOrder(self.btn_next, self.btn_back)

    def _setup_preview_tab_order(self):
        self.setTabOrder(self.preview_table, self.btn_back)
        self.setTabOrder(self.btn_back, self.btn_next)
        self.setTabOrder(self.btn_next, self.bulk_edit_btn)
        self.setTabOrder(self.bulk_edit_btn, self.shift_dates_btn)
        self.setTabOrder(self.shift_dates_btn, self.split_row_btn)
        self.setTabOrder(self.split_row_btn, self.merge_rows_btn)
        self.setTabOrder(self.merge_rows_btn, self.copy_debug_btn)
        self.setTabOrder(self.copy_debug_btn, self.export_debug_btn)
        self.setTabOrder(self.export_debug_btn, self.debug_toggle_btn)

    def _on_preview_row_double_click(self, index):
        """Open edit dialog for transaction on double-click"""
        row = index.row()
        if row < 0 or row >= len(self.preview_transactions):
            return
        
        txn = self.preview_transactions[row]
        is_duplicate = self.preview_duplicate_flags[row] if row < len(self.preview_duplicate_flags) else False
        
        # Import dialog here to avoid circular import
        from ui.dialogs.transaction_edit_dialog import TransactionEditDialog
        
        dialog = TransactionEditDialog(self, txn, is_preview=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_txn = dialog.get_data()
            # Update the transaction in preview list
            self.preview_transactions[row].update(updated_txn)
            # Refresh the table row
            self._update_preview_row(row)
            self._update_preview_summary()

    def _selected_preview_rows(self) -> list[int]:
        rows = sorted(set(self.preview_table.getCheckedRows()))
        if rows:
            return rows
        selected = sorted({item.row() for item in self.preview_table.selectedItems()})
        return selected

    def _on_preview_item_changed(self, item: QTableWidgetItem):
        if self._preview_cell_change_lock:
            return
        row = item.row()
        col = item.column()
        if row < 0 or row >= len(self.preview_transactions):
            return
        if col == 0 or col == 8:
            return

        txn = self.preview_transactions[row]
        text = (item.text() or "").strip()
        try:
            if col == 1:
                txn["transaction_type"] = "Income" if text.lower().startswith("credit") or text == "Income" else "Expense"
            elif col == 2:
                txn["mode"] = text or None
            elif col == 3:
                txn["category"] = text or None
            elif col == 4:
                txn["amount"] = float(text.replace("₹", "").replace(",", "").strip() or 0)
            elif col == 5:
                txn["balance_after"] = None if not text or text in ["—", "-"] else float(text.replace("₹", "").replace(",", "").strip())
            elif col == 6:
                txn["description"] = text or None
            elif col == 7:
                txn["reference_no"] = text or None
        except Exception:
            show_warning("Could not apply the edit. Reverting the row.")
        finally:
            self._update_preview_row(row)
            self._update_preview_summary()

    def _bulk_edit_selected_rows(self):
        rows = self._selected_preview_rows()
        if not rows:
            show_warning("Select one or more rows to bulk edit.")
            return
        base = dict(self.preview_transactions[rows[0]])
        from ui.dialogs.transaction_edit_dialog import TransactionEditDialog
        dialog = TransactionEditDialog(self, base, is_preview=True)
        dialog.setWindowTitle("Bulk Edit Selected Rows")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.get_data()
        for row in rows:
            if row >= len(self.preview_transactions):
                continue
            self.preview_transactions[row].update(updated)
            self._update_preview_row(row)
        self._update_preview_summary()

    def _shift_selected_dates(self):
        rows = self._selected_preview_rows()
        if not rows:
            show_warning("Select one or more rows to shift dates.")
            return
        days, ok = QInputDialog.getInt(self, "Shift Dates", "Shift selected dates by how many days?", value=1, min=-3650, max=3650)
        if not ok or days == 0:
            return
        from datetime import timedelta
        for row in rows:
            try:
                current = datetime.fromisoformat(self.preview_transactions[row]["transaction_date"]).date()
                self.preview_transactions[row]["transaction_date"] = (current + timedelta(days=days)).isoformat()
                self._update_preview_row(row)
            except Exception:
                continue
        self._update_preview_summary()

    def _split_selected_row(self):
        rows = self._selected_preview_rows()
        if len(rows) != 1:
            show_warning("Select exactly one row to split.")
            return
        row = rows[0]
        txn = self.preview_transactions[row]
        max_split = float(txn.get("amount") or 0)
        if max_split <= 0:
            show_warning("This row does not have a valid amount.")
            return
        split_amount, ok = QInputDialog.getDouble(self, "Split Row", "Amount to move into the new split row:", value=max_split / 2, min=0.01, max=max_split, decimals=2)
        if not ok or split_amount <= 0 or split_amount >= max_split:
            return
        new_row = dict(txn)
        new_row["amount"] = round(split_amount, 2)
        txn["amount"] = round(max_split - split_amount, 2)
        self.preview_transactions.insert(row + 1, new_row)
        is_dup = self.preview_duplicate_flags[row] if row < len(self.preview_duplicate_flags) else False
        self.preview_duplicate_flags.insert(row + 1, is_dup)
        self._populate_preview_table()

    def _merge_selected_rows(self):
        rows = self._selected_preview_rows()
        if len(rows) < 2:
            show_warning("Select at least two rows to merge.")
            return
        rows = sorted(rows)
        base = dict(self.preview_transactions[rows[0]])
        total_amount = 0.0
        descriptions = []
        for row in rows:
            txn = self.preview_transactions[row]
            total_amount += float(txn.get("amount") or 0)
            desc = (txn.get("description") or "").strip()
            if desc:
                descriptions.append(desc)
        base["amount"] = round(total_amount, 2)
        if descriptions:
            base["description"] = " / ".join(descriptions)[:200]
        base["transaction_date"] = self.preview_transactions[rows[0]].get("transaction_date")

        # Replace selected rows with a single merged row
        for row in reversed(rows):
            self.preview_transactions.pop(row)
            if row < len(self.preview_duplicate_flags):
                self.preview_duplicate_flags.pop(row)
        self.preview_transactions.insert(rows[0], base)
        self.preview_duplicate_flags.insert(rows[0], False)
        self._populate_preview_table()
