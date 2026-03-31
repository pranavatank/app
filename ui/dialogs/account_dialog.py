"""
ui/dialogs/account_dialog.py — Bank account management dialog with clean styling.
FIX: All buttons now have explicit inline styles (no objectName dependency in QDialog).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QMessageBox, QComboBox, QDoubleSpinBox,
    QCheckBox, QDateEdit, QTextEdit, QTabWidget, QWidget, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ui.theme import Theme
from config import ACCOUNT_TYPES
from models.person import get_all_persons
from models.bank_account import add_account, get_all_accounts, update_account, delete_account


def _btn(text: str, style: str = "primary") -> QPushButton:
    b = QPushButton(text)
    if style == "secondary":
        b.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                border: 1.5px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: {Theme.PRIMARY_LIGHT};
                border-color: {Theme.PRIMARY};
                color: {Theme.PRIMARY_DARK};
            }}
        """)
    elif style == "danger":
        b.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.DANGER},stop:1 {Theme.DANGER_DARK});
                color: white; border: none; border-radius: 8px;
                padding: 8px 18px; font-size: 13px; font-weight: 700; min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {Theme.DANGER_DARK}; }}
        """)
    else:  # primary
        b.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.PRIMARY},stop:1 {Theme.PRIMARY_DARK});
                color: white; border: none; border-radius: 8px;
                padding: 8px 18px; font-size: 13px; font-weight: 700; min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {Theme.PRIMARY_DARK}; }}
        """)
    return b


class AccountManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Bank Accounts")
        self.setMinimumSize(950, 540)
        self._build_ui()
        self._load_accounts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        header = QHBoxLayout()
        title = QLabel("Bank Accounts")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        btn_add = _btn("＋  Add Account", "primary")
        btn_add.clicked.connect(self._on_add)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Person", "Bank Name", "Type", "Account No.", "IFSC",
            "Opening Balance", "Current Balance", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(7, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        actions = QHBoxLayout(); actions.addStretch()
        btn_edit = _btn("✏  Edit", "secondary")
        btn_edit.clicked.connect(self._on_edit)
        actions.addWidget(btn_edit)
        btn_del = _btn("🗑  Delete", "danger")
        btn_del.clicked.connect(self._on_delete)
        actions.addWidget(btn_del)
        btn_close = _btn("Close", "secondary")
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)

    def _load_accounts(self):
        self.table.setRowCount(0)
        for acc in get_all_accounts():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(acc.get("person_name","—")))
            self.table.setItem(r, 1, QTableWidgetItem(acc["bank_name"]))
            self.table.setItem(r, 2, QTableWidgetItem(acc["account_type"]))
            self.table.setItem(r, 3, QTableWidgetItem(acc.get("account_number_masked") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(acc.get("ifsc_code") or "—"))
            self.table.setItem(r, 5, QTableWidgetItem(f"₹ {acc['opening_balance']:,.2f}"))
            self.table.setItem(r, 6, QTableWidgetItem(f"₹ {acc['current_balance']:,.2f}"))
            self.table.setItem(r, 7, QTableWidgetItem(str(acc["account_id"])))
            self.table.setRowHeight(r, 32)

    def _on_add(self):
        persons = get_all_persons()
        if not persons:
            QMessageBox.warning(self, "No Persons", "Add a family member first."); return
        dlg = AccountDialog(self, persons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            add_account(**dlg.get_data())
            self._load_accounts()

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select an account."); return
        aid = int(self.table.item(row, 7).text())
        accounts = get_all_accounts()
        acc_data = next((a for a in accounts if a["account_id"] == aid), None)
        if not acc_data: return
        dlg = AccountDialog(self, get_all_persons(), acc_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            update_account(aid, **dlg.get_data())
            self._load_accounts()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select an account."); return
        aid  = int(self.table.item(row, 7).text())
        name = self.table.item(row, 1).text()
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete account '{name}'?\n\nAll transactions for this account will also be deleted!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_account(aid)
            self._load_accounts()


class AccountDialog(QDialog):
    def __init__(self, parent=None, persons=None, account_data=None):
        super().__init__(parent)
        self.persons = persons or []
        self.account_data = account_data
        self.setWindowTitle("Edit Account" if account_data else "Add Account")
        self.setMinimumSize(660, 580)
        self._build_ui()
        if account_data:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 18)

        tabs = QTabWidget()
        tabs.addTab(self._basic_tab(),   "📋 Basic Info")
        tabs.addTab(self._bank_tab(),    "🏦 Bank Details")
        tabs.addTab(self._contact_tab(), "📞 Contact")
        tabs.addTab(self._card_tab(),    "💳 Debit Card")
        layout.addWidget(tabs)

        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {Theme.BORDER};")
        layout.addWidget(div)

        btns = QHBoxLayout(); btns.addStretch()
        btn_cancel = _btn("Cancel", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btn_save = _btn("Save Account", "primary")
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _form_widget(self) -> tuple[QWidget, QFormLayout]:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(12)
        f.setContentsMargins(16, 16, 16, 16)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        return w, f

    def _spin(self, prefix="₹ ", min_val=0, max_val=99_999_999.99) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(min_val, max_val)
        s.setDecimals(2)
        s.setGroupSeparatorShown(True)
        s.setPrefix(prefix)
        s.setFixedHeight(40)
        return s

    def _combo(self, items: list) -> QComboBox:
        c = QComboBox(); c.addItems(items); c.setFixedHeight(40); return c

    def _field(self, placeholder="") -> QLineEdit:
        e = QLineEdit(); e.setPlaceholderText(placeholder); e.setFixedHeight(40); return e

    def _basic_tab(self) -> QWidget:
        w, f = self._form_widget()

        self.person_combo = QComboBox()
        self.person_combo.setFixedHeight(40)
        for p in self.persons:
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])
        f.addRow("Person *:", self.person_combo)

        self.bank_input = self._field("e.g. HDFC Bank")
        f.addRow("Bank Name *:", self.bank_input)

        self.type_combo = self._combo(ACCOUNT_TYPES)
        f.addRow("Account Type *:", self.type_combo)

        self.account_no_input = self._field("e.g. XXXX1234")
        f.addRow("Account No. (masked):", self.account_no_input)

        self.customer_id_input = self._field()
        f.addRow("Customer ID:", self.customer_id_input)

        self.opening_date = QDateEdit()
        self.opening_date.setCalendarPopup(True)
        self.opening_date.setDate(QDate.currentDate())
        self.opening_date.setDisplayFormat("yyyy-MM-dd")
        self.opening_date.setFixedHeight(40)
        f.addRow("Opening Date:", self.opening_date)

        self.status_combo = self._combo(["Active","Inactive","Closed"])
        f.addRow("Status:", self.status_combo)

        self.opening_balance = self._spin()
        f.addRow("Opening Balance:", self.opening_balance)

        self.interest_rate = QDoubleSpinBox()
        self.interest_rate.setRange(0, 100); self.interest_rate.setDecimals(2)
        self.interest_rate.setSuffix(" %"); self.interest_rate.setValue(3.5)
        self.interest_rate.setFixedHeight(40)
        f.addRow("Interest Rate:", self.interest_rate)

        return w

    def _bank_tab(self) -> QWidget:
        w, f = self._form_widget()

        self.ifsc_input = self._field("e.g. HDFC0001234")
        self.ifsc_input.setMaxLength(11)
        f.addRow("IFSC Code:", self.ifsc_input)

        self.micr_input = self._field("e.g. 360240001")
        self.micr_input.setMaxLength(9)
        f.addRow("MICR Code:", self.micr_input)

        self.branch_name_input = self._field()
        f.addRow("Branch Name:", self.branch_name_input)

        self.branch_address_input = QTextEdit()
        self.branch_address_input.setMaximumHeight(80)
        f.addRow("Branch Address:", self.branch_address_input)

        return w

    def _contact_tab(self) -> QWidget:
        w, f = self._form_widget()

        self.email_input = self._field("email@example.com")
        f.addRow("Email ID:", self.email_input)

        self.phone_input = self._field("e.g. 9876543210")
        f.addRow("Phone No:", self.phone_input)

        self.comm_address_input = QTextEdit()
        self.comm_address_input.setMaximumHeight(80)
        f.addRow("Communication Address:", self.comm_address_input)

        self.nomination_combo = self._combo(["","Registered","Not Registered"])
        f.addRow("Nomination Status:", self.nomination_combo)

        self.nominee_input = self._field()
        f.addRow("Nominee Name:", self.nominee_input)

        return w

    def _card_tab(self) -> QWidget:
        w, f = self._form_widget()

        self.debit_card_check = QCheckBox("Debit Card Enabled")
        self.debit_card_check.toggled.connect(self._on_card_toggled)
        f.addRow("", self.debit_card_check)

        self.debit_charges = self._spin()
        self.debit_charges.setEnabled(False)
        f.addRow("Annual Charges:", self.debit_charges)

        self.debit_effective = QDateEdit()
        self.debit_effective.setCalendarPopup(True)
        self.debit_effective.setDate(QDate.currentDate())
        self.debit_effective.setDisplayFormat("yyyy-MM-dd")
        self.debit_effective.setFixedHeight(40)
        self.debit_effective.setEnabled(False)
        f.addRow("Effective From:", self.debit_effective)

        return w

    def _on_card_toggled(self, checked):
        self.debit_charges.setEnabled(checked)
        self.debit_effective.setEnabled(checked)

    def _load_data(self):
        d = self.account_data
        for i in range(self.person_combo.count()):
            if self.person_combo.itemData(i) == d.get("person_id"):
                self.person_combo.setCurrentIndex(i); break
        self.bank_input.setText(d.get("bank_name",""))
        self.type_combo.setCurrentText(d.get("account_type","Savings"))
        self.account_no_input.setText(d.get("account_number_masked") or "")
        self.customer_id_input.setText(d.get("customer_id") or "")
        if d.get("account_opening_date"):
            qd = QDate.fromString(d["account_opening_date"],"yyyy-MM-dd")
            if qd.isValid(): self.opening_date.setDate(qd)
        self.status_combo.setCurrentText(d.get("account_status","Active"))
        self.opening_balance.setValue(d.get("opening_balance",0.0))
        self.interest_rate.setValue(d.get("interest_rate",3.5))
        self.ifsc_input.setText(d.get("ifsc_code") or "")
        self.micr_input.setText(d.get("micr_code") or "")
        self.branch_name_input.setText(d.get("branch_name") or "")
        self.branch_address_input.setPlainText(d.get("branch_address") or "")
        self.email_input.setText(d.get("email_id") or "")
        self.phone_input.setText(d.get("phone_no") or "")
        self.comm_address_input.setPlainText(d.get("communication_address") or "")
        self.nomination_combo.setCurrentText(d.get("nomination_status") or "")
        self.nominee_input.setText(d.get("nominee_name") or "")
        self.debit_card_check.setChecked(bool(d.get("debit_card_enabled",0)))
        self.debit_charges.setValue(d.get("debit_card_charges",0.0))
        if d.get("debit_card_effective_from"):
            qd = QDate.fromString(d["debit_card_effective_from"],"yyyy-MM-dd")
            if qd.isValid(): self.debit_effective.setDate(qd)

    def _on_save(self):
        if not self.bank_input.text().strip():
            QMessageBox.warning(self,"Missing","Please enter a bank name."); return
        self.accept()

    def get_data(self) -> dict:
        return {
            "person_id":               self.person_combo.currentData(),
            "bank_name":               self.bank_input.text().strip(),
            "account_type":            self.type_combo.currentText(),
            "account_number_masked":   self.account_no_input.text().strip() or None,
            "customer_id":             self.customer_id_input.text().strip() or None,
            "account_opening_date":    self.opening_date.date().toString("yyyy-MM-dd"),
            "account_status":          self.status_combo.currentText(),
            "opening_balance":         self.opening_balance.value(),
            "interest_rate":           self.interest_rate.value(),
            "ifsc_code":               self.ifsc_input.text().strip() or None,
            "micr_code":               self.micr_input.text().strip() or None,
            "branch_name":             self.branch_name_input.text().strip() or None,
            "branch_address":          self.branch_address_input.toPlainText().strip() or None,
            "email_id":                self.email_input.text().strip() or None,
            "phone_no":                self.phone_input.text().strip() or None,
            "communication_address":   self.comm_address_input.toPlainText().strip() or None,
            "nomination_status":       self.nomination_combo.currentText() or None,
            "nominee_name":            self.nominee_input.text().strip() or None,
            "debit_card_enabled":      1 if self.debit_card_check.isChecked() else 0,
            "debit_card_charges":      self.debit_charges.value() if self.debit_card_check.isChecked() else 0.0,
            "debit_card_effective_from": self.debit_effective.date().toString("yyyy-MM-dd") if self.debit_card_check.isChecked() else None,
        }
