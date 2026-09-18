"""
ui/dialogs/income_expectation_dialog.py — Income expectation CRUD and transaction linking dialogs.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFormLayout, QDateEdit, QDoubleSpinBox, QTextEdit, QMessageBox, QFrame, QSpinBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from ui.theme import Theme
from ui.icons import set_btn_icon, set_btn_icon_auto
from ui.widgets.toast_utils import show_warning
from ui.widgets.excel_table import ExcelTableWithStats
from ui.widgets.money_label import format_inr
from config import get_all_financial_years, fy_date_range
from models.bank_account import get_accounts_for_person
from models.transaction import get_transactions
from models.income_expectation import (
    link_actual_transaction, unlink_actual_transaction, get_income_expectations
)


# Income types used in the app
INCOME_TYPES = ["Salary", "Rent", "Interest", "Dividend", "Business", "Freelance", "Other"]
FREQUENCIES = ["One-Time", "Monthly", "Quarterly", "Half-Yearly", "Annual"]


def _btn(text: str, style: str = "primary") -> QPushButton:
    """Quick button factory."""
    return Theme.btn(text, style, height=36, min_width=100)


class IncomeExpectationDialog(QDialog):
    """Dialog for adding/editing income expectations."""

    def __init__(self, parent=None, persons=None, existing=None, preselect_person_id=None):
        """
        Args:
            parent: Parent widget
            persons: List of person dicts with 'person_id' and 'full_name' keys
            existing: Existing expectation dict (for editing mode)
            preselect_person_id: Person ID to preselect if not in existing mode
        """
        super().__init__(parent)
        self.persons = persons or []
        self.existing = existing
        self.preselect_person_id = preselect_person_id
        self._linking_dialog = None

        self.setWindowTitle("Edit Income Expectation" if existing else "Add Income Expectation")
        self.setMinimumWidth(500)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        """Build dialog layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        # Form fields
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Person
        self.person_combo = QComboBox()
        self.person_combo.addItem("— Select Person —", None)
        for p in self.persons:
            self.person_combo.addItem(p.get("full_name", ""), p.get("person_id"))
        self.person_combo.setMinimumHeight(36)
        self.person_combo.setMaximumWidth(Theme.INPUT_SELECT_LONG_MAX_WIDTH)
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        self.person_combo.setAccessibleName("Person")
        form.addRow("Person *:", self.person_combo)

        # Account
        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(36)
        self.account_combo.setMaximumWidth(Theme.INPUT_SELECT_LONG_MAX_WIDTH)
        self.account_combo.setAccessibleName("Account")
        form.addRow("Account *:", self.account_combo)

        # Income Type
        self.income_type_combo = QComboBox()
        self.income_type_combo.addItems(INCOME_TYPES)
        self.income_type_combo.setMinimumHeight(36)
        self.income_type_combo.setMaximumWidth(Theme.INPUT_SELECT_LONG_MAX_WIDTH)
        self.income_type_combo.setAccessibleName("Income Type")
        form.addRow("Income Type *:", self.income_type_combo)

        # Expected Amount
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setMinimum(0.01)
        self.amount_spin.setMaximum(99999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("₹ ")
        self.amount_spin.setMinimumHeight(36)
        self.amount_spin.setMaximumWidth(Theme.INPUT_CURRENCY_MAX_WIDTH)
        self.amount_spin.setAccessibleName("Expected Amount")
        form.addRow("Expected Amount *:", self.amount_spin)

        # Frequency
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(FREQUENCIES)
        self.frequency_combo.setMinimumHeight(36)
        self.frequency_combo.setMaximumWidth(Theme.INPUT_SELECT_LONG_MAX_WIDTH)
        self.frequency_combo.currentIndexChanged.connect(self._on_frequency_changed)
        self.frequency_combo.setAccessibleName("Frequency")
        form.addRow("Frequency *:", self.frequency_combo)

        # Expected Date (switches between day spinner and date edit)
        date_layout = QHBoxLayout()

        # Day of month spinner (for recurring)
        self.day_spin = QSpinBox()
        self.day_spin.setMinimum(1)
        self.day_spin.setMaximum(31)
        self.day_spin.setMinimumHeight(36)
        self.day_spin.setMaximumWidth(Theme.INPUT_CURRENCY_MAX_WIDTH)
        self.day_spin.setAccessibleName("Day of Month")
        date_layout.addWidget(self.day_spin)

        # Full date picker (for one-time/annual)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setMinimumHeight(36)
        self.date_edit.setMaximumWidth(Theme.INPUT_DATE_MAX_WIDTH)
        self.date_edit.setAccessibleName("Expected Date")
        date_layout.addWidget(self.date_edit)
        date_layout.addStretch()

        form.addRow("Expected Date *:", date_layout)
        self._on_frequency_changed()  # Set initial visibility

        # Financial Year
        self.fy_combo = QComboBox()
        fy_list = get_all_financial_years(since_year=2020)
        self.fy_combo.addItems(fy_list)
        self.fy_combo.setMinimumHeight(36)
        self.fy_combo.setMaximumWidth(Theme.INPUT_SELECT_LONG_MAX_WIDTH)
        self.fy_combo.setAccessibleName("Financial Year")
        form.addRow("Financial Year *:", self.fy_combo)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional notes about this income expectation")
        self.notes_edit.setMinimumHeight(68)
        self.notes_edit.setAccessibleName("Notes")
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        # Linking section (only show if editing)
        if self.existing:
            layout.addSpacing(6)
            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet(f"color: {Theme.BORDER};")
            layout.addWidget(div)
            layout.addSpacing(6)

            # Link info panel
            self.link_panel = self._build_link_panel()
            layout.addWidget(self.link_panel)

        layout.addStretch()

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {Theme.BORDER};")
        layout.addWidget(div)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = _btn("Cancel", "secondary")
        btn_cancel.setAccessibleName("Cancel income expectation dialog")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save_text = "Save" if self.existing else "Add"
        btn_save = _btn(btn_save_text, "primary")
        btn_save.setAccessibleName(f"{btn_save_text} income expectation")
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

        self.setTabOrder(self.person_combo, self.account_combo)
        self.setTabOrder(self.account_combo, self.income_type_combo)
        self.setTabOrder(self.income_type_combo, self.amount_spin)
        self.setTabOrder(self.amount_spin, self.frequency_combo)

    def _build_link_panel(self) -> QFrame:
        """Build the transaction linking panel for editing."""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SUCCESS_LIGHT};
                border: 1px solid {Theme.SUCCESS};
                border-radius: {Theme.RADIUS_CONTROL}px;
                padding: 12px 16px;
            }}
        """)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        txn_id = self.existing.get("actual_transaction_id")

        if txn_id:
            # Show linked transaction info
            info_text = f"Linked to Txn #{txn_id}"
            if self.existing.get("actual_date"):
                info_text += f" ({self.existing.get('actual_date')})"
            if self.existing.get("actual_amount"):
                info_text += f" · {format_inr(self.existing.get('actual_amount'))}"

            lbl = QLabel(info_text)
            lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
            lbl.setStyleSheet(f"color: {Theme.SUCCESS_DARK};")
            layout.addWidget(lbl)

            layout.addStretch()

            btn_unlink = _btn("  Unlink", "destructive")
            set_btn_icon_auto(btn_unlink, "unlink")
            btn_unlink.setAccessibleName("Unlink transaction")
            btn_unlink.clicked.connect(self._on_unlink_transaction)
            layout.addWidget(btn_unlink)
        else:
            # Show "Link Transaction" button
            lbl = QLabel("No transaction linked")
            lbl.setFont(QFont("Segoe UI", 12))
            lbl.setStyleSheet(f"color: {Theme.SUCCESS_DARK};")
            layout.addWidget(lbl)

            layout.addStretch()

            btn_link = _btn("  Link Transaction", "success")
            set_btn_icon(btn_link, "link")
            btn_link.setAccessibleName("Link actual transaction")
            btn_link.clicked.connect(self._on_link_transaction)
            layout.addWidget(btn_link)

        return panel

    def _on_person_changed(self):
        """Refresh accounts when person changes."""
        person_id = self.person_combo.currentData()
        self.account_combo.clear()

        if person_id:
            try:
                accounts = get_accounts_for_person(person_id)
                self.account_combo.addItem("— Select Account —", None)
                for acc in accounts:
                    label = f"{acc.get('bank_display_name') or acc.get('bank_name')} ({acc.get('account_type')})"
                    self.account_combo.addItem(label, acc.get("account_id"))
            except Exception as e:
                show_warning(f"Error loading accounts: {e}")

    def _on_frequency_changed(self):
        """Toggle date input visibility based on frequency."""
        freq = self.frequency_combo.currentText()

        if freq in ("Monthly", "Quarterly", "Half-Yearly"):
            # Show day spinner, hide date edit
            self.day_spin.setVisible(True)
            self.date_edit.setVisible(False)
        else:  # One-Time, Annual
            # Hide day spinner, show date edit
            self.day_spin.setVisible(False)
            self.date_edit.setVisible(True)

    def _on_link_transaction(self):
        """Open LinkActualDialog."""
        person_id = self.person_combo.currentData()
        account_id = self.account_combo.currentData()

        if not person_id or not account_id:
            show_warning("Please select Person and Account first.")
            return

        dlg = LinkActualDialog(self, self.existing, person_id, account_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            txn_id = dlg.get_selected_transaction_id()
            if txn_id:
                link_actual_transaction(self.existing["expectation_id"], txn_id)
                # Refresh the link panel
                self.existing["actual_transaction_id"] = txn_id
                # Rebuild link panel (remove old one first)
                layout = self.layout()
                for i in range(layout.count()):
                    widget = layout.itemAt(i).widget()
                    if widget and widget.objectName() == "LinkPanel":
                        layout.removeWidget(widget)
                        widget.deleteLater()
                self.link_panel = self._build_link_panel()
                # Re-insert at correct position (after divider, before next divider)
                layout.insertWidget(layout.count() - 3, self.link_panel)

    def _on_unlink_transaction(self):
        """Unlink transaction with confirmation."""
        reply = QMessageBox.question(
            self,
            "Confirm Unlink",
            "Unlink this income expectation from its matched transaction?\n\nThe expectation will remain but will not be linked to a specific transaction.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            unlink_actual_transaction(self.existing["expectation_id"])
            self.existing["actual_transaction_id"] = None
            # Rebuild link panel
            layout = self.layout()
            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if widget == self.link_panel:
                    layout.removeWidget(widget)
                    widget.deleteLater()
            self.link_panel = self._build_link_panel()
            layout.insertWidget(layout.count() - 3, self.link_panel)

    def _load_data(self):
        """Load existing data if editing."""
        if not self.existing:
            # Preselect person if provided
            if self.preselect_person_id:
                for i in range(self.person_combo.count()):
                    if self.person_combo.itemData(i) == self.preselect_person_id:
                        self.person_combo.setCurrentIndex(i)
                        break
            return

        # Editing mode: load data
        person_id = self.existing.get("person_id")
        account_id = self.existing.get("account_id")

        # Set person
        for i in range(self.person_combo.count()):
            if self.person_combo.itemData(i) == person_id:
                self.person_combo.setCurrentIndex(i)
                break

        # Refresh accounts and set account
        self._on_person_changed()
        for i in range(self.account_combo.count()):
            if self.account_combo.itemData(i) == account_id:
                self.account_combo.setCurrentIndex(i)
                break

        # Set income type
        income_type = self.existing.get("income_type")
        idx = self.income_type_combo.findText(income_type)
        if idx >= 0:
            self.income_type_combo.setCurrentIndex(idx)

        # Set amount
        self.amount_spin.setValue(self.existing.get("expected_amount", 0))

        # Set frequency
        freq = self.existing.get("frequency", "One-Time")
        idx = self.frequency_combo.findText(freq)
        if idx >= 0:
            self.frequency_combo.setCurrentIndex(idx)

        # Set expected date
        expected_date_str = self.existing.get("expected_date")
        if freq in ("Monthly", "Quarterly", "Half-Yearly"):
            # Day of month
            try:
                self.day_spin.setValue(int(expected_date_str))
            except (ValueError, TypeError):
                self.day_spin.setValue(1)
        else:
            # Full date
            try:
                qd = QDate.fromString(expected_date_str, "yyyy-MM-dd")
                if qd.isValid():
                    self.date_edit.setDate(qd)
            except Exception:
                pass

        # Set financial year
        fy = self.existing.get("financial_year")
        idx = self.fy_combo.findText(fy)
        if idx >= 0:
            self.fy_combo.setCurrentIndex(idx)
        self.fy_combo.setEnabled(False)  # Disable in edit mode

        # Set notes
        notes = self.existing.get("notes")
        if notes:
            self.notes_edit.setText(notes)

    def _on_save(self):
        """Validate and accept dialog."""
        if not self.person_combo.currentData():
            show_warning("Please select a Person.")
            return

        if not self.account_combo.currentData():
            show_warning("Please select an Account.")
            return

        if self.amount_spin.value() <= 0:
            show_warning("Expected Amount must be greater than 0.")
            return

        self.accept()

    def get_data(self) -> dict:
        """Return dialog data as a dict matching add_income_expectation() kwargs."""
        freq = self.frequency_combo.currentText()

        if freq in ("Monthly", "Quarterly", "Half-Yearly"):
            expected_date = str(self.day_spin.value())
        else:
            expected_date = self.date_edit.date().toString("yyyy-MM-dd")

        return {
            "person_id": self.person_combo.currentData(),
            "account_id": self.account_combo.currentData(),
            "income_type": self.income_type_combo.currentText(),
            "expected_amount": self.amount_spin.value(),
            "expected_date": expected_date,
            "frequency": freq,
            "financial_year": self.fy_combo.currentText(),
            "notes": self.notes_edit.toPlainText().strip() or None,
        }


class LinkActualDialog(QDialog):
    """Dialog for selecting and linking an actual transaction to an expectation."""

    def __init__(self, parent=None, expectation=None, person_id=None, account_id=None):
        """
        Args:
            parent: Parent widget
            expectation: Existing expectation dict (for context)
            person_id: Person ID to filter transactions
            account_id: Account ID to filter transactions
        """
        super().__init__(parent)
        self.expectation = expectation or {}
        self.person_id = person_id
        self.account_id = account_id
        self._selected_txn_id = None

        self.setWindowTitle("Link Transaction")
        self.setMinimumSize(700, 400)
        self._build_ui()
        self._load_transactions()

    def _build_ui(self):
        """Build dialog layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Instructions
        instructions = QLabel("Select a transaction to link with this income expectation:")
        instructions.setFont(QFont("Segoe UI", 12))
        layout.addWidget(instructions)

        # Transaction table (read-only, single selection)
        self.table_widget = ExcelTableWithStats(show_checkboxes=False, read_only=True)
        self.table = self.table_widget.table
        self.table.setHeaders(["Date", "Category", "Amount", "Description", "ID"])
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setColumnHidden(4, True)  # Hide ID column
        self.table.setAccessibleName("Available transactions")
        self.table.setAccessibleDescription("List of unlinked income transactions available to link.")
        self.table.setSortingEnabled(False)
        self.table_widget.setMinimumHeight(300)
        layout.addWidget(self.table_widget)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = _btn("Cancel", "secondary")
        btn_cancel.setAccessibleName("Cancel transaction linking")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_link = _btn("Link", "success")
        set_btn_icon(btn_link, "link")
        btn_link.setAccessibleName("Link selected transaction")
        btn_link.clicked.connect(self._on_link)
        btns.addWidget(btn_link)
        layout.addLayout(btns)

    def _load_transactions(self):
        """Load unlinked income transactions for the selected account/FY."""
        self.table.setRowCount(0)

        if not self.person_id or not self.account_id:
            return

        try:
            fy = self.expectation.get("financial_year")
            fy_start, fy_end = fy_date_range(fy) if fy else (None, None)

            # Get all income transactions
            txns = get_transactions(
                person_id=self.person_id,
                account_id=self.account_id,
                transaction_type="Income"
            )

            # Filter: only within FY, and not already linked
            linked_ids = set()
            existing = get_income_expectations(
                person_id=self.person_id,
                financial_year=fy
            )
            for exp in existing:
                if exp.get("actual_transaction_id"):
                    linked_ids.add(exp["actual_transaction_id"])

            for txn in txns:
                txn_id = txn.get("transaction_id")
                if txn_id in linked_ids:
                    continue

                # Filter by date range if FY is set
                if fy_start and fy_end:
                    txn_date_str = txn.get("transaction_date")
                    try:
                        txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d").date()
                        if not (fy_start.date() <= txn_date <= fy_end.date()):
                            continue
                    except (ValueError, AttributeError):
                        continue

                row_data = [
                    txn.get("transaction_date", "—"),
                    txn.get("category", "—"),
                    format_inr(txn.get("amount", 0)),
                    txn.get("description", "—"),
                    str(txn_id)
                ]
                self.table.addDataRow(row_data, user_data=txn_id)

                # Right-align amount
                row = self.table.rowCount() - 1
                amount_item = self.table.item(row, 2)
                if amount_item:
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        except Exception as e:
            show_warning(f"Error loading transactions: {e}")

    def _on_link(self):
        """Accept and store selected transaction."""
        current_row = self.table.currentRow()
        if current_row < 0:
            show_warning("Please select a transaction to link.")
            return

        # Get the ID from the hidden ID column
        id_item = self.table.item(current_row, 4)
        if id_item:
            self._selected_txn_id = int(id_item.text())
            self.accept()

    def get_selected_transaction_id(self):
        """Return the selected transaction ID, or None if not selected."""
        return self._selected_txn_id
