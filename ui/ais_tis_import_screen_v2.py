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
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from core.session import session
from models.person import get_person
from models.form26as import save_form26as_import, get_form26as_import, get_form26as_records
from models.ais_tis_import import save_ais_tis_data, get_ais_tis_data, save_ais_tis_records, get_ais_tis_records
from models.income_source import (
    get_income_source_by_tan, save_income_source, get_all_income_sources,
    SOURCE_TYPES, SOURCE_TYPE_EMPLOYER, SOURCE_TYPE_BANK
)
from engines.form26as_parser import parse_form26as_pdf, parse_form26as_text_simple, extract_financial_year_from_ay
from engines.ais_tis_parser import parse_ais_json, parse_tis_json
from engines.pdf_extractor import extract_pdf_text
import json


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

        # Tab widget with 3 tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
                background: {Theme.SURFACE};
            }}
            QTabBar::tab {{
                background: {Theme.SURFACE_ALT};
                color: {Theme.TEXT_SECONDARY};
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: {Theme.PRIMARY};
                color: white;
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{
                background: {Theme.PRIMARY_LIGHT};
                color: {Theme.PRIMARY_DARK};
            }}
        """)

        # Tab 1: Form 26AS
        self.tab_26as = self._build_26as_tab()
        self.tabs.addTab(self.tab_26as, "📄 Form 26AS")

        # Tab 2: AIS
        self.tab_ais = self._build_ais_tab()
        self.tabs.addTab(self.tab_ais, "📑 AIS")

        # Tab 3: TIS
        self.tab_tis = self._build_tis_tab()
        self.tabs.addTab(self.tab_tis, "📋 TIS")

        layout.addWidget(self.tabs, 1)
        
        # Debug panel at bottom (collapsible)
        self._build_debug_panel(layout)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(Theme.card_style(radius=10, padding=12))
        h_layout = QHBoxLayout(header)
        h_layout.setSpacing(12)

        title = QLabel("Income Tax Data Import")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(14))
        h_layout.addWidget(title)

        self.person_label = QLabel("Select person")
        self.person_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=11, weight=500))
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
        btn_import = Theme.btn("📤 Import Form 26AS PDF", "primary", height=36, min_width=200)
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
        self.table_26as.setColumnCount(7)
        self.table_26as.setHorizontalHeaderLabels([
            "Deductor Name", "TAN", "Section", "Date", "Amount Paid", "TDS Deducted", "Status"
        ])
        self.table_26as.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_26as.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_26as.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_layout.addWidget(self.table_26as)
        
        scroll.setWidget(table_container)
        layout.addWidget(scroll, 1)
        return tab

    def _build_ais_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Import button
        btn_layout = QHBoxLayout()
        btn_import = Theme.btn("📤 Import AIS JSON", "success", height=36, min_width=180)
        btn_import.clicked.connect(self._import_ais)
        btn_layout.addWidget(btn_import)
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
        self.table_ais.setColumnCount(6)
        self.table_ais.setHorizontalHeaderLabels([
            "Source", "TAN", "Type", "Amount", "TDS", "Quarter"
        ])
        self.table_ais.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_ais.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_ais.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_layout.addWidget(self.table_ais)
        
        scroll.setWidget(table_container)
        layout.addWidget(scroll, 1)
        return tab

    def _build_tis_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Import button
        btn_layout = QHBoxLayout()
        btn_import = Theme.btn("📤 Import TIS JSON", "info", height=36, min_width=180)
        btn_import.clicked.connect(self._import_tis)
        btn_layout.addWidget(btn_import)
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
        self.table_tis.setColumnCount(6)
        self.table_tis.setHorizontalHeaderLabels([
            "Source", "TAN", "Type", "Amount", "TDS", "Quarter"
        ])
        self.table_tis.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_tis.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_tis.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_layout.addWidget(self.table_tis)
        
        scroll.setWidget(table_container)
        layout.addWidget(scroll, 1)
        return tab

    def _build_debug_panel(self, parent_layout):
        """Collapsible debug panel at bottom."""
        self.debug_frame = QFrame()
        self.debug_frame.setStyleSheet(Theme.card_style(radius=8, padding=8))
        self.debug_frame.setMaximumHeight(200)
        self.debug_frame.hide()
        
        debug_layout = QVBoxLayout(self.debug_frame)
        debug_layout.setContentsMargins(8, 8, 8, 8)
        debug_layout.setSpacing(4)
        
        debug_header = QHBoxLayout()
        debug_title = QLabel("🐞 Debug: Extracted Text")
        debug_title.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=11, weight=600))
        debug_header.addWidget(debug_title)
        debug_header.addStretch()
        
        btn_close_debug = QPushButton("✕")
        btn_close_debug.setFixedSize(20, 20)
        btn_close_debug.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_SECONDARY};
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {Theme.DANGER};
            }}
        """)
        btn_close_debug.clicked.connect(self.debug_frame.hide)
        debug_header.addWidget(btn_close_debug)
        debug_layout.addLayout(debug_header)
        
        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setStyleSheet(f"""
            background: {Theme.SURFACE_ALT};
            border: 1px solid {Theme.BORDER};
            border-radius: 6px;
            padding: 6px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 10px;
            color: {Theme.TEXT_PRIMARY};
        """)
        debug_layout.addWidget(self.debug_text)
        
        parent_layout.addWidget(self.debug_frame)
        
        # Toggle button
        self.btn_toggle_debug = Theme.btn("🐞 Show Debug", "ghost", height=28, min_width=120)
        self.btn_toggle_debug.clicked.connect(self._toggle_debug)
        parent_layout.addWidget(self.btn_toggle_debug)

    def refresh(self):
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            self.person_label.setText("⚠ Please select a person from the top bar")
            self.person_label.setStyleSheet(Theme.text_style(color=Theme.WARNING, size=11, weight=500))
            self.table_26as.setRowCount(0)
            self.table_ais.setRowCount(0)
            self.table_tis.setRowCount(0)
            return
        
        person = get_person(pid)
        if person:
            self.person_label.setText(f"{person['full_name']} · FY {fy}")
            self.person_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=600))
        
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
        
        # Get TIS import (source_type = 'TIS')
        from core.database import get_connection
        conn = get_connection()
        row = conn.execute("""
            SELECT * FROM AISTISImport
            WHERE person_id = ? AND financial_year = ? AND source_type = 'TIS'
            ORDER BY import_date DESC LIMIT 1
        """, (pid, fy)).fetchone()
        conn.close()
        
        if not row:
            self.table_tis.setRowCount(0)
            return
        
        import_data = dict(row)
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
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
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
            self.btn_toggle_debug.setText("🐞 Hide Debug")
            
            # Parse Form 26AS
            parsed = parse_form26as_pdf(pdf_text)
            
            if not parsed["records"]:
                # Try simple parser
                parsed["records"] = parse_form26as_text_simple(pdf_text)
            
            if not parsed["records"]:
                QMessageBox.warning(self, "No Records", "No TDS records found in PDF.")
                return
            
            # Determine FY
            if parsed["assessment_year"]:
                import_fy = extract_financial_year_from_ay(parsed["assessment_year"])
            else:
                import_fy = fy
            
            # Process records and match with income sources
            processed_records = []
            new_sources = []
            
            for rec in parsed["records"]:
                tan = rec.get("deductor_tan", "").strip().upper()
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
            
            QMessageBox.information(
                self, "Import Successful",
                f"Imported {len(processed_records)} TDS records from Form 26AS."
            )
            
            self._load_26as_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import Form 26AS:\n{str(e)}")

    def _import_ais(self):
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
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
            
            # Parse AIS
            source_type = "AIS" if "ais" in file_path.lower() else "TIS"
            if source_type == "AIS":
                parsed = parse_ais_json(json_data)
            else:
                parsed = parse_tis_json(json_data)
            
            # Show debug
            self.debug_text.setPlainText(raw_json[:5000])  # First 5000 chars
            self.debug_frame.show()
            self.btn_toggle_debug.setText("🐞 Hide Debug")
            
            # Check for existing AIS data
            existing = get_ais_tis_data(pid, fy)
            
            # Merge with existing if present
            if existing:
                # Update missing fields only
                for key in ["salary_income", "fd_interest", "savings_interest", "other_interest",
                           "dividend_income", "rental_income", "other_income", "tds_deducted"]:
                    if parsed.get(key, 0) > 0 and existing.get(key, 0) == 0:
                        existing[key] = parsed[key]
                parsed = existing
            
            # Save to database
            import_id = save_ais_tis_data(
                person_id=pid,
                financial_year=fy,
                source_type=source_type,
                raw_json=raw_json,
                data=parsed
            )
            
            # Save detailed records
            records = parsed.get("details", [])
            if records:
                # Convert details to proper format
                formatted_records = []
                for rec in records:
                    formatted_records.append({
                        "record_type": rec.get("type", "unknown"),
                        "information_code": rec.get("section", ""),
                        "information_description": rec.get("type", ""),
                        "information_source": rec.get("source", rec.get("deductor", "")),
                        "source_tan": rec.get("tan", ""),
                        "amount": rec.get("amount", 0),
                        "tds_deducted": rec.get("tds", 0),
                    })
                save_ais_tis_records(import_id, formatted_records)
                # Process new TANs
                new_sources = []
                for rec in formatted_records:
                    tan = (rec.get("source_tan") or "").strip().upper()
                    if tan and not get_income_source_by_tan(tan):
                        new_sources.append(rec)
                
                if new_sources:
                    self._handle_new_sources_ais(new_sources)
            
            QMessageBox.information(
                self, "Import Successful",
                f"Imported AIS/TIS data for FY {fy}."
            )
            
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
        
        import_data = get_ais_tis_data(pid, fy)
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
            self.btn_toggle_debug.setText("🐞 Show Debug")
        else:
            self.debug_frame.show()
            self.btn_toggle_debug.setText("🐞 Hide Debug")

    def _import_tis(self):
        """Import TIS JSON - similar to AIS but separate storage."""
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
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
            
            # Parse TIS
            parsed = parse_tis_json(json_data)
            
            # Show debug
            self.debug_text.setPlainText(raw_json[:5000])  # First 5000 chars
            
            # Check for existing TIS data
            existing = get_ais_tis_data(pid, fy)
            
            # Save to database with TIS source type
            import_id = save_ais_tis_data(
                person_id=pid,
                financial_year=fy,
                source_type="TIS",
                raw_json=raw_json,
                data=parsed
            )
            
            # Save detailed records
            records = parsed.get("details", [])
            if records:
                formatted_records = []
                for rec in records:
                    formatted_records.append({
                        "record_type": rec.get("type", "unknown"),
                        "information_code": rec.get("section", ""),
                        "information_description": rec.get("type", ""),
                        "information_source": rec.get("source", rec.get("deductor", "")),
                        "source_tan": rec.get("tan", ""),
                        "amount": rec.get("amount", 0),
                        "tds_deducted": rec.get("tds", 0),
                    })
                save_ais_tis_records(import_id, formatted_records)
                
                # Process new TANs
                new_sources = []
                for rec in formatted_records:
                    tan = (rec.get("source_tan") or "").strip().upper()
                    if tan and not get_income_source_by_tan(tan):
                        new_sources.append(rec)
                
                if new_sources:
                    self._handle_new_sources_ais(new_sources)
            
            QMessageBox.information(
                self, "Import Successful",
                f"Imported TIS data for FY {fy}."
            )
            
            self._load_tis_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import TIS:\n{str(e)}")


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
        
        title = QLabel(f"🔍 New TANs found in {self.source_type}")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(14))
        layout.addWidget(title)
        
        info = QLabel(
            "The following TANs are not in your database. "
            "Please select the type of income source for each:"
        )
        info.setWordWrap(True)
        info.setStyleSheet(Theme.text_style(size=12))
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
            label.setStyleSheet(Theme.text_style(size=11))
            
            combo = QComboBox()
            combo.addItems(SOURCE_TYPES)
            combo.setCurrentText(SOURCE_TYPE_EMPLOYER)
            combo.setFixedHeight(32)
            
            self.combos.append((rec, combo))
            form_layout.addRow(label, combo)
        
        layout.addWidget(form_frame)
        
        if len(self.records) > 10:
            note = QLabel(f"Note: Showing first 10 of {len(self.records)} new sources.")
            note.setStyleSheet(Theme.muted_style(11))
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
