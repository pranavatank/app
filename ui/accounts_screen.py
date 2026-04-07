"""
ui/accounts_screen.py — Card-based account management screen.
FIX: All dialog and card buttons use Theme.btn() for guaranteed visibility.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QGridLayout, QDialog,
    QFormLayout, QTabWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from models.bank_account import get_all_accounts, add_account, update_account, delete_account
from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
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

        btn_add = Theme.btn("＋  Add Account", "primary", height=38, min_width=140)
        btn_add.clicked.connect(self._on_add_account)
        header.addWidget(btn_add)
        layout.addLayout(header)

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
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        accounts = get_all_accounts()
        if not accounts:
            no_data = QLabel("💼  No accounts found.\nClick '＋ Add Account' to get started.")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data.setStyleSheet(
                f"color: {Theme.TEXT_MUTED}; font-size: 15px; padding: 60px; background: transparent;")
            self.cards_layout.addWidget(no_data, 0, 0, 1, 2)
            return

        for idx, account in enumerate(accounts):
            card = self._create_card(account)
            self.cards_layout.addWidget(card, idx // 2, idx % 2)
        self.cards_layout.setRowStretch(len(accounts) // 2 + 1, 1)

    def _create_card(self, account: dict) -> QFrame:
        accent_map = {
            "Savings":   Theme.SUCCESS,
            "Current":   Theme.PRIMARY,
            "Salary":    Theme.TEAL,
            "FD-linked": Theme.WARNING,
        }
        accent = accent_map.get(account.get("account_type", "Savings"), Theme.PRIMARY)

        card = QFrame()
        card.setObjectName("accountCard")
        card.setStyleSheet(f"""
            QFrame#accountCard {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-left: 4px solid {accent};
                border-radius: 12px;
            }}
            QFrame#accountCard:hover {{
                border: 1px solid {accent};
                border-left: 4px solid {accent};
                background-color: #FAFBFF;
            }}
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda e: self._on_card_clicked(account)
        card.setMinimumHeight(190)

        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        # Bank + status
        header = QHBoxLayout()
        bank_label = QLabel(f"🏦  {account.get('bank_display_name', account['bank_name'])}")
        bank_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bank_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        header.addWidget(bank_label)
        header.addStretch()

        status = account.get("account_status", "Active")
        sc = {
            "Active":   (Theme.SUCCESS,  Theme.SUCCESS_LIGHT),
            "Inactive": (Theme.WARNING,  Theme.WARNING_LIGHT),
            "Closed":   (Theme.DANGER,   Theme.DANGER_LIGHT),
        }.get(status, (Theme.TEXT_SECONDARY, Theme.SURFACE_ALT))
        status_lbl = QLabel(status)
        status_lbl.setStyleSheet(f"""
            background: {sc[1]}; color: {sc[0]};
            padding: 4px 12px; border-radius: 12px;
            font-size: 11px; font-weight: 700; border: none;
        """)
        status_lbl.setFixedHeight(24)
        header.addWidget(status_lbl)
        layout.addLayout(header)

        # Type + person
        info = QLabel(f"{account['account_type']}  ·  {account.get('person_name','—')}")
        info.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px; background: transparent;")
        layout.addWidget(info)

        if account.get("account_number_masked"):
            acc_lbl = QLabel(f"Account: {account['account_number_masked']}")
            acc_lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px; background: transparent;")
            layout.addWidget(acc_lbl)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {Theme.DIVIDER}; border: none;")
        layout.addWidget(div)

        # Balance
        bal_row = QHBoxLayout()
        bal_lbl = QLabel("Current Balance")
        bal_lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; background: transparent;")
        bal_row.addWidget(bal_lbl)
        bal_row.addStretch()
        bal_val = QLabel(f"₹ {account['current_balance']:,.2f}")
        bal_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        bal_val.setStyleSheet(f"color: {Theme.SUCCESS}; background: transparent;")
        bal_row.addWidget(bal_val)
        layout.addLayout(bal_row)

        # IFSC / branch
        parts = []
        if account.get("ifsc_code"):    parts.append(f"IFSC: {account['ifsc_code']}")
        if account.get("branch_name"):  parts.append(account["branch_name"])
        if parts:
            det = QLabel("  ·  ".join(parts))
            det.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; background: transparent;")
            det.setWordWrap(True)
            layout.addWidget(det)

        if account.get("debit_card_enabled"):
            dc = QLabel(f"💳  Debit Card — ₹{account.get('debit_card_charges',0):.0f}/yr")
            dc.setStyleSheet(f"color: {Theme.WARNING}; font-size: 11px; font-weight: 600; background: transparent;")
            layout.addWidget(dc)

        layout.addStretch()
        return card

    def _on_card_clicked(self, account: dict):
        persons = get_all_persons()
        view_dlg = AccountDialog(self, persons, account, view_only=True)
        if view_dlg.exec() == QDialog.DialogCode.Accepted:
            if view_dlg.action == "delete":
                self._load_accounts()
                return
            if view_dlg.action != "edit":
                return
            edit_dlg = AccountDialog(self, persons, account)
            if edit_dlg.exec() == QDialog.DialogCode.Accepted:
                payload = edit_dlg.get_data()
                tan_code = payload.pop("tan_code", None)
                update_account(account["account_id"], **payload)
                get_or_create_bank(payload.get("bank_name") or "")
                if tan_code:
                    update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)
                self._load_accounts()

    def _on_add_account(self):
        persons = get_all_persons()
        if not persons:
            QMessageBox.warning(self, "No Persons",
                "Please add a family member first before adding accounts.")
            return
        dlg = AccountDialog(self, persons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            add_account(**payload)
            get_or_create_bank(payload.get("bank_name") or "")
            if tan_code:
                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)
            self._load_accounts()


