"""
ui/dialogs/account_dialog.py — Bank account management dialog with clean styling.
FIX: All buttons now have explicit inline styles (no objectName dependency in QDialog).
"""

import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QMessageBox, QComboBox, QDoubleSpinBox,
    QCheckBox, QDateEdit, QTextEdit, QTabWidget, QWidget, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.widgets.excel_table import enable_copy_shortcut
from ui.icons import set_btn_icon, tab_icon, icon_label
from config import ACCOUNT_TYPES
from models.person import get_all_persons
from models.bank_account import add_account, get_all_accounts, update_account, delete_account
from models.bank import get_all_banks, get_or_create_bank, update_bank_tan_code_if_exists
from models.account_holder import get_account_holders, add_account_holder


def _btn(text: str, style: str = "primary") -> QPushButton:
    return Theme.btn(text, style, height=36, min_width=100)


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
        header.setSpacing(10)
        header.addWidget(icon_label("bank_details", size=20, color=Theme.PRIMARY))
        title = QLabel("Bank Accounts")
        title.setStyleSheet(Theme.title_style(14))
        header.addWidget(title)
        header.addStretch()
        btn_add = _btn(" Add Account", "primary")
        set_btn_icon(btn_add, "add")
        btn_add.setAccessibleName("Add account")
        btn_add.clicked.connect(self._on_add)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Person", "Bank Name", "TAN", "Type", "Account No.", "IFSC",
            "Opening Balance", "Current Balance", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(8, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        enable_copy_shortcut(self.table)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAccessibleName("Bank accounts table")
        self.table.setAccessibleDescription("Table of bank accounts with person, bank, account type, and balances.")
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        actions = QHBoxLayout(); actions.addStretch()
        btn_edit = _btn(" Edit", "edit")
        set_btn_icon(btn_edit, "edit")
        btn_edit.setAccessibleName("Edit account")
        btn_edit.clicked.connect(self._on_edit)
        actions.addWidget(btn_edit)
        btn_del = _btn(" Delete", "danger")
        set_btn_icon(btn_del, "delete")
        btn_del.setAccessibleName("Delete account")
        btn_del.clicked.connect(self._on_delete)
        actions.addWidget(btn_del)
        btn_close = _btn("Close", "secondary")
        btn_close.setAccessibleName("Close account manager")
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)

    def _load_accounts(self):
        self.table.setRowCount(0)
        for acc in get_all_accounts():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(acc.get("person_name","—")))
            self.table.setItem(r, 1, QTableWidgetItem(acc.get("bank_display_name") or acc["bank_name"]))
            self.table.setItem(r, 2, QTableWidgetItem(acc.get("tan_code") or "—"))
            self.table.setItem(r, 3, QTableWidgetItem(acc["account_type"]))
            self.table.setItem(r, 4, QTableWidgetItem(acc.get("account_number_masked") or "—"))
            self.table.setItem(r, 5, QTableWidgetItem(acc.get("ifsc_code") or "—"))
            self.table.setItem(r, 6, QTableWidgetItem(f"₹ {acc['opening_balance']:,.2f}"))
            self.table.setItem(r, 7, QTableWidgetItem(f"₹ {acc['current_balance']:,.2f}"))
            self.table.setItem(r, 8, QTableWidgetItem(str(acc["account_id"])))
            self.table.setRowHeight(r, 32)

    def _on_add(self):
        persons = get_all_persons()
        if not persons:
            QMessageBox.warning(self, "No Persons", "Add a family member first."); return
        dlg = AccountDialog(self, persons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            account_id = add_account(**payload)
            get_or_create_bank(payload.get("bank_name") or "")
            if tan_code:
                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)

            # Save account holders
            for holder in dlg._holders_data:
                add_account_holder(account_id, holder["person_id"], holder["is_primary"])

            self._load_accounts()

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select an account."); return
        aid = int(self.table.item(row, 8).text())
        accounts = get_all_accounts()
        acc_data = next((a for a in accounts if a["account_id"] == aid), None)
        if not acc_data: return
        dlg = AccountDialog(self, get_all_persons(), acc_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            update_account(aid, **payload)
            get_or_create_bank(payload.get("bank_name") or "")
            if tan_code:
                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)

            # Update account holders: clear old and add new
            from core.database import get_connection
            conn = get_connection()
            conn.execute("DELETE FROM AccountHolder WHERE account_id = ?", (aid,))
            conn.commit()
            conn.close()

            for holder in dlg._holders_data:
                add_account_holder(aid, holder["person_id"], holder["is_primary"])

            self._load_accounts()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select an account."); return
        aid  = int(self.table.item(row, 8).text())
        name = self.table.item(row, 1).text()
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete account '{name}'?\n\nAll transactions for this account will also be deleted!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_account(aid)
            self._load_accounts()


