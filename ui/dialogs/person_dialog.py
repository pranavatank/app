"""
ui/dialogs/person_dialog.py — Person management dialog
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QMessageBox, QDateEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from models.person import add_person, get_all_persons, update_person, delete_person


class PersonManagementDialog(QDialog):
    """Dialog to manage persons (family members)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Family Members")
        self.setMinimumSize(700, 500)
        self._build_ui()
        self._load_persons()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Family Members")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("+ Add Person")
        btn_add.setObjectName("primaryBtn")
        btn_add.clicked.connect(self._on_add_person)
        header.addWidget(btn_add)

        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Name", "Date of Birth", "PAN", "Notes", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(4, True)  # Hide ID column
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_edit_person)
        layout.addWidget(self.table)

        # Actions
        actions = QHBoxLayout()
        actions.addStretch()

        btn_edit = QPushButton("Edit")
        btn_edit.setObjectName("secondaryBtn")
        btn_edit.clicked.connect(self._on_edit_person)
        actions.addWidget(btn_edit)

        btn_delete = QPushButton("Delete")
        btn_delete.setObjectName("dangerBtn")
        btn_delete.clicked.connect(self._on_delete_person)
        actions.addWidget(btn_delete)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)

        layout.addLayout(actions)

    def _load_persons(self):
        """Load all persons into table."""
        persons = get_all_persons()
        self.table.setRowCount(0)

        for person in persons:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(person["full_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(person.get("date_of_birth") or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(person.get("pan_number") or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(person.get("contact_notes") or "—"))
            self.table.setItem(row, 4, QTableWidgetItem(str(person["person_id"])))

    def _on_add_person(self):
        """Add new person."""
        dialog = PersonDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            add_person(**data)
            self._load_persons()
            QMessageBox.information(self, "Success", "Person added successfully!")

    def _on_edit_person(self):
        """Edit selected person."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a person to edit.")
            return

        person_id = int(self.table.item(row, 4).text())
        person_data = {
            "person_id": person_id,
            "full_name": self.table.item(row, 0).text(),
            "date_of_birth": self.table.item(row, 1).text() if self.table.item(row, 1).text() != "—" else None,
            "pan_number": self.table.item(row, 2).text() if self.table.item(row, 2).text() != "—" else None,
            "contact_notes": self.table.item(row, 3).text() if self.table.item(row, 3).text() != "—" else None,
        }

        dialog = PersonDialog(self, person_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            update_person(person_id, **data)
            self._load_persons()
            QMessageBox.information(self, "Success", "Person updated successfully!")

    def _on_delete_person(self):
        """Delete selected person."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a person to delete.")
            return

        person_id = int(self.table.item(row, 4).text())
        name = self.table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete person '{name}'?\n\nThis will also delete all associated accounts and transactions!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_person(person_id)
            self._load_persons()
            QMessageBox.information(self, "Deleted", "Person deleted successfully!")


class PersonDialog(QDialog):
    """Dialog for adding/editing a person."""

    def __init__(self, parent=None, person_data=None):
        super().__init__(parent)
        self.person_data = person_data
        self.setWindowTitle("Edit Person" if person_data else "Add Person")
        self.setMinimumWidth(400)
        self._build_ui()

        if person_data:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(12)

        # Full Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., John Doe")
        form.addRow("Full Name *:", self.name_input)

        # Date of Birth
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDate(QDate.currentDate())
        self.dob_input.setDisplayFormat("dd-MM-yyyy")
        form.addRow("Date of Birth:", self.dob_input)

        # PAN Number
        self.pan_input = QLineEdit()
        self.pan_input.setPlaceholderText("e.g., ABCDE1234F")
        self.pan_input.setMaxLength(10)
        form.addRow("PAN Number:", self.pan_input)

        # Contact Notes
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional notes")
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

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

    def _load_data(self):
        """Load existing person data."""
        self.name_input.setText(self.person_data.get("full_name", ""))
        
        dob = self.person_data.get("date_of_birth")
        if dob:
            qdate = QDate.fromString(dob, "yyyy-MM-dd")
            if qdate.isValid():
                self.dob_input.setDate(qdate)

        self.pan_input.setText(self.person_data.get("pan_number") or "")
        self.notes_input.setText(self.person_data.get("contact_notes") or "")

    def _on_save(self):
        """Validate and save."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Field", "Please enter a name.")
            return

        self.accept()

    def get_data(self) -> dict:
        """Get form data."""
        return {
            "full_name": self.name_input.text().strip(),
            "date_of_birth": self.dob_input.date().toString("yyyy-MM-dd"),
            "pan_number": self.pan_input.text().strip() or None,
            "contact_notes": self.notes_input.text().strip() or None,
        }
