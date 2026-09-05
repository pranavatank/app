"""
ui/dialogs/fd_dialog.py — Add/edit dialog for fixed deposits.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QDateEdit, QFormLayout, QFrame, QScrollArea,
    QWidget, QSpinBox, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QDoubleValidator

from datetime import date

from ui.theme import Theme
from ui.widgets.toast_utils import show_success, show_warning
from config import COMPOUNDING_TYPES, fy_date_range, get_current_financial_year, get_all_financial_years
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person
from models.fixed_deposit import (
    add_fd, update_fd, get_fd, get_fd_link_candidates
)
from models.fd_interest_record import get_total_fd_interest
from engines.interest_engine import (
    calculate_fd_maturity_bank_style,
    calculate_fd_maturity_date,
    calculate_fd_maturity_flexible,
    calculate_fd_quarterly_credit_breakdown,
    allocate_fd_interest_to_fy,
)


class FDDialog(QDialog):
    def __init__(self, parent, mode="add", fd_id=None):
        super().__init__(parent)
        self.mode = mode; self.fd_id = fd_id; self.fd_data = None
        self.setWindowTitle("Add Fixed Deposit" if mode=="add" else "Edit Fixed Deposit")
        self.setMinimumWidth(500)
        self._build_ui()
        if mode == "edit" and fd_id:
            self._load_fd()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        title = QLabel("Fixed Deposit Details")
        title.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        helper = QLabel("Enter FD inputs below. Scroll for advanced fields and bulk-create options.")
        helper.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(helper)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        form_container = QWidget()
        form_container_layout = QVBoxLayout(form_container)
        form_container_layout.setContentsMargins(0, 0, 0, 0)
        form_container_layout.setSpacing(12)

        form = QFormLayout(); form.setSpacing(12)

        self.person_combo = QComboBox()
        for p in get_all_persons():
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        form.addRow("Person:", self.person_combo)

        self.account_combo = QComboBox()
        form.addRow("Bank Account:", self.account_combo)
        self._on_person_changed()

        self.principal_input = QLineEdit(); self.principal_input.setPlaceholderText("e.g. 100000")
        self.principal_input.setValidator(QDoubleValidator(0.01, 99_999_999.99, 2, self.principal_input))
        self.principal_input.textChanged.connect(self._calc)
        form.addRow("Principal (₹):", self.principal_input)

        self.fd_no_input = QLineEdit(); self.fd_no_input.setPlaceholderText("FD/TD unique number")
        form.addRow("FD No / TD No:", self.fd_no_input)

        self.rate_input = QLineEdit(); self.rate_input.setPlaceholderText("e.g. 7.5")
        self.rate_input.setValidator(QDoubleValidator(0.01, 100.0, 2, self.rate_input))
        self.rate_input.textChanged.connect(self._calc)
        form.addRow("Interest Rate (%):", self.rate_input)

        tenure_row = QHBoxLayout()
        self.tenure_years_input = QLineEdit(); self.tenure_years_input.setPlaceholderText("Years")
        self.tenure_years_input.textChanged.connect(self._calc)
        tenure_row.addWidget(self.tenure_years_input)
        self.tenure_months_input = QLineEdit(); self.tenure_months_input.setPlaceholderText("Months")
        self.tenure_months_input.textChanged.connect(self._calc)
        tenure_row.addWidget(self.tenure_months_input)
        self.tenure_days_input = QLineEdit(); self.tenure_days_input.setPlaceholderText("Days")
        self.tenure_days_input.textChanged.connect(self._calc)
        tenure_row.addWidget(self.tenure_days_input)
        form.addRow("Tenure (Y/M/D):", tenure_row)

        self.compounding_combo = QComboBox()
        self.compounding_combo.addItems(COMPOUNDING_TYPES)
        self.compounding_combo.currentTextChanged.connect(self._calc)
        form.addRow("Compounding:", self.compounding_combo)

        self.amount_method_combo = QComboBox()
        self.amount_method_combo.addItem("Current Formula", userData="Formula")
        self.amount_method_combo.addItem("Bank-style Daily (Leap-aware)", userData="BankStyle")
        self.amount_method_combo.currentIndexChanged.connect(self._calc)
        form.addRow("Use Amount For FY/Tax:", self.amount_method_combo)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.dateChanged.connect(self._calc)
        form.addRow("Start Date:", self.start_date)

        # Calculated outputs
        self.maturity_date_lbl = QLabel("—")
        self.maturity_date_lbl.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        form.addRow("Maturity Date:", self.maturity_date_lbl)

        self.maturity_amount_formula_lbl = QLabel("—")
        self.maturity_amount_formula_lbl.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        form.addRow("Maturity (Current Formula):", self.maturity_amount_formula_lbl)

        self.maturity_amount_bank_lbl = QLabel("—")
        self.maturity_amount_bank_lbl.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        form.addRow("Maturity (Bank-style Daily):", self.maturity_amount_bank_lbl)

        self.maturity_amount_lbl = QLabel("—")
        self.maturity_amount_lbl.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {Theme.SUCCESS};")
        form.addRow("Selected Maturity Amount:", self.maturity_amount_lbl)

        self.expected_interest_input = QLineEdit(); self.expected_interest_input.setPlaceholderText("Auto = Maturity - Principal")
        form.addRow("Expected Interest (₹):", self.expected_interest_input)

        self.actual_interest_input = QLineEdit(); self.actual_interest_input.setPlaceholderText("Optional")
        form.addRow("Actual Interest (₹):", self.actual_interest_input)

        self.fd_count_spin = QSpinBox()
        self.fd_count_spin.setRange(1, 25)
        self.fd_count_spin.setValue(1)
        form.addRow("No. of FDs:", self.fd_count_spin)

        self.fd_numbers_input = QLineEdit()
        self.fd_numbers_input.setPlaceholderText("Comma-separated FD Nos when count > 1")
        form.addRow("FD Nos (Bulk):", self.fd_numbers_input)

        form_container_layout.addLayout(form)
        scroll.setWidget(form_container)
        layout.addWidget(scroll, 1)

        btns = QHBoxLayout(); btns.addStretch()
        btn_show = Theme.btn("Show Calculations", "secondary", height=36, min_width=130)
        btn_show.clicked.connect(self._on_show_calculations)
        btns.addWidget(btn_show)
        btn_cancel = Theme.btn("Cancel", "secondary", height=36, min_width=95)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btn_save = Theme.btn("Save FD", "primary", height=36, min_width=100)
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _on_person_changed(self):
        pid = self.person_combo.currentData()
        self.account_combo.clear()
        for acc in get_accounts_for_person(pid):
            self.account_combo.addItem(f"{acc.get('bank_display_name', acc['bank_name'])} ({acc['account_type']})", userData=acc["account_id"])

    def _calc(self):
        try:
            p = float(self.principal_input.text() or 0)
            r = float(self.rate_input.text() or 0)
            y = int(self.tenure_years_input.text() or 0)
            m = int(self.tenure_months_input.text() or 0)
            d = int(self.tenure_days_input.text() or 0)
            c = self.compounding_combo.currentText()
            s = self.start_date.date().toPyDate()
            if p > 0 and r > 0 and (y > 0 or m > 0 or d > 0):
                mat_date = calculate_fd_maturity_date(s, y, m, d)
                mat_formula = calculate_fd_maturity_flexible(p, r, s, mat_date, c, y, m, d)
                mat_bank = calculate_fd_maturity_bank_style(
                    p, r, s, mat_date, c,
                    y, m, d,
                )
                method = self.amount_method_combo.currentData()
                selected = mat_bank if method == "BankStyle" else mat_formula
                self.maturity_date_lbl.setText(mat_date.strftime("%d/%m/%y"))
                self.maturity_amount_formula_lbl.setText(f"₹ {mat_formula:,.2f}")
                self.maturity_amount_bank_lbl.setText(f"₹ {mat_bank:,.2f}")
                self.maturity_amount_lbl.setText(f"₹ {selected:,.2f}")
            else:
                self.maturity_date_lbl.setText("—")
                self.maturity_amount_formula_lbl.setText("—")
                self.maturity_amount_bank_lbl.setText("—")
                self.maturity_amount_lbl.setText("—")
        except (ValueError, Exception):
            self.maturity_date_lbl.setText("—")
            self.maturity_amount_formula_lbl.setText("—")
            self.maturity_amount_bank_lbl.setText("—")
            self.maturity_amount_lbl.setText("—")

    def _next_financial_year(self, fy: str) -> str:
        start = int(fy.split("-")[0]) + 1
        return f"{start}-{str(start + 1)[2:]}"

    def _input_snapshot(self) -> dict | None:
        try:
            principal = float(self.principal_input.text() or 0)
            rate = float(self.rate_input.text() or 0)
            tenure_years = int(self.tenure_years_input.text() or 0)
            tenure_months = int(self.tenure_months_input.text() or 0)
            tenure_days = int(self.tenure_days_input.text() or 0)
            compounding = self.compounding_combo.currentText()
            method = self.amount_method_combo.currentData() or "Formula"
            start = self.start_date.date().toPyDate()

            if principal <= 0 or rate <= 0:
                return None
            if tenure_years <= 0 and tenure_months <= 0 and tenure_days <= 0:
                return None

            maturity_date = calculate_fd_maturity_date(start, tenure_years, tenure_months, tenure_days)
            maturity_formula = calculate_fd_maturity_flexible(
                principal, rate, start, maturity_date, compounding,
                tenure_years, tenure_months, tenure_days
            )
            maturity_bank = calculate_fd_maturity_bank_style(
                principal, rate, start, maturity_date, compounding,
                tenure_years, tenure_months, tenure_days
            )
            maturity_selected = maturity_bank if method == "BankStyle" else maturity_formula

            if not (self.expected_interest_input.text() or "").strip():
                self.expected_interest_input.setText(f"{(maturity_selected - principal):.2f}")

            return {
                "principal": principal,
                "rate": rate,
                "tenure_years": tenure_years,
                "tenure_months": tenure_months,
                "tenure_days": tenure_days,
                "compounding": compounding,
                "method": method,
                "start": start,
                "maturity_date": maturity_date,
                "maturity_formula": maturity_formula,
                "maturity_bank": maturity_bank,
                "maturity_selected": maturity_selected,
            }
        except (ValueError, Exception):
            return None

    def _fy_interest_from_snapshot(self, snap: dict, financial_year: str) -> tuple[float, int]:
        fy_start, fy_end = fy_date_range(financial_year)
        overlap_start = max(snap["start"], fy_start)
        overlap_end = min(snap["maturity_date"], fy_end)
        if overlap_start > overlap_end:
            return 0.0, 0

        overlap_days = (overlap_end - overlap_start).days + 1
        total_days = (snap["maturity_date"] - snap["start"]).days + 1
        total_interest = snap["maturity_selected"] - snap["principal"]
        fy_interest = (total_interest * overlap_days) / total_days
        return round(fy_interest, 2), overlap_days

    def _quarter_rows_from_snapshot(self, snap: dict) -> list[dict]:
        total_interest = snap["maturity_selected"] - snap["principal"]
        rows = calculate_fd_quarterly_credit_breakdown(
            principal=float(snap["principal"]),
            rate=float(snap["rate"]),
            start_date=snap["start"],
            maturity_date=snap["maturity_date"],
            compounding=snap["compounding"],
            total_interest=float(total_interest),
        )
        return [{
            **r,
            "period": f"{r['period_start']} to {r['period_end']}",
        } for r in rows]

    def _build_report_text(self, snap: dict) -> str:
        method_text = "Bank-style Daily (Leap-aware)" if snap["method"] == "BankStyle" else "Current Formula"
        total_interest = snap["maturity_selected"] - snap["principal"]

        quarter_rows = self._quarter_rows_from_snapshot(snap)

        lines = [
            "FD Calculation Report",
            "=" * 70,
            f"Principal:            Rs {snap['principal']:,.2f}",
            f"Rate:                 {snap['rate']:.2f}%",
            f"Compounding:          {snap['compounding']}",
            f"Start Date:           {snap['start'].strftime('%d/%m/%y')}",
            f"Maturity Date:        {snap['maturity_date'].strftime('%d/%m/%y')}",
            f"Tenure Input:         {snap['tenure_years']}y {snap['tenure_months']}m {snap['tenure_days']}d",
            "",
            "Method-wise Maturity",
            "-" * 70,
            f"Current Formula:      Rs {snap['maturity_formula']:,.2f}",
            f"Bank-style Daily:     Rs {snap['maturity_bank']:,.2f}",
            f"Selected Method:      {method_text}",
            f"Selected Maturity:    Rs {snap['maturity_selected']:,.2f}",
            f"Selected Interest:    Rs {total_interest:,.2f}",
            "",
            "Quarter-wise Interest Allocation (Selected Method)",
            "-" * 70,
            "FY         AY         Quarter  Days  Interest",
        ]

        current_fy = get_current_financial_year()
        next_fy = self._next_financial_year(current_fy)
        current_fy_interest = 0.0
        next_fy_interest = 0.0

        for row in quarter_rows:
            lines.append(f"{row['fy']:<10} {row['ay']:<10} {row['quarter']:<8} {row['days']:<5} Rs {row['interest']:,.2f}")
            if row["fy"] == current_fy:
                current_fy_interest += row["interest"]
            if row["fy"] == next_fy:
                next_fy_interest += row["interest"]

        lines.extend([
            "",
            f"Current FY ({current_fy}) Interest: Rs {current_fy_interest:,.2f}",
            f"Next FY ({next_fy}) Interest:    Rs {next_fy_interest:,.2f}",
        ])

        return "\n".join(lines)

    def _on_show_calculations(self):
        snap = self._input_snapshot()
        if not snap:
            show_warning(
                "Enter valid Principal, Rate, and at least one tenure value (Years/Months/Days)."
            )
            return

        report = self._build_report_text(snap)
        quarter_rows = self._quarter_rows_from_snapshot(snap)

        dlg = QDialog(self)
        dlg.setWindowTitle("FD Calculation Details")
        dlg.setMinimumSize(860, 620)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 14, 16, 12)
        v.setSpacing(10)

        title = QLabel("Detailed FD Calculation")
        title.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY}; font-size: 14px;")
        v.addWidget(title)

        summary = QLabel(
            f"Selected Maturity: ₹ {snap['maturity_selected']:,.2f}   |   "
            f"Selected Interest: ₹ {snap['maturity_selected'] - snap['principal']:,.2f}"
        )
        summary.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-weight: 600;")
        v.addWidget(summary)

        q_title = QLabel("Quarter-wise Interest")
        q_title.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        v.addWidget(q_title)

        q_table = QTableWidget()
        q_table.setColumnCount(6)
        q_table.setHorizontalHeaderLabels(["FY", "AY", "Quarter", "Period", "Days", "Interest"])
        q_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate([90, 90, 70, 240, 70, 120]):
            q_table.setColumnWidth(i, w)
        q_table.setRowCount(len(quarter_rows))
        for i, row in enumerate(quarter_rows):
            q_table.setItem(i, 0, QTableWidgetItem(row["fy"]))
            q_table.setItem(i, 1, QTableWidgetItem(row["ay"]))
            q_table.setItem(i, 2, QTableWidgetItem(row["quarter"]))
            q_table.setItem(i, 3, QTableWidgetItem(row["period"]))
            q_table.setItem(i, 4, QTableWidgetItem(str(row["days"])))
            q_table.setItem(i, 5, QTableWidgetItem(f"₹ {row['interest']:,.2f}"))
            q_table.setRowHeight(i, 28)
        q_table.setMinimumHeight(220)
        q_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        q_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        v.addWidget(q_table)

        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(report)
        txt.setMaximumHeight(210)
        v.addWidget(txt)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = Theme.btn("Close", "primary", height=36, min_width=95)
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        v.addLayout(btn_row)

        dlg.exec()

    def _load_fd(self):
        self.fd_data = get_fd(self.fd_id)
        if not self.fd_data: return
        for i in range(self.person_combo.count()):
            if self.person_combo.itemData(i) == self.fd_data["person_id"]:
                self.person_combo.setCurrentIndex(i); break
        for i in range(self.account_combo.count()):
            if self.account_combo.itemData(i) == self.fd_data["account_id"]:
                self.account_combo.setCurrentIndex(i); break
        self.principal_input.setText(str(self.fd_data["principal_amount"]))
        self.fd_no_input.setText(self.fd_data.get("fd_reference_no") or "")
        self.rate_input.setText("" if self.fd_data.get("interest_rate") is None else str(self.fd_data["interest_rate"]))
        years = self.fd_data.get("tenure_years")
        months = self.fd_data.get("tenure_months")
        days = self.fd_data.get("tenure_days")
        self.tenure_years_input.setText("" if years in (None, 0) else str(years))
        self.tenure_months_input.setText("" if months in (None, 0) else str(months))
        self.tenure_days_input.setText("" if days in (None, 0) else str(days))
        self.compounding_combo.setCurrentText(self.fd_data.get("compounding_type") or "Quarterly")
        method = self.fd_data.get("maturity_calc_method") or "Formula"
        idx = self.amount_method_combo.findData(method)
        self.amount_method_combo.setCurrentIndex(idx if idx >= 0 else 0)
        exp_i = self.fd_data.get("expected_interest_amount")
        act_i = self.fd_data.get("actual_interest_amount")
        self.expected_interest_input.setText("" if exp_i in (None, 0) else str(exp_i))
        self.actual_interest_input.setText("" if act_i in (None, 0) else str(act_i))
        self.fd_count_spin.setValue(1)
        self.fd_count_spin.setEnabled(False)
        self.fd_numbers_input.setEnabled(False)
        s = date.fromisoformat(self.fd_data["start_date"])
        self.start_date.setDate(QDate(s.year, s.month, s.day))
        self._calc()

    def _on_save(self):
        try:
            account_id = self.account_combo.currentData()
            person_id  = self.person_combo.currentData()
            principal  = float(self.principal_input.text())
            rate       = float(self.rate_input.text())
            tenure_years  = int(self.tenure_years_input.text() or 0)
            tenure_months = int(self.tenure_months_input.text() or 0)
            tenure_days   = int(self.tenure_days_input.text() or 0)
            compounding= self.compounding_combo.currentText()
            start      = self.start_date.date().toPyDate()
            fd_ref_no = (self.fd_no_input.text() or "").strip() or None
            expected_interest = float(self.expected_interest_input.text()) if (self.expected_interest_input.text() or "").strip() else None
            actual_interest = float(self.actual_interest_input.text()) if (self.actual_interest_input.text() or "").strip() else None
            if not account_id or principal<=0 or rate<=0 or rate>100 or (tenure_years<=0 and tenure_months<=0 and tenure_days<=0):
                show_warning("Please fill all fields correctly (interest rate must be between 0 and 100)."); return
            mat_date = calculate_fd_maturity_date(start, tenure_years, tenure_months, tenure_days)
            mat_formula = calculate_fd_maturity_flexible(
                principal, rate, start, mat_date, compounding,
                tenure_years, tenure_months, tenure_days
            )
            mat_bank = calculate_fd_maturity_bank_style(
                principal, rate, start, mat_date, compounding,
                tenure_years, tenure_months, tenure_days,
            )
            method = self.amount_method_combo.currentData() or "Formula"
            mat_amt = mat_bank if method == "BankStyle" else mat_formula
            if expected_interest is None:
                expected_interest = round(mat_amt - principal, 2)
            if self.mode == "add":
                fd_count = int(self.fd_count_spin.value())
                fd_numbers = [n.strip() for n in (self.fd_numbers_input.text() or "").split(",") if n.strip()]
                if fd_count > 1 and fd_numbers and len(fd_numbers) != fd_count:
                    show_warning("For bulk create, provide exactly one FD no per record.")
                    return

                if fd_count > 1 and not fd_numbers:
                    show_warning("For bulk create, provide comma-separated unique FD numbers.")
                    return

                created = 0
                for i in range(fd_count):
                    ref = fd_ref_no
                    if fd_numbers:
                        ref = fd_numbers[i]
                    fd_id = add_fd(
                        account_id, person_id, principal, start.isoformat(),
                        tenure_months, rate, compounding, mat_date.isoformat(), mat_amt,
                        mat_formula, mat_bank, method,
                        tenure_years, tenure_days,
                        ref,
                        expected_interest,
                        actual_interest,
                    )
                    allocate_fd_interest_to_fy(fd_id)
                    created += 1
                show_success(f"{created} Fixed Deposit record(s) added!")
            else:
                update_fd(self.fd_id, principal, start.isoformat(), tenure_months, rate,
                          compounding, mat_date.isoformat(), mat_amt, "Active",
                          mat_formula, mat_bank, method,
                          tenure_years, tenure_days,
                          fd_ref_no,
                          expected_interest,
                          actual_interest,
                          self.fd_data.get("linked_transaction_id"),
                          self.fd_data.get("source_statement_file"),
                          self.fd_data.get("source_transaction_id"))
                allocate_fd_interest_to_fy(self.fd_id)
                show_success("Fixed Deposit updated!")
            self.accept()
        except ValueError:
            show_warning("Please enter valid numeric values.")
        except Exception as e:
            show_warning(f"Failed to save the fixed deposit: {e}")
