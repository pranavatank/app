"""
ui/transactions_screen.py — Transaction management with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QFormLayout, QDateEdit, QDoubleSpinBox, QTextEdit,
    QMessageBox, QFrame, QAbstractItemView, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from ui.widgets.excel_table import ExcelTableWithStats

from ui.theme import Theme
from ui.date_utils import format_display_date
from core.session import session
from config import (
    INCOME_CATEGORIES, EXPENSE_CATEGORIES,
    TRANSACTION_MODES, get_all_financial_years, get_current_financial_year
)
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person, get_all_accounts
from models.transaction import (
    get_transactions, add_transaction, update_transaction, delete_transaction,
    reprocess_internal_transfers
)

_COL_DATE=0; _COL_TYPE=1; _COL_CAT=2; _COL_MODE=3; _COL_REF=4; _COL_DESC=5
_COL_AMOUNT=6; _COL_BAL=7; _COL_ACCT=8; _COL_PERSON=9; _COL_ID=10


class _DateSortItem(QTableWidgetItem):
    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        left_iso = self.data(Qt.ItemDataRole.UserRole)
        right_iso = other.data(Qt.ItemDataRole.UserRole)
        if left_iso and right_iso:
            left_date = QDate.fromString(str(left_iso), "yyyy-MM-dd")
            right_date = QDate.fromString(str(right_iso), "yyyy-MM-dd")
            if left_date.isValid() and right_date.isValid():
                return left_date < right_date
        return super().__lt__(other)


class TransactionsScreen(QWidget):
    def __init__(self, parent_window=None):
        super().__init__()
        self._parent_window = parent_window
        self._all_persons: list[dict] = []
        self._all_accounts: list[dict] = []
        self._current_rows: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(16)

        # Action bar
        layout.addWidget(self._build_action_bar())
        # Filter bar
        layout.addWidget(self._build_filter_bar())
        # Table
        layout.addWidget(self._build_table(), stretch=1)
        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        layout.addWidget(self.status_label)

    def _build_action_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("actionBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.btn_add = QPushButton("＋  Add Transaction")
        self.btn_add.setObjectName("primaryBtn")
        self.btn_add.setFixedHeight(40)
        self.btn_add.clicked.connect(self._add_transaction)
        layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("✏  Edit")
        self.btn_edit.setObjectName("secondaryBtn")
        self.btn_edit.setFixedHeight(40)
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._edit_transaction)
        layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑  Delete")
        self.btn_delete.setObjectName("dangerBtn")
        self.btn_delete.setFixedHeight(40)
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_transaction)
        layout.addWidget(self.btn_delete)

        self.btn_reprocess = QPushButton("Reprocess Data")
        self.btn_reprocess.setObjectName("secondaryBtn")
        self.btn_reprocess.setFixedHeight(40)
        self.btn_reprocess.clicked.connect(self._reprocess_data)
        layout.addWidget(self.btn_reprocess)

        layout.addStretch()

        # Pill badges
        self.lbl_income_sum  = self._badge("Income: —",  Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK)
        self.lbl_expense_sum = self._badge("Expense: —", Theme.DANGER_LIGHT,  Theme.DANGER_DARK)
        self.lbl_net_sum     = self._badge("Net: —",     Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK)
        layout.addWidget(self.lbl_income_sum)
        layout.addWidget(self.lbl_expense_sum)
        layout.addWidget(self.lbl_net_sum)

        return bar

    def _badge(self, text, bg, fg) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border-radius: 12px;
            padding: 5px 14px;
            font-size: 12px;
            font-weight: 600;
        """)
        return lbl

    def _build_filter_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("filterBar")
        bar.setStyleSheet(f"""
            QFrame#filterBar {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Theme.TEXT_SECONDARY};")
            return l

        layout.addWidget(lbl("Person"))
        self.f_person = QComboBox(); self.f_person.setFixedWidth(140); self.f_person.setFixedHeight(32)
        self.f_person.addItem("All Persons", userData=None)
        self.f_person.currentIndexChanged.connect(self._on_filter_person_changed)
        layout.addWidget(self.f_person)

        layout.addWidget(lbl("Account"))
        self.f_account = QComboBox(); self.f_account.setFixedWidth(180); self.f_account.setFixedHeight(32)
        self.f_account.addItem("All Accounts", userData=None)
        layout.addWidget(self.f_account)

        layout.addWidget(lbl("FY"))
        self.f_fy = QComboBox(); self.f_fy.setFixedWidth(95); self.f_fy.setFixedHeight(32)
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.f_fy.addItem(fy)
        self.f_fy.setCurrentText(session.selected_fy)
        layout.addWidget(self.f_fy)

        layout.addWidget(lbl("Type"))
        self.f_type = QComboBox(); self.f_type.setFixedWidth(110); self.f_type.setFixedHeight(32)
        self.f_type.addItems(["All Types", "Income", "Expense", "Transfer"])
        layout.addWidget(self.f_type)

        layout.addWidget(lbl("Search"))
        self.f_search = QLineEdit(); self.f_search.setPlaceholderText("description / category …")
        self.f_search.setFixedWidth(180); self.f_search.setFixedHeight(32)
        layout.addWidget(self.f_search)

        layout.addStretch()

        btn_filter = QPushButton("Apply")
        btn_filter.setFixedHeight(32); btn_filter.setFixedWidth(80)
        btn_filter.clicked.connect(self.refresh)
        layout.addWidget(btn_filter)

        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("secondaryBtn")
        btn_clear.setFixedHeight(32); btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self._clear_filters)
        layout.addWidget(btn_clear)

        return bar

    def _build_table(self) -> QWidget:
        headers = ["Date","Type","Category","Mode","Reference No","Description","Amount (₹)","Balance After (₹)","Account","Person","ID"]
        self.table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.table = self.table_widget.table
        self.table.editable = True  # Enable editing for certain columns
        self.table.setHeaders(headers)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setSortingEnabled(True)
        self.table.cellDataChanged.connect(self._on_table_data_changed)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate([40,90,80,130,100,150,210,110,130,160,120,0]):
            self.table.setColumnWidth(i, w)
        self.table.setColumnHidden(_COL_ID+1, True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._edit_transaction)
        return self.table_widget

    def refresh(self):
        self._reload_filter_persons()
        self._fetch_and_display()

    def _reload_filter_persons(self):
        self.f_person.blockSignals(True)
        self.f_person.clear()
        self._all_persons = get_all_persons()
        self.f_person.addItem("All Persons", userData=None)
        for p in self._all_persons:
            self.f_person.addItem(p["full_name"], userData=p["person_id"])
        if session.selected_person_id:
            for i in range(self.f_person.count()):
                if self.f_person.itemData(i) == session.selected_person_id:
                    self.f_person.setCurrentIndex(i); break
        self.f_person.blockSignals(False)
        self._reload_filter_accounts()

    def _reload_filter_accounts(self):
        self.f_account.blockSignals(True)
        self.f_account.clear()
        pid = self.f_person.currentData()
        if pid is None:
            self._all_accounts = get_all_accounts()
            self.f_account.addItem("All Accounts", userData=None)
            for a in self._all_accounts:
                self.f_account.addItem(f"{a['person_name']} — {a.get('bank_display_name', a['bank_name'])} ({a['account_type']})", userData=a["account_id"])
        else:
            self._all_accounts = get_accounts_for_person(pid)
            self.f_account.addItem("All Accounts", userData=None)
            for a in self._all_accounts:
                self.f_account.addItem(f"{a.get('bank_display_name', a['bank_name'])} ({a['account_type']})", userData=a["account_id"])
        self.f_account.blockSignals(False)

    def _fetch_and_display(self):
        pid  = self.f_person.currentData()
        aid  = self.f_account.currentData()
        fy   = self.f_fy.currentText() or None
        typ  = self.f_type.currentText()
        typ  = None if typ == "All Types" else typ
        term = self.f_search.text().strip().lower()

        rows = get_transactions(account_id=aid, person_id=pid, financial_year=fy, transaction_type=typ)
        if term:
            rows = [r for r in rows if term in (r.get("description") or "").lower()
                    or term in (r.get("category") or "").lower()
                    or term in (r.get("reference_no") or "").lower()]

        self._current_rows = rows
        self._populate_table(rows)
        self._update_pills(rows)
        self.btn_edit.setEnabled(False)
        self.btn_delete.setEnabled(False)

    def _populate_table(self, rows):
        # Block signals during refresh
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        type_colors = {
            "Income":   QColor(Theme.SUCCESS),
            "Expense":  QColor(Theme.DANGER),
            "Transfer": QColor(Theme.INFO),
        }

        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # Add checkbox widget in column 0
            cb = QCheckBox()
            cb.setChecked(False)
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(r, 0, cb_widget)
            
            txn_type = row.get("transaction_type", "")
            color    = type_colors.get(txn_type, QColor(Theme.TEXT_PRIMARY))

            def item(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text) if text is not None else "—")
                it.setForeground(color)
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            def amt_item(val):
                it = QTableWidgetItem(f"{val:,.2f}" if val is not None else "—")
                it.setForeground(color)
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                return it

            date_display = format_display_date(row.get("transaction_date"))
            date_item = _DateSortItem(date_display)
            date_item.setForeground(color)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            date_item.setData(Qt.ItemDataRole.UserRole, row.get("transaction_date"))
            self.table.setItem(r, _COL_DATE+1, date_item)
            
            type_item = item(txn_type)
            self.table.setItem(r, _COL_TYPE+1, type_item)
            
            # Category - editable
            cat_item = item(row.get("category",""))
            cat_item.setFlags(cat_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_CAT+1, cat_item)
            
            # Mode - editable
            mode_item = item(row.get("mode",""))
            mode_item.setFlags(mode_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_MODE+1, mode_item)
            
            # Reference - editable
            ref_item = item(row.get("reference_no") or "—")
            ref_item.setFlags(ref_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_REF+1, ref_item)
            
            # Description - editable
            desc_item = item(row.get("description",""))
            desc_item.setFlags(desc_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_DESC+1, desc_item)
            
            # Amount - editable
            amt_item_val = amt_item(row.get("amount"))
            amt_item_val.setFlags(amt_item_val.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_AMOUNT+1, amt_item_val)
            
            # Balance - editable
            bal_item_val = amt_item(row.get("balance_after"))
            bal_item_val.setFlags(bal_item_val.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_BAL+1, bal_item_val)
            
            self.table.setItem(r, _COL_ACCT+1,   item(row.get("bank_display_name") or row.get("bank_name", "")))
            self.table.setItem(r, _COL_PERSON+1, item(row.get("person_name","")))
            self.table.setItem(r, _COL_ID+1,     QTableWidgetItem(str(row["transaction_id"])))
            self.table.setRowHeight(r, 32)

        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)  # Re-enable signals
        count = self.table.rowCount()
        self.status_label.setText(f"Showing {count} transaction{'s' if count!=1 else ''}.")

    def _update_pills(self, rows):
        income  = sum(
            r["amount"] for r in rows
            if r.get("transaction_type") == "Income" and not r.get("is_internal_transfer")
        )
        expense = sum(
            r["amount"] for r in rows
            if r.get("transaction_type") == "Expense" and not r.get("is_internal_transfer")
        )
        net = income - expense
        self.lbl_income_sum.setText(f"Income: ₹ {income:,.2f}")
        self.lbl_expense_sum.setText(f"Expense: ₹ {expense:,.2f}")
        sign = "+" if net >= 0 else ""
        self.lbl_net_sum.setText(f"Net: {sign}₹ {net:,.2f}")

    def _reprocess_data(self):
        reply = QMessageBox.question(
            self,
            "Reprocess Internal Transfers",
            "This will scan bank-transfer-like entries across all accounts "
            "and relink internal transfers. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        pairs, marked = reprocess_internal_transfers()
        self._fetch_and_display()
        if self._parent_window:
            self._parent_window.refresh_overview()
        QMessageBox.information(
            self,
            "Reprocess Completed",
            f"Linked pairs: {pairs}\nTransactions marked as Internal Transfer: {marked}",
        )

    def _add_transaction(self):
        persons  = get_all_persons()
        accounts = get_all_accounts()
        if not persons:
            QMessageBox.information(self, "No Persons", "Add a family member first.")
            return
        if not accounts:
            QMessageBox.information(self, "No Accounts", "Add a bank account first.")
            return
        dlg = TransactionDialog(self, persons=persons, accounts=accounts,
                                preselect_person_id=session.selected_person_id,
                                preselect_account_id=session.selected_account_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            add_transaction(**dlg.get_data())
            self._fetch_and_display()
            if self._parent_window: self._parent_window.refresh_overview()

    def _edit_transaction(self):
        txn = self._selected_transaction()
        if txn is None: return
        dlg = TransactionDialog(self, persons=get_all_persons(),
                                accounts=get_all_accounts(), existing=txn)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            update_transaction(txn["transaction_id"], data["transaction_date"],
                               data["transaction_type"], data["amount"],
                               data.get("category"), data.get("mode"), data.get("description"), data.get("reference_no"))
            self._fetch_and_display()
            if self._parent_window: self._parent_window.refresh_overview()

    def _delete_transaction(self):
        txn = self._selected_transaction()
        if txn is None: return
        desc = txn.get("description") or f"₹ {txn['amount']:,.2f}"
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete \"{desc}\"?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_transaction(txn["transaction_id"])
            self._fetch_and_display()
            if self._parent_window: self._parent_window.refresh_overview()

    def _selected_transaction(self):
        if not self.table.selectedItems(): return None
        id_item = self.table.item(self.table.currentRow(), _COL_ID+1)
        if id_item is None: return None
        txn_id = int(id_item.text())
        return next((r for r in self._current_rows if r["transaction_id"] == txn_id), None)

    def _on_selection_changed(self):
        has = bool(self.table.selectedItems())
        self.btn_edit.setEnabled(has)
        self.btn_delete.setEnabled(has)

    def _on_table_data_changed(self):
        """Handle data changes in table (after paste or edit)."""
        # Note: Auto-save not implemented to avoid accidental overwrites
        # Users should use Edit button to save changes
        pass

    def _on_filter_person_changed(self): self._reload_filter_accounts()

    def _clear_filters(self):
        self.f_person.setCurrentIndex(0)
        self.f_account.setCurrentIndex(0)
        self.f_fy.setCurrentText(get_current_financial_year())
        self.f_type.setCurrentIndex(0)
        self.f_search.clear()
        self._fetch_and_display()


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
        self.cmb_type.addItems(["Income","Expense","Transfer"])
        self.cmb_type.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Type *", self.cmb_type)

        self.cmb_category = QComboBox()
        self._populate_categories("Income")
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
        self.desc_edit.setFixedHeight(68)
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
        if txn_type == "Income": self.cmb_category.addItems(INCOME_CATEGORIES)
        elif txn_type == "Expense": self.cmb_category.addItems(EXPENSE_CATEGORIES)
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
        typ = txn.get("transaction_type","Income")
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
            QMessageBox.warning(self, "Missing", "Please select an account."); return
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Amount must be > 0."); return
        self.accept()

    def get_data(self) -> dict:
        bal_val = self.bal_spin.value()
        bal = None if bal_val == self.bal_spin.minimum() else bal_val
        return {
            "account_id":       self.cmb_account.currentData(),
            "person_id":        self.cmb_person.currentData(),
            "transaction_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "transaction_type": self.cmb_type.currentText(),
            "category":         self.cmb_category.currentText().strip() or None,
            "mode":             self.cmb_mode.currentText().strip() or None,
            "reference_no":     self.ref_input.text().strip().upper() or None,
            "amount":           self.amount_spin.value(),
            "description":      self.desc_edit.toPlainText().strip() or None,
            "balance_after":    bal,
            "source":           "Manual",
        }
