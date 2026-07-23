"""
ui/dialogs/account_metadata_dialog.py — Confirm account metadata from statement
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QCheckBox, QFrame, QScrollArea, QWidget, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import icon_label
from models.bank_account import update_account


class AccountMetadataDialog(QDialog):
    """Dialog to review and confirm account metadata extracted from statement."""

    def __init__(self, parent, account_id: int, account_name: str, metadata: dict):
        super().__init__(parent)
        self.account_id = account_id
        self.metadata = metadata
        self.setWindowTitle(f"Update Account Details - {account_name}")
        self.setMinimumSize(920, 680)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with gradient
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.gradient(Theme.SUCCESS_GRADIENT_START, Theme.SUCCESS_GRADIENT_END)};
                border-radius: 0;
            }}
        """)
        header_frame.setFixedHeight(104)
        
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(28, 0, 28, 0)
        header_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(icon_label("account_found", size=22, color="#FFFFFF"))
        title = QLabel("Account Details Found")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        title_row.addWidget(title)
        title_row.addStretch()
        header_layout.addLayout(title_row)
        
        subtitle = QLabel("Review and confirm the information extracted from your bank statement")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 13px; background: transparent;")
        header_layout.addWidget(subtitle)

        total_detected = sum(1 for v in self.metadata.values() if str(v or "").strip())
        helper = QLabel(f"Detected {total_detected} fields. You can edit before saving.")
        helper.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px; background: transparent;")
        header_layout.addWidget(helper)
        
        layout.addWidget(header_frame)

        # Content area
        content_widget = QWidget()
        content_widget.setStyleSheet(f"background: {Theme.BG};")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(28, 24, 28, 24)

        # Top summary row
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        info_frame = QFrame()
        info_frame.setObjectName("MetaInfoCard")
        info_frame.setStyleSheet(
            Theme.card_style(
                bg=Theme.INFO_LIGHT,
                border_color=Theme.INFO,
                radius=10,
                padding=0,
                left_accent=Theme.INFO,
                selector="QFrame#MetaInfoCard",
            )
        )
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(10)

        info_icon = QLabel("ℹ️")
        info_icon.setFont(QFont("Segoe UI Emoji", 16))
        info_icon.setStyleSheet("background: transparent; border: none;")
        info_layout.addWidget(info_icon)

        info_text = QLabel(
            "You can edit any field before updating. "
            "Use the checkbox below if you want to skip updates."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(Theme.text_style(color=Theme.INFO_DARK, size=13) + " border: none;")
        info_layout.addWidget(info_text, stretch=1)
        top_row.addWidget(info_frame, 2)

        stats_frame = QFrame()
        stats_frame.setObjectName("MetaStatsCard")
        stats_frame.setStyleSheet(
            Theme.tinted_surface_style(radius=10, border_color=Theme.BORDER, selector="QFrame#MetaStatsCard")
        )
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(6)

        stats_title = QLabel("Quick Summary")
        stats_title.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))
        stats_layout.addWidget(stats_title)

        stats_values = QLabel(f"Fields detected: {total_detected}")
        stats_values.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=12))
        stats_layout.addWidget(stats_values)

        top_row.addWidget(stats_frame, 1)
        content_layout.addLayout(top_row)

        # Scroll area for fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {Theme.BG}; border: none;")

        fields_container = QWidget()
        fields_container.setStyleSheet(f"background: {Theme.BG};")
        fields_layout = QVBoxLayout(fields_container)
        fields_layout.setSpacing(14)
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
            section_frame.setObjectName("MetadataSectionCard")
            section_frame.setStyleSheet(
                Theme.card_style(
                    bg=Theme.SURFACE,
                    border_color=Theme.BORDER,
                    radius=12,
                    padding=0,
                    selector="QFrame#MetadataSectionCard",
                )
            )
            
            section_layout = QVBoxLayout(section_frame)
            section_layout.setSpacing(12)
            section_layout.setContentsMargins(18, 14, 18, 14)

            # Section title
            section_label = QLabel(section_title)
            section_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            section_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=700))
            section_layout.addWidget(section_label)

            # Divider
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet(f"background: {Theme.DIVIDER}; border: none;")
            section_layout.addWidget(div)

            # Fields grid
            grid = QGridLayout()
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(10)
            grid.setColumnStretch(1, 1)

            row = 0
            for key, label in section_fields:
                value = self.metadata.get(key)
                if not value:
                    continue

                # Label
                field_label = QLabel(f"{label}:")
                field_label.setStyleSheet(Theme.section_label_style())
                field_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                grid.addWidget(field_label, row, 0)

                # Input widget
                if key in multiline_fields:
                    widget = QTextEdit()
                    widget.setPlainText(value)
                    widget.setMaximumHeight(82)
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
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(12)

        # Update checkbox
        self.update_check = QCheckBox("Update account with these details")
        self.update_check.setChecked(True)
        self.update_check.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=600))
        self.update_check.setAccessibleName("Update account checkbox")
        footer_layout.addWidget(self.update_check)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_skip = Theme.btn("Skip", "secondary", height=40, min_width=104)
        btn_skip.setAccessibleName("Skip account metadata update")
        btn_skip.clicked.connect(self.reject)
        btn_layout.addWidget(btn_skip)

        btn_confirm = Theme.btn("Confirm & Update", "primary", height=40, min_width=168)
        btn_confirm.setAccessibleName("Confirm account metadata update")
        btn_confirm.clicked.connect(self._on_confirm)
        btn_layout.addWidget(btn_confirm)

        first_field = next(iter(self.fields.values()), None)
        if first_field is not None:
            self.setTabOrder(self.update_check, first_field)
            self.setTabOrder(btn_skip, btn_confirm)

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
