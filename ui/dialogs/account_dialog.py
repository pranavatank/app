"""
ui/dialogs/account_dialog.py — Bank account management dialog
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QMessageBox, QComboBox, QDoubleSpinBox,
    QCheckBox, QDateEdit, QTextEdit, QTabWidget, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from config import ACCOUNT_TYPES
from models.person import get_all_persons
from models.bank_account import add_account, get_all_accounts, update_account, delete_account


class AccountManagementDialog(QDialog):
    """Dialog to manage bank accounts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Bank Accounts")
        self.setMinimumSize(900, 500)
        self._build_ui()
        self._load_accounts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Bank Accounts")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("+ Add Account")
        btn_add.setObjectName("primaryBtn")
        btn_add.clicked.connect(self._on_add_account)
        header.addWidget(btn_add)

        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Person", "Bank Name", "Type", "Account No.", "IFSC",
            "Opening Balance", "Current Balance", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(7, True)  # Hide ID column
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_edit_account)
        layout.addWidget(self.table)

        # Actions
        actions = QHBoxLayout()
        actions.addStretch()

        btn_edit = QPushButton("Edit")
        btn_edit.setObjectName("secondaryBtn")
        btn_edit.clicked.connect(self._on_edit_account)
        actions.addWidget(btn_edit)

        btn_delete = QPushButton("Delete")
        btn_delete.setObjectName("dangerBtn")
        btn_delete.clicked.connect(self._on_delete_account)
        actions.addWidget(btn_delete)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)

        layout.addLayout(actions)

    def _load_accounts(self):
        """Load all accounts into table."""
        accounts = get_all_accounts()
        self.table.setRowCount(0)

        for account in accounts:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(account.get("person_name", "—")))
            self.table.setItem(row, 1, QTableWidgetItem(account["bank_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(account["account_type"]))
            self.table.setItem(row, 3, QTableWidgetItem(account.get("account_number_masked") or "—"))
            self.table.setItem(row, 4, QTableWidgetItem(account.get("ifsc_code") or "—"))
            self.table.setItem(row, 5, QTableWidgetItem(f"₹ {account['opening_balance']:,.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"₹ {account['current_balance']:,.2f}"))
            self.table.setItem(row, 7, QTableWidgetItem(str(account["account_id"])))

    def _on_add_account(self):
        """Add new account."""
        persons = get_all_persons()
        if not persons:
            QMessageBox.warning(
                self, "No Persons",
                "Please add a family member first before adding accounts."
            )
            return

        dialog = AccountDialog(self, persons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            add_account(**data)
            self._load_accounts()
            QMessageBox.information(self, "Success", "Account added successfully!")

    def _on_edit_account(self):
        """Edit selected account."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an account to edit.")
            return

        account_id = int(self.table.item(row, 7).text())
        persons = get_all_persons()
        
        # Get account data
        accounts = get_all_accounts()
        account_data = next((a for a in accounts if a["account_id"] == account_id), None)
        
        if not account_data:
            return

        dialog = AccountDialog(self, persons, account_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            update_account(account_id, **data)
            self._load_accounts()
            QMessageBox.information(self, "Success", "Account updated successfully!")

    def _on_delete_account(self):
        """Delete selected account."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an account to delete.")
            return

        account_id = int(self.table.item(row, 7).text())
        bank_name = self.table.item(row, 1).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete account '{bank_name}'?\n\nThis will also delete all associated transactions!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_account(account_id)
            self._load_accounts()
            QMessageBox.information(self, "Deleted", "Account deleted successfully!")


class AccountDialog(QDialog):
    """Dialog for adding/editing a bank account with all details."""

    def __init__(self, parent=None, persons=None, account_data=None):
        super().__init__(parent)
        self.persons = persons or []
        self.account_data = account_data
        self.setWindowTitle("Edit Account" if account_data else "Add Account")
        self.setMinimumSize(650, 600)
        self._build_ui()

        if account_data:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Tabs for organized input
        tabs = QTabWidget()
        tabs.addTab(self._create_basic_tab(), "Basic Info")
        tabs.addTab(self._create_bank_tab(), "Bank Details")
        tabs.addTab(self._create_contact_tab(), "Contact & Nomination")
        tabs.addTab(self._create_debit_card_tab(), "Debit Card")
        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save")
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _create_basic_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)

        # Person
        self.person_combo = QComboBox()
        for person in self.persons:
            self.person_combo.addItem(person["full_name"], userData=person["person_id"])
        layout.addRow("Person *:", self.person_combo)

        # Bank Name
        self.bank_input = QLineEdit()
        self.bank_input.setPlaceholderText("e.g., HDFC Bank")
        layout.addRow("Bank Name *:", self.bank_input)

        # Account Type
        self.type_combo = QComboBox()
        self.type_combo.addItems(ACCOUNT_TYPES)
        layout.addRow("Account Type *:", self.type_combo)

        # Account Number (masked)
        self.account_no_input = QLineEdit()
        self.account_no_input.setPlaceholderText("e.g., XXXX1234")
        layout.addRow("Account No. (masked):", self.account_no_input)

        # Customer ID
        self.customer_id_input = QLineEdit()
        layout.addRow("Customer ID:", self.customer_id_input)

        # CKYC ID
        self.ckyc_input = QLineEdit()
        layout.addRow("CKYC ID:", self.ckyc_input)

        # Opening Date
        self.opening_date = QDateEdit()
        self.opening_date.setCalendarPopup(True)
        self.opening_date.setDate(QDate.currentDate())
        self.opening_date.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Opening Date:", self.opening_date)

        # Account Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Active", "Inactive", "Closed"])
        layout.addRow("Status:", self.status_combo)

        # Opening Balance
        self.opening_balance = QDoubleSpinBox()
        self.opening_balance.setRange(-99999999.99, 99999999.99)
        self.opening_balance.setDecimals(2)
        self.opening_balance.setGroupSeparatorShown(True)
        self.opening_balance.setPrefix("₹ ")
        self.opening_balance.setValue(0.0)
        layout.addRow("Opening Balance:", self.opening_balance)

        # Interest Rate
        self.interest_rate = QDoubleSpinBox()
        self.interest_rate.setRange(0, 100)
        self.interest_rate.setDecimals(2)
        self.interest_rate.setSuffix(" %")
        self.interest_rate.setValue(3.5)
        layout.addRow("Interest Rate:", self.interest_rate)

        return widget

    def _create_bank_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)

        # IFSC Code
        self.ifsc_input = QLineEdit()
        self.ifsc_input.setPlaceholderText("e.g., HDFC0001234")
        self.ifsc_input.setMaxLength(11)
        layout.addRow("IFSC Code:", self.ifsc_input)

        # MICR Code
        self.micr_input = QLineEdit()
        self.micr_input.setPlaceholderText("e.g., 360240001")
        self.micr_input.setMaxLength(9)
        layout.addRow("MICR Code:", self.micr_input)

        # Branch Name
        self.branch_name_input = QLineEdit()
        layout.addRow("Branch Name:", self.branch_name_input)

        # Branch Address
        self.branch_address_input = QTextEdit()
        self.branch_address_input.setMaximumHeight(80)
        layout.addRow("Branch Address:", self.branch_address_input)

        return widget

    def _create_contact_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)

        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        layout.addRow("Email ID:", self.email_input)

        # Phone
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("1234567890")
        layout.addRow("Phone No:", self.phone_input)

        # Communication Address
        self.comm_address_input = QTextEdit()
        self.comm_address_input.setMaximumHeight(80)
        layout.addRow("Communication Address:", self.comm_address_input)

        # Nomination Status
        self.nomination_combo = QComboBox()
        self.nomination_combo.addItems(["", "Registered", "Not Registered"])
        layout.addRow("Nomination Status:", self.nomination_combo)

        # Nominee Name
        self.nominee_input = QLineEdit()
        layout.addRow("Nominee Name:", self.nominee_input)

        return widget

    def _create_debit_card_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(12)

        # Debit Card Enabled
        self.debit_card_check = QCheckBox("Debit Card Enabled")
        self.debit_card_check.toggled.connect(self._on_debit_card_toggled)
        layout.addRow("", self.debit_card_check)

        # Annual Charges
        self.debit_charges = QDoubleSpinBox()
        self.debit_charges.setRange(0, 10000)
        self.debit_charges.setDecimals(2)
        self.debit_charges.setPrefix("₹ ")
        self.debit_charges.setValue(0.0)
        self.debit_charges.setEnabled(False)
        layout.addRow("Annual Charges:", self.debit_charges)

        # Effective From
        self.debit_effective = QDateEdit()
        self.debit_effective.setCalendarPopup(True)
        self.debit_effective.setDate(QDate.currentDate())
        self.debit_effective.setDisplayFormat("yyyy-MM-dd")
        self.debit_effective.setEnabled(False)
        layout.addRow("Effective From:", self.debit_effective)

        return widget

    def _on_debit_card_toggled(self, checked: bool):
        self.debit_charges.setEnabled(checked)
        self.debit_effective.setEnabled(checked)

    def _load_data(self):
        """Load existing account data."""
        # Basic tab
        for i in range(self.person_combo.count()):
            if self.person_combo.itemData(i) == self.account_data.get("person_id"):
                self.person_combo.setCurrentIndex(i)
                break

        self.bank_input.setText(self.account_data.get("bank_name", ""))
        self.type_combo.setCurrentText(self.account_data.get("account_type", "Savings"))
        self.account_no_input.setText(self.account_data.get("account_number_masked") or "")
        self.customer_id_input.setText(self.account_data.get("customer_id") or "")
        self.ckyc_input.setText(self.account_data.get("ckyc_id") or "")
        
        if self.account_data.get("account_opening_date"):
            self.opening_date.setDate(QDate.fromString(self.account_data["account_opening_date"], "yyyy-MM-dd"))
        
        self.status_combo.setCurrentText(self.account_data.get("account_status", "Active"))
        self.opening_balance.setValue(self.account_data.get("opening_balance", 0.0))
        self.interest_rate.setValue(self.account_data.get("interest_rate", 3.5))

        # Bank tab
        self.ifsc_input.setText(self.account_data.get("ifsc_code") or "")
        self.micr_input.setText(self.account_data.get("micr_code") or "")
        self.branch_name_input.setText(self.account_data.get("branch_name") or "")
        self.branch_address_input.setPlainText(self.account_data.get("branch_address") or "")

        # Contact tab
        self.email_input.setText(self.account_data.get("email_id") or "")
        self.phone_input.setText(self.account_data.get("phone_no") or "")
        self.comm_address_input.setPlainText(self.account_data.get("communication_address") or "")
        self.nomination_combo.setCurrentText(self.account_data.get("nomination_status") or "")
        self.nominee_input.setText(self.account_data.get("nominee_name") or "")

        # Debit card tab
        debit_enabled = self.account_data.get("debit_card_enabled", 0)
        self.debit_card_check.setChecked(bool(debit_enabled))
        self.debit_charges.setValue(self.account_data.get("debit_card_charges", 0.0))
        
        if self.account_data.get("debit_card_effective_from"):
            self.debit_effective.setDate(QDate.fromString(self.account_data["debit_card_effective_from"], "yyyy-MM-dd"))

    def _on_save(self):
        """Validate and save."""
        bank_name = self.bank_input.text().strip()
        if not bank_name:
            QMessageBox.warning(self, "Missing Field", "Please enter a bank name.")
            return

        self.accept()

    def get_data(self) -> dict:
        """Get form data."""
        data = {
            "person_id": self.person_combo.currentData(),
            "bank_name": self.bank_input.text().strip(),
            "account_type": self.type_combo.currentText(),
            "account_number_masked": self.account_no_input.text().strip() or None,
            "customer_id": self.customer_id_input.text().strip() or None,
            "ckyc_id": self.ckyc_input.text().strip() or None,
            "account_opening_date": self.opening_date.date().toString("yyyy-MM-dd"),
            "account_status": self.status_combo.currentText(),
            "opening_balance": self.opening_balance.value(),
            "interest_rate": self.interest_rate.value(),
            "ifsc_code": self.ifsc_input.text().strip() or None,
            "micr_code": self.micr_input.text().strip() or None,
            "branch_name": self.branch_name_input.text().strip() or None,
            "branch_address": self.branch_address_input.toPlainText().strip() or None,
            "email_id": self.email_input.text().strip() or None,
            "phone_no": self.phone_input.text().strip() or None,
            "communication_address": self.comm_address_input.toPlainText().strip() or None,
            "nomination_status": self.nomination_combo.currentText() or None,
            "nominee_name": self.nominee_input.text().strip() or None,
            "debit_card_enabled": 1 if self.debit_card_check.isChecked() else 0,
            "debit_card_charges": self.debit_charges.value() if self.debit_card_check.isChecked() else 0.0,
            "debit_card_effective_from": self.debit_effective.date().toString("yyyy-MM-dd") if self.debit_card_check.isChecked() else None,
        }
        return data
