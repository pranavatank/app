"""
ui/dialogs/income_source_dialog.py — Income source management dialog.

Create/edit income sources (employers, companies, banks, etc.).
"""

import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QTextEdit, QPushButton, QFormLayout, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import icon_label
from models.income_source import (
    save_income_source, get_income_source, SOURCE_TYPES
)


class IncomeSourceDialog(QDialog):
    """Dialog for creating/editing income sources."""
    
    def __init__(self, source_id: int = None, parent=None):
        super().__init__(parent)
        self.source_id = source_id
        self.setWindowTitle("Income Source" if not source_id else "Edit Income Source")
        self.setMinimumWidth(550)
        self._build_ui()
        if source_id:
            self._load_data()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(icon_label("income_src", size=20, color=Theme.PRIMARY))
        title = QLabel("Add Income Source" if not self.source_id else "Edit Income Source")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setProperty("textrole", "title-md")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)
        
        # Form
        form_frame = QFrame()
        form_frame.setStyleSheet(Theme.card_style(radius=10, padding=16))
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(12)
        
        # Source Type
        self.type_combo = QComboBox()
        self.type_combo.addItems(SOURCE_TYPES)
        self.type_combo.setFixedHeight(36)
        self.type_combo.setAccessibleName("Income source type")
        form_layout.addRow("Source Type:", self.type_combo)
        
        # Source Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., ABC Company Ltd")
        self.name_input.setFixedHeight(36)
        self.name_input.setAccessibleName("Income source name")
        form_layout.addRow("Name:*", self.name_input)
        
        # TAN
        self.tan_input = QLineEdit()
        self.tan_input.setPlaceholderText("e.g., ABCD12345E")
        self.tan_input.setFixedHeight(36)
        self.tan_input.setMaxLength(10)
        self.tan_input.setAccessibleName("Income source TAN")
        form_layout.addRow("TAN:", self.tan_input)
        
        # PAN
        self.pan_input = QLineEdit()
        self.pan_input.setPlaceholderText("e.g., ABCDE1234F")
        self.pan_input.setFixedHeight(36)
        self.pan_input.setMaxLength(10)
        self.pan_input.setAccessibleName("Income source PAN")
        form_layout.addRow("PAN:", self.pan_input)
        
        # Address
        self.address_input = QTextEdit()
        self.address_input.setPlaceholderText("Full address")
        self.address_input.setMaximumHeight(80)
        self.address_input.setAccessibleName("Income source address")
        form_layout.addRow("Address:", self.address_input)
        
        # Contact Person
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Contact person name")
        self.contact_input.setFixedHeight(36)
        self.contact_input.setAccessibleName("Contact person")
        form_layout.addRow("Contact Person:", self.contact_input)
        
        # Phone
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Phone number")
        self.phone_input.setFixedHeight(36)
        self.phone_input.setAccessibleName("Phone number")
        form_layout.addRow("Phone:", self.phone_input)
        
        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email address")
        self.email_input.setFixedHeight(36)
        self.email_input.setAccessibleName("Email address")
        form_layout.addRow("Email:", self.email_input)
        
        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Additional notes")
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setAccessibleName("Income source notes")
        form_layout.addRow("Notes:", self.notes_input)
        
        layout.addWidget(form_frame)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = Theme.btn("Cancel", "secondary", height=38, min_width=100)
        btn_cancel.setAccessibleName("Cancel income source dialog")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_save = Theme.btn("Save", "primary", height=38, min_width=100)
        btn_save.setAccessibleName("Save income source")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)

        self.setTabOrder(self.type_combo, self.name_input)
        self.setTabOrder(self.name_input, self.tan_input)
        self.setTabOrder(self.tan_input, self.pan_input)
        self.setTabOrder(self.pan_input, self.address_input)
        self.setTabOrder(self.address_input, self.contact_input)
        self.setTabOrder(self.contact_input, self.phone_input)
        self.setTabOrder(self.phone_input, self.email_input)
        self.setTabOrder(self.email_input, self.notes_input)
        self.setTabOrder(self.notes_input, btn_cancel)
        self.setTabOrder(btn_cancel, btn_save)
        
        layout.addLayout(btn_layout)
    
    def _load_data(self):
        """Load existing source data."""
        source = get_income_source(self.source_id)
        if not source:
            return
        
        self.type_combo.setCurrentText(source.get("source_type", ""))
        self.name_input.setText(source.get("source_name", ""))
        self.tan_input.setText(source.get("tan", ""))
        self.pan_input.setText(source.get("pan", ""))
        self.address_input.setPlainText(source.get("address", ""))
        self.contact_input.setText(source.get("contact_person", ""))
        self.phone_input.setText(source.get("phone", ""))
        self.email_input.setText(source.get("email", ""))
        self.notes_input.setPlainText(source.get("notes", ""))
    
    def _save(self):
        """Save income source."""
        name = self.name_input.text().strip()
        if not name:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Validation Error", "Source name is required.")
            return
        
        tan = self.tan_input.text().strip().upper()
        if tan and not re.fullmatch(r"[A-Z]{4}[0-9]{5}[A-Z]", tan):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid TAN", "TAN must be 10 characters in the format ABCD12345E.")
            return

        pan = self.pan_input.text().strip().upper()
        if pan and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid PAN", "PAN must be 10 characters in the format ABCDE1234F.")
            return

        email = self.email_input.text().strip()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
            return

        phone = self.phone_input.text().strip()
        if phone and not re.fullmatch(r"[0-9]{10}", re.sub(r"[\s\-+]", "", phone).removeprefix("91")):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Phone", "Please enter a valid 10-digit phone number.")
            return

        try:
            save_income_source(
                source_type=self.type_combo.currentText(),
                source_name=name,
                tan=tan if tan else None,
                pan=self.pan_input.text().strip().upper() or None,
                address=self.address_input.toPlainText().strip() or None,
                contact_person=self.contact_input.text().strip() or None,
                phone=self.phone_input.text().strip() or None,
                email=self.email_input.text().strip() or None,
                notes=self.notes_input.toPlainText().strip() or None,
            )
            self.accept()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Save Error", f"Failed to save income source:\n{str(e)}")
