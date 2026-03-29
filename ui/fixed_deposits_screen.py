"""
ui/fixed_deposits_screen.py — FD management screen with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QComboBox, QDateEdit, QMessageBox, QFrame,
    QPlainTextEdit, QSpinBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from datetime import date
from dateutil.relativedelta import relativedelta

from ui.theme import Theme
from core.session import session
from config import COMPOUNDING_TYPES, fy_date_range, get_assessment_year, get_current_financial_year
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person
from models.fixed_deposit import (
    add_fd,
    get_all_fds,
    update_fd,
    delete_fd,
    get_fd_link_candidates,
    link_fd_transaction,
    unlink_fd_transaction,
    auto_link_fd_records,
)
from engines.interest_engine import (
    calculate_fd_maturity,
    calculate_fd_maturity_bank_style,
    calculate_fd_maturity_date,
    calculate_fd_maturity_flexible,
    allocate_fd_interest_to_fy,
)


class FixedDepositsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Fixed Deposits")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("＋  Add FD")
        btn_add.setObjectName("primaryBtn"); btn_add.setFixedHeight(38)
        btn_add.clicked.connect(self._on_add_fd)
        header.addWidget(btn_add)

        btn_del = QPushButton("🗑  Delete Selected")
        btn_del.setObjectName("dangerBtn"); btn_del.setFixedHeight(38)
        btn_del.clicked.connect(self._on_delete_fd)
        header.addWidget(btn_del)

        btn_link = QPushButton("🔗  Link Txn")
        btn_link.setObjectName("successBtn"); btn_link.setFixedHeight(38)
        btn_link.clicked.connect(self._on_link_fd_transaction)
        header.addWidget(btn_link)

        btn_auto = QPushButton("⚡  Auto-Link")
        btn_auto.setObjectName("successBtn"); btn_auto.setFixedHeight(38)
        btn_auto.clicked.connect(self._on_auto_link)
        header.addWidget(btn_auto)

        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(14)
        self.table.setHorizontalHeaderLabels([
            "Person", "Bank", "FD No", "Principal", "Rate %", "Tenure",
            "Compounding", "Start Date", "Maturity Date", "Maturity Amount",
            "Expected Interest", "Actual Interest", "Method", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self._on_edit_fd)
        for i, w in enumerate([110,120,110,110,70,90,100,100,110,130,130,120,110,85]):
            self.table.setColumnWidth(i, w)
        layout.addWidget(self.table)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        layout.addWidget(self.status_label)

    def refresh(self):
        fds = get_all_fds(person_id=session.selected_person_id)
        self.table.setRowCount(0)

        status_colors = {
            "Active":  QColor(Theme.SUCCESS),
            "Matured": QColor(Theme.WARNING),
            "Pending Details": QColor(Theme.INFO),
            "Closed":  QColor(Theme.TEXT_MUTED),
        }

        for fd in fds:
            r = self.table.rowCount()
            self.table.insertRow(r)

            def item(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text) if text is not None else "—")
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            self.table.setItem(r, 0, item(fd["person_name"]))
            self.table.setItem(r, 1, item(fd["bank_name"]))
            self.table.setItem(r, 2, item(fd.get("fd_reference_no") or "—"))
            self.table.setItem(r, 3, item(session.mask(fd["principal_amount"]),
                                          Qt.AlignmentFlag.AlignRight))
            rate = fd.get("interest_rate")
            rate_text = "—" if rate is None else f"{rate:.2f}%"
            self.table.setItem(r, 4, item(rate_text, Qt.AlignmentFlag.AlignRight))
            tenure_text = self._format_tenure(fd)
            self.table.setItem(r, 5, item(tenure_text))
            self.table.setItem(r, 6, item(fd.get("compounding_type") or "—"))
            self.table.setItem(r, 7, item(fd["start_date"]))
            self.table.setItem(r, 8, item(fd.get("maturity_date") or "—"))
            maturity_amount = fd.get("maturity_amount")
            maturity_text = "—" if maturity_amount is None else session.mask(maturity_amount)
            self.table.setItem(r, 9, item(maturity_text, Qt.AlignmentFlag.AlignRight))

            exp_i = fd.get("expected_interest_amount")
            exp_t = "—" if exp_i in (None, 0) else session.mask(exp_i)
            self.table.setItem(r, 10, item(exp_t, Qt.AlignmentFlag.AlignRight))

            act_i = fd.get("actual_interest_amount")
            act_t = "—" if act_i in (None, 0) else session.mask(act_i)
            self.table.setItem(r, 11, item(act_t, Qt.AlignmentFlag.AlignRight))

            method = fd.get("maturity_calc_method") or "Formula"
            method_text = "Bank-style" if method == "BankStyle" else "Formula"
            self.table.setItem(r, 12, item(method_text))

            status_item = item(fd["status"])
            status_item.setForeground(status_colors.get(fd["status"], QColor(Theme.TEXT_MUTED)))
            self.table.setItem(r, 13, status_item)

            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, fd["fd_id"])
            self.table.setRowHeight(r, 32)

        count = self.table.rowCount()
        self.status_label.setText(f"Showing {count} fixed deposit{'s' if count!=1 else ''}.")

    def _format_tenure(self, fd: dict) -> str:
        years = fd.get("tenure_years") or 0
        months = fd.get("tenure_months") or 0
        days = fd.get("tenure_days") or 0
        if years == 0 and months == 0 and days == 0:
            return "—"

        parts = []
        if years:
            parts.append(f"{years}y")
        if months:
            parts.append(f"{months}m")
        if days:
            parts.append(f"{days}d")
        return " ".join(parts)

    def _on_add_fd(self):
        if FDDialog(self, mode="add").exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            if self.parent_window: self.parent_window.refresh_overview()

    def _on_edit_fd(self):
        row = self.table.currentRow()
        if row < 0: return
        fd_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if FDDialog(self, mode="edit", fd_id=fd_id).exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            if self.parent_window: self.parent_window.refresh_overview()

    def _on_delete_fd(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an FD."); return
        fd_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Delete FD", "Delete this Fixed Deposit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_fd(fd_id)
            self.refresh()
            if self.parent_window: self.parent_window.refresh_overview()

    def _selected_fd_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an FD.")
            return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _on_link_fd_transaction(self):
        fd_id = self._selected_fd_id()
        if not fd_id:
            return

        dlg = LinkFDTransactionDialog(self, fd_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            txn_id = dlg.get_selected_transaction_id()
            if txn_id:
                link_fd_transaction(fd_id, txn_id)
                self.refresh()
                if self.parent_window:
                    self.parent_window.refresh_overview()

    def _on_auto_link(self):
        if not session.selected_person_id:
            QMessageBox.information(self, "Select Person", "Please select a person first.")
            return

        linked = auto_link_fd_records(session.selected_person_id, session.selected_fy)
        if linked > 0:
            QMessageBox.information(self, "Auto-Link Complete", f"Linked {linked} FD record(s) with account transactions.")
            self.refresh()
            if self.parent_window:
                self.parent_window.refresh_overview()
        else:
            QMessageBox.information(self, "No Matches", "No FD references were matched in account transactions.")


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
        self.principal_input.textChanged.connect(self._calc)
        form.addRow("Principal (₹):", self.principal_input)

        self.fd_no_input = QLineEdit(); self.fd_no_input.setPlaceholderText("FD/TD unique number")
        form.addRow("FD No / TD No:", self.fd_no_input)

        self.rate_input = QLineEdit(); self.rate_input.setPlaceholderText("e.g. 7.5")
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

        layout.addLayout(form)

        btns = QHBoxLayout(); btns.addStretch()
        btn_show = QPushButton("Show Calculations")
        btn_show.setObjectName("secondaryBtn"); btn_show.clicked.connect(self._on_show_calculations)
        btns.addWidget(btn_show)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondaryBtn"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btn_save = QPushButton("Save FD")
        btn_save.setObjectName("primaryBtn"); btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _on_person_changed(self):
        pid = self.person_combo.currentData()
        self.account_combo.clear()
        for acc in get_accounts_for_person(pid):
            self.account_combo.addItem(f"{acc['bank_name']} ({acc['account_type']})", userData=acc["account_id"])

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
                self.maturity_date_lbl.setText(mat_date.isoformat())
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

    def _build_report_text(self, snap: dict) -> str:
        method_text = "Bank-style Daily (Leap-aware)" if snap["method"] == "BankStyle" else "Current Formula"
        total_interest = snap["maturity_selected"] - snap["principal"]

        lines = [
            "FD Calculation Report",
            "=" * 70,
            f"Principal:            Rs {snap['principal']:,.2f}",
            f"Rate:                 {snap['rate']:.2f}%",
            f"Compounding:          {snap['compounding']}",
            f"Start Date:           {snap['start'].isoformat()}",
            f"Maturity Date:        {snap['maturity_date'].isoformat()}",
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
            "FY-wise Interest Allocation (Selected Method)",
            "-" * 70,
            "FY         AY         Days Overlap     Interest",
        ]

        cursor = snap["start"]
        seen = set()
        current_fy = get_current_financial_year()
        next_fy = self._next_financial_year(current_fy)
        current_fy_interest = 0.0
        next_fy_interest = 0.0

        while cursor <= snap["maturity_date"]:
            if cursor.month >= 4:
                fy = f"{cursor.year}-{str(cursor.year + 1)[2:]}"
            else:
                fy = f"{cursor.year - 1}-{str(cursor.year)[2:]}"

            if fy not in seen:
                seen.add(fy)
                ay = get_assessment_year(fy)
                interest, days = self._fy_interest_from_snapshot(snap, fy)
                lines.append(f"{fy:<10} {ay:<10} {days:<16} Rs {interest:,.2f}")
                if fy == current_fy:
                    current_fy_interest = interest
                if fy == next_fy:
                    next_fy_interest = interest

            cursor = date(cursor.year + 1, 4, 1) if cursor.month >= 4 else date(cursor.year, 4, 1)

        lines.extend([
            "",
            f"Current FY ({current_fy}) Interest: Rs {current_fy_interest:,.2f}",
            f"Next FY ({next_fy}) Interest:    Rs {next_fy_interest:,.2f}",
        ])

        return "\n".join(lines)

    def _on_show_calculations(self):
        snap = self._input_snapshot()
        if not snap:
            QMessageBox.warning(
                self,
                "Incomplete Input",
                "Enter valid Principal, Rate, and at least one tenure value (Years/Months/Days)."
            )
            return

        report = self._build_report_text(snap)

        dlg = QDialog(self)
        dlg.setWindowTitle("FD Calculation Details")
        dlg.setMinimumSize(760, 560)
        v = QVBoxLayout(dlg)

        title = QLabel("Detailed FD Calculation")
        title.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY}; font-size: 14px;")
        v.addWidget(title)

        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(report)
        v.addWidget(txt)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("primaryBtn")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        v.addLayout(btn_row)

        dlg.exec()

    def _load_fd(self):
        from models.fixed_deposit import get_fd
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
            if not account_id or principal<=0 or rate<=0 or (tenure_years<=0 and tenure_months<=0 and tenure_days<=0):
                QMessageBox.warning(self,"Invalid","Please fill all fields correctly."); return
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
                    QMessageBox.warning(self, "Invalid FD Nos", "For bulk create, provide exactly one FD no per record.")
                    return

                if fd_count > 1 and not fd_numbers:
                    QMessageBox.warning(self, "FD Nos Required", "For bulk create, provide comma-separated unique FD numbers.")
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
                QMessageBox.information(self, "Success", f"{created} Fixed Deposit record(s) added!")
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
                QMessageBox.information(self, "Success", "Fixed Deposit updated!")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric values.")


class LinkFDTransactionDialog(QDialog):
    def __init__(self, parent, fd_id: int):
        super().__init__(parent)
        self.fd_id = fd_id
        self._selected_txn_id = None
        self.setWindowTitle("Link Account Transaction")
        self.setMinimumSize(920, 520)
        self._build_ui()
        self._load_rows()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)

        title = QLabel("Fetch and link transaction from the same account")
        title.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Type", "Amount", "Category", "Mode", "Description", "Txn ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        for i, w in enumerate([95, 75, 110, 120, 95, 340, 70]):
            self.table.setColumnWidth(i, w)
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        btns.addStretch()

        btn_unlink = QPushButton("Unlink")
        btn_unlink.setObjectName("dangerBtn")
        btn_unlink.clicked.connect(self._on_unlink)
        btns.addWidget(btn_unlink)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondaryBtn")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_link = QPushButton("Link Selected")
        btn_link.setObjectName("primaryBtn")
        btn_link.clicked.connect(self._on_link)
        btns.addWidget(btn_link)

        layout.addLayout(btns)

    def _load_rows(self):
        rows = get_fd_link_candidates(self.fd_id)
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(row.get("transaction_date") or "—"))
            self.table.setItem(r, 1, QTableWidgetItem(row.get("transaction_type") or "—"))
            self.table.setItem(r, 2, QTableWidgetItem(f"₹ {float(row.get('amount') or 0):,.2f}"))
            self.table.setItem(r, 3, QTableWidgetItem(row.get("category") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(row.get("mode") or "—"))
            self.table.setItem(r, 5, QTableWidgetItem((row.get("description") or "")[:220]))
            self.table.setItem(r, 6, QTableWidgetItem(str(row.get("transaction_id"))))
            self.table.setRowHeight(r, 30)

    def _on_unlink(self):
        unlink_fd_transaction(self.fd_id)
        self._selected_txn_id = None
        self.accept()

    def _on_link(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to link.")
            return
        self._selected_txn_id = int(self.table.item(row, 6).text())
        self.accept()

    def get_selected_transaction_id(self):
        return self._selected_txn_id