class AccountDialog(QDialog):
    def __init__(self, parent=None, persons=None, account_data=None, view_only: bool = False):
        super().__init__(parent)
        self.persons = persons or []
        self.account_data = account_data
        self.action = None
        self.view_only = view_only
        if view_only:
            self.setWindowTitle("View Account")
        else:
            self.setWindowTitle("Edit Account" if account_data else "Add Account")
        self.setMinimumSize(660, 580)
        self._build_ui()
        if account_data:
            self._load_data()
        if self.view_only:
            self._set_view_only()

    def _populate_bank_combo(self):
        self.bank_combo.clear()
        self.bank_combo.addItem("-- Select or Type New Bank --", userData=None)
        for bank in get_all_banks():
            display = bank.get("display_name") or bank.get("nickname") or bank.get("bank_name")
            actual = bank.get("bank_name") or ""
            if display and actual and display != actual:
                text = f"{display} ({actual})"
            else:
                text = actual
            self.bank_combo.addItem(text, userData=actual)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 18)

        tabs = QTabWidget()
        tabs.setAccessibleName("Account details tabs")
        tabs.addTab(self._scroll_tab(self._basic_tab()),   "Basic Info")
        tabs.addTab(self._scroll_tab(self._bank_tab()),    "Bank Details")
        tabs.addTab(self._scroll_tab(self._contact_tab()), "Contact")
        tabs.addTab(self._scroll_tab(self._card_tab()),    "Debit Card")
        tabs.addTab(self._holders_tab(),                   "Account Holders")
        tabs.setTabIcon(0, tab_icon("basic_info"))
        tabs.setTabIcon(1, tab_icon("bank_details"))
        tabs.setTabIcon(2, tab_icon("contact"))
        tabs.setTabIcon(3, tab_icon("debit_card"))
        tabs.setTabIcon(4, tab_icon("person"))
        layout.addWidget(tabs)

        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {Theme.BORDER};")
        layout.addWidget(div)

        btns = QHBoxLayout(); btns.addStretch()
        btn_cancel = _btn("Close" if self.view_only else "Cancel", "secondary")
        btn_cancel.setAccessibleName("Close account dialog" if self.view_only else "Cancel account dialog")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        if self.view_only:
            btn_delete = _btn("Delete", "danger")
            btn_delete.setAccessibleName("Delete account")
            btn_delete.clicked.connect(self._on_delete_from_view)
            btns.addWidget(btn_delete)
            btn_edit = _btn("Edit", "edit")
            btn_edit.setAccessibleName("Edit account")
            btn_edit.clicked.connect(self._on_edit_from_view)
            btns.addWidget(btn_edit)
        else:
            btn_save = _btn("Save Account", "primary")
            btn_save.setAccessibleName("Save account")
            btn_save.clicked.connect(self._on_save)
            btns.addWidget(btn_save)
        layout.addLayout(btns)

        if self.view_only:
            self.setTabOrder(btn_cancel, btn_delete)
            self.setTabOrder(btn_delete, btn_edit)
        else:
            self.setTabOrder(btn_cancel, btn_save)

    def _on_edit_from_view(self):
        self.action = "edit"
        self.accept()

    def _on_delete_from_view(self):
        if not self.account_data:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete account '{self.account_data.get('bank_name', 'Selected Account')}'?\n\n"
            "All transactions for this account will also be deleted!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_account(self.account_data["account_id"])
            QMessageBox.information(self, "Deleted", "Account deleted successfully!")
            self.action = "delete"
            self.accept()

    def _set_view_only(self):
        for w in self.findChildren(QLineEdit):
            w.setReadOnly(True)
        for w in self.findChildren(QTextEdit):
            w.setReadOnly(True)
        for w in self.findChildren(QComboBox):
            w.setEnabled(False)
        for w in self.findChildren(QDoubleSpinBox):
            w.setEnabled(False)
        for w in self.findChildren(QDateEdit):
            w.setEnabled(False)
        for w in self.findChildren(QCheckBox):
            w.setEnabled(False)

    def _scroll_tab(self, tab_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(tab_widget)
        return scroll

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
        self.person_combo.setAccessibleName("Person selector")
        for p in self.persons:
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])
        f.addRow("Person *:", self.person_combo)

        self.bank_combo = QComboBox()
        self.bank_combo.setEditable(True)
        self.bank_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.bank_combo.setFixedHeight(40)
        self.bank_combo.setAccessibleName("Bank selector")
        self._populate_bank_combo()
        f.addRow("Bank Name *:", self.bank_combo)

        self.holder_name_input = self._field("Name as per bank records")
        self.holder_name_input.setAccessibleName("Account holder name")
        f.addRow("Account Holder Name:", self.holder_name_input)

        self.tan_input = self._field("e.g. BLRJ07125G")
        self.tan_input.setAccessibleName("TAN code")
        self.tan_input.setMaxLength(10)
        self.tan_input.textChanged.connect(
            lambda txt: self.tan_input.setText((txt or "").upper()) if (txt or "") != (txt or "").upper() else None
        )
        f.addRow("TAN No.:", self.tan_input)

        self.type_combo = self._combo(ACCOUNT_TYPES)
        self.type_combo.setAccessibleName("Account type")
        f.addRow("Account Type *:", self.type_combo)

        self.account_no_input = self._field("e.g. XXXX1234")
        self.account_no_input.setAccessibleName("Masked account number")
        f.addRow("Account No. (masked):", self.account_no_input)

        self.account_no_full_input = self._field("Optional full account number")
        self.account_no_full_input.setAccessibleName("Full account number")
        f.addRow("Account No. (full):", self.account_no_full_input)

        self.customer_id_input = self._field()
        self.customer_id_input.setAccessibleName("Customer ID")
        f.addRow("Customer ID:", self.customer_id_input)

        self.ckyc_input = self._field()
        self.ckyc_input.setAccessibleName("CKYC ID")
        f.addRow("CKYC ID:", self.ckyc_input)

        self.opening_date = QDateEdit()
        self.opening_date.setCalendarPopup(True)
        self.opening_date.setDate(QDate.currentDate())
        self.opening_date.setDisplayFormat("dd/MM/yy")
        self.opening_date.setFixedHeight(40)
        self.opening_date.setAccessibleName("Opening date")
        f.addRow("Opening Date:", self.opening_date)

        self.status_combo = self._combo(["Active","Inactive","Closed"])
        self.status_combo.setAccessibleName("Account status")
        f.addRow("Status:", self.status_combo)

        self.currency_combo = self._combo(["INR", "USD", "EUR", "GBP"])
        self.currency_combo.setAccessibleName("Currency")
        f.addRow("Currency:", self.currency_combo)

        self.opening_balance = self._spin()
        self.opening_balance.setAccessibleName("Opening balance")
        f.addRow("Opening Balance:", self.opening_balance)

        self.current_balance_input = self._field()
        self.current_balance_input.setReadOnly(True)
        self.current_balance_input.setAccessibleName("Current balance")
        f.addRow("Current Balance:", self.current_balance_input)

        self.interest_rate = QDoubleSpinBox()
        self.interest_rate.setRange(0, 100); self.interest_rate.setDecimals(2)
        self.interest_rate.setSuffix(" %"); self.interest_rate.setValue(3.5)
        self.interest_rate.setFixedHeight(40)
        self.interest_rate.setAccessibleName("Interest rate")
        f.addRow("Interest Rate:", self.interest_rate)

        self.created_at_input = self._field()
        self.created_at_input.setReadOnly(True)
        f.addRow("Created At:", self.created_at_input)

        self.setTabOrder(self.person_combo, self.bank_combo)
        self.setTabOrder(self.bank_combo, self.holder_name_input)
        self.setTabOrder(self.holder_name_input, self.tan_input)
        self.setTabOrder(self.tan_input, self.type_combo)
        self.setTabOrder(self.type_combo, self.account_no_input)
        self.setTabOrder(self.account_no_input, self.account_no_full_input)
        self.setTabOrder(self.account_no_full_input, self.customer_id_input)
        self.setTabOrder(self.customer_id_input, self.ckyc_input)
        self.setTabOrder(self.ckyc_input, self.opening_date)
        self.setTabOrder(self.opening_date, self.status_combo)
        self.setTabOrder(self.status_combo, self.currency_combo)
        self.setTabOrder(self.currency_combo, self.opening_balance)
        self.setTabOrder(self.opening_balance, self.current_balance_input)
        self.setTabOrder(self.current_balance_input, self.interest_rate)

        return w

    def _bank_tab(self) -> QWidget:
        w, f = self._form_widget()

        self.ifsc_input = self._field("e.g. HDFC0001234")
        self.ifsc_input.setAccessibleName("IFSC code")
        self.ifsc_input.setMaxLength(11)
        self.ifsc_input.textChanged.connect(
            lambda txt: self.ifsc_input.setText((txt or "").upper()) if (txt or "") != (txt or "").upper() else None
        )
        f.addRow("IFSC Code:", self.ifsc_input)

        self.micr_input = self._field("e.g. 360240001")
        self.micr_input.setAccessibleName("MICR code")
        self.micr_input.setMaxLength(9)
        f.addRow("MICR Code:", self.micr_input)

        self.branch_name_input = self._field()
        self.branch_name_input.setAccessibleName("Branch name")
        f.addRow("Branch Name:", self.branch_name_input)

        self.branch_address_input = QTextEdit()
        self.branch_address_input.setMaximumHeight(80)
        self.branch_address_input.setAccessibleName("Branch address")
        f.addRow("Branch Address:", self.branch_address_input)

        self.setTabOrder(self.ifsc_input, self.micr_input)
        self.setTabOrder(self.micr_input, self.branch_name_input)
        self.setTabOrder(self.branch_name_input, self.branch_address_input)

        return w

    def _contact_tab(self) -> QWidget:
        w, f = self._form_widget()

        self.email_input = self._field("email@example.com")
        self.email_input.setAccessibleName("Email address")
        f.addRow("Email ID:", self.email_input)

        self.phone_input = self._field("e.g. 9876543210")
        self.phone_input.setAccessibleName("Phone number")
        f.addRow("Phone No:", self.phone_input)

        self.comm_address_input = QTextEdit()
        self.comm_address_input.setMaximumHeight(80)
        self.comm_address_input.setAccessibleName("Communication address")
        f.addRow("Communication Address:", self.comm_address_input)

        self.nomination_combo = self._combo(["","Registered","Not Registered"])
        self.nomination_combo.setAccessibleName("Nomination status")
        f.addRow("Nomination Status:", self.nomination_combo)

        self.nominee_input = self._field()
        self.nominee_input.setAccessibleName("Nominee name")
        f.addRow("Nominee Name:", self.nominee_input)

        self.setTabOrder(self.email_input, self.phone_input)
        self.setTabOrder(self.phone_input, self.comm_address_input)
        self.setTabOrder(self.comm_address_input, self.nomination_combo)
        self.setTabOrder(self.nomination_combo, self.nominee_input)

        return w

    def _card_tab(self) -> QWidget:
        w, f = self._form_widget()

        self.debit_card_check = QCheckBox("Debit Card Enabled")
        self.debit_card_check.setAccessibleName("Debit card enabled")
        self.debit_card_check.toggled.connect(self._on_card_toggled)
        f.addRow("", self.debit_card_check)

        self.debit_charges = self._spin()
        self.debit_charges.setEnabled(False)
        self.debit_charges.setAccessibleName("Debit card annual charges")
        f.addRow("Annual Charges:", self.debit_charges)

        self.debit_effective = QDateEdit()
        self.debit_effective.setCalendarPopup(True)
        self.debit_effective.setDate(QDate.currentDate())
        self.debit_effective.setDisplayFormat("dd/MM/yy")
        self.debit_effective.setFixedHeight(40)
        self.debit_effective.setEnabled(False)
        self.debit_effective.setAccessibleName("Debit card effective date")
        f.addRow("Effective From:", self.debit_effective)

        self.setTabOrder(self.debit_card_check, self.debit_charges)
        self.setTabOrder(self.debit_charges, self.debit_effective)

        return w

    def _holders_tab(self) -> QWidget:
        """Tab to manage joint account holders."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        lbl = QLabel("Account Holders (for joint accounts)")
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(lbl)

        # Info label
        info_lbl = QLabel("Select one or more family members who hold this account. "
                          "The primary holder is the one who declares interest income.")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        # Table of holders
        self.holders_table = QTableWidget()
        self.holders_table.setColumnCount(3)
        self.holders_table.setHorizontalHeaderLabels(["Person", "Entity Type", "Primary"])
        self.holders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.holders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.holders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.holders_table.setAlternatingRowColors(True)
        self.holders_table.setShowGrid(False)
        self.holders_table.verticalHeader().setVisible(False)
        self.holders_table.setMaximumHeight(250)
        layout.addWidget(self.holders_table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_add_holder = Theme.btn(" Add Holder", "primary", height=36, min_width=100)
        set_btn_icon(self.btn_add_holder, "add")
        self.btn_add_holder.clicked.connect(self._on_add_holder)
        self.btn_add_holder.setAccessibleName("Add joint account holder")
        btn_layout.addWidget(self.btn_add_holder)

        self.btn_remove_holder = Theme.btn(" Remove", "secondary", height=36, min_width=100)
        set_btn_icon(self.btn_remove_holder, "delete")
        self.btn_remove_holder.clicked.connect(self._on_remove_holder)
        self.btn_remove_holder.setAccessibleName("Remove selected holder")
        btn_layout.addWidget(self.btn_remove_holder)

        self.btn_set_primary = Theme.btn(" Set as Primary", "secondary", height=36, min_width=120)
        self.btn_set_primary.clicked.connect(self._on_set_primary)
        self.btn_set_primary.setAccessibleName("Set selected holder as primary")
        btn_layout.addWidget(self.btn_set_primary)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addStretch()

        self._holders_data = []  # Track holder person_ids

        return w

    def _on_add_holder(self):
        """Add a new holder to the account."""
        # Get list of persons not already added
        all_persons = [p for p in self.persons]
        added_ids = {h["person_id"] for h in self._holders_data}
        available = [p for p in all_persons if p["person_id"] not in added_ids]

        if not available:
            QMessageBox.information(self, "No Available", "All family members are already added as holders.")
            return

        # Simple selection dialog
        names = [p["full_name"] for p in available]
        names_str = "\n".join(names)
        from PyQt6.QtWidgets import QInputDialog
        selected, ok = QInputDialog.getItem(
            self, "Add Holder", "Select a family member:", names, 0, False
        )
        if not ok:
            return

        # Find the selected person
        person = next((p for p in available if p["full_name"] == selected), None)
        if person:
            self._holders_data.append({
                "person_id": person["person_id"],
                "full_name": person["full_name"],
                "entity_type": "Individual",
                "is_primary": 0
            })
            self._refresh_holders_table()

    def _on_remove_holder(self):
        """Remove the selected holder."""
        row = self.holders_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a holder to remove.")
            return
        if len(self._holders_data) <= 1:
            QMessageBox.warning(self, "Cannot Remove", "An account must have at least one holder.")
            return
        del self._holders_data[row]
        self._refresh_holders_table()

    def _on_set_primary(self):
        """Set the selected holder as primary."""
        row = self.holders_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a holder to set as primary.")
            return
        for h in self._holders_data:
            h["is_primary"] = 0
        self._holders_data[row]["is_primary"] = 1
        self._refresh_holders_table()

    def _refresh_holders_table(self):
        """Refresh the holders table display."""
        self.holders_table.setRowCount(len(self._holders_data))
        for idx, holder in enumerate(self._holders_data):
            name_item = QTableWidgetItem(holder["full_name"])
            entity_item = QTableWidgetItem(holder.get("entity_type", "Individual"))
            primary_item = QTableWidgetItem("Yes" if holder.get("is_primary") else "No")

            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            entity_item.setFlags(entity_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            primary_item.setFlags(primary_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.holders_table.setItem(idx, 0, name_item)
            self.holders_table.setItem(idx, 1, entity_item)
            self.holders_table.setItem(idx, 2, primary_item)
            self.holders_table.setRowHeight(idx, 32)

    def _on_card_toggled(self, checked):
        self.debit_charges.setEnabled(checked)
        self.debit_effective.setEnabled(checked)

    def _load_data(self):
        d = self.account_data
        for i in range(self.person_combo.count()):
            if self.person_combo.itemData(i) == d.get("person_id"):
                self.person_combo.setCurrentIndex(i); break
        bank_name = d.get("bank_name", "")
        idx = -1
        for i in range(self.bank_combo.count()):
            if (self.bank_combo.itemData(i) or "").strip().lower() == bank_name.strip().lower():
                idx = i
                break
        if idx >= 0:
            self.bank_combo.setCurrentIndex(idx)
        else:
            self.bank_combo.setEditText(bank_name)
        self.holder_name_input.setText(d.get("account_holder_name") or "")
        self.tan_input.setText((d.get("tan_code") or "").upper())
        self.type_combo.setCurrentText(d.get("account_type","Savings"))
        self.account_no_input.setText(d.get("account_number_masked") or "")
        self.account_no_full_input.setText(d.get("account_number_full") or "")
        self.customer_id_input.setText(d.get("customer_id") or "")
        self.ckyc_input.setText(d.get("ckyc_id") or "")
        if d.get("account_opening_date"):
            qd = QDate.fromString(d["account_opening_date"],"yyyy-MM-dd")
            if qd.isValid(): self.opening_date.setDate(qd)
        self.status_combo.setCurrentText(d.get("account_status","Active"))
        self.currency_combo.setCurrentText(d.get("currency") or "INR")
        self.opening_balance.setValue(d.get("opening_balance",0.0))
        self.current_balance_input.setText(f"₹ {d.get('current_balance', 0.0):,.2f}")
        self.interest_rate.setValue(d.get("interest_rate",3.5))
        self.created_at_input.setText(d.get("created_at") or "")
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

        # Load account holders
        account_id = d.get("account_id")
        if account_id:
            holders = get_account_holders(account_id)
            self._holders_data = [
                {
                    "person_id": h["person_id"],
                    "full_name": h["full_name"],
                    "entity_type": h.get("entity_type", "Individual"),
                    "is_primary": h["is_primary"]
                }
                for h in holders
            ]
            self._refresh_holders_table()
        else:
            # New account: add the currently selected person as primary holder
            person_id = self.person_combo.currentData()
            person_name = self.person_combo.currentText()
            if person_id:
                self._holders_data = [
                    {
                        "person_id": person_id,
                        "full_name": person_name,
                        "entity_type": "Individual",
                        "is_primary": 1
                    }
                ]
                self._refresh_holders_table()

    def _on_save(self):
        bank_name = (self.bank_combo.currentData() or self.bank_combo.currentText() or "").strip()
        if not bank_name or bank_name == "-- Select or Type New Bank --":
            QMessageBox.warning(self,"Missing","Please enter a bank name."); return

        tan = self.tan_input.text().strip().upper()
        if tan and not re.fullmatch(r"[A-Z]{4}[0-9]{5}[A-Z]", tan):
            QMessageBox.warning(self, "Invalid TAN", "TAN must be 10 characters in the format ABCD12345E.")
            return

        ifsc = self.ifsc_input.text().strip().upper()
        if ifsc and not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
            QMessageBox.warning(self, "Invalid IFSC", "IFSC must be 11 characters in the format HDFC0001234.")
            return

        micr = self.micr_input.text().strip()
        if micr and not re.fullmatch(r"[0-9]{9}", micr):
            QMessageBox.warning(self, "Invalid MICR", "MICR code must be exactly 9 digits.")
            return

        email = self.email_input.text().strip()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
            return

        phone = self.phone_input.text().strip()
        if phone and not re.fullmatch(r"[0-9]{10}", re.sub(r"[\s\-+]", "", phone).removeprefix("91")):
            QMessageBox.warning(self, "Invalid Phone", "Please enter a valid 10-digit phone number.")
            return

        self.accept()

    def get_data(self) -> dict:
        bank_name = (self.bank_combo.currentData() or self.bank_combo.currentText() or "").strip()
        return {
            "person_id":               self.person_combo.currentData(),
            "bank_name":               bank_name,
            "account_holder_name":     self.holder_name_input.text().strip() or None,
            "tan_code":                self.tan_input.text().strip().upper() or None,
            "account_type":            self.type_combo.currentText(),
            "account_number_masked":   self.account_no_input.text().strip() or None,
            "account_number_full":     self.account_no_full_input.text().strip() or None,
            "customer_id":             self.customer_id_input.text().strip() or None,
            "ckyc_id":                 self.ckyc_input.text().strip() or None,
            "account_opening_date":    self.opening_date.date().toString("yyyy-MM-dd"),
            "account_status":          self.status_combo.currentText(),
            "currency":                self.currency_combo.currentText(),
            "opening_balance":         self.opening_balance.value(),
            "interest_rate":           self.interest_rate.value(),
            "ifsc_code":               self.ifsc_input.text().strip().upper() or None,
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
