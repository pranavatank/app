"""
ui/dialogs/bank_dialog.py — Bank management dialog with person-like operations.
"""

import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import icon_label, set_btn_icon
from ui.widgets.excel_table import enable_copy_shortcut
from ui.widgets.toast_utils import show_warning
from models.bank import add_bank, get_all_banks, get_bank, update_bank, delete_bank


def _btn(text: str, style: str = "primary") -> QPushButton:
    return Theme.btn(text, style, height=36, min_width=100)


class BankManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Banks")
        self.setMinimumSize(760, 520)
        self._build_ui()
        self._load_banks()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

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
        btn_add.clicked.connect(self._on_add)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Nickname", "Bank Name (Actual)", "TAN", "Created", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(4, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        enable_copy_shortcut(self.table)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAccessibleName("Bank list")
        self.table.setAccessibleDescription("Table of bank masters with nickname, actual name, TAN, and created date.")
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_edit = _btn("  Edit", "edit")
        set_btn_icon(btn_edit, "edit")
        btn_edit.setAccessibleName("Edit bank")
        btn_edit.clicked.connect(self._on_edit)
        actions.addWidget(btn_edit)
        btn_del = _btn("  Delete", "danger")
        set_btn_icon(btn_del, "delete")
        btn_del.setAccessibleName("Delete bank")
        btn_del.clicked.connect(self._on_delete)
        actions.addWidget(btn_del)
        btn_close = _btn("Close", "secondary")
        btn_close.setAccessibleName("Close bank manager")
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)

    def _load_banks(self):
        self.table.setRowCount(0)
        for b in get_all_banks():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(b.get("nickname") or "—"))
            self.table.setItem(r, 1, QTableWidgetItem(b.get("bank_name") or ""))
            self.table.setItem(r, 2, QTableWidgetItem(b.get("tan_code") or "—"))
            self.table.setItem(r, 3, QTableWidgetItem(b.get("created_at") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(str(b["bank_id"])))
            self.table.setRowHeight(r, 32)

    def _on_add(self):
        dlg = BankDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            add_bank(data["bank_name"], nickname=data["nickname"])
            if data.get("tan_code"):
                bid_row = [b for b in get_all_banks() if (b.get("bank_name") or "").lower() == data["bank_name"].lower()]
                if bid_row:
                    update_bank(bid_row[0]["bank_id"], data["bank_name"], data["nickname"], data["tan_code"])
            self._load_banks()

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0:
            show_warning("Please select a bank.")
            return
        bank_id = int(self.table.item(row, 4).text())
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

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            show_warning("Please select a bank.")
            return
        bank_id = int(self.table.item(row, 4).text())
        bank_name = self.table.item(row, 1).text()
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete bank '{bank_name}'?\n\nOnly bank master row will be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_bank(bank_id)
            self._load_banks()


class BankDialog(QDialog):
    def __init__(self, parent=None, bank_data=None):
        super().__init__(parent)
        self.bank_data = bank_data
        self.setWindowTitle("Edit Bank" if bank_data else "Add Bank")
        self.setMinimumWidth(460)
        self._build_ui()
        if bank_data:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("Display name in UI, e.g. Salary Bank")
        self.nickname_input.setFixedHeight(40)
        self.nickname_input.setAccessibleName("Bank nickname")
        form.addRow("Nickname:", self.nickname_input)

        self.bank_name_input = QLineEdit()
        self.bank_name_input.setPlaceholderText("Actual bank name, e.g. HDFC Bank")
        self.bank_name_input.setFixedHeight(40)
        self.bank_name_input.setAccessibleName("Bank name")
        form.addRow("Bank Name *:", self.bank_name_input)

        self.tan_input = QLineEdit()
        self.tan_input.setPlaceholderText("Optional TAN")
        self.tan_input.setMaxLength(10)
        self.tan_input.setFixedHeight(40)
        self.tan_input.setAccessibleName("Bank TAN")
        self.tan_input.textChanged.connect(
            lambda txt: self.tan_input.setText((txt or "").upper()) if (txt or "") != (txt or "").upper() else None
        )
        form.addRow("TAN:", self.tan_input)

        layout.addLayout(form)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {Theme.BORDER};")
        layout.addWidget(div)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = _btn("Cancel", "secondary")
        btn_cancel.setAccessibleName("Cancel bank dialog")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btn_save = _btn("Save", "primary")
        btn_save.setAccessibleName("Save bank")
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

        self.setTabOrder(self.nickname_input, self.bank_name_input)
        self.setTabOrder(self.bank_name_input, self.tan_input)
        self.setTabOrder(self.tan_input, btn_cancel)
        self.setTabOrder(btn_cancel, btn_save)

    def _load_data(self):
        self.nickname_input.setText(self.bank_data.get("nickname") or "")
        self.bank_name_input.setText(self.bank_data.get("bank_name") or "")
        self.tan_input.setText((self.bank_data.get("tan_code") or "").upper())

    def _on_save(self):
        if not self.bank_name_input.text().strip():
            show_warning("Please enter bank name.")
            return
        tan = self.tan_input.text().strip().upper()
        if tan and not re.fullmatch(r"[A-Z]{4}[0-9]{5}[A-Z]", tan):
            show_warning("TAN must be 10 characters in the format ABCD12345E.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "nickname": self.nickname_input.text().strip() or None,
            "bank_name": self.bank_name_input.text().strip(),
            "tan_code": self.tan_input.text().strip().upper() or None,
        }
