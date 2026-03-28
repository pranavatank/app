"""
ui/fixed_deposits_screen.py — FD management screen with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QComboBox, QDateEdit, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from datetime import date
from dateutil.relativedelta import relativedelta

from ui.theme import Theme
from core.session import session
from config import COMPOUNDING_TYPES
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person
from models.fixed_deposit import add_fd, get_all_fds, update_fd, delete_fd
from engines.interest_engine import calculate_fd_maturity, allocate_fd_interest_to_fy


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

        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Person","Bank","Principal","Rate %","Tenure",
            "Compounding","Start Date","Maturity Date","Maturity Amount","Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self._on_edit_fd)
        for i, w in enumerate([120,140,120,70,90,110,100,110,140,85]):
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
            self.table.setItem(r, 2, item(session.mask(fd["principal_amount"]),
                                          Qt.AlignmentFlag.AlignRight))
            rate = fd.get("interest_rate")
            rate_text = "—" if rate is None else f"{rate:.2f}%"
            self.table.setItem(r, 3, item(rate_text, Qt.AlignmentFlag.AlignRight))
            tenure = fd.get("tenure_months")
            tenure_text = "—" if tenure is None else f"{tenure} mo"
            self.table.setItem(r, 4, item(tenure_text))
            self.table.setItem(r, 5, item(fd.get("compounding_type") or "—"))
            self.table.setItem(r, 6, item(fd["start_date"]))
            self.table.setItem(r, 7, item(fd.get("maturity_date") or "—"))
            maturity_amount = fd.get("maturity_amount")
            maturity_text = "—" if maturity_amount is None else session.mask(maturity_amount)
            self.table.setItem(r, 8, item(maturity_text, Qt.AlignmentFlag.AlignRight))

            status_item = item(fd["status"])
            status_item.setForeground(status_colors.get(fd["status"], QColor(Theme.TEXT_MUTED)))
            self.table.setItem(r, 9, status_item)

            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, fd["fd_id"])
            self.table.setRowHeight(r, 32)

        count = self.table.rowCount()
        self.status_label.setText(f"Showing {count} fixed deposit{'s' if count!=1 else ''}.")

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

        self.rate_input = QLineEdit(); self.rate_input.setPlaceholderText("e.g. 7.5")
        self.rate_input.textChanged.connect(self._calc)
        form.addRow("Interest Rate (%):", self.rate_input)

        self.tenure_input = QLineEdit(); self.tenure_input.setPlaceholderText("e.g. 12")
        self.tenure_input.textChanged.connect(self._calc)
        form.addRow("Tenure (months):", self.tenure_input)

        self.compounding_combo = QComboBox()
        self.compounding_combo.addItems(COMPOUNDING_TYPES)
        self.compounding_combo.currentTextChanged.connect(self._calc)
        form.addRow("Compounding:", self.compounding_combo)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.dateChanged.connect(self._calc)
        form.addRow("Start Date:", self.start_date)

        # Calculated outputs
        self.maturity_date_lbl = QLabel("—")
        self.maturity_date_lbl.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        form.addRow("Maturity Date:", self.maturity_date_lbl)

        self.maturity_amount_lbl = QLabel("—")
        self.maturity_amount_lbl.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {Theme.SUCCESS};")
        form.addRow("Maturity Amount:", self.maturity_amount_lbl)

        layout.addLayout(form)

        btns = QHBoxLayout(); btns.addStretch()
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
            t = int(self.tenure_input.text() or 0)
            c = self.compounding_combo.currentText()
            s = self.start_date.date().toPyDate()
            if p > 0 and r > 0 and t > 0:
                mat_date = s + relativedelta(months=t)
                mat_amt  = calculate_fd_maturity(p, r, t, c)
                self.maturity_date_lbl.setText(mat_date.isoformat())
                self.maturity_amount_lbl.setText(f"₹ {mat_amt:,.2f}")
            else:
                self.maturity_date_lbl.setText("—")
                self.maturity_amount_lbl.setText("—")
        except (ValueError, Exception):
            self.maturity_date_lbl.setText("—")
            self.maturity_amount_lbl.setText("—")

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
        self.rate_input.setText("" if self.fd_data.get("interest_rate") is None else str(self.fd_data["interest_rate"]))
        self.tenure_input.setText("" if self.fd_data.get("tenure_months") is None else str(self.fd_data["tenure_months"]))
        self.compounding_combo.setCurrentText(self.fd_data.get("compounding_type") or "Quarterly")
        s = date.fromisoformat(self.fd_data["start_date"])
        self.start_date.setDate(QDate(s.year, s.month, s.day))

    def _on_save(self):
        try:
            account_id = self.account_combo.currentData()
            person_id  = self.person_combo.currentData()
            principal  = float(self.principal_input.text())
            rate       = float(self.rate_input.text())
            tenure     = int(self.tenure_input.text())
            compounding= self.compounding_combo.currentText()
            start      = self.start_date.date().toPyDate()
            if not account_id or principal<=0 or rate<=0 or tenure<=0:
                QMessageBox.warning(self,"Invalid","Please fill all fields correctly."); return
            mat_date = start + relativedelta(months=tenure)
            mat_amt  = calculate_fd_maturity(principal, rate, tenure, compounding)
            if self.mode == "add":
                fd_id = add_fd(account_id, person_id, principal, start.isoformat(),
                               tenure, rate, compounding, mat_date.isoformat(), mat_amt)
                allocate_fd_interest_to_fy(fd_id)
                QMessageBox.information(self, "Success", "Fixed Deposit added!")
            else:
                update_fd(self.fd_id, principal, start.isoformat(), tenure, rate,
                          compounding, mat_date.isoformat(), mat_amt, "Active")
                allocate_fd_interest_to_fy(self.fd_id)
                QMessageBox.information(self, "Success", "Fixed Deposit updated!")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric values.")
