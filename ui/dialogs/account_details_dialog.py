"""
ui/dialogs/account_details_dialog.py — Account detail panel with tabs.
This can be used as either a dialog or an in-screen panel.
"""

from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QFormLayout, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import set_btn_icon, tab_icon
from ui.widgets.toast_utils import show_success
from models.bank_account import update_account, delete_account
from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
from models.person import get_all_persons
from ui.dialogs.account_dialog import AccountDialog


class AccountDetailsPanel(QWidget):
    """Read-only or editable account details panel that can be used in-screen."""

    def __init__(self, parent=None, account: dict = None, on_updated=None, on_deleted=None):
        super().__init__(parent)
        self.account = account
        self.on_updated = on_updated
        self.on_deleted = on_deleted
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        if not self.account:
            empty = QLabel("No account selected")
            empty.setObjectName("AccountDetailsEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
            return

        layout.addWidget(self._header())

        scroll = QScrollArea()
        scroll.setObjectName("AccountDetailsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("AccountDetailsContent")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(16)

        tabs = QTabWidget()
        tabs.addTab(self._tab_basic(),   "Basic Info")
        tabs.addTab(self._tab_bank(),    "Bank Details")
        tabs.addTab(self._tab_contact(), "Contact")
        tabs.addTab(self._tab_card(),    "Debit Card")
        tabs.setTabIcon(0, tab_icon("basic_info"))
        tabs.setTabIcon(1, tab_icon("bank_details"))
        tabs.setTabIcon(2, tab_icon("contact"))
        tabs.setTabIcon(3, tab_icon("debit_card"))
        cl.addWidget(tabs)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        layout.addWidget(self._footer())

    def update_account(self, account: dict):
        """Update the displayed account."""
        self.account = account
        self._build_ui()

    def _header(self) -> QFrame:
        h = QFrame()
        h.setObjectName("AccountDetailsHeader")
        h.setMinimumHeight(68)
        hl = QHBoxLayout(h)
        hl.setContentsMargins(28, 0, 28, 0)
        title = QLabel(self.account.get('bank_display_name', self.account['bank_name']))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setProperty("textrole", "title-lg")
        hl.addWidget(title)
        hl.addStretch()
        status = self.account.get("account_status", "Active")
        sl = QLabel(status)
        sl.setObjectName("AccountStatusBadge")
        hl.addWidget(sl)
        return h

    def _footer(self) -> QFrame:
        f = QFrame()
        f.setObjectName("AccountDetailsFooter")
        f.setMinimumHeight(68)
        fl = QHBoxLayout(f)
        fl.setContentsMargins(28, 14, 28, 14)
        fl.addStretch()

        btn_edit = Theme.btn(" Edit", "edit", height=40, min_width=110)
        set_btn_icon(btn_edit, "edit")
        btn_edit.clicked.connect(self._on_edit)
        fl.addWidget(btn_edit)

        btn_del = Theme.btn(" Delete", "danger", height=40, min_width=110)
        set_btn_icon(btn_del, "delete")
        btn_del.clicked.connect(self._on_delete)
        fl.addWidget(btn_del)

        btn_close = Theme.btn("Close", "secondary", height=40, min_width=110)
        btn_close.clicked.connect(self._on_close)
        fl.addWidget(btn_close)
        return f

    def _tab_basic(self) -> QWidget:
        w = QWidget(); w.setObjectName("AccountTabContent")
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
        w = QWidget(); w.setObjectName("AccountTabContent")
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
        w = QWidget(); w.setObjectName("AccountTabContent")
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
        w = QWidget(); w.setObjectName("AccountTabContent")
        l = QVBoxLayout(w); l.setContentsMargins(10,12,10,12); l.setSpacing(14)
        if self.account.get("debit_card_enabled"):
            l.addWidget(self._section("Debit Card", [
                ("Status",          "Enabled ✓"),
                ("Annual Charges",  f"₹ {self.account.get('debit_card_charges',0):,.2f}"),
                ("Effective From",  self.account.get("debit_card_effective_from","—")),
            ]))
        else:
            no = QLabel("No debit card enabled for this account.")
            no.setObjectName("AccountDetailsNoCard")
            no.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(no)
        l.addStretch()
        return w

    def _section(self, title: str, fields: list) -> QFrame:
        sec = QFrame()
        sec.setObjectName("AccountDetailSection")
        sl = QVBoxLayout(sec)
        sl.setSpacing(12)
        sl.setContentsMargins(20, 16, 20, 16)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        t.setProperty("textrole", "emphasis-md")
        sl.addWidget(t)

        div = QFrame()
        div.setObjectName("AccountDetailDivider")
        div.setFixedHeight(1)
        sl.addWidget(div)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for field in fields:
            lbl = QLabel(f"{field[0]}:")
            lbl.setProperty("textrole", "section-label")
            val = QLabel(field[1])
            val.setProperty("textrole", "body-md")
            if len(field) == 3 and field[2]:
                val.setWordWrap(True)
            form.addRow(lbl, val)
        sl.addLayout(form)
        return sec

    def _on_edit(self):
        dlg = AccountDialog(self, get_all_persons(), self.account)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            update_account(self.account["account_id"], **payload)
            get_or_create_bank(payload.get("bank_name") or "")
            if tan_code:
                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)
            if self.on_updated:
                self.on_updated(self.account["account_id"])

    def _on_delete(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete account '{self.account.get('bank_display_name', self.account['bank_name'])}'?\n\n"
            "All transactions for this account will also be deleted!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_account(self.account["account_id"])
            show_success("Account deleted successfully!")
            if self.on_deleted:
                self.on_deleted()

    def _on_close(self):
        """Clear selection when close is clicked."""
        self.account = None
        self._build_ui()


class AccountDetailsDialog(QDialog):
    """Modal dialog wrapper for AccountDetailsPanel (for backward compatibility)."""

    def __init__(self, parent, account: dict):
        super().__init__(parent)
        self.account = account
        self.setWindowTitle(f"{account.get('bank_display_name', account['bank_name'])} — Account Details")
        self.setMinimumSize(720, 660)
        self.panel = AccountDetailsPanel(self, account,
                                         on_updated=self._on_updated,
                                         on_deleted=self._on_deleted)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.panel)

    def _on_updated(self, account_id):
        self.accept()

    def _on_deleted(self):
        self.accept()
