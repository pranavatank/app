"""
ui/ais_tis_import_screen.py — AIS/TIS PDF import + comparison view.
FIX: PasswordDialog buttons use Theme.btn() for guaranteed visibility.
FIX: Main screen import/refresh buttons also use Theme.btn().
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame, QComboBox, QTextEdit, QGroupBox,
    QDialog, QLineEdit, QFormLayout, QCheckBox, QScrollArea,
    QRadioButton, QButtonGroup, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ui.widgets.excel_table import ExcelTableWithStats

from ui.theme import Theme
from ui.date_utils import format_display_datetime
from core.session import session
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person, add_account
from models.ais_tis_import import (
    save_ais_tis_data, get_ais_tis_data,
    save_ais_tis_pdf_lines, save_ais_tis_records, get_ais_tis_records,
)
from models.transaction import get_income_total
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from engines.ais_tis_parser import parse_ais_json, parse_tis_json, parse_ais_pdf_text, parse_tis_pdf_text
from engines.pdf_extractor import extract_pdf_text, PDFExtractionError
from models.bank import (
    update_bank_tan_code_if_exists,
    extract_bank_name_and_tan,
    get_or_create_bank,
)


class ImportTypeDialog(QDialog):
    """Prompt user to choose import source type before selecting PDF."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Import Type")
        self.setModal(True)
        self.resize(360, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Choose which statement you want to import")
        title.setStyleSheet(Theme.section_label_style())
        layout.addWidget(title)

        self.group = QButtonGroup(self)
        self.rb_ais = QRadioButton("AIS (Annual Information Statement)")
        self.rb_tis = QRadioButton("TIS (Tax Information Statement)")
        self.rb_ais.setChecked(True)
        self.group.addButton(self.rb_ais)
        self.group.addButton(self.rb_tis)

        layout.addWidget(self.rb_ais)
        layout.addWidget(self.rb_tis)

        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = Theme.btn("Continue", "primary", height=34, min_width=100)
        cancel_btn = Theme.btn("Cancel", "secondary", height=34, min_width=90)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

    def selected_type(self) -> str:
        return "AIS" if self.rb_ais.isChecked() else "TIS"


class SourceAccountLinkDialog(QDialog):
    """Map imported AIS/TIS sources to an existing account bank and persist TAN mapping."""

    def __init__(self, person_accounts: list[dict], source_rows: list[dict], parent=None):
        super().__init__(parent)
        self.person_accounts = person_accounts or []
        self.source_rows = source_rows or []
        self._combos = []
        self.setWindowTitle("Link Imported Sources")
        self.setModal(True)
        self.resize(900, 420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Select which existing account bank should be linked for each imported source. "
            "When TAN is available, it will be attached to the selected bank."
        )
        info.setWordWrap(True)
        info.setStyleSheet(Theme.muted_style(12))
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Imported Source", "Detected Bank", "Unique No. (TAN)", "Link To Account Bank"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Build unique bank options from person's accounts.
        bank_options = []
        seen = set()
        for acc in self.person_accounts:
            bname = (acc.get("bank_name") or "").strip()
            if not bname:
                continue
            key = bname.lower()
            if key in seen:
                continue
            seen.add(key)
            bank_options.append(bname)
        bank_options.sort()

        self.table.setRowCount(len(self.source_rows))
        for i, row in enumerate(self.source_rows):
            src = row.get("source") or ""
            det_bank = row.get("detected_bank") or ""
            tan = row.get("tan") or ""
            self.table.setItem(i, 0, QTableWidgetItem(src))
            self.table.setItem(i, 1, QTableWidgetItem(det_bank))
            self.table.setItem(i, 2, QTableWidgetItem(tan or "—"))

            combo = QComboBox()
            combo.addItem("(skip)", "")
            for opt in bank_options:
                combo.addItem(opt, opt)

            # Preselect matching bank when possible.
            if det_bank:
                idx = combo.findData(det_bank)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            self.table.setCellWidget(i, 3, combo)
            self._combos.append(combo)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = Theme.btn("Cancel", "secondary", height=34, min_width=90)
        save_btn = Theme.btn("Save Links", "primary", height=34, min_width=110)
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def selected_links(self) -> list[dict]:
        links = []
        for i, row in enumerate(self.source_rows):
            target_bank = self._combos[i].currentData()
            if not target_bank:
                continue
            links.append({
                "source": row.get("source") or "",
                "detected_bank": row.get("detected_bank") or "",
                "tan": row.get("tan") or "",
                "target_bank": target_bank,
            })
        return links


class AISTISImportScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_data = None
        self._current_import_id = 0
        self._current_records = []
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # Header card
        header_card = QFrame()
        header_card.setObjectName("AisHeaderCard")
        header_card.setStyleSheet(f"""
            QFrame#AisHeaderCard {{
                background-color: {Theme.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("AIS / TIS Import")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(16))
        title_col.addWidget(title)

        self.header_meta = QLabel("Select a person to view import insights")
        self.header_meta.setStyleSheet(Theme.muted_style(12))
        title_col.addWidget(self.header_meta)
        title_row.addLayout(title_col)
        title_row.addStretch()

        btn_import = Theme.btn("📄  Import PDF", "primary", height=40, min_width=136)
        btn_import.clicked.connect(self._on_import_pdf)
        title_row.addWidget(btn_import)

        btn_refresh = Theme.btn("🔄  Refresh", "secondary", height=40, min_width=112)
        btn_refresh.clicked.connect(self.refresh)
        title_row.addWidget(btn_refresh)
        header_layout.addLayout(title_row)

        info = QLabel(
            "Import password-protected AIS/TIS PDFs and compare portal income with your app data. "
            "Use breakdown filters to inspect source-level records and TDS details."
        )
        info.setWordWrap(True)
        info.setStyleSheet(Theme.text_style(color=Theme.INFO_DARK, size=12) + f" background: {Theme.INFO_LIGHT}; border: 1px solid {Theme.INFO}; border-radius: 8px; padding: 10px 12px;")
        header_layout.addWidget(info)

        chips = QHBoxLayout(); chips.setSpacing(8)
        self.chip_source = QLabel("Source: —")
        self.chip_fy = QLabel("FY: —")
        self.chip_rows = QLabel("Rows: 0")
        self.chip_tds = QLabel("TDS: ₹0.00")
        for chip in [self.chip_source, self.chip_fy, self.chip_rows, self.chip_tds]:
            chip.setStyleSheet(Theme.badge_style(Theme.SURFACE_ALT, Theme.TEXT_SECONDARY, radius=10, padding="4px 10px", size=11, weight=600))
            chips.addWidget(chip)
        chips.addStretch()
        header_layout.addLayout(chips)
        main_layout.addWidget(header_card)

        # Split workspace
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        # Left: comparison + summary
        left_card = QFrame()
        left_card.setObjectName("AisLeftCard")
        left_card.setStyleSheet(f"""
            QFrame#AisLeftCard {{
                background-color: {Theme.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(14, 12, 14, 12)
        left_layout.setSpacing(10)

        comp_label = QLabel("Income Comparison: AIS/TIS vs App Data")
        comp_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        comp_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))
        left_layout.addWidget(comp_label)

        self.table_widget = ExcelTableWithStats(show_checkboxes=False)
        self.table = self.table_widget.table
        self.table.setHeaders([
            "Income Type", "Actual (AIS/TIS)", "Expected (App)", "Difference", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(280)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {Theme.SURFACE_ALT};
                border: none;
                border-radius: 10px;
                gridline-color: {Theme.DIVIDER};
            }}
            QHeaderView::section {{
                background: {Theme.SURFACE};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 9px 8px;
                font-weight: 700;
                border-bottom: 1px solid {Theme.DIVIDER};
            }}
        """)
        left_layout.addWidget(self.table_widget, 1)

        summary_lbl = QLabel("Import Summary")
        summary_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        summary_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=10, weight=700))
        left_layout.addWidget(summary_lbl)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setStyleSheet(f"""
            background-color: {Theme.SURFACE_ALT};
            color: {Theme.TEXT_PRIMARY};
            border: none;
            border-radius: 8px;
            padding: 8px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
        """)
        left_layout.addWidget(self.details_text)
        splitter.addWidget(left_card)

        # Right: breakdown panel
        right_card = QFrame()
        right_card.setObjectName("AisRightCard")
        right_card.setStyleSheet(f"""
            QFrame#AisRightCard {{
                background-color: {Theme.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(14, 12, 14, 12)
        right_layout.setSpacing(10)

        breakdown_title = QLabel("Transaction Breakdown")
        breakdown_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        breakdown_title.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))
        right_layout.addWidget(breakdown_title)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        controls_row.addWidget(self._lbl("Source"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(220)
        self.source_combo.setFixedHeight(36)
        self.source_combo.currentIndexChanged.connect(self._update_breakdown_table)
        self.source_combo.setStyleSheet(f"""
            QComboBox {{
                background: {Theme.SURFACE_ALT};
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
            }}
        """)
        controls_row.addWidget(self.source_combo)

        controls_row.addWidget(self._lbl("Quarter"))
        self.quarter_combo = QComboBox()
        self.quarter_combo.setMinimumWidth(110)
        self.quarter_combo.setFixedHeight(36)
        self.quarter_combo.currentIndexChanged.connect(self._update_breakdown_table)
        self.quarter_combo.setStyleSheet(f"""
            QComboBox {{
                background: {Theme.SURFACE_ALT};
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
            }}
        """)
        controls_row.addWidget(self.quarter_combo)
        controls_row.addStretch()
        right_layout.addLayout(controls_row)

        self.unique_label = QLabel("")
        self.unique_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
        right_layout.addWidget(self.unique_label)

        self.breakdown_table_widget = ExcelTableWithStats(show_checkboxes=False)
        self.breakdown_table = self.breakdown_table_widget.table
        self.breakdown_table.setHeaders([
            "Date", "Amount Paid/Credited", "TDS Deducted", "TDS Deposited", "Status"
        ])
        self.breakdown_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.breakdown_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.breakdown_table.setMinimumHeight(380)
        self.breakdown_table.setStyleSheet(f"""
            QTableWidget {{
                background: {Theme.SURFACE_ALT};
                border: none;
                border-radius: 10px;
                gridline-color: {Theme.DIVIDER};
            }}
            QHeaderView::section {{
                background: {Theme.SURFACE};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 9px 8px;
                font-weight: 700;
                border-bottom: 1px solid {Theme.DIVIDER};
            }}
        """)
        right_layout.addWidget(self.breakdown_table_widget, 1)

        status_frame = QFrame()
        status_frame.setObjectName("AisStatusFrame")
        status_frame.setStyleSheet(f"""
            QFrame#AisStatusFrame {{
                background: {Theme.SURFACE_ALT};
                border: none;
                border-radius: 10px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 8, 10, 8)
        status_layout.setSpacing(8)
        status_icon = QLabel("ℹ️")
        status_icon.setFont(QFont("Segoe UI Emoji", 14))
        status_layout.addWidget(status_icon)
        self.status_label = QLabel("No data imported yet. Click '📄 Import PDF' to begin.")
        self.status_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=11))
        status_layout.addWidget(self.status_label, 1)
        right_layout.addWidget(status_frame)

        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter, 1)

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(Theme.section_label_style())
        return l

    def _update_header_chips(self, source_text: str = "—", fy: str = "—", rows: int = 0, tds: float = 0.0):
        self.chip_source.setText(f"Source: {source_text}")
        self.chip_fy.setText(f"FY: {fy}")
        self.chip_rows.setText(f"Rows: {rows}")
        self.chip_tds.setText(f"TDS: ₹ {tds:,.2f}")

        self.chip_source.setStyleSheet(Theme.badge_style(Theme.INFO_LIGHT, Theme.INFO_DARK, radius=10, padding="4px 10px", size=11, weight=600))
        self.chip_fy.setStyleSheet(Theme.badge_style(Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK, radius=10, padding="4px 10px", size=11, weight=600))
        self.chip_rows.setStyleSheet(Theme.badge_style(Theme.SURFACE_ALT, Theme.TEXT_SECONDARY, radius=10, padding="4px 10px", size=11, weight=600))
        self.chip_tds.setStyleSheet(Theme.badge_style(Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK, radius=10, padding="4px 10px", size=11, weight=600))

    def refresh(self):
        person_id = session.selected_person_id
        fy = session.selected_fy

        self.header_meta.setText(f"FY {fy} • {'Person selected' if person_id else 'Select a person to continue'}")

        if not person_id:
            self.table.setRowCount(0)
            self.details_text.clear()
            self.status_label.setText("Please select a person from the top bar.")
            self._update_header_chips(source_text="—", fy=fy or "—", rows=0, tds=0.0)
            return

        ais_data = get_ais_tis_data(person_id, fy)
        if not ais_data:
            self.table.setRowCount(0)
            self.details_text.clear()
            self.source_combo.clear()
            self.quarter_combo.clear()
            self.breakdown_table.setRowCount(0)
            self.unique_label.setText("")
            self.status_label.setText(
                f"No AIS/TIS data imported for FY {fy}. Click '📄 Import PDF' to import.")
            self._update_header_chips(source_text="Not imported", fy=fy or "—", rows=0, tds=0.0)
            return

        try:
            self._current_import_id = int(ais_data.get("import_id") or 0)
        except Exception:
            self._current_import_id = 0

        self._current_records = []
        if self._current_import_id:
            try:
                self._current_records = get_ais_tis_records(self._current_import_id)
            except Exception:
                self._current_records = []

        app_salary   = get_income_total(person_id=person_id, financial_year=fy, category="Salary")
        app_fd       = get_total_fd_interest(fy, person_id=person_id)
        app_savings  = get_total_savings_interest(fy, person_id=person_id)
        app_dividend = get_income_total(person_id=person_id, financial_year=fy, category="Dividend")
        app_rental   = get_income_total(person_id=person_id, financial_year=fy, category="Rental Income")
        app_other    = get_income_total(person_id=person_id, financial_year=fy, category="Other Income")

        comparisons = [
            ("Salary Income",    ais_data.get('salary_income', 0),   app_salary),
            ("FD Interest",      ais_data.get('fd_interest', 0),      app_fd),
            ("Savings Interest", ais_data.get('savings_interest', 0), app_savings),
            ("Other Interest",   ais_data.get('other_interest', 0),   0),
            ("Dividend Income",  ais_data.get('dividend_income', 0),  app_dividend),
            ("Rental Income",    ais_data.get('rental_income', 0),    app_rental),
            ("Other Income",     ais_data.get('other_income', 0),     app_other),
        ]

        self.table.setRowCount(0)
        for income_type, actual, expected in comparisons:
            if actual == 0 and expected == 0:
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)

            def item(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            self.table.setItem(r, 0, item(income_type))
            self.table.setItem(r, 1, item(session.mask(actual),   Qt.AlignmentFlag.AlignRight))
            self.table.setItem(r, 2, item(session.mask(expected), Qt.AlignmentFlag.AlignRight))

            diff = actual - expected
            diff_text = session.mask(abs(diff))
            if diff > 0:   diff_text = f"+{diff_text}"
            elif diff < 0: diff_text = f"-{diff_text}"
            else:          diff_text = "—"
            diff_item = item(diff_text, Qt.AlignmentFlag.AlignRight)
            diff_item.setForeground(QColor(
                Theme.WARNING if diff > 100 else (Theme.DANGER if diff < -100 else Theme.SUCCESS)))
            self.table.setItem(r, 3, diff_item)

            if abs(diff) < 10:
                status, sc = "✓ Match", Theme.SUCCESS
            elif abs(diff) < 1000:
                status, sc = "⚠ Minor Diff", Theme.WARNING
            else:
                status, sc = "✗ Mismatch", Theme.DANGER
            si = item(status)
            si.setForeground(QColor(sc))
            self.table.setItem(r, 4, si)
            self.table.setRowHeight(r, 36)

        # Summary text
        lines = [
            f"Import Date : {format_display_datetime(ais_data.get('import_date'))}",
            f"Source      : {(ais_data.get('source_type') or 'Unknown').upper()}",
            f"Financial Yr: {fy}", "",
            f"Salary      : ₹ {ais_data.get('salary_income',0):>14,.2f}",
            f"FD Interest : ₹ {ais_data.get('fd_interest',0):>14,.2f}",
            f"Sav Interest: ₹ {ais_data.get('savings_interest',0):>14,.2f}",
            f"Other Int   : ₹ {ais_data.get('other_interest',0):>14,.2f}",
            f"Dividend    : ₹ {ais_data.get('dividend_income',0):>14,.2f}",
            f"Rental      : ₹ {ais_data.get('rental_income',0):>14,.2f}",
            f"Other Income: ₹ {ais_data.get('other_income',0):>14,.2f}",
            f"TDS Deducted: ₹ {ais_data.get('tds_deducted',0):>14,.2f}",
        ]
        self.details_text.setPlainText("\n".join(lines))

        self._populate_breakdown_dropdowns()
        self._update_breakdown_table()
        count = self.table.rowCount()
        self.status_label.setText(
            f"Showing {count} income type{'s' if count != 1 else ''} comparison.")
        self._update_header_chips(
            source_text=(ais_data.get("source_type") or "Unknown").upper(),
            fy=fy or "—",
            rows=len(self._current_records or []),
            tds=float(ais_data.get("tds_deducted") or 0.0),
        )

    def _on_import_pdf(self):
        person_id = session.selected_person_id
        if not person_id:
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
            return

        type_dlg = ImportTypeDialog(self)
        if type_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        selected_type = type_dlg.selected_type()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {selected_type} PDF File",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not file_path:
            return

        pwd_dlg = PasswordDialog(self)
        if pwd_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        password = pwd_dlg.get_password()
        if not password:
            QMessageBox.warning(self, "No Password", "Password is required to open the PDF.")
            return

        try:
            result = extract_pdf_text(file_path, password=password)
        except PDFExtractionError as e:
            QMessageBox.critical(self, "PDF Extraction Failed",
                f"Could not extract text. Please check your password.\n\nError: {e}")
            return

        extracted_text = result.text
        try:
            source_type, parsed_data = self._parse_pdf_by_selected_type(selected_type, extracted_text)
        except Exception as e:
            QMessageBox.critical(self, "Parse Failed", f"Could not parse selected PDF.\n\nError: {e}")
            return

        try:
            fy = session.selected_fy
            import_id = save_ais_tis_data(person_id, fy, source_type, extracted_text, parsed_data)
            if import_id:
                save_ais_tis_pdf_lines(import_id, extracted_text)
                save_ais_tis_records(import_id, parsed_data.get('details', []))
                for rec in (parsed_data.get('details') or []):
                    src = (rec.get("information_source") or rec.get("source") or "").strip()
                    tan = (rec.get("source_tan") or "").strip()
                    bank_name = ""
                    if src and not tan:
                        bank_name, tan = extract_bank_name_and_tan(src)
                    elif src and tan:
                        bank_name, _ = extract_bank_name_and_tan(src)
                    if bank_name and tan:
                        update_bank_tan_code_if_exists(bank_name, tan)

                self._prompt_missing_reference_actions(person_id, parsed_data.get('details', []))

            QMessageBox.information(self, "Import Success",
                f"{source_type} imported for FY {fy}!\n\n"
                f"Salary     : ₹ {parsed_data['salary_income']:,.2f}\n"
                f"FD Interest: ₹ {parsed_data['fd_interest']:,.2f}\n"
                f"Sav Int    : ₹ {parsed_data['savings_interest']:,.2f}\n"
                f"TDS        : ₹ {parsed_data['tds_deducted']:,.2f}")
            self.refresh()
            if self.parent_window:
                self.parent_window.refresh_overview()
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Error: {e}")

    def _parse_pdf_by_selected_type(self, selected_type: str, extracted_text: str):
        text_l = (extracted_text or "").lower()
        has_ais_marker = "annual information statement" in text_l or "(ais)" in text_l
        has_tis_marker = "tax information statement" in text_l or "(tis)" in text_l

        expected_parser = parse_ais_pdf_text if selected_type == "AIS" else parse_tis_pdf_text
        fallback_parser = parse_tis_pdf_text if selected_type == "AIS" else parse_ais_pdf_text
        fallback_type = "TIS" if selected_type == "AIS" else "AIS"

        parsed = expected_parser(extracted_text)
        details_count = len(parsed.get("details") or [])

        # If user selected one type but markers strongly indicate the other,
        # confirm if we should switch parser to keep import robust.
        marker_mismatch = (selected_type == "AIS" and has_tis_marker and not has_ais_marker) or (
            selected_type == "TIS" and has_ais_marker and not has_tis_marker
        )
        if marker_mismatch:
            reply = QMessageBox.question(
                self,
                "Type Mismatch Detected",
                f"This PDF appears to be {fallback_type}.\n"
                f"You selected {selected_type}.\n\n"
                f"Do you want to import as {fallback_type} instead?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                parsed_fb = fallback_parser(extracted_text)
                return fallback_type, parsed_fb

        # Parser fallback if selected parser yields no structured records.
        if details_count == 0:
            parsed_fb = fallback_parser(extracted_text)
            fb_count = len(parsed_fb.get("details") or [])
            if fb_count > 0:
                reply = QMessageBox.question(
                    self,
                    "Switch Parser",
                    f"Selected {selected_type} parser found no details, but {fallback_type} parser found {fb_count} records.\n\n"
                    f"Import as {fallback_type}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    return fallback_type, parsed_fb

        return selected_type, parsed

    def _prompt_missing_reference_actions(self, person_id: int, details: list[dict]) -> None:
        source_rows = self._collect_source_rows(details)
        if not source_rows:
            return

        person_accounts = get_accounts_for_person(person_id)
        person_account_names = {
            (a.get("bank_name") or "").strip().lower() for a in person_accounts
        }

        missing_for_person = sorted({
            r["detected_bank"]
            for r in source_rows
            if r.get("detected_bank") and r["detected_bank"].strip().lower() not in person_account_names
        })

        if not missing_for_person:
            return

        lines = [
            "Some imported banks are not linked to this person's account list:",
            "",
        ]
        lines.extend([f"- {b}" for b in missing_for_person[:12]])
        lines.append("")
        lines.append("Choose how you want to continue.")

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Bank Linking Required")
        msg.setText("\n".join(lines))

        add_btn = msg.addButton("Add Missing Bank Accounts", QMessageBox.ButtonRole.AcceptRole)
        link_btn = msg.addButton("Link To Existing Accounts", QMessageBox.ButtonRole.ActionRole)
        later_btn = msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(add_btn)
        msg.exec()

        if msg.clickedButton() is add_btn:
            added_count = self._add_missing_bank_accounts(person_id, source_rows)
            QMessageBox.information(
                self,
                "Accounts Added",
                f"Added {added_count} bank account(s) for selected person."
            )
            return

        if msg.clickedButton() is link_btn:
            if not person_accounts:
                QMessageBox.warning(
                    self,
                    "No Accounts Found",
                    "No existing accounts available to link. Use 'Add Missing Bank Accounts' first."
                )
                return

            link_dlg = SourceAccountLinkDialog(person_accounts, source_rows, self)
            if link_dlg.exec() != QDialog.DialogCode.Accepted:
                return

            linked = self._apply_source_links(link_dlg.selected_links())
            QMessageBox.information(
                self,
                "Linking Completed",
                f"Linked {linked} source mapping(s) and updated TAN codes where available."
            )

    def _collect_source_rows(self, details: list[dict]) -> list[dict]:
        rows = {}
        for rec in (details or []):
            src = (rec.get("information_source") or rec.get("source") or "").strip()
            if not src:
                continue
            tan = (rec.get("source_tan") or "").strip().upper()
            bank_name, parsed_tan = extract_bank_name_and_tan(src)
            if not tan:
                tan = parsed_tan
            key = src.lower()
            if key not in rows:
                rows[key] = {
                    "source": src,
                    "detected_bank": bank_name,
                    "tan": tan,
                }
            elif tan and not rows[key].get("tan"):
                rows[key]["tan"] = tan
        return sorted(rows.values(), key=lambda r: (r.get("detected_bank") or "", r.get("source") or ""))

    def _add_missing_bank_accounts(self, person_id: int, source_rows: list[dict]) -> int:
        existing = {
            (a.get("bank_name") or "").strip().lower() for a in get_accounts_for_person(person_id)
        }
        added = 0
        for row in source_rows:
            bank_name = (row.get("detected_bank") or "").strip()
            tan = (row.get("tan") or "").strip().upper()
            if not bank_name or bank_name.lower() in existing:
                continue

            # Ensure bank master exists and then store TAN when available.
            get_or_create_bank(bank_name)
            if tan:
                update_bank_tan_code_if_exists(bank_name, tan)

            masked = f"AIS-{tan[-4:]}" if tan else "AIS-LINK"
            add_account(
                person_id=person_id,
                bank_name=bank_name,
                account_type="Savings",
                account_number_masked=masked,
                opening_balance=0.0,
                interest_rate=0.0,
            )
            existing.add(bank_name.lower())
            added += 1
        return added

    def _apply_source_links(self, links: list[dict]) -> int:
        applied = 0
        for link in links:
            target_bank = (link.get("target_bank") or "").strip()
            tan = (link.get("tan") or "").strip().upper()
            if not target_bank:
                continue

            get_or_create_bank(target_bank)
            if tan:
                update_bank_tan_code_if_exists(target_bank, tan)
            applied += 1
        return applied

    def _populate_breakdown_dropdowns(self):
        self.source_combo.blockSignals(True)
        self.quarter_combo.blockSignals(True)
        try:
            self.source_combo.clear()
            self.quarter_combo.clear()
            if not self._current_records:
                self.source_combo.addItem("(no breakdown)", "")
                self.quarter_combo.addItem("(all)", "")
                return
            sources = []
            for r in self._current_records:
                if r.get("record_type") == "summary":
                    src = (r.get("information_source") or "").strip()
                    if src and src not in sources:
                        sources.append(src)
            if not sources:
                for r in self._current_records:
                    if r.get("record_type") != "detail": continue
                    src = (r.get("information_source") or "").strip()
                    if src and src not in sources:
                        sources.append(src)
            if not sources:
                self.source_combo.addItem("(no source found)", "")
            else:
                for s in sources:
                    self.source_combo.addItem(s, s)
            self.quarter_combo.addItem("(all)", "")
            quarters = []
            for r in self._current_records:
                q = (r.get("quarter") or "").strip()
                if q and q not in quarters:
                    quarters.append(q)
            for q in sorted(quarters, key=lambda x: int(x[1]) if len(x)>1 and x[1].isdigit() else 9):
                self.quarter_combo.addItem(q, q)
        finally:
            self.source_combo.blockSignals(False)
            self.quarter_combo.blockSignals(False)

    def _update_breakdown_table(self):
        src     = self.source_combo.currentData()    if hasattr(self, "source_combo")  else ""
        quarter = self.quarter_combo.currentData()   if hasattr(self, "quarter_combo") else ""

        detail_rows = []
        summary_row = None
        for r in (self._current_records or []):
            if src and (r.get("information_source") or "").strip() != src:
                continue
            if r.get("record_type") == "summary" and summary_row is None:
                summary_row = r
            if r.get("record_type") != "detail":
                continue
            if quarter and (r.get("quarter") or "").strip() != quarter:
                continue
            detail_rows.append(r)

        unique_pairs   = set()
        unique_amounts = set()
        for r in detail_rows:
            dt  = (r.get("payment_date") or "").strip()
            amt = r.get("amount_paid")
            if isinstance(amt, (int, float)):
                unique_pairs.add((dt, float(amt)))
                unique_amounts.add(float(amt))

        self.unique_label.setText(
            f"Rows: {len(detail_rows)}  |  Unique credits: {len(unique_pairs)}  |  Unique amounts: {len(unique_amounts)}")

        summary_text = ""
        if summary_row:
            code = summary_row.get("information_code") or ""
            desc = summary_row.get("information_description") or ""
            amt  = summary_row.get("amount")
            cnt  = summary_row.get("count")
            if isinstance(amt, (int, float)):
                summary_text = (f"{code} {desc}  |  Total=₹{amt:,.2f}"
                                f"  |  Count={cnt if cnt is not None else '—'}")

        self.breakdown_table.setRowCount(0)
        if summary_text:
            self.breakdown_table.insertRow(0)
            it = QTableWidgetItem(summary_text)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            it.setForeground(QColor(Theme.TEXT_SECONDARY))
            self.breakdown_table.setItem(0, 0, it)
            for c in range(1, 5):
                self.breakdown_table.setItem(0, c, QTableWidgetItem(""))
            self.breakdown_table.setRowHeight(0, 28)

        start = 1 if summary_text else 0
        for idx, r in enumerate(detail_rows, start=start):
            self.breakdown_table.insertRow(idx)

            def item(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            dt      = r.get("payment_date")  or ""
            amt_p   = r.get("amount_paid")
            tds_ded = r.get("tds_deducted")
            tds_dep = r.get("tds_deposited")
            status  = r.get("status") or ""

            ar = r.get("amount_reported")
            ap = r.get("amount_processed")
            aa = r.get("amount_accepted")
            if not dt and any(isinstance(v,(int,float)) for v in [ar,ap,aa]):
                parts = []
                if isinstance(ar,(int,float)): parts.append(f"Reported={ar:,.2f}")
                if isinstance(ap,(int,float)): parts.append(f"Processed={ap:,.2f}")
                if isinstance(aa,(int,float)): parts.append(f"Accepted={aa:,.2f}")
                status = (f"{status} {' '.join(parts)}").strip()

            self.breakdown_table.setItem(idx, 0, item(dt))
            self.breakdown_table.setItem(idx, 1, item(f"{amt_p:,.2f}" if isinstance(amt_p,(int,float)) else "", Qt.AlignmentFlag.AlignRight))
            self.breakdown_table.setItem(idx, 2, item(f"{tds_ded:,.2f}" if isinstance(tds_ded,(int,float)) else "", Qt.AlignmentFlag.AlignRight))
            self.breakdown_table.setItem(idx, 3, item(f"{tds_dep:,.2f}" if isinstance(tds_dep,(int,float)) else "", Qt.AlignmentFlag.AlignRight))
            self.breakdown_table.setItem(idx, 4, item(status))
            self.breakdown_table.setRowHeight(idx, 30)


class PasswordDialog(QDialog):
    """Password entry dialog for encrypted PDF files. Uses Theme.btn() for all buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter PDF Password")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        # Info
        info = QLabel(
            "🔒  This file is encrypted. Please enter the password.\n\n"
            "The password is typically your PAN number or PAN + Date of Birth."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            background: {Theme.PRIMARY_LIGHT};
            border: 1px solid {Theme.INFO};
            border-radius: 8px;
            padding: 12px;
            font-size: 13px;
        """)
        layout.addWidget(info)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("e.g. ABCDE1234F or ABCDE1234F01011990")
        self.password_input.setFixedHeight(40)
        self.password_input.returnPressed.connect(self.accept)
        form.addRow("Password:", self.password_input)

        self.show_check = QCheckBox("Show password")
        self.show_check.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13))
        self.show_check.stateChanged.connect(self._toggle_visibility)
        form.addRow("", self.show_check)
        layout.addLayout(form)

        # Hint card
        hint = QLabel(
            "💡  Common formats:\n"
            "  •  PAN only  (e.g. ABCDE1234F)\n"
            "  •  PAN + DOB  (e.g. ABCDE1234F01011990)\n"
            "  •  DOB in DDMMYYYY format"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"""
            color: {Theme.TEXT_SECONDARY};
            background: {Theme.SURFACE_ALT};
            border: 1px solid {Theme.BORDER};
            border-radius: 8px;
            padding: 10px;
            font-size: 12px;
        """)
        layout.addWidget(hint)

        # Buttons — Theme.btn() for guaranteed visibility in QDialog
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = Theme.btn("Cancel", "secondary", height=38, min_width=100)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_ok = Theme.btn("🔓  Decrypt & Import", "primary", height=38, min_width=160)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _toggle_visibility(self, state):
        mode = QLineEdit.EchoMode.Normal if state else QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(mode)

    def get_password(self) -> str:
        return self.password_input.text().strip()
