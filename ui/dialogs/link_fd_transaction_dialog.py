"""
ui/dialogs/link_fd_transaction_dialog.py — Dialog for linking FD to a transaction.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

from ui.theme import Theme
from ui.date_utils import format_display_date
from models.transaction import display_transaction_type
from models.fixed_deposit import (
    get_fd_link_candidates, link_fd_transaction, unlink_fd_transaction
)


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

        btn_unlink = Theme.btn("Unlink", "danger", height=36, min_width=90)
        btn_unlink.clicked.connect(self._on_unlink)
        btns.addWidget(btn_unlink)

        btn_cancel = Theme.btn("Cancel", "secondary", height=36, min_width=90)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_link = Theme.btn("Link Selected", "primary", height=36, min_width=120)
        btn_link.clicked.connect(self._on_link)
        btns.addWidget(btn_link)

        layout.addLayout(btns)

    def _load_rows(self):
        rows = get_fd_link_candidates(self.fd_id)
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(format_display_date(row.get("transaction_date"))))
            self.table.setItem(r, 1, QTableWidgetItem(display_transaction_type(row.get("transaction_type") or "—")))
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
