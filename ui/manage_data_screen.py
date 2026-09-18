"""
ui/manage_data_screen.py — Manage Data sub-screen with tabbed People/Banks/Accounts management.
Consolidates PersonManagementDialog, BankManagementDialog, and AccountManagementDialog
into a single tabbed interface.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QMessageBox, QDialog, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.theme import Theme
from ui.icons import set_btn_icon, icon_label
from ui.widgets.excel_table import enable_copy_shortcut
from ui.widgets.toast_utils import show_warning
from ui.date_utils import format_display_date
from models.person import add_person, get_all_persons, get_person, update_person, delete_person
from models.bank import add_bank, get_all_banks, get_bank, update_bank, delete_bank
from models.bank_account import add_account, get_all_accounts, update_account, delete_account
from models.account_holder import get_account_holders, add_account_holder

from ui.dialogs.person_dialog import PersonDialog
from ui.dialogs.bank_dialog import BankDialog
from ui.dialogs.account_dialog import AccountDialog


def _btn(text: str, style: str = "primary") -> QPushButton:
    return Theme.btn(text, style, height=36, min_width=100)


class ManageDataScreen(QWidget):
    """Tabbed sub-screen for managing People, Banks, and Accounts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Data")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_people_tab(), "People")
        self.tabs.addTab(self._build_banks_tab(), "Banks")
        self.tabs.addTab(self._build_accounts_tab(), "Accounts")
        layout.addWidget(self.tabs)

    def _build_people_tab(self) -> QWidget:
        """Build the People management tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(icon_label("persons", size=20, color=Theme.PRIMARY))
        title = QLabel("People")
        title.setProperty("textrole", "title-sm")
        header.addWidget(title)
        header.addStretch()
        btn_add = _btn("  Add Person", "primary")
        set_btn_icon(btn_add, "add")
        btn_add.setAccessibleName("Add person")
        btn_add.clicked.connect(self._on_add_person)
        header.addWidget(btn_add)
        layout.addLayout(header)

        # Table
        self.people_table = QTableWidget()
        self.people_table.setColumnCount(5)
        self.people_table.setHorizontalHeaderLabels(["Nickname", "Date of Birth", "PAN", "Notes", "ID"])
        self.people_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.people_table.setColumnHidden(4, True)
        self.people_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.people_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        enable_copy_shortcut(self.people_table)
        self.people_table.setAlternatingRowColors(True)
        self.people_table.setShowGrid(False)
        self.people_table.verticalHeader().setVisible(False)
        self.people_table.setAccessibleName("Family members table")
        self.people_table.setAccessibleDescription("Table of family members with date of birth, PAN, and notes.")
        self.people_table.doubleClicked.connect(self._on_edit_person)
        layout.addWidget(self.people_table)

        # Actions
        actions = QHBoxLayout()
        actions.addStretch()
        btn_edit = _btn("  Edit", "edit")
        set_btn_icon(btn_edit, "edit")
        btn_edit.setAccessibleName("Edit person")
        btn_edit.clicked.connect(self._on_edit_person)
        actions.addWidget(btn_edit)
        btn_del = _btn("  Delete", "danger")
        set_btn_icon(btn_del, "delete")
        btn_del.setAccessibleName("Delete person")
        btn_del.clicked.connect(self._on_delete_person)
        actions.addWidget(btn_del)
        layout.addLayout(actions)

        self._load_people()
        return page

    def _build_banks_tab(self) -> QWidget:
        """Build the Banks management tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(icon_label("bank", size=20, color=Theme.PRIMARY))
        title = QLabel("Banks")
        title.setProperty("textrole", "title-sm")
        header.addWidget(title)
        header.addStretch()
        btn_add = _btn("  Add Bank", "primary")
        set_btn_icon(btn_add, "add")
        btn_add.setAccessibleName("Add bank")
        btn_add.clicked.connect(self._on_add_bank)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.banks_table = QTableWidget()
        self.banks_table.setColumnCount(5)
        self.banks_table.setHorizontalHeaderLabels(["Nickname", "Bank Name (Actual)", "TAN", "Created", "ID"])
        self.banks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.banks_table.setColumnHidden(4, True)
        self.banks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.banks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        enable_copy_shortcut(self.banks_table)
        self.banks_table.setAlternatingRowColors(True)
        self.banks_table.setShowGrid(False)
        self.banks_table.verticalHeader().setVisible(False)
        self.banks_table.setAccessibleName("Bank list")
        self.banks_table.setAccessibleDescription("Table of bank masters with nickname, actual name, TAN, and created date.")
        self.banks_table.doubleClicked.connect(self._on_edit_bank)
        layout.addWidget(self.banks_table)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_edit = _btn("  Edit", "edit")
        set_btn_icon(btn_edit, "edit")
        btn_edit.setAccessibleName("Edit bank")
        btn_edit.clicked.connect(self._on_edit_bank)
        actions.addWidget(btn_edit)
        btn_del = _btn("  Delete", "danger")
        set_btn_icon(btn_del, "delete")
        btn_del.setAccessibleName("Delete bank")
        btn_del.clicked.connect(self._on_delete_bank)
        actions.addWidget(btn_del)
        layout.addLayout(actions)

        self._load_banks()
        return page

    def _build_accounts_tab(self) -> QWidget:
        """Build the Accounts management tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(icon_label("bank_details", size=20, color=Theme.PRIMARY))
        title = QLabel("Bank Accounts")
        title.setProperty("textrole", "title-sm")
        header.addWidget(title)
        header.addStretch()
        btn_add = _btn(" Add Account", "primary")
        set_btn_icon(btn_add, "add")
        btn_add.setAccessibleName("Add account")
        btn_add.clicked.connect(self._on_add_account)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(9)
        self.accounts_table.setHorizontalHeaderLabels([
            "Person", "Bank Name", "TAN", "Type", "Account No.", "IFSC",
            "Opening Balance", "Current Balance", "ID"
        ])
        self.accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.accounts_table.setColumnHidden(8, True)
        self.accounts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        enable_copy_shortcut(self.accounts_table)
        self.accounts_table.setAlternatingRowColors(True)
        self.accounts_table.setShowGrid(False)
        self.accounts_table.verticalHeader().setVisible(False)
        self.accounts_table.setAccessibleName("Bank accounts table")
        self.accounts_table.setAccessibleDescription("Table of bank accounts with person, bank, account type, and balances.")
        self.accounts_table.doubleClicked.connect(self._on_edit_account)
        layout.addWidget(self.accounts_table)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_edit = _btn(" Edit", "edit")
        set_btn_icon(btn_edit, "edit")
        btn_edit.setAccessibleName("Edit account")
        btn_edit.clicked.connect(self._on_edit_account)
        actions.addWidget(btn_edit)
        btn_del = _btn(" Delete", "danger")
        set_btn_icon(btn_del, "delete")
        btn_del.setAccessibleName("Delete account")
        btn_del.clicked.connect(self._on_delete_account)
        actions.addWidget(btn_del)
        layout.addLayout(actions)

        self._load_accounts()
        return page

    # ── People methods ────────────────────────────────────────────────────────

    def _load_people(self):
        self.people_table.setRowCount(0)
        for p in get_all_persons():
            r = self.people_table.rowCount()
            self.people_table.insertRow(r)
            self.people_table.setItem(r, 0, QTableWidgetItem(p.get("full_name") or ""))
            self.people_table.setItem(r, 1, QTableWidgetItem(format_display_date(p.get("date_of_birth"))))
            self.people_table.setItem(r, 2, QTableWidgetItem(p.get("pan_number") or "—"))
            self.people_table.setItem(r, 3, QTableWidgetItem(p.get("contact_notes") or "—"))
            self.people_table.setItem(r, 4, QTableWidgetItem(str(p["person_id"])))
            self.people_table.setRowHeight(r, 32)

    def _on_add_person(self):
        dlg = PersonDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            add_person(**dlg.get_data())
            self._load_people()

    def _on_edit_person(self):
        row = self.people_table.currentRow()
        if row < 0:
            show_warning("Please select a person.")
            return
        pid = int(self.people_table.item(row, 4).text())
        data = get_person(pid)
        if not data:
            show_warning("Person record no longer exists.")
            self._load_people()
            return
        dlg = PersonDialog(self, data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            update_person(pid, **dlg.get_data())
            self._load_people()

    def _on_delete_person(self):
        row = self.people_table.currentRow()
        if row < 0:
            show_warning("Please select a person.")
            return
        pid = int(self.people_table.item(row, 4).text())
        name = self.people_table.item(row, 0).text()
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete '{name}'?\n\nThis will also delete all their accounts and transactions!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_person(pid)
            self._load_people()

    # ── Banks methods ────────────────────────────────────────────────────────

    def _load_banks(self):
        self.banks_table.setRowCount(0)
        for b in get_all_banks():
            r = self.banks_table.rowCount()
            self.banks_table.insertRow(r)
            self.banks_table.setItem(r, 0, QTableWidgetItem(b.get("nickname") or "—"))
            self.banks_table.setItem(r, 1, QTableWidgetItem(b.get("bank_name") or ""))
            self.banks_table.setItem(r, 2, QTableWidgetItem(b.get("tan_code") or "—"))
            self.banks_table.setItem(r, 3, QTableWidgetItem(b.get("created_at") or "—"))
            self.banks_table.setItem(r, 4, QTableWidgetItem(str(b["bank_id"])))
            self.banks_table.setRowHeight(r, 32)

    def _on_add_bank(self):
        dlg = BankDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            add_bank(data["bank_name"], nickname=data["nickname"])
            if data.get("tan_code"):
                bid_row = [b for b in get_all_banks() if (b.get("bank_name") or "").lower() == data["bank_name"].lower()]
                if bid_row:
                    update_bank(bid_row[0]["bank_id"], data["bank_name"], data["nickname"], data["tan_code"])
            self._load_banks()

    def _on_edit_bank(self):
        row = self.banks_table.currentRow()
        if row < 0:
            show_warning("Please select a bank.")
            return
        bank_id = int(self.banks_table.item(row, 4).text())
        data = get_bank(bank_id)
        if not data:
            show_warning("Bank record no longer exists.")
            self._load_banks()
            return

        dlg = BankDialog(self, data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            update_bank(bank_id, payload["bank_name"], payload["nickname"], payload["tan_code"])
            self._load_banks()

    def _on_delete_bank(self):
        row = self.banks_table.currentRow()
        if row < 0:
            show_warning("Please select a bank.")
            return
        bank_id = int(self.banks_table.item(row, 4).text())
        bank_name = self.banks_table.item(row, 1).text()
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete bank '{bank_name}'?\n\nOnly bank master row will be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_bank(bank_id)
            self._load_banks()

    # ── Accounts methods ────────────────────────────────────────────────────────

    def _load_accounts(self):
        self.accounts_table.setRowCount(0)
        for acc in get_all_accounts():
            r = self.accounts_table.rowCount()
            self.accounts_table.insertRow(r)
            self.accounts_table.setItem(r, 0, QTableWidgetItem(acc.get("person_name","—")))
            self.accounts_table.setItem(r, 1, QTableWidgetItem(acc.get("bank_display_name") or acc["bank_name"]))
            self.accounts_table.setItem(r, 2, QTableWidgetItem(acc.get("tan_code") or "—"))
            self.accounts_table.setItem(r, 3, QTableWidgetItem(acc["account_type"]))
            self.accounts_table.setItem(r, 4, QTableWidgetItem(acc.get("account_number_masked") or "—"))
            self.accounts_table.setItem(r, 5, QTableWidgetItem(acc.get("ifsc_code") or "—"))
            self.accounts_table.setItem(r, 6, QTableWidgetItem(f"₹ {acc['opening_balance']:,.2f}"))
            self.accounts_table.setItem(r, 7, QTableWidgetItem(f"₹ {acc['current_balance']:,.2f}"))
            self.accounts_table.setItem(r, 8, QTableWidgetItem(str(acc["account_id"])))
            self.accounts_table.setRowHeight(r, 32)

    def _on_add_account(self):
        persons = get_all_persons()
        if not persons:
            show_warning("Add a family member first.")
            return
        dlg = AccountDialog(self, persons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            account_id = add_account(**payload)
            from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
            get_or_create_bank(payload.get("bank_name") or "")
            if tan_code:
                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)

            # Save account holders
            for holder in dlg._holders_data:
                add_account_holder(account_id, holder["person_id"], holder["is_primary"])

            self._load_accounts()

    def _on_edit_account(self):
        row = self.accounts_table.currentRow()
        if row < 0:
            show_warning("Select an account.")
            return
        aid = int(self.accounts_table.item(row, 8).text())
        accounts = get_all_accounts()
        acc_data = next((a for a in accounts if a["account_id"] == aid), None)
        if not acc_data:
            return
        dlg = AccountDialog(self, get_all_persons(), acc_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            update_account(aid, **payload)
            from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
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

    def _on_delete_account(self):
        row = self.accounts_table.currentRow()
        if row < 0:
            show_warning("Select an account.")
            return
        aid = int(self.accounts_table.item(row, 8).text())
        name = self.accounts_table.item(row, 1).text()
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete account '{name}'?\n\nAll transactions for this account will also be deleted!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_account(aid)
            self._load_accounts()
