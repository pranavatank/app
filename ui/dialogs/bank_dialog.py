"""
ui/dialogs/bank_dialog.py — Bank management dialog with person-like operations.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from models.bank import add_bank, get_all_banks, get_bank, update_bank, delete_bank


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
    else:
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
        title = QLabel("Banks")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        btn_add = _btn("＋  Add Bank", "primary")
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
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        actions.addStretch()
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
            QMessageBox.warning(self, "No Selection", "Please select a bank.")
            return
        bank_id = int(self.table.item(row, 4).text())
        data = get_bank(bank_id)
        if not data:
            QMessageBox.warning(self, "Not Found", "Bank record no longer exists.")
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
            QMessageBox.warning(self, "No Selection", "Please select a bank.")
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
        form.addRow("Nickname:", self.nickname_input)

        self.bank_name_input = QLineEdit()
        self.bank_name_input.setPlaceholderText("Actual bank name, e.g. HDFC Bank")
        self.bank_name_input.setFixedHeight(40)
        form.addRow("Bank Name *:", self.bank_name_input)

        self.tan_input = QLineEdit()
        self.tan_input.setPlaceholderText("Optional TAN")
        self.tan_input.setMaxLength(10)
        self.tan_input.setFixedHeight(40)
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
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btn_save = _btn("Save", "primary")
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _load_data(self):
        self.nickname_input.setText(self.bank_data.get("nickname") or "")
        self.bank_name_input.setText(self.bank_data.get("bank_name") or "")
        self.tan_input.setText((self.bank_data.get("tan_code") or "").upper())

    def _on_save(self):
        if not self.bank_name_input.text().strip():
            QMessageBox.warning(self, "Missing", "Please enter bank name.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "nickname": self.nickname_input.text().strip() or None,
            "bank_name": self.bank_name_input.text().strip(),
            "tan_code": self.tan_input.text().strip().upper() or None,
        }