class AccountDetailsDialog(QDialog):
    """Full account detail view with tabs. All buttons use Theme.btn()."""

    def __init__(self, parent, account: dict):
        super().__init__(parent)
        self.account = account
        self.setWindowTitle(f"{account.get('bank_display_name', account['bank_name'])} — Account Details")
        self.setMinimumSize(720, 660)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {Theme.BG}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background: {Theme.BG};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(16)

        tabs = QTabWidget()
        tabs.addTab(self._tab_basic(),   "📋 Basic Info")
        tabs.addTab(self._tab_bank(),    "🏦 Bank Details")
        tabs.addTab(self._tab_contact(), "📞 Contact")
        tabs.addTab(self._tab_card(),    "💳 Debit Card")
        cl.addWidget(tabs)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        layout.addWidget(self._footer())

    def _header(self) -> QFrame:
        h = QFrame()
        h.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.PRIMARY}, stop:1 {Theme.PRIMARY_DARK});
            }}
        """)
        h.setFixedHeight(68)
        hl = QHBoxLayout(h)
        hl.setContentsMargins(28, 0, 28, 0)
        title = QLabel(f"🏦  {self.account.get('bank_display_name', self.account['bank_name'])}")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        hl.addWidget(title)
        hl.addStretch()
        status = self.account.get("account_status", "Active")
        sl = QLabel(status)
        sl.setStyleSheet(f"""
            background: white; color: {Theme.PRIMARY_DARK};
            padding: 6px 16px; border-radius: 14px;
            font-weight: 700; font-size: 13px;
        """)
        hl.addWidget(sl)
        return h

    def _footer(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border-top: 1px solid {Theme.BORDER};
            }}
        """)
        f.setFixedHeight(68)
        fl = QHBoxLayout(f)
        fl.setContentsMargins(28, 14, 28, 14)
        fl.addStretch()

        btn_edit = Theme.btn("✏️  Edit", "primary", height=40, min_width=110)
        btn_edit.clicked.connect(self._on_edit)
        fl.addWidget(btn_edit)

        btn_del = Theme.btn("🗑️  Delete", "danger", height=40, min_width=110)
        btn_del.clicked.connect(self._on_delete)
        fl.addWidget(btn_del)

        btn_close = Theme.btn("Close", "secondary", height=40, min_width=110)
        btn_close.clicked.connect(self.reject)
        fl.addWidget(btn_close)
        return f

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _tab_basic(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        l = QVBoxLayout(w); l.setContentsMargins(10,12,10,12); l.setSpacing(14)
        holder = self.account.get("account_holder_name") or self.account.get("person_name","—")
        l.addWidget(self._section("Account Information", [
            ("Account Type",             self.account.get("account_type","—")),
            ("Person (App)",             self.account.get("person_name","—")),
            ("Account Holder (Bank)",    holder),
            ("Account Number",           self.account.get("account_number_masked","—")),
            ("Customer ID",              self.account.get("customer_id","—")),
            ("CKYC ID",                  self.account.get("ckyc_id","—")),
            ("Opening Date",             self.account.get("account_opening_date","—")),
            ("Currency",                 self.account.get("currency","INR")),
            ("Status",                   self.account.get("account_status","Active")),
        ]))
        l.addWidget(self._section("Balance", [
            ("Opening Balance",  f"₹ {self.account.get('opening_balance',0):,.2f}"),
            ("Current Balance",  f"₹ {self.account.get('current_balance',0):,.2f}"),
            ("Interest Rate",    f"{self.account.get('interest_rate',0):.2f}%"),
        ]))
        l.addStretch()
        return w

    def _tab_bank(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        l = QVBoxLayout(w); l.setContentsMargins(10,12,10,12); l.setSpacing(14)
        l.addWidget(self._section("Bank Details", [
            ("IFSC Code",     self.account.get("ifsc_code","—")),
            ("MICR Code",     self.account.get("micr_code","—")),
            ("Branch Name",   self.account.get("branch_name","—")),
            ("Branch Address",self.account.get("branch_address","—"), True),
        ]))
        l.addStretch()
        return w

    def _tab_contact(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        l = QVBoxLayout(w); l.setContentsMargins(10,12,10,12); l.setSpacing(14)
        l.addWidget(self._section("Contact", [
            ("Email",   self.account.get("email_id","—")),
            ("Phone",   self.account.get("phone_no","—")),
            ("Address", self.account.get("communication_address","—"), True),
        ]))
        l.addWidget(self._section("Nomination", [
            ("Status",        self.account.get("nomination_status","—")),
            ("Nominee Name",  self.account.get("nominee_name","—")),
        ]))
        l.addStretch()
        return w

    def _tab_card(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        l = QVBoxLayout(w); l.setContentsMargins(10,12,10,12); l.setSpacing(14)
        if self.account.get("debit_card_enabled"):
            l.addWidget(self._section("Debit Card", [
                ("Status",          "Enabled ✓"),
                ("Annual Charges",  f"₹ {self.account.get('debit_card_charges',0):,.2f}"),
                ("Effective From",  self.account.get("debit_card_effective_from","—")),
            ]))
        else:
            no = QLabel("💳  No debit card enabled for this account.")
            no.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 14px; padding: 40px;")
            l.addWidget(no)
        l.addStretch()
        return w

    def _section(self, title: str, fields: list) -> QFrame:
        sec = QFrame()
        sec.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
        """)
        sl = QVBoxLayout(sec)
        sl.setSpacing(12)
        sl.setContentsMargins(20, 16, 20, 16)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        sl.addWidget(t)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {Theme.DIVIDER}; border: none;")
        sl.addWidget(div)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for field in fields:
            lbl = QLabel(f"{field[0]}:")
            lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; background: transparent;")
            val = QLabel(field[1])
            val.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; background: transparent;")
            if len(field) == 3 and field[2]:
                val.setWordWrap(True)
            form.addRow(lbl, val)
        sl.addLayout(form)
        return sec

    def _on_edit(self):
        from models.person import get_all_persons
        from ui.dialogs.account_dialog import AccountDialog
        dlg = AccountDialog(self, get_all_persons(), self.account)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            update_account(self.account["account_id"], **payload)
            get_or_create_bank(payload.get("bank_name") or "")
            if tan_code:
                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)
            self.accept()

    def _on_delete(self):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete account '{self.account.get('bank_display_name', self.account['bank_name'])}'?\n\n"
            "All transactions for this account will also be deleted!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_account(self.account["account_id"])
            QMessageBox.information(self, "Deleted", "Account deleted successfully!")
            self.accept()
