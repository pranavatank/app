"""
ui/ais_tis_import_screen.py — AIS/TIS JSON import screen with comparison view
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame, QComboBox, QTextEdit, QGroupBox,
    QDialog, QLineEdit, QFormLayout, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ui.theme import Theme
from core.session import session
from config import get_current_financial_year
from models.person import get_all_persons
from models.ais_tis_import import (
    save_ais_tis_data,
    get_ais_tis_data,
    save_ais_tis_pdf_lines,
    save_ais_tis_records,
    get_ais_tis_records,
)
from models.transaction import get_income_total
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from engines.ais_tis_parser import parse_ais_json, parse_tis_json, parse_ais_pdf_text, parse_tis_pdf_text
from engines.pdf_extractor import extract_pdf_text, PDFExtractionError
from models.bank import update_bank_tan_code_if_exists, extract_bank_name_and_tan


class AISTISImportScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_data = None
        self._current_import_id = 0
        self._current_records = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("AIS/TIS Import")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        btn_import_pdf = QPushButton("📄  Import PDF")
        btn_import_pdf.setObjectName("primaryBtn")
        btn_import_pdf.setFixedHeight(38)
        btn_import_pdf.clicked.connect(self._on_import_pdf)
        header.addWidget(btn_import_pdf)

        btn_refresh = QPushButton("🔄  Refresh")
        btn_refresh.setObjectName("secondaryBtn")
        btn_refresh.setFixedHeight(38)
        btn_refresh.clicked.connect(self.refresh)
        header.addWidget(btn_refresh)

        layout.addLayout(header)

        # Info card
        info_card = QFrame()
        info_card.setObjectName("card")
        info_card.setMaximumHeight(90)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)

        info_title = QLabel("📋 Annual Information Statement (AIS) / Tax Information Statement (TIS)")
        info_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_title.setStyleSheet(f"color: {Theme.PRIMARY};")
        info_layout.addWidget(info_title)

        info_text = QLabel(
            "Import your AIS/TIS PDF downloaded from the Income Tax portal (password-protected). "
            "The system will compare portal totals with expected data from your app."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        info_layout.addWidget(info_text)

        layout.addWidget(info_card)

        # Comparison table
        table_label = QLabel("Income Comparison: AIS/TIS vs App Data")
        table_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        table_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Income Type", "Actual (AIS/TIS)", "Expected (App)", "Difference", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

        # Details section
        details_group = QGroupBox("Import Details")
        details_layout = QVBoxLayout(details_group)

        # Structured breakdown controls
        breakdown_controls = QHBoxLayout()

        breakdown_controls.addWidget(QLabel("Bank/Source:"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(360)
        self.source_combo.currentIndexChanged.connect(self._update_breakdown_table)
        breakdown_controls.addWidget(self.source_combo)

        breakdown_controls.addWidget(QLabel("Quarter:"))
        self.quarter_combo = QComboBox()
        self.quarter_combo.setMinimumWidth(160)
        self.quarter_combo.currentIndexChanged.connect(self._update_breakdown_table)
        breakdown_controls.addWidget(self.quarter_combo)

        breakdown_controls.addStretch()
        self.unique_label = QLabel("")
        self.unique_label.setObjectName("mutedLabel")
        breakdown_controls.addWidget(self.unique_label)

        details_layout.addLayout(breakdown_controls)

        self.breakdown_table = QTableWidget()
        self.breakdown_table.setColumnCount(5)
        self.breakdown_table.setHorizontalHeaderLabels([
            "Date", "Amount Paid/Credited", "TDS Deducted", "TDS Deposited", "Status"
        ])
        self.breakdown_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.breakdown_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.breakdown_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.breakdown_table.setAlternatingRowColors(True)
        self.breakdown_table.verticalHeader().setVisible(False)
        self.breakdown_table.setShowGrid(False)
        self.breakdown_table.setMinimumHeight(220)
        details_layout.addWidget(self.breakdown_table)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setStyleSheet(f"""
            background-color: {Theme.SURFACE_ALT};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER};
            border-radius: 8px;
            padding: 8px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
        """)
        details_layout.addWidget(self.details_text)
        
        layout.addWidget(details_group)

        self.status_label = QLabel("No data imported yet. Click 'Import PDF' to begin.")
        self.status_label.setObjectName("mutedLabel")
        layout.addWidget(self.status_label)

    def refresh(self):
        """Refresh comparison data."""
        person_id = session.selected_person_id
        fy = session.selected_fy

        if not person_id:
            self.table.setRowCount(0)
            self.details_text.clear()
            self.status_label.setText("Please select a person from the top bar.")
            return

        # Get AIS/TIS data
        ais_data = get_ais_tis_data(person_id, fy)
        
        if not ais_data:
            self.table.setRowCount(0)
            self.details_text.clear()
            self.source_combo.clear()
            self.quarter_combo.clear()
            self.breakdown_table.setRowCount(0)
            self.unique_label.setText("")
            self.status_label.setText(f"No AIS/TIS data imported for FY {fy}. Click 'Import PDF' to import.")
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

        # Get app data
        app_salary = get_income_total(person_id=person_id, financial_year=fy, category="Salary")
        app_fd_interest = get_total_fd_interest(fy, person_id=person_id)
        app_savings_interest = get_total_savings_interest(fy, person_id=person_id)
        app_dividend = get_income_total(person_id=person_id, financial_year=fy, category="Dividend")
        app_rental = get_income_total(person_id=person_id, financial_year=fy, category="Rental Income")
        app_other = get_income_total(person_id=person_id, financial_year=fy, category="Other Income")

        # Build comparison table
        comparisons = [
            ("Salary Income", ais_data.get('salary_income', 0), app_salary),
            ("FD Interest", ais_data.get('fd_interest', 0), app_fd_interest),
            ("Savings Interest", ais_data.get('savings_interest', 0), app_savings_interest),
            ("Other Interest", ais_data.get('other_interest', 0), 0),
            ("Dividend Income", ais_data.get('dividend_income', 0), app_dividend),
            ("Rental Income", ais_data.get('rental_income', 0), app_rental),
            ("Other Income", ais_data.get('other_income', 0), app_other),
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
            self.table.setItem(r, 1, item(session.mask(actual), Qt.AlignmentFlag.AlignRight))
            self.table.setItem(r, 2, item(session.mask(expected), Qt.AlignmentFlag.AlignRight))
            
            diff = actual - expected
            diff_text = session.mask(abs(diff))
            if diff > 0:
                diff_text = f"+{diff_text}"
            elif diff < 0:
                diff_text = f"-{diff_text}"
            else:
                diff_text = "—"
            
            diff_item = item(diff_text, Qt.AlignmentFlag.AlignRight)
            if diff > 100:
                diff_item.setForeground(QColor(Theme.WARNING))
            elif diff < -100:
                diff_item.setForeground(QColor(Theme.DANGER))
            else:
                diff_item.setForeground(QColor(Theme.SUCCESS))
            self.table.setItem(r, 3, diff_item)

            # Status
            if abs(diff) < 10:
                status = "✓ Match"
                status_color = Theme.SUCCESS
            elif abs(diff) < 1000:
                status = "⚠ Minor Diff"
                status_color = Theme.WARNING
            else:
                status = "✗ Mismatch"
                status_color = Theme.DANGER
            
            status_item = item(status)
            status_item.setForeground(QColor(status_color))
            self.table.setItem(r, 4, status_item)
            
            self.table.setRowHeight(r, 36)

        # Show details + breakdown
        source_type = (ais_data.get('source_type') or 'Unknown').upper()
        raw = ais_data.get('raw_json') or ''

        parsed_records = []
        try:
            import_id = int(ais_data.get("import_id") or 0)
        except Exception:
            import_id = 0

        if import_id:
            try:
                parsed_records = get_ais_tis_records(import_id)
            except Exception:
                parsed_records = []

        # Fallback: compute records on the fly if DB has none.
        if not parsed_records and source_type in ("AIS", "TIS"):
            raw_stripped = raw.lstrip()
            if raw_stripped.startswith("{") or raw_stripped.startswith("["):
                try:
                    parsed = parse_ais_json(raw) if source_type == "AIS" else parse_tis_json(raw)
                    parsed_records = parsed.get("details") or []
                except Exception:
                    parsed_records = []
            else:
                try:
                    parsed = parse_ais_pdf_text(raw) if source_type == "AIS" else parse_tis_pdf_text(raw)
                    parsed_records = parsed.get("details") or []
                except Exception:
                    parsed_records = []

        lines = []
        lines.append(f"Import Date: {ais_data.get('import_date', 'Unknown')}")
        lines.append(f"Source: {source_type}")
        lines.append(f"Financial Year: {fy}")
        lines.append("")
        lines.append("Totals")
        lines.append(f"  Salary Income: {ais_data.get('salary_income', 0):,.2f}")
        lines.append(f"  FD Interest: {ais_data.get('fd_interest', 0):,.2f}")
        lines.append(f"  Savings Interest: {ais_data.get('savings_interest', 0):,.2f}")
        lines.append(f"  Other Interest: {ais_data.get('other_interest', 0):,.2f}")
        lines.append(f"  Dividend Income: {ais_data.get('dividend_income', 0):,.2f}")
        lines.append(f"  Rental Income: {ais_data.get('rental_income', 0):,.2f}")
        lines.append(f"  Other Income: {ais_data.get('other_income', 0):,.2f}")
        lines.append(f"  TDS Deducted: {ais_data.get('tds_deducted', 0):,.2f}")

        if parsed_records:
            lines.append("")
            lines.append("Breakdown")
            for d in parsed_records:
                # JSON parser uses keys like type/section/deductor; PDF parser uses code/source/bucket.
                code = d.get('code') or d.get('section') or ''
                desc = d.get('description') or d.get('type') or ''
                src = d.get('source') or d.get('deductor') or ''
                amt = d.get('amount')
                tds = d.get('tds')

                # DB record shape
                if not code:
                    code = d.get('information_code') or ''
                if not desc:
                    desc = d.get('information_description') or ''
                if not src:
                    src = d.get('information_source') or ''
                if amt is None:
                    amt = d.get('amount')
                if tds is None:
                    tds = d.get('tds_deducted')

                q = d.get('quarter')
                dt = d.get('payment_date')
                amt_paid = d.get('amount_paid')
                status = d.get('status')

                parts = []
                if code:
                    parts.append(str(code))
                if desc:
                    parts.append(str(desc))
                if src:
                    parts.append(str(src))
                if q:
                    parts.append(str(q))
                if dt:
                    parts.append(str(dt))
                if isinstance(amt_paid, (int, float)):
                    parts.append(f"Paid={amt_paid:,.2f}")
                if isinstance(amt, (int, float)):
                    parts.append(f"Amount={amt:,.2f}")
                if isinstance(tds, (int, float)):
                    parts.append(f"TDS={tds:,.2f}")
                if status:
                    parts.append(str(status))
                lines.append("  - " + " | ".join(parts))

        self.details_text.clear()
        self.details_text.setPlainText("\n".join(lines))

        self._populate_breakdown_dropdowns()
        self._update_breakdown_table()

        count = self.table.rowCount()
        self.status_label.setText(f"Showing {count} income type{'s' if count != 1 else ''} comparison.")

    def _on_import_pdf(self):
        """Import AIS/TIS PDF by extracting text (password-protected) and parsing key totals."""
        person_id = session.selected_person_id
        if not person_id:
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select AIS/TIS PDF File", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if not file_path:
            return

        password_dialog = PasswordDialog(self)
        password_dialog.setWindowTitle("Enter PDF Password")
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        password = password_dialog.get_password()
        if not password:
            QMessageBox.warning(self, "No Password", "Password is required to open the PDF.")
            return

        try:
            result = extract_pdf_text(file_path, password=password)
        except PDFExtractionError as e:
            QMessageBox.critical(
                self,
                "PDF Extraction Failed",
                f"Failed to extract text from PDF. Please check your password.\n\nError: {str(e)}",
            )
            return

        extracted_text = result.text
        # Detect AIS vs TIS from extracted text.
        text_l = extracted_text.lower()
        if "annual information statement" in text_l or "(ais)" in text_l:
            source_type = "AIS"
            parsed_data = parse_ais_pdf_text(extracted_text)
        elif "tax information statement" in text_l or "(tis)" in text_l:
            source_type = "TIS"
            parsed_data = parse_tis_pdf_text(extracted_text)
        else:
            QMessageBox.information(
                self,
                "PDF Extracted",
                "PDF text extracted successfully, but this PDF doesn't clearly look like AIS or TIS. "
                "Showing extracted text in details panel.",
            )
            self.details_text.clear()
            self.details_text.setPlainText(extracted_text)
            self.status_label.setText(
                f"PDF text extracted from {result.pages_extracted} page{'s' if result.pages_extracted != 1 else ''}."
            )
            return

        try:
            fy = session.selected_fy
            import_id = save_ais_tis_data(person_id, fy, source_type, extracted_text, parsed_data)

            if import_id:
                # Store everything from PDF: raw lines + structured records
                save_ais_tis_pdf_lines(import_id, extracted_text)
                save_ais_tis_records(import_id, parsed_data.get('details', []))

                # Update TAN code into Bank master table (only if that bank already exists).
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

            QMessageBox.information(
                self, "Import Success",
                f"{source_type} PDF imported successfully for FY {fy}!\n\n"
                f"Salary: ₹{parsed_data['salary_income']:,.2f}\n"
                f"FD Interest: ₹{parsed_data['fd_interest']:,.2f}\n"
                f"Savings Interest: ₹{parsed_data['savings_interest']:,.2f}\n"
                f"TDS Deducted: ₹{parsed_data['tds_deducted']:,.2f}"
            )

            self.refresh()
            if self.parent_window:
                self.parent_window.refresh_overview()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Failed",
                f"Failed to import PDF:\n\nError: {str(e)}",
            )

    def _populate_breakdown_dropdowns(self):
        # Build bank/source list from summary records.
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

            # TIS often has sources only on detail rows.
            if not sources:
                for r in self._current_records:
                    if r.get("record_type") != "detail":
                        continue
                    src = (r.get("information_source") or "").strip()
                    if src and src not in sources:
                        sources.append(src)

            if not sources:
                self.source_combo.addItem("(no bank/source found)", "")
            else:
                for s in sources:
                    self.source_combo.addItem(s, s)

            self.quarter_combo.addItem("(all)", "")
            quarters = []
            for r in self._current_records:
                q = (r.get("quarter") or "").strip()
                if q and q not in quarters:
                    quarters.append(q)
            # Stable order Q1..Q4 if present
            quarters_sorted = sorted(
                quarters,
                key=lambda x: int(x[1]) if len(x) > 1 and x[1].isdigit() else 9,
            )
            for q in quarters_sorted:
                self.quarter_combo.addItem(q, q)
        finally:
            self.source_combo.blockSignals(False)
            self.quarter_combo.blockSignals(False)

    def _update_breakdown_table(self):
        src = self.source_combo.currentData() if hasattr(self, "source_combo") else ""
        quarter = self.quarter_combo.currentData() if hasattr(self, "quarter_combo") else ""

        # Filter detail rows by selection.
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

        # Update unique-FD heuristic: unique (date, amount_paid) pairs in the selection.
        unique_pairs = set()
        unique_amounts = set()
        for r in detail_rows:
            dt = (r.get("payment_date") or "").strip()
            amt = r.get("amount_paid")
            if isinstance(amt, (int, float)):
                unique_pairs.add((dt, float(amt)))
                unique_amounts.add(float(amt))

        summary_text = ""
        if summary_row is not None:
            code = summary_row.get("information_code") or ""
            desc = summary_row.get("information_description") or ""
            amt = summary_row.get("amount")
            cnt = summary_row.get("count")
            if isinstance(amt, (int, float)):
                summary_text = f"{code} {desc} | Total={amt:,.2f} | Count={cnt if cnt is not None else '—'}"

        self.unique_label.setText(
            f"Rows: {len(detail_rows)} | Unique credits: {len(unique_pairs)} | Unique amounts: {len(unique_amounts)}"
        )

        # Fill table
        self.breakdown_table.setRowCount(0)

        # Optional: show one header-like row as the first row (summary context)
        if summary_text:
            self.breakdown_table.insertRow(0)
            it = QTableWidgetItem(summary_text)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            it.setForeground(QColor(Theme.TEXT_SECONDARY))
            self.breakdown_table.setItem(0, 0, it)
            for c in range(1, 5):
                self.breakdown_table.setItem(0, c, QTableWidgetItem(""))
            self.breakdown_table.setRowHeight(0, 30)

        start_row = 1 if summary_text else 0
        for idx, r in enumerate(detail_rows, start=start_row):
            self.breakdown_table.insertRow(idx)

            def item(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            dt = r.get("payment_date") or ""
            amt_paid = r.get("amount_paid")
            tds_ded = r.get("tds_deducted")
            tds_dep = r.get("tds_deposited")
            status = r.get("status") or ""

            # For TIS annexure rows, surface reported/processed/accepted in Status to avoid UI changes.
            ar = r.get("amount_reported")
            ap = r.get("amount_processed")
            aa = r.get("amount_accepted")
            if not dt and (isinstance(ar, (int, float)) or isinstance(ap, (int, float)) or isinstance(aa, (int, float))):
                parts = []
                if isinstance(ar, (int, float)):
                    parts.append(f"Reported={ar:,.2f}")
                if isinstance(ap, (int, float)):
                    parts.append(f"Processed={ap:,.2f}")
                if isinstance(aa, (int, float)):
                    parts.append(f"Accepted={aa:,.2f}")
                extra = " ".join(parts)
                status = (f"{status} {extra}").strip() if status else extra

            self.breakdown_table.setItem(idx, 0, item(dt))
            self.breakdown_table.setItem(idx, 1, item(f"{amt_paid:,.2f}" if isinstance(amt_paid, (int, float)) else "", Qt.AlignmentFlag.AlignRight))
            self.breakdown_table.setItem(idx, 2, item(f"{tds_ded:,.2f}" if isinstance(tds_ded, (int, float)) else "", Qt.AlignmentFlag.AlignRight))
            self.breakdown_table.setItem(idx, 3, item(f"{tds_dep:,.2f}" if isinstance(tds_dep, (int, float)) else "", Qt.AlignmentFlag.AlignRight))
            self.breakdown_table.setItem(idx, 4, item(status))
            self.breakdown_table.setRowHeight(idx, 30)


class PasswordDialog(QDialog):
    """Dialog to enter password for encrypted AIS/TIS files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter Decryption Password")
        self.setModal(True)
        self.setMinimumWidth(450)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        # Info
        info_label = QLabel(
            "🔒 This file is encrypted. Please enter the password to decrypt it.\n\n"
            "The password is typically your PAN number or PAN + Date of Birth."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(info_label)
        
        # Form
        form = QFormLayout()
        form.setSpacing(12)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter password (e.g., PAN or PAN+DOB)")
        self.password_input.setMinimumHeight(36)
        form.addRow("Password:", self.password_input)
        
        self.show_password_check = QCheckBox("Show password")
        self.show_password_check.stateChanged.connect(self._toggle_password_visibility)
        form.addRow("", self.show_password_check)
        
        layout.addLayout(form)
        
        # Hint
        hint_label = QLabel(
            "💡 Hint: Common formats are:\n"
            "  • PAN only (e.g., ABCDE1234F)\n"
            "  • PAN + DOB (e.g., ABCDE1234F01011990)\n"
            "  • DOB in DDMMYYYY format"
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet(f"""
            color: {Theme.TEXT_MUTED};
            font-size: 12px;
            background-color: {Theme.SURFACE_ALT};
            padding: 10px;
            border-radius: 6px;
        """)
        layout.addWidget(hint_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondaryBtn")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setMinimumWidth(100)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_decrypt = QPushButton("🔓  Decrypt")
        btn_decrypt.setObjectName("primaryBtn")
        btn_decrypt.setFixedHeight(36)
        btn_decrypt.setMinimumWidth(100)
        btn_decrypt.clicked.connect(self.accept)
        btn_layout.addWidget(btn_decrypt)
        
        layout.addLayout(btn_layout)
    
    def _toggle_password_visibility(self, state):
        if state == Qt.CheckState.Checked.value:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def get_password(self) -> str:
        return self.password_input.text().strip()
