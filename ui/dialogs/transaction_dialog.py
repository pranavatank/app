"""
ui/dialogs/transaction_dialog.py — Add/edit dialog for transactions.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit,
    QDateEdit, QDoubleSpinBox, QTextEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QDate

from ui.widgets.toast_utils import show_warning
from config import INCOME_CATEGORIES, EXPENSE_CATEGORIES, TRANSACTION_MODES
from models.transaction import (
    display_transaction_type, normalize_transaction_type
)


class TransactionDialog(QDialog):
    def __init__(self, parent=None, persons=None, accounts=None,
                 existing=None, preselect_person_id=None, preselect_account_id=None):
        super().__init__(parent)
        self._persons  = persons or []
        self._accounts = accounts or []
        self._existing = existing
        self._preselect_pid = preselect_person_id
        self._preselect_aid = preselect_account_id
        self.setWindowTitle("Edit Transaction" if existing else "Add Transaction")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build_ui()
        if existing: self._prefill(existing)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cmb_person = QComboBox()
        for p in self._persons:
            self.cmb_person.addItem(p["full_name"], userData=p["person_id"])
        self.cmb_person.currentIndexChanged.connect(self._on_person_changed)
        if self._preselect_pid:
            for i in range(self.cmb_person.count()):
                if self.cmb_person.itemData(i) == self._preselect_pid:
                    self.cmb_person.setCurrentIndex(i); break
        form.addRow("Person *", self.cmb_person)

        self.cmb_account = QComboBox()
        self._populate_accounts()
        if self._preselect_aid:
            for i in range(self.cmb_account.count()):
                if self.cmb_account.itemData(i) == self._preselect_aid:
                    self.cmb_account.setCurrentIndex(i); break
        form.addRow("Account *", self.cmb_account)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yy")
        form.addRow("Date *", self.date_edit)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Credit","Debit","Transfer"])
        self.cmb_type.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Type *", self.cmb_type)

        self.cmb_category = QComboBox()
        self._populate_categories("Credit")
        form.addRow("Category", self.cmb_category)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems([""]+TRANSACTION_MODES)
        form.addRow("Mode", self.cmb_mode)

        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("Optional reference no. (UTR/IB/SCREF/...)")
        form.addRow("Reference No", self.ref_input)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 99_999_999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setGroupSeparatorShown(True)
        self.amount_spin.setPrefix("₹ ")
        form.addRow("Amount *", self.amount_spin)

        self.bal_spin = QDoubleSpinBox()
        self.bal_spin.setRange(-99_999_999.99, 99_999_999.99)
        self.bal_spin.setDecimals(2)
        self.bal_spin.setGroupSeparatorShown(True)
        self.bal_spin.setPrefix("₹ ")
        self.bal_spin.setSpecialValueText("—")
        self.bal_spin.setValue(self.bal_spin.minimum())
        form.addRow("Balance After", self.bal_spin)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMinimumHeight(68)
        self.desc_edit.setPlaceholderText("Optional description / notes …")
        form.addRow("Description", self.desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save" if self._existing else "Add")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_accounts(self):
        self.cmb_account.clear()
        pid = self.cmb_person.currentData()
        for a in self._accounts:
            if pid is None or a.get("person_id") == pid:
                self.cmb_account.addItem(f"{a.get('bank_display_name', a['bank_name'])} ({a['account_type']})", userData=a["account_id"])

    def _populate_categories(self, txn_type):
        self.cmb_category.clear()
        self.cmb_category.addItem("", userData=None)
        norm = normalize_transaction_type(txn_type)
        if norm == "Income": self.cmb_category.addItems(INCOME_CATEGORIES)
        elif norm == "Expense": self.cmb_category.addItems(EXPENSE_CATEGORIES)
        else: self.cmb_category.addItem("Transfer")

    def _prefill(self, txn):
        for i in range(self.cmb_person.count()):
            if self.cmb_person.itemData(i) == txn.get("person_id"):
                self.cmb_person.setCurrentIndex(i); break
        self._populate_accounts()
        for i in range(self.cmb_account.count()):
            if self.cmb_account.itemData(i) == txn.get("account_id"):
                self.cmb_account.setCurrentIndex(i); break
        d = txn.get("transaction_date","")
        if d:
            qd = QDate.fromString(d,"yyyy-MM-dd")
            if qd.isValid(): self.date_edit.setDate(qd)
        typ = display_transaction_type(txn.get("transaction_type", "Income"))
        self.cmb_type.setCurrentText(typ)
        self._populate_categories(typ)
        idx = self.cmb_category.findText(txn.get("category") or "")
        if idx >= 0: self.cmb_category.setCurrentIndex(idx)
        idx = self.cmb_mode.findText(txn.get("mode") or "")
        if idx >= 0: self.cmb_mode.setCurrentIndex(idx)
        self.ref_input.setText(txn.get("reference_no") or "")
        self.amount_spin.setValue(txn.get("amount",0.0))
        bal = txn.get("balance_after")
        if bal is not None: self.bal_spin.setValue(bal)
        self.desc_edit.setPlainText(txn.get("description") or "")

    def _on_person_changed(self): self._populate_accounts()
    def _on_type_changed(self, t): self._populate_categories(t)

    def _on_accept(self):
        if not self.cmb_account.currentData():
            show_warning("Please select an account."); return
        if self.amount_spin.value() <= 0:
            show_warning("Amount must be > 0."); return
        self.accept()

    def get_data(self) -> dict:
        bal_val = self.bal_spin.value()
        bal = None if bal_val == self.bal_spin.minimum() else bal_val
        return {
            "account_id":       self.cmb_account.currentData(),
            "person_id":        self.cmb_person.currentData(),
            "transaction_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "transaction_type": normalize_transaction_type(self.cmb_type.currentText()),
            "category":         self.cmb_category.currentText().strip() or None,
            "mode":             self.cmb_mode.currentText().strip() or None,
            "reference_no":     self.ref_input.text().strip().upper() or None,
            "amount":           self.amount_spin.value(),
            "description":      self.desc_edit.toPlainText().strip() or None,
            "balance_after":    bal,
            "source":           "Manual",
        }
