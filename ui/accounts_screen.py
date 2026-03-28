"""
ui/accounts_screen.py — Beautiful card-based account management screen
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox, QDateEdit,
    QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from ui.theme import Theme
from models.bank_account import get_all_accounts, delete_account
from models.person import get_all_persons
from ui.dialogs.account_dialog import AccountDialog


class AccountsScreen(QWidget):
    """Card-based account management screen."""

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_accounts()

    def _build_ui(self):
        self.setStyleSheet(f"background-color: {Theme.BG};")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # Header
        header = QHBoxLayout()
        title = QLabel("🏛️  Bank Accounts")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("+ Add Account")
        btn_add.setObjectName("primaryBtn")
        btn_add.setFixedHeight(38)
        btn_add.setFixedWidth(140)
        btn_add.clicked.connect(self._on_add_account)
        header.addWidget(btn_add)

        layout.addLayout(header)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {Theme.BG}; border: none;")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet(f"background: {Theme.BG};")
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(20)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)

    def _load_accounts(self):
        """Load all accounts as cards."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        accounts = get_all_accounts()
        
        if not accounts:
            no_data = QLabel("💼  No accounts found. Click '+ Add Account' to create one.")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 15px; padding: 60px; background: transparent;")
            self.cards_layout.addWidget(no_data, 0, 0, 1, 2)
            return

        # Display cards in grid (2 columns)
        for idx, account in enumerate(accounts):
            card = self._create_account_card(account)
            row = idx // 2
            col = idx % 2
            self.cards_layout.addWidget(card, row, col)
        
        # Add stretch to push cards to top
        self.cards_layout.setRowStretch(len(accounts) // 2 + 1, 1)

    def _create_account_card(self, account: dict) -> QFrame:
        """Create a beautiful card for an account."""
        card = QFrame()
        card.setObjectName("accountCard")
        
        # Determine accent color based on account type
        accent_colors = {
            "Savings": Theme.SUCCESS,
            "Current": Theme.PRIMARY,
            "Salary": Theme.TEAL,
            "FD-linked": Theme.WARNING,
        }
        accent = accent_colors.get(account.get('account_type', 'Savings'), Theme.PRIMARY)
        
        card.setStyleSheet(f"""
            QFrame#accountCard {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-left: 4px solid {accent};
                border-radius: 12px;
                padding: 0;
            }}
            QFrame#accountCard:hover {{
                border: 1px solid {accent};
                border-left: 4px solid {accent};
                background-color: {Theme.SURFACE};
            }}
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda e: self._on_card_clicked(account)
        card.setMinimumHeight(180)

        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Bank name and status
        header = QHBoxLayout()
        header.setSpacing(10)
        
        bank_label = QLabel(f"🏦 {account['bank_name']}")
        bank_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bank_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        header.addWidget(bank_label)
        header.addStretch()

        status = account.get('account_status', 'Active')
        status_colors = {
            'Active': (Theme.SUCCESS, Theme.SUCCESS_LIGHT),
            'Inactive': (Theme.WARNING, Theme.WARNING_LIGHT),
            'Closed': (Theme.DANGER, Theme.DANGER_LIGHT),
        }
        status_fg, status_bg = status_colors.get(status, (Theme.TEXT_SECONDARY, Theme.SURFACE_ALT))
        
        status_label = QLabel(status)
        status_label.setStyleSheet(f"""
            background: {status_bg};
            color: {status_fg};
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            border: none;
        """)
        status_label.setFixedHeight(24)
        header.addWidget(status_label)
        layout.addLayout(header)

        # Account type and person
        info_label = QLabel(f"{account['account_type']} • {account.get('person_name', 'Unknown')}")
        info_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px; background: transparent;")
        layout.addWidget(info_label)

        # Account number
        if account.get('account_number_masked'):
            acc_no = QLabel(f"Account: {account['account_number_masked']}")
            acc_no.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; background: transparent;")
            layout.addWidget(acc_no)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {Theme.DIVIDER}; border: none;")
        layout.addWidget(div)

        # Balance
        balance_layout = QHBoxLayout()
        balance_label = QLabel("Current Balance")
        balance_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; background: transparent;")
        balance_layout.addWidget(balance_label)
        balance_layout.addStretch()

        balance_value = QLabel(f"₹ {account['current_balance']:,.2f}")
        balance_value.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        balance_value.setStyleSheet(f"color: {Theme.SUCCESS}; background: transparent;")
        balance_layout.addWidget(balance_value)
        layout.addLayout(balance_layout)

        # IFSC and Branch
        details_parts = []
        if account.get('ifsc_code'):
            details_parts.append(f"IFSC: {account['ifsc_code']}")
        if account.get('branch_name'):
            details_parts.append(account['branch_name'])
        
        if details_parts:
            details_label = QLabel(" • ".join(details_parts))
            details_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; background: transparent;")
            details_label.setWordWrap(True)
            layout.addWidget(details_label)

        # Debit card indicator
        if account.get('debit_card_enabled'):
            card_label = QLabel(f"💳 Debit Card (₹{account.get('debit_card_charges', 0):.0f}/yr)")
            card_label.setStyleSheet(f"color: {Theme.WARNING}; font-size: 11px; font-weight: 600; background: transparent;")
            layout.addWidget(card_label)

        layout.addStretch()
        return card

    def _on_card_clicked(self, account: dict):
        """Show account details dialog."""
        dialog = AccountDetailsDialog(self, account)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_accounts()

    def _on_add_account(self):
        """Add new account."""
        persons = get_all_persons()
        if not persons:
            QMessageBox.warning(
                self, "No Persons",
                "Please add a family member first before adding accounts."
            )
            return

        dialog = AccountDialog(self, persons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_accounts()


class AccountDetailsDialog(QDialog):
    """Detailed view of account with all information."""

    def __init__(self, parent, account: dict):
        super().__init__(parent)
        self.account = account
        self.setWindowTitle(f"{account['bank_name']} - Account Details")
        self.setMinimumSize(750, 650)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with gradient
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.PRIMARY}, stop:1 {Theme.PRIMARY_DARK});
                border-radius: 0;
            }}
        """)
        header_frame.setFixedHeight(80)
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(28, 0, 28, 0)
        
        title = QLabel(f"🏦 {self.account['bank_name']}")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        status = self.account.get('account_status', 'Active')
        status_label = QLabel(status)
        status_label.setStyleSheet(f"""
            background: white;
            color: {Theme.PRIMARY_DARK};
            padding: 6px 16px;
            border-radius: 14px;
            font-weight: 700;
            font-size: 13px;
        """)
        header_layout.addWidget(status_label)
        
        layout.addWidget(header_frame)

        # Scroll area for details
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {Theme.BG}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background: {Theme.BG};")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(28, 24, 28, 24)

        # Account Information Section
        content_layout.addWidget(self._create_section("Account Information", [
            ("Account Type", self.account.get('account_type', '—')),
            ("Account Holder", self.account.get('person_name', '—')),
            ("Account Number", self.account.get('account_number_masked', '—')),
            ("Customer ID", self.account.get('customer_id', '—')),
            ("CKYC ID", self.account.get('ckyc_id', '—')),
            ("Opening Date", self.account.get('account_opening_date', '—')),
            ("Currency", self.account.get('currency', 'INR')),
        ]))

        # Bank Details Section
        content_layout.addWidget(self._create_section("Bank Details", [
            ("IFSC Code", self.account.get('ifsc_code', '—')),
            ("MICR Code", self.account.get('micr_code', '—')),
            ("Branch Name", self.account.get('branch_name', '—')),
            ("Branch Address", self.account.get('branch_address', '—'), True),
        ]))

        # Balance Information
        content_layout.addWidget(self._create_section("Balance Information", [
            ("Opening Balance", f"₹ {self.account.get('opening_balance', 0):,.2f}"),
            ("Current Balance", f"₹ {self.account.get('current_balance', 0):,.2f}"),
            ("Interest Rate", f"{self.account.get('interest_rate', 0):.2f}%"),
        ]))

        # Contact Information
        if self.account.get('email_id') or self.account.get('phone_no') or self.account.get('communication_address'):
            content_layout.addWidget(self._create_section("Contact Information", [
                ("Email", self.account.get('email_id', '—')),
                ("Phone", self.account.get('phone_no', '—')),
                ("Address", self.account.get('communication_address', '—'), True),
            ]))

        # Nomination Details
        if self.account.get('nomination_status'):
            content_layout.addWidget(self._create_section("Nomination", [
                ("Status", self.account.get('nomination_status', '—')),
                ("Nominee Name", self.account.get('nominee_name', '—')),
            ]))

        # Debit Card Details
        if self.account.get('debit_card_enabled'):
            content_layout.addWidget(self._create_section("Debit Card", [
                ("Status", "Enabled"),
                ("Annual Charges", f"₹ {self.account.get('debit_card_charges', 0):,.2f}"),
                ("Effective From", self.account.get('debit_card_effective_from', '—')),
            ]))

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Action buttons
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background: {Theme.SURFACE}; border-top: 1px solid {Theme.BORDER};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(28, 16, 28, 16)
        btn_layout.addStretch()

        btn_edit = QPushButton("✏️ Edit")
        btn_edit.setObjectName("primaryBtn")
        btn_edit.setFixedHeight(38)
        btn_edit.setFixedWidth(100)
        btn_edit.clicked.connect(self._on_edit)
        btn_layout.addWidget(btn_edit)

        btn_delete = QPushButton("🗑️ Delete")
        btn_delete.setObjectName("dangerBtn")
        btn_delete.setFixedHeight(38)
        btn_delete.setFixedWidth(100)
        btn_delete.clicked.connect(self._on_delete)
        btn_layout.addWidget(btn_delete)

        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondaryBtn")
        btn_close.setFixedHeight(38)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)

        layout.addWidget(btn_frame)

    def _create_section(self, title: str, fields: list) -> QFrame:
        """Create a section with title and fields."""
        section = QFrame()
        section.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
                padding: 0;
            }}
        """)

        layout = QVBoxLayout(section)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 16, 20, 16)

        # Section title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title_label)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {Theme.DIVIDER}; border: none;")
        layout.addWidget(div)

        # Fields
        for field in fields:
            if len(field) == 3 and field[2]:  # Multiline field
                field_layout = QVBoxLayout()
                field_layout.setSpacing(6)
                
                label = QLabel(f"{field[0]}:")
                label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; background: transparent;")
                field_layout.addWidget(label)
                
                value = QLabel(field[1])
                value.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; background: transparent;")
                value.setWordWrap(True)
                field_layout.addWidget(value)
                
                layout.addLayout(field_layout)
            else:
                field_layout = QHBoxLayout()
                
                label = QLabel(f"{field[0]}:")
                label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; background: transparent;")
                label.setFixedWidth(160)
                field_layout.addWidget(label)
                
                value = QLabel(field[1])
                value.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; background: transparent;")
                field_layout.addWidget(value)
                field_layout.addStretch()
                
                layout.addLayout(field_layout)

        return section

    def _on_edit(self):
        """Edit account."""
        from models.person import get_all_persons
        persons = get_all_persons()
        dialog = AccountDialog(self, persons, self.account)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.accept()

    def _on_delete(self):
        """Delete account."""
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete account '{self.account['bank_name']}'?\n\nThis will also delete all associated transactions!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_account(self.account['account_id'])
            QMessageBox.information(self, "Deleted", "Account deleted successfully!")
            self.accept()
