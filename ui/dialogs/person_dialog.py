"""
ui/dialogs/person_dialog.py — Person management dialog with clean theme styling.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QMessageBox, QDateEdit, QFrame
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.date_utils import format_display_date
from models.person import add_person, get_all_persons, get_person, update_person, delete_person


def _btn(text: str, style: str = "primary") -> QPushButton:
    """Create a consistently styled button."""
    b = QPushButton(text)
    styles = {
        "primary": (Theme.PRIMARY, Theme.PRIMARY_DARK),
        "success": (Theme.SUCCESS, Theme.SUCCESS_DARK),
        "danger":  (Theme.DANGER,  Theme.DANGER_DARK),
        "secondary": None,
    }
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
    else:
        c1, c2 = styles[style]
        b.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c1},stop:1 {c2});
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 700;
                min-height: 32px;
            }}
            QPushButton:hover {{ background-color: {c2}; }}
        """)
    return b


class PersonManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Family Members")
        self.setMinimumSize(720, 520)
        self._build_ui()
        self._load_persons()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Family Members")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        btn_add = _btn("＋  Add Person", "primary")
        btn_add.clicked.connect(self._on_add)
        header.addWidget(btn_add)
        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Nickname", "Date of Birth", "PAN", "Notes", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(4, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        # Actions
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

    def _load_persons(self):
        self.table.setRowCount(0)
        for p in get_all_persons():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(p.get("full_name") or ""))
            self.table.setItem(r, 1, QTableWidgetItem(format_display_date(p.get("date_of_birth"))))
            self.table.setItem(r, 2, QTableWidgetItem(p.get("pan_number") or "—"))
            self.table.setItem(r, 3, QTableWidgetItem(p.get("contact_notes") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(str(p["person_id"])))
            self.table.setRowHeight(r, 32)

    def _on_add(self):
        dlg = PersonDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            add_person(**dlg.get_data())
            self._load_persons()

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a person."); return
        pid  = int(self.table.item(row, 4).text())
        data = get_person(pid)
        if not data:
            QMessageBox.warning(self, "Not Found", "Person record no longer exists.")
            self._load_persons()
            return
        dlg = PersonDialog(self, data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            update_person(pid, **dlg.get_data())
            self._load_persons()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a person."); return
        pid  = int(self.table.item(row, 4).text())
        name = self.table.item(row, 0).text()
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete '{name}'?\n\nThis will also delete all their accounts and transactions!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_person(pid)
            self._load_persons()


class PersonDialog(QDialog):
    def __init__(self, parent=None, person_data=None):
        super().__init__(parent)
        self.person_data = person_data
        self.setWindowTitle("Edit Person" if person_data else "Add Person")
        self.setMinimumWidth(420)
        self._build_ui()
        if person_data:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("e.g. Rajesh")
        self.nickname_input.setFixedHeight(40)
        form.addRow("Nickname *:", self.nickname_input)

        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("e.g. Rajesh")
        self.first_name_input.setFixedHeight(40)
        form.addRow("First Name:", self.first_name_input)

        self.middle_name_input = QLineEdit()
        self.middle_name_input.setPlaceholderText("e.g. Kumar")
        self.middle_name_input.setFixedHeight(40)
        form.addRow("Middle Name:", self.middle_name_input)

        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("e.g. Sharma")
        self.last_name_input.setFixedHeight(40)
        form.addRow("Last Name:", self.last_name_input)

        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDate(QDate.currentDate())
        self.dob_input.setDisplayFormat("dd/MM/yy")
        self.dob_input.setFixedHeight(40)
        form.addRow("Date of Birth:", self.dob_input)

        self.pan_input = QLineEdit()
        self.pan_input.setPlaceholderText("e.g. ABCDE1234F")
        self.pan_input.setMaxLength(10)
        self.pan_input.setFixedHeight(40)
        form.addRow("PAN Number:", self.pan_input)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional notes")
        self.notes_input.setFixedHeight(40)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        # Divider
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {Theme.BORDER};")
        layout.addWidget(div)

        btns = QHBoxLayout(); btns.addStretch()
        btn_cancel = _btn("Cancel", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btn_save = _btn("Save", "primary")
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _load_data(self):
        self.nickname_input.setText(self.person_data.get("full_name", ""))
        self.first_name_input.setText(self.person_data.get("first_name") or "")
        self.middle_name_input.setText(self.person_data.get("middle_name") or "")
        self.last_name_input.setText(self.person_data.get("last_name") or "")
        dob = self.person_data.get("date_of_birth")
        if dob:
            qd = QDate.fromString(dob, "yyyy-MM-dd")
            if qd.isValid(): self.dob_input.setDate(qd)
        self.pan_input.setText(self.person_data.get("pan_number") or "")
        self.notes_input.setText(self.person_data.get("contact_notes") or "")

    def _on_save(self):
        if not self.nickname_input.text().strip():
            QMessageBox.warning(self, "Missing", "Please enter a nickname."); return
        self.accept()

    def get_data(self) -> dict:
        return {
            "full_name":     self.nickname_input.text().strip(),
            "first_name":    self.first_name_input.text().strip() or None,
            "middle_name":   self.middle_name_input.text().strip() or None,
            "last_name":     self.last_name_input.text().strip() or None,
            "date_of_birth": self.dob_input.date().toString("yyyy-MM-dd"),
            "pan_number":    self.pan_input.text().strip() or None,
            "contact_notes": self.notes_input.text().strip() or None,
        }
