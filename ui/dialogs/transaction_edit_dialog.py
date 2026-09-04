"""
ui/dialogs/transaction_edit_dialog.py — Quick edit dialog for transactions in preview
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QDateEdit, QFormLayout, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import icon_label
from config import INCOME_CATEGORIES, EXPENSE_CATEGORIES, TRANSACTION_MODES


class TransactionEditDialog(QDialog):
    def __init__(self, parent=None, transaction_data=None, is_preview=False):
        super().__init__(parent)
        self.transaction_data = transaction_data or {}
        self.is_preview = is_preview
        self.setWindowTitle("Edit Transaction")
        self.setMinimumWidth(500)
        self._build_ui()
        if transaction_data:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(icon_label("edit", size=20, color=Theme.PRIMARY))
        title = QLabel("Edit Transaction")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setProperty("textrole", "title-sm")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setFixedHeight(38)
        self.date_edit.setAccessibleName("Transaction date")
        self.date_edit.setAccessibleDescription("Edit the date for this transaction.")
        self.date_edit.setToolTip("Edit the date for this transaction.")
        self.date_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Date:"), self.date_edit)

        # Type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Income", "Expense"])
        self.type_combo.setFixedHeight(38)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.type_combo.setAccessibleName("Transaction type")
        self.type_combo.setAccessibleDescription("Choose whether the transaction is income or expense.")
        self.type_combo.setToolTip("Choose whether the transaction is income or expense.")
        self.type_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Type:"), self.type_combo)

        # Mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(TRANSACTION_MODES)
        self.mode_combo.setEditable(True)
        self.mode_combo.setFixedHeight(38)
        self.mode_combo.setAccessibleName("Transaction mode")
        self.mode_combo.setAccessibleDescription("Edit or choose the transaction mode.")
        self.mode_combo.setToolTip("Edit or choose the transaction mode.")
        self.mode_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Mode:"), self.mode_combo)

        # Category
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setFixedHeight(38)
        self.category_combo.setAccessibleName("Transaction category")
        self.category_combo.setAccessibleDescription("Edit or choose the transaction category.")
        self.category_combo.setToolTip("Edit or choose the transaction category.")
        self.category_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Category:"), self.category_combo)

        # Amount
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        self.amount_edit.setFixedHeight(38)
        self.amount_edit.setAccessibleName("Transaction amount")
        self.amount_edit.setAccessibleDescription("Enter the transaction amount.")
        self.amount_edit.setToolTip("Enter the transaction amount.")
        self.amount_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Amount:"), self.amount_edit)

        # Balance After
        self.balance_edit = QLineEdit()
        self.balance_edit.setPlaceholderText("Optional")
        self.balance_edit.setFixedHeight(38)
        self.balance_edit.setAccessibleName("Balance after transaction")
        self.balance_edit.setAccessibleDescription("Enter the account balance after the transaction, if known.")
        self.balance_edit.setToolTip("Enter the account balance after the transaction, if known.")
        self.balance_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Balance After:"), self.balance_edit)

        # Description
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Transaction description")
        self.description_edit.setFixedHeight(38)
        self.description_edit.setAccessibleName("Transaction description")
        self.description_edit.setAccessibleDescription("Edit the description for this transaction.")
        self.description_edit.setToolTip("Edit the description for this transaction.")
        self.description_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Description:"), self.description_edit)

        # Reference
        self.reference_edit = QLineEdit()
        self.reference_edit.setPlaceholderText("Reference number")
        self.reference_edit.setFixedHeight(38)
        self.reference_edit.setAccessibleName("Reference number")
        self.reference_edit.setAccessibleDescription("Edit the transaction reference number, if available.")
        self.reference_edit.setToolTip("Edit the transaction reference number, if available.")
        self.reference_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        form.addRow(self._label("Reference:"), self.reference_edit)

        layout.addLayout(form)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {Theme.BORDER};")
        layout.addWidget(div)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        
        btn_cancel = Theme.btn("Cancel", "secondary", height=38, min_width=100)
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setShortcut("Escape")
        btn_cancel.setAccessibleName("Cancel transaction edit")
        btn_cancel.setAccessibleDescription("Close the dialog without saving changes.")
        btns.addWidget(btn_cancel)
        
        btn_save = Theme.btn("Save", "primary", height=38, min_width=100)
        btn_save.clicked.connect(self.accept)
        btn_save.setDefault(True)
        btn_save.setShortcut("Return")
        btn_save.setAccessibleName("Save transaction edit")
        btn_save.setAccessibleDescription("Save the edited transaction details.")
        btns.addWidget(btn_save)
        
        layout.addLayout(btns)

        self.setTabOrder(self.date_edit, self.type_combo)
        self.setTabOrder(self.type_combo, self.mode_combo)
        self.setTabOrder(self.mode_combo, self.category_combo)
        self.setTabOrder(self.category_combo, self.amount_edit)
        self.setTabOrder(self.amount_edit, self.balance_edit)
        self.setTabOrder(self.balance_edit, self.description_edit)
        self.setTabOrder(self.description_edit, self.reference_edit)
        self.setTabOrder(self.reference_edit, btn_cancel)
        self.setTabOrder(btn_cancel, btn_save)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("textrole", "section-label")
        return lbl

    def _on_type_changed(self, txn_type: str):
        """Update category dropdown based on type"""
        self.category_combo.clear()
        if txn_type == "Income":
            self.category_combo.addItems(INCOME_CATEGORIES)
        else:
            self.category_combo.addItems(EXPENSE_CATEGORIES)

    def _load_data(self):
        """Load transaction data into form"""
        # Date
        date_str = self.transaction_data.get("transaction_date", "")
        if date_str:
            qdate = QDate.fromString(date_str, "yyyy-MM-dd")
            if qdate.isValid():
                self.date_edit.setDate(qdate)

        # Type
        txn_type = self.transaction_data.get("transaction_type", "Expense")
        if txn_type in ["Income", "Expense"]:
            self.type_combo.setCurrentText(txn_type)
        
        # Trigger category update
        self._on_type_changed(txn_type)

        # Mode
        mode = self.transaction_data.get("mode", "")
        if mode:
            self.mode_combo.setCurrentText(mode)

        # Category
        category = self.transaction_data.get("category", "")
        if category:
            self.category_combo.setCurrentText(category)

        # Amount
        amount = self.transaction_data.get("amount", 0)
        self.amount_edit.setText(str(amount))

        # Balance
        balance = self.transaction_data.get("balance_after")
        if balance is not None:
            self.balance_edit.setText(str(balance))

        # Description
        desc = self.transaction_data.get("description", "")
        self.description_edit.setText(desc)

        # Reference
        ref = self.transaction_data.get("reference_no", "")
        self.reference_edit.setText(ref)

    def get_data(self) -> dict:
        """Get edited transaction data"""
        balance_text = self.balance_edit.text().strip()
        try:
            balance_after = float(balance_text) if balance_text else None
        except ValueError:
            balance_after = None

        try:
            amount = float(self.amount_edit.text().strip() or "0")
        except ValueError:
            amount = 0.0

        return {
            "transaction_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "transaction_type": self.type_combo.currentText(),
            "mode": self.mode_combo.currentText().strip() or None,
            "category": self.category_combo.currentText().strip() or None,
            "amount": amount,
            "balance_after": balance_after,
            "description": self.description_edit.text().strip() or None,
            "reference_no": self.reference_edit.text().strip() or None,
        }
