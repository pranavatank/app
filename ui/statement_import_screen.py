"""
ui/statement_import_screen.py — 5-step import wizard with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QProgressBar, QFrame, QCheckBox,
    QPlainTextEdit, QApplication, QScrollArea, QProgressDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from datetime import datetime
import json
import os
import re
import warnings

from ui.widgets.excel_table import ExcelTableWithStats

from ui.theme import Theme
from ui.date_utils import format_display_date
from core.session import session
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person, get_account, update_account
from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
from models.transaction import add_transaction, check_duplicate
from models.fixed_deposit import add_fd_from_statement, apply_statement_redemption_event
from models.statement_import_log import log_import
from engines.statement_parser import parse_statement_with_debug, filter_duplicates, validate_transactions
from engines.statement_metadata_extractor import extract_account_metadata
from ui.dialogs.account_dialog import AccountDialog


class StatementImportScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_step = 1
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
        self.statement_text = ""  # Store for metadata extraction
        self.fds_created_last_import = 0
        self._loader = None
        self._build_ui()

    def _show_loader(self, title: str, message: str) -> None:
        if self._loader is None:
            self._loader = QProgressDialog(message, "", 0, 0, self)
            self._loader.setCancelButton(None)
            self._loader.setWindowModality(Qt.WindowModality.WindowModal)
            self._loader.setMinimumDuration(0)
            self._loader.setAutoClose(False)
            self._loader.setAutoReset(False)
            self._loader.setWindowTitle(title)
            self._loader.setStyleSheet(f"""
                QProgressDialog {{
                    background: {Theme.SURFACE};
                    color: {Theme.TEXT_PRIMARY};
                }}
                QLabel {{
                    color: {Theme.TEXT_PRIMARY};
                    font-size: 13px;
                    font-weight: 600;
                    min-width: 320px;
                }}
                QProgressBar {{
                    border: 1px solid {Theme.BORDER};
                    border-radius: 8px;
                    background: {Theme.SURFACE_ALT};
                    text-align: center;
                    min-height: 14px;
                }}
                QProgressBar::chunk {{
                    background: {Theme.PRIMARY};
                    border-radius: 7px;
                }}
            """)
        else:
            self._loader.setWindowTitle(title)
            self._loader.setLabelText(message)

        self.btn_next.setEnabled(False)
        self.btn_back.setEnabled(False)
        self._loader.show()
        QApplication.processEvents()

    def _update_loader(self, message: str) -> None:
        if self._loader is not None:
            self._loader.setLabelText(message)
            QApplication.processEvents()

    def _hide_loader(self) -> None:
        if self._loader is not None:
            self._loader.hide()
        self.btn_next.setEnabled(True)
        self.btn_back.setEnabled(self.current_step > 1)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Header
        title = QLabel("📄  Statement Import Wizard")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        # Step progress bar
        self.progress = QProgressBar()
        self.progress.setMaximum(5)
        self.progress.setValue(1)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Step %v of %m")
        self.progress.setFixedHeight(24)
        layout.addWidget(self.progress)

        # Step indicator pills
        steps_row = QHBoxLayout(); steps_row.setSpacing(8)
        self._step_labels = []
        step_names = ["Select Person","Select Account","Choose File","Preview","Complete"]
        for i, name in enumerate(step_names):
            lbl = QLabel(f"{i+1}. {name}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(28)
            lbl.setStyleSheet(self._step_style(i+1, 1))
            steps_row.addWidget(lbl)
            self._step_labels.append(lbl)
        layout.addLayout(steps_row)

        # Content card
        self.content_frame = QFrame()
        self.content_frame.setObjectName("stepCard")
        self.content_frame.setStyleSheet(f"""
            QFrame#stepCard {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
        """)
        card_layout = QVBoxLayout(self.content_frame)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(14)

        self.content_scroll.setWidget(self.content_widget)
        card_layout.addWidget(self.content_scroll)
        layout.addWidget(self.content_frame, stretch=1)

        # Nav buttons
        nav = QHBoxLayout()
        nav.addStretch()
        self.btn_back = QPushButton("← Back")
        self.btn_back.setObjectName("secondaryBtn")
        self.btn_back.setFixedHeight(38); self.btn_back.setFixedWidth(100)
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)
        self.btn_next = QPushButton("Next →")
        self.btn_next.setObjectName("primaryBtn")
        self.btn_next.setFixedHeight(38); self.btn_next.setFixedWidth(120)
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_next)
        layout.addLayout(nav)

        self._show_step(1)

    def _step_style(self, step_num, current) -> str:
        if step_num == current:
            return f"""
                background-color: {Theme.PRIMARY}; color: white;
                border-radius: 6px; font-size: 11px; font-weight: 700;
                padding: 0 10px;
            """
        elif step_num < current:
            return f"""
                background-color: {Theme.SUCCESS_LIGHT}; color: {Theme.SUCCESS_DARK};
                border-radius: 6px; font-size: 11px; font-weight: 600;
                padding: 0 10px;
            """
        else:
            return f"""
                background-color: {Theme.SURFACE_ALT}; color: {Theme.TEXT_MUTED};
                border-radius: 6px; font-size: 11px;
                padding: 0 10px;
            """

    def _show_step(self, step: int):
        self.current_step = step
        self.progress.setValue(step)
        for i, lbl in enumerate(self._step_labels):
            lbl.setStyleSheet(self._step_style(i+1, step))

        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        if   step == 1: self._build_step1()
        elif step == 2: self._build_step2()
        elif step == 3: self._build_step3()
        elif step == 4: self._build_step4()
        elif step == 5: self._build_step5()

        self.btn_back.setEnabled(step > 1)
        self.btn_next.setText("Finish" if step == 5 else "Next →")

    def _step_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        return lbl

    def _step_subtitle(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def _build_step1(self):
        self.content_layout.addWidget(self._step_title("Step 1: Select Person"))
        self.content_layout.addWidget(self._step_subtitle("Choose the family member for this statement."))
        self.person_combo = QComboBox()
        for p in get_all_persons():
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])
        if self.selected_person_id:
            for i in range(self.person_combo.count()):
                if self.person_combo.itemData(i) == self.selected_person_id:
                    self.person_combo.setCurrentIndex(i)
        self.content_layout.addWidget(self.person_combo)
        self.content_layout.addStretch()

    def _build_step2(self):
        self.content_layout.addWidget(self._step_title("Step 2: Select Bank Account"))
        self.content_layout.addWidget(self._step_subtitle("Choose the bank account for this statement."))
        self.account_combo = QComboBox()
        accounts = get_accounts_for_person(self.selected_person_id)
        for acc in accounts:
            self.account_combo.addItem(
                f"{acc.get('bank_display_name', acc['bank_name'])} — {acc['account_type']} ({acc.get('account_number_masked','') or ''})",
                userData=acc["account_id"])
        if self.selected_account_id:
            for i in range(self.account_combo.count()):
                if self.account_combo.itemData(i) == self.selected_account_id:
                    self.account_combo.setCurrentIndex(i)
        self.content_layout.addWidget(self.account_combo)
        self.content_layout.addStretch()

    def _build_step3(self):
        self.content_layout.addWidget(self._step_title("Step 3: Choose Statement File"))
        self.content_layout.addWidget(self._step_subtitle("Select a PDF or Excel bank statement file."))

        file_row = QHBoxLayout()
        self.file_label = QLabel(self.selected_file.split("/")[-1] if self.selected_file else "No file selected")
        self.file_label.setStyleSheet(f"""
            background: {Theme.SURFACE_ALT}; color: {Theme.TEXT_SECONDARY};
            border: 1px solid {Theme.BORDER}; border-radius: 8px;
            padding: 8px 12px; font-size: 12px;
        """)
        file_row.addWidget(self.file_label, stretch=1)
        btn = QPushButton("Browse…")
        btn.setObjectName("secondaryBtn"); btn.setFixedHeight(38)
        btn.clicked.connect(self._browse_file)
        file_row.addWidget(btn)
        self.content_layout.addLayout(file_row)

        type_lbl = QLabel("File Type")
        type_lbl.setStyleSheet(f"font-weight: 600; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        self.content_layout.addWidget(type_lbl)
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems(["PDF", "Excel"])
        self.content_layout.addWidget(self.file_type_combo)
        self.content_layout.addStretch()

    def _build_step4(self):
        self.content_layout.addWidget(self._step_title("Step 4: Preview Transactions"))
        total_preview = len(self.preview_transactions)
        importable = len(self.parsed_transactions)
        selected_default = max(0, importable)
        if total_preview:
            info_text = (
                f"Parsed {total_preview} transactions. "
                f"New: {importable}, Duplicates: {self.duplicate_count}."
            )
        else:
            info_text = "No transactions extracted. Review Import Debug Panel below for details."
        info = QLabel(info_text)
        info.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        self.content_layout.addWidget(info)

        summary_row = QHBoxLayout()
        self.preview_summary_label = QLabel(
            f"Total: {total_preview}   |   Importable: {importable}   |   Selected: {selected_default}"
        )
        self.preview_summary_label.setStyleSheet(
            f"color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
        )
        summary_row.addWidget(self.preview_summary_label)
        summary_row.addStretch()

        btn_select_all = QPushButton("Select All New")
        btn_select_all.setObjectName("secondaryBtn")
        btn_select_all.setFixedHeight(32)
        btn_select_all.setFixedWidth(120)
        btn_select_all.clicked.connect(lambda: self._set_preview_selection(True))
        summary_row.addWidget(btn_select_all)

        btn_clear_all = QPushButton("Clear Selection")
        btn_clear_all.setObjectName("secondaryBtn")
        btn_clear_all.setFixedHeight(32)
        btn_clear_all.setFixedWidth(120)
        btn_clear_all.clicked.connect(lambda: self._set_preview_selection(False))
        summary_row.addWidget(btn_clear_all)

        self.content_layout.addLayout(summary_row)

        self.preview_table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.preview_table = self.preview_table_widget.table
        self.preview_table.setHeaders([
            "Date", "Type", "Mode", "Category", "Amount", "Balance", "Description", "Status"
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setStyleSheet(f"""
            QTableWidget {{
                background: {Theme.SURFACE_ALT};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                alternate-background-color: {Theme.SURFACE};
            }}
            QHeaderView::section {{
                background: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {Theme.BORDER};
                font-weight: 600;
            }}
        """)
        for i, w in enumerate([40,95,80,95,120,110,110,280,95]):
            self.preview_table.setColumnWidth(i, w)

        self.preview_table.setRowCount(len(self.preview_transactions))
        # Block signals during population
        self.preview_table.blockSignals(True)
        
        for idx, txn in enumerate(self.preview_transactions):
            # Add checkbox widget in column 0
            cb = QCheckBox()
            is_duplicate = self.preview_duplicate_flags[idx] if idx < len(self.preview_duplicate_flags) else False
            cb.setChecked(not is_duplicate)
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.preview_table.setCellWidget(idx, 0, cb_widget)
            
            date_item = QTableWidgetItem(format_display_date(txn.get("transaction_date")))
            type_item = QTableWidgetItem(txn["transaction_type"])
            mode_item = QTableWidgetItem(txn.get("mode", "") or "")
            cat_item = QTableWidgetItem(txn.get("category","") or "")
            amt_item = QTableWidgetItem(f"₹ {txn['amount']:,.2f}")
            bal_val = txn.get("balance_after")
            bal_item = QTableWidgetItem("—" if bal_val is None else f"₹ {bal_val:,.2f}")
            desc_item = QTableWidgetItem(txn.get("description","") or "")
            status_item = QTableWidgetItem("Duplicate" if is_duplicate else "New")

            for col, item in enumerate([date_item, type_item, mode_item, cat_item, amt_item, bal_item, desc_item, status_item]):
                if is_duplicate:
                    item.setForeground(QColor(120, 130, 145))
                elif col == 1:
                    if txn["transaction_type"] == "Income":
                        item.setForeground(QColor(56, 161, 105))
                    elif txn["transaction_type"] == "Expense":
                        item.setForeground(QColor(220, 38, 38))
                self.preview_table.setItem(idx, col+1, item)

            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.preview_table.setRowHeight(idx, 30)
            
        self.preview_table.blockSignals(False)  # Re-enable signals
        self.preview_table.setMinimumHeight(260)
        self.content_layout.addWidget(self.preview_table_widget, stretch=2)
        self._update_preview_summary()

        debug_title = QLabel("Import Debug Panel")
        debug_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        debug_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        self.content_layout.addWidget(debug_title)

        self.debug_output = QPlainTextEdit()
        self.debug_output.setReadOnly(True)
        self.debug_output.setMinimumHeight(170)
        self.debug_output.setMaximumHeight(240)
        self.debug_output.setPlainText(self._build_debug_text())
        self.debug_output.setStyleSheet(f"""
            background: {Theme.SURFACE_ALT};
            color: {Theme.TEXT_SECONDARY};
            border: 1px solid {Theme.BORDER};
            border-radius: 8px;
            font-size: 12px;
        """)
        self.content_layout.addWidget(self.debug_output)

        actions_row = QHBoxLayout()
        actions_row.addStretch()

        self.copy_debug_btn = QPushButton("Copy Report")
        self.copy_debug_btn.setObjectName("secondaryBtn")
        self.copy_debug_btn.setFixedHeight(34)
        self.copy_debug_btn.setFixedWidth(120)
        self.copy_debug_btn.clicked.connect(self._copy_debug_report)
        actions_row.addWidget(self.copy_debug_btn)

        self.export_debug_btn = QPushButton("Export Report")
        self.export_debug_btn.setObjectName("secondaryBtn")
        self.export_debug_btn.setFixedHeight(34)
        self.export_debug_btn.setFixedWidth(130)
        self.export_debug_btn.clicked.connect(self._export_debug_report)
        actions_row.addWidget(self.export_debug_btn)

        self.content_layout.addLayout(actions_row)

    def _build_step5(self):
        self.content_layout.addStretch()
        icon = QLabel("✅")
        icon.setFont(QFont("Segoe UI Emoji", 48))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(icon)

        success = QLabel("Import Complete!")
        success.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        success.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success.setStyleSheet(f"color: {Theme.SUCCESS};")
        self.content_layout.addWidget(success)

        stats_text = f"Imported {len(self.parsed_transactions)} transactions\nAccount: {self.bank_name}"
        if self.fds_created_last_import > 0:
            stats_text += f"\nFD records auto-created: {self.fds_created_last_import}"
        stats = QLabel(stats_text)
        stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        self.content_layout.addWidget(stats)
        self.content_layout.addStretch()

    def _is_fd_opening_transaction(self, txn: dict) -> bool:
        """Detect FD opening debit from statement narration."""
        if txn.get("transaction_type") != "Expense":
            return False
        desc = (txn.get("description") or "").upper()

        # Typical bank narrations: INITIAL PAYIN FD..., ... TD/00091116/..., TERM DEPOSIT
        patterns = [
            r"\bINITIAL\s+PAYIN\s+FD\b",
            r"\bFD\d{6,}\b",
            r"\bTD/\d+\b",
            r"\bTD\.?\s+GENERIC\s+PAYIN\b",
            r"\bPAYIN\s+DEBIT\b",
            r"\bTERM\s+DEPOSIT\b",
            r"\bFIXED\s+DEPOSIT\b",
            r"\b\d+\s*FD\b",
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

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Bank Statement", "",
            "All Files (*.pdf *.xls *.xlsx);;PDF (*.pdf);;Excel (*.xls *.xlsx)")
        if path:
            self.selected_file = path
            self.file_label.setText(path.split("/")[-1] or path.split("\\")[-1])

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
        importable = sum(1 for flag in self.preview_duplicate_flags if not flag)
        selected = len(self.preview_table.getCheckedRows())
        self.preview_summary_label.setText(
            f"Total: {total}   |   Importable: {importable}   |   Selected: {selected}"
        )

    def _build_debug_payload(self) -> dict:
        return {
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

    def _copy_debug_report(self):
        report = self._build_debug_text()
        QApplication.clipboard().setText(report)
        QMessageBox.information(self, "Copied", "Debug report copied to clipboard.")

    def _export_debug_report(self):
        default_name = "import_debug_report.json"
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Debug Report",
            default_name,
            "JSON Files (*.json);;Text Files (*.txt)"
        )
        if not path:
            return

        save_as_json = path.lower().endswith(".json") or "JSON" in selected_filter
        save_as_txt = path.lower().endswith(".txt") or "Text" in selected_filter

        try:
            if save_as_json and not path.lower().endswith(".json") and not save_as_txt:
                path = f"{path}.json"
            elif save_as_txt and not path.lower().endswith(".txt") and not save_as_json:
                path = f"{path}.txt"

            if path.lower().endswith(".txt"):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._build_debug_text())
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._build_debug_payload(), f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, "Exported", f"Debug report saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _go_next(self):
        if self.current_step == 1:
            self.selected_person_id = self.person_combo.currentData()
            if not self.selected_person_id:
                QMessageBox.warning(self, "No Person", "Please select a person."); return
            self._show_step(2)

        elif self.current_step == 2:
            self.selected_account_id = self.account_combo.currentData()
            if not self.selected_account_id:
                QMessageBox.warning(self, "No Account", "Please select an account."); return
            acc = get_account(self.selected_account_id)
            self.bank_name = acc["bank_name"] if acc else "Unknown"
            self._show_step(3)

        elif self.current_step == 3:
            if not self.selected_file:
                QMessageBox.warning(self, "No File", "Please select a statement file."); return
            self.file_type = self.file_type_combo.currentText()
            self._show_loader(
                "Processing Statement",
                "Reading statement and extracting transactions..."
            )
            try:
                # Parse statement
                txns, debug_info = parse_statement_with_debug(
                    self.selected_file,
                    self.file_type,
                    self.bank_name
                )
                self.import_debug_info = debug_info or {}
                
                # Extract and offer to update account metadata
                try:
                    self._update_loader("Extracting account metadata from statement...")
                    # Read statement text for metadata extraction
                    if self.file_type.upper() == "PDF":
                        import pdfplumber
                        with pdfplumber.open(self.selected_file) as pdf:
                            self.statement_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                    else:
                        import pandas as pd
                        with warnings.catch_warnings():
                            warnings.filterwarnings(
                                "ignore",
                                message="Workbook contains no default style, apply openpyxl's default",
                                category=UserWarning,
                            )
                            df = pd.read_excel(self.selected_file)
                        self.statement_text = df.to_string()
                    
                    metadata = extract_account_metadata(self.statement_text)
                    
                    # Show metadata dialog if any metadata found
                    if any(metadata.values()):
                        acc = get_account(self.selected_account_id)
                        self._hide_loader()
                        persons = get_all_persons()
                        merged = dict(acc or {})
                        for k, v in metadata.items():
                            if v not in (None, ""):
                                merged[k] = v

                        dialog = AccountDialog(self, persons, merged)
                        dialog.setWindowTitle(f"Update Account Details - {(acc or {}).get('bank_name', 'Account')}")
                        if dialog.exec() == QDialog.DialogCode.Accepted:
                            payload = dialog.get_data()
                            tan_code = payload.pop("tan_code", None)
                            update_account(self.selected_account_id, **payload)
                            get_or_create_bank(payload.get("bank_name") or "")
                            if tan_code:
                                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)
                        self._show_loader(
                            "Processing Statement",
                            "Validating transactions and checking duplicates..."
                        )
                except Exception as e:
                    # Metadata extraction is optional, don't fail import
                    print(f"Metadata extraction failed: {e}")

                self._update_loader("Validating transactions and checking duplicates...")
                
                if not txns:
                    self.parsed_transactions = []
                    self.preview_transactions = []
                    self.preview_duplicate_flags = []
                    self.validation_errors = []
                    self.duplicate_count = 0
                    self._show_step(4)
                    QMessageBox.information(
                        self,
                        "No Transactions",
                        "Could not extract transactions.\n\n"
                        "Step 4 Import Debug Panel now shows detailed extraction issues."
                    )
                    return
                valid, errors = validate_transactions(txns)
                self.validation_errors = errors
                if errors:
                    QMessageBox.warning(
                        self,
                        "Validation Errors",
                        "Some rows were skipped. Open Step 4 Import Debug Panel for details."
                    )

                self.preview_transactions = valid
                self.preview_duplicate_flags = [
                    check_duplicate(
                        self.selected_account_id,
                        row["transaction_date"],
                        row["amount"],
                        row["description"],
                    )
                    for row in valid
                ]
                unique = [row for row, is_dup in zip(valid, self.preview_duplicate_flags) if not is_dup]
                dups = sum(1 for is_dup in self.preview_duplicate_flags if is_dup)
                self.duplicate_count = dups

                if dups > 0:
                    if dups == len(valid) and valid:
                        QMessageBox.information(
                            self,
                            "All Duplicates",
                            "All extracted rows already exist for this account. "
                            "Preview shows parsed rows, but duplicates are disabled for import."
                        )
                    else:
                        QMessageBox.information(self,"Duplicates",f"{dups} duplicate(s) will be skipped.")
                self.parsed_transactions = unique
                self._show_step(4)
            except Exception as e:
                QMessageBox.critical(self,"Parse Error", str(e))
            finally:
                self._hide_loader()

        elif self.current_step == 4:
            if not self.preview_transactions:
                QMessageBox.warning(
                    self,
                    "Nothing to Import",
                    "No transactions are available to import. Please go back and choose another statement file."
                )
                return

            self._show_loader(
                "Importing Transactions",
                "Saving transactions, creating FD entries, and writing import log..."
            )

            imported = 0
            fds_created = 0
            try:
                total_rows = len(self.preview_transactions)
                checked_rows = self.preview_table.getCheckedRows()
                
                for idx in checked_rows:
                    if idx % 25 == 0:
                        self._update_loader(
                            f"Importing selected transactions... {len([i for i in checked_rows if i <= idx])}/{len(checked_rows)} processed"
                        )

                    is_duplicate = self.preview_duplicate_flags[idx] if idx < len(self.preview_duplicate_flags) else False
                    if is_duplicate:
                        continue
                        
                    txn = self.preview_transactions[idx]
                    txn_id = add_transaction(
                        account_id=self.selected_account_id,
                        person_id=self.selected_person_id,
                        transaction_date=txn["transaction_date"],
                        transaction_type=txn["transaction_type"],
                        amount=txn["amount"],
                        category=txn.get("category"),
                        mode=txn.get("mode"),
                        reference_no=txn.get("reference_no"),
                        description=txn.get("description"),
                        balance_after=txn.get("balance_after"),
                        source="Statement Import"
                    )
                    imported += 1

                    # Best-effort maturity handling for redemption-like income rows.
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

                if imported == 0:
                    QMessageBox.warning(
                        self,
                        "Nothing Selected",
                        "Please select at least one transaction to import."
                    )
                    return

                self._update_loader("Finalizing import log and summary...")
                log_import(
                    account_id=self.selected_account_id, person_id=self.selected_person_id,
                    bank_name=self.bank_name,
                    file_name=(self.selected_file.split("/")[-1] or self.selected_file.split("\\")[-1]),
                    file_type=self.file_type, records_imported=imported, status="Success")
                self.fds_created_last_import = fds_created
                self.parsed_transactions = self.parsed_transactions[:imported]
                self._show_step(5)
            finally:
                self._hide_loader()

        elif self.current_step == 5:
            if self.parent_window: self.parent_window.refresh_overview()
            self.refresh()

    def _go_back(self):
        if self.current_step > 1: self._show_step(self.current_step - 1)

    def refresh(self):
        self.current_step = 1
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
        self._show_step(1)
