"""
ui/dialogs/account_metadata_dialog.py — Confirm account metadata from statement
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QCheckBox, QFrame, QScrollArea, QWidget, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from models.bank_account import update_account


class AccountMetadataDialog(QDialog):
    """Dialog to review and confirm account metadata extracted from statement."""

    def __init__(self, parent, account_id: int, account_name: str, metadata: dict):
        super().__init__(parent)
        self.account_id = account_id
        self.metadata = metadata
        self.setWindowTitle(f"Update Account Details - {account_name}")
        self.setMinimumSize(800, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with gradient
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.SUCCESS}, stop:1 {Theme.SUCCESS_DARK});
                border-radius: 0;
            }}
        """)
        header_frame.setFixedHeight(90)
        
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(28, 0, 28, 0)
        header_layout.setSpacing(6)
        
        title = QLabel("📄 Account Details Found")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        header_layout.addWidget(title)
        
        subtitle = QLabel("Review and confirm the information extracted from your bank statement")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 13px; background: transparent;")
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header_frame)

        # Content area
        content_widget = QWidget()
        content_widget.setStyleSheet(f"background: {Theme.BG};")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(28, 24, 28, 24)

        # Info message
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.INFO_LIGHT};
                border: 1px solid {Theme.INFO};
                border-left: 4px solid {Theme.INFO};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setSpacing(12)
        
        info_icon = QLabel("ℹ️")
        info_icon.setFont(QFont("Segoe UI Emoji", 16))
        info_icon.setStyleSheet("background: transparent; border: none;")
        info_layout.addWidget(info_icon)
        
        info_text = QLabel(
            "You can edit any field before updating. "
            "Uncheck the box below if you don't want to update the account."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(f"color: {Theme.INFO_DARK}; font-size: 13px; background: transparent; border: none;")
        info_layout.addWidget(info_text, stretch=1)
        
        content_layout.addWidget(info_frame)

        # Scroll area for fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {Theme.BG}; border: none;")

        fields_container = QWidget()
        fields_container.setStyleSheet(f"background: {Theme.BG};")
        fields_layout = QVBoxLayout(fields_container)
        fields_layout.setSpacing(16)
        fields_layout.setContentsMargins(0, 0, 0, 0)

        # Create fields for each metadata item
        self.fields = {}
        
        sections = {
            "Account Information": [
                ('customer_id', 'Customer ID'),
                ('account_number_full', 'Account Number'),
                ('ckyc_id', 'CKYC ID'),
                ('account_opening_date', 'Opening Date'),
                ('account_status', 'Account Status'),
                ('account_type', 'Account Type'),
                ('currency', 'Currency'),
            ],
            "Bank Details": [
                ('ifsc_code', 'IFSC Code'),
                ('micr_code', 'MICR Code'),
                ('branch_name', 'Branch Name'),
                ('branch_address', 'Branch Address'),
            ],
            "Contact Information": [
                ('email_id', 'Email ID'),
                ('phone_no', 'Phone Number'),
                ('communication_address', 'Communication Address'),
            ],
            "Nomination": [
                ('nomination_status', 'Nomination Status'),
                ('nominee_name', 'Nominee Name'),
            ],
        }

        multiline_fields = ['branch_address', 'communication_address']

        for section_title, section_fields in sections.items():
            # Check if section has any data
            has_data = any(self.metadata.get(key) for key, _ in section_fields)
            if not has_data:
                continue

            # Section card
            section_frame = QFrame()
            section_frame.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.SURFACE};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 12px;
                    padding: 0;
                }}
            """)
            
            section_layout = QVBoxLayout(section_frame)
            section_layout.setSpacing(14)
            section_layout.setContentsMargins(20, 16, 20, 16)

            # Section title
            section_label = QLabel(section_title)
            section_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            section_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
            section_layout.addWidget(section_label)

            # Divider
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet(f"background: {Theme.DIVIDER}; border: none;")
            section_layout.addWidget(div)

            # Fields grid
            grid = QGridLayout()
            grid.setSpacing(12)
            grid.setColumnStretch(1, 1)

            row = 0
            for key, label in section_fields:
                value = self.metadata.get(key)
                if not value:
                    continue

                # Label
                field_label = QLabel(f"{label}:")
                field_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; background: transparent;")
                field_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                grid.addWidget(field_label, row, 0)

                # Input widget
                if key in multiline_fields:
                    widget = QTextEdit()
                    widget.setPlainText(value)
                    widget.setMaximumHeight(70)
                else:
                    widget = QLineEdit(value)
                
                grid.addWidget(widget, row, 1)
                self.fields[key] = widget
                row += 1

            section_layout.addLayout(grid)
            fields_layout.addWidget(section_frame)

        fields_layout.addStretch()
        scroll.setWidget(fields_container)
        content_layout.addWidget(scroll)

        layout.addWidget(content_widget)

        # Footer with checkbox and buttons
        footer_frame = QFrame()
        footer_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border-top: 1px solid {Theme.BORDER};
            }}
        """)
        footer_layout = QVBoxLayout(footer_frame)
        footer_layout.setContentsMargins(28, 16, 28, 16)
        footer_layout.setSpacing(12)

        # Update checkbox
        self.update_check = QCheckBox("✓ Update account with these details")
        self.update_check.setChecked(True)
        self.update_check.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        footer_layout.addWidget(self.update_check)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_skip = QPushButton("Skip")
        btn_skip.setObjectName("secondaryBtn")
        btn_skip.setFixedHeight(38)
        btn_skip.setFixedWidth(100)
        btn_skip.clicked.connect(self.reject)
        btn_layout.addWidget(btn_skip)

        btn_confirm = QPushButton("Confirm & Update")
        btn_confirm.setObjectName("primaryBtn")
        btn_confirm.setFixedHeight(38)
        btn_confirm.setFixedWidth(160)
        btn_confirm.clicked.connect(self._on_confirm)
        btn_layout.addWidget(btn_confirm)

        footer_layout.addLayout(btn_layout)
        layout.addWidget(footer_frame)

    def _on_confirm(self):
        """Update account with confirmed metadata."""
        if not self.update_check.isChecked():
            self.accept()
            return

        # Collect updated values from fields
        update_data = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QTextEdit):
                value = widget.toPlainText().strip()
            else:
                value = widget.text().strip()
            
            if value:
                update_data[key] = value

        # Update account
        if update_data:
            # Generate masked account number if full number provided
            if 'account_number_full' in update_data and 'account_number_masked' not in update_data:
                from engines.statement_metadata_extractor import mask_account_number
                update_data['account_number_masked'] = mask_account_number(update_data['account_number_full'])
            
            update_account(self.account_id, **update_data)

        self.accept()
