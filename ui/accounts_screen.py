"""
ui/accounts_screen.py — Account management with card/list view toggle.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QGridLayout, QDialog, QMessageBox,
    QTabWidget, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme.theme import Theme
from ui.icons import set_btn_icon, icon_label as app_icon_label, pixmap as app_pixmap, is_available as icons_available, tab_icon
from ui.widgets.chart_widget import ChartWidget
from models.bank_account import get_all_accounts, add_account, update_account, delete_account, get_account
from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
from models.person import get_all_persons
from models.fixed_deposit import get_all_fds
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from ui.dialogs.account_dialog import AccountDialog


class AccountsScreen(QWidget):
    """Account management with card/list view toggle."""

    def __init__(self, selected_person_id=None, selected_fy=None):
        super().__init__()
        self.selected_person_id = selected_person_id
        self.selected_fy = selected_fy or "2024-25"
        self.view_mode = "card"  # card or list
        self._build_ui()
        self._load_accounts()

    def _build_ui(self):
        # NOTE: no inline background override here — QMainWindow/QWidget base
        # style already paints Theme.BG via the global stylesheet, and that
        # rule DOES refresh live on theme switch. An inline setStyleSheet()
        # here would freeze the colour at build time and break live switching.
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # Header
        header = QHBoxLayout()
        title = QLabel("Bank Accounts")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(18))
        header.addWidget(title)
        header.addStretch()

        # View toggle button
        self.btn_toggle = Theme.btn(" List View", "secondary", height=38, min_width=120)
        set_btn_icon(self.btn_toggle, "list_view", color=Theme.TEXT_SECONDARY)
        self.btn_toggle.setAccessibleName("Toggle account view")
        self.btn_toggle.setAccessibleDescription("Switch between card and list view.")
        self.btn_toggle.clicked.connect(self._toggle_view)
        header.addWidget(self.btn_toggle)

        btn_add = Theme.btn(" Add Account", "primary", height=38, min_width=140)
        set_btn_icon(btn_add, "add")
        btn_add.setAccessibleName("Add account")
        btn_add.setAccessibleDescription("Open the dialog to add a new bank account.")
        btn_add.clicked.connect(self._on_add_account)
        header.addWidget(btn_add)
        layout.addLayout(header)

        # Bank-wise balance chart
        self.bank_chart = ChartWidget()
        self.bank_chart.setFixedHeight(350)
        layout.addWidget(self.bank_chart)

        # Container for both views
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(0)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self.container)
        layout.addWidget(scroll, stretch=1)

        self.setAccessibleName("Accounts screen")
        self.setAccessibleDescription("Manage bank accounts in card or list view.")

    def _toggle_view(self):
        self.view_mode = "list" if self.view_mode == "card" else "card"
        self.btn_toggle.setText(" Card View" if self.view_mode == "list" else " List View")
        set_btn_icon(self.btn_toggle, "card_view" if self.view_mode == "list" else "list_view", color=Theme.TEXT_SECONDARY)
        self._load_accounts()

    def _load_accounts(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        accounts = get_all_accounts()
        if self.selected_person_id:
            accounts = [a for a in accounts if a["person_id"] == self.selected_person_id]

        if not accounts:
            no_data_container = QFrame()
            no_data_container.setStyleSheet(Theme.empty_state_style())
            no_data_layout = QVBoxLayout(no_data_container)
            no_data_layout.setContentsMargins(0, 0, 0, 0)
            no_data = QLabel("No accounts found.\nClick 'Add Account' to get started.")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data.setStyleSheet(
                f"color: {Theme.TEXT_MUTED}; font-size: 15px; background: transparent;")
            no_data_layout.addWidget(no_data)
            self.container_layout.addWidget(no_data_container)
            self._refresh_bank_chart()
            return

        if self.view_mode == "card":
            self._render_card_view(accounts)
        else:
            self._render_list_view(accounts)

        self._refresh_bank_chart()

    def _render_card_view(self, accounts):
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(20)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        for idx, account in enumerate(accounts):
            card = self._create_card(account)
            grid_layout.addWidget(card, idx // 2, idx % 2)
        grid_layout.setRowStretch(len(accounts) // 2 + 1, 1)
        self.container_layout.addWidget(grid_widget)

    def _render_list_view(self, accounts):
        # Group by bank if all persons selected
        if self.selected_person_id is None:
            grouped = {}
            for acc in accounts:
                bank = acc.get("bank_display_name", acc["bank_name"])
                if bank not in grouped:
                    grouped[bank] = []
                grouped[bank].append(acc)

            for bank_name in sorted(grouped.keys()):
                bank_section = self._create_bank_section(bank_name, grouped[bank_name])
                self.container_layout.addWidget(bank_section)
        else:
            # Single person - show all accounts directly
            for acc in accounts:
                list_item = self._create_list_item(acc)
                self.container_layout.addWidget(list_item)

        self.container_layout.addStretch()

    def _create_bank_section(self, bank_name, accounts):
        section = QFrame()
        section.setStyleSheet(f"background: transparent; border: none;")
        layout = QVBoxLayout(section)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 16)

        # Bank header
        header = QLabel(bank_name)
        header.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.setStyleSheet(Theme.text_style(color=Theme.PRIMARY, size=15, weight=700))
        layout.addWidget(header)

        # Accounts under this bank
        for acc in accounts:
            list_item = self._create_list_item(acc)
            layout.addWidget(list_item)

        return section

    def _create_list_item(self, account):
        # Get FD and interest data
        fds = get_all_fds(person_id=account["person_id"])
        account_fds = [fd for fd in fds if fd["account_id"] == account["account_id"] and fd["status"] == "Active"]
        fd_value = sum(fd["principal_amount"] for fd in account_fds)
        
        fd_interest = get_total_fd_interest(self.selected_fy, account_id=account["account_id"])
        savings_interest = get_total_savings_interest(self.selected_fy, account_id=account["account_id"])

        item = QFrame()
        item.setObjectName("listItem")
        item.setStyleSheet(f"""
            QFrame#listItem {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
                padding: 16px 20px;
            }}
            QFrame#listItem:hover {{
                background: {Theme.SURFACE_ALT};
                border-color: {Theme.PRIMARY};
            }}
        """)
        item.setGraphicsEffect(Theme.shadow_card())
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        item.setAccessibleName(f"Account card for {account.get('bank_display_name', account['bank_name'])}")
        item.setAccessibleDescription("Open detailed account information.")
        item.mousePressEvent = lambda e: self._on_card_clicked(account)
        item.setMinimumHeight(80)

        layout = QHBoxLayout(item)
        layout.setSpacing(24)
        layout.setContentsMargins(0, 0, 0, 0)

        # Left: Bank + Person info
        left = QVBoxLayout()
        left.setSpacing(4)
        
        bank_lbl = QLabel(account.get("bank_display_name", account["bank_name"]))
        bank_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bank_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=14, weight=700))
        left.addWidget(bank_lbl)

        if self.selected_person_id is None:
            person_lbl = QLabel(account.get('person_name', '—'))
            person_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=12))
            left.addWidget(person_lbl)

        type_lbl = QLabel(f"{account['account_type']}  •  {account.get('account_number_masked', '—')}")
        type_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=12))
        left.addWidget(type_lbl)

        layout.addLayout(left, 3)

        # Right: Metrics
        metrics = QHBoxLayout()
        metrics.setSpacing(32)

        # Current Balance
        bal_box = QVBoxLayout()
        bal_box.setSpacing(2)
        bal_label = QLabel("Current Balance")
        bal_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
        bal_box.addWidget(bal_label)
        bal_val = QLabel(f"₹ {account['current_balance']:,.0f}")
        bal_val.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        bal_val.setStyleSheet(Theme.text_style(color=Theme.SUCCESS, size=15, weight=700))
        bal_box.addWidget(bal_val)
        metrics.addLayout(bal_box)

        # FD Value
        fd_box = QVBoxLayout()
        fd_box.setSpacing(2)
        fd_label = QLabel("Open FDs")
        fd_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
        fd_box.addWidget(fd_label)
        fd_val = QLabel(f"₹ {fd_value:,.0f}")
        fd_val.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        fd_val.setStyleSheet(Theme.text_style(color=Theme.WARNING, size=15, weight=700))
        fd_box.addWidget(fd_val)
        metrics.addLayout(fd_box)

        # FD Interest (FY)
        fdi_box = QVBoxLayout()
        fdi_box.setSpacing(2)
        fdi_label = QLabel(f"FD Interest ({self.selected_fy})")
        fdi_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
        fdi_box.addWidget(fdi_label)
        fdi_val = QLabel(f"₹ {fd_interest:,.0f}")
        fdi_val.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        fdi_val.setStyleSheet(Theme.text_style(color=Theme.INFO, size=14, weight=700))
        fdi_box.addWidget(fdi_val)
        metrics.addLayout(fdi_box)

        # Savings Interest (FY)
        si_box = QVBoxLayout()
        si_box.setSpacing(2)
        si_label = QLabel(f"Savings Interest ({self.selected_fy})")
        si_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
        si_box.addWidget(si_label)
        si_val = QLabel(f"₹ {savings_interest:,.0f}")
        si_val.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        si_val.setStyleSheet(Theme.text_style(color=Theme.TEAL, size=14, weight=700))
        si_box.addWidget(si_val)
        metrics.addLayout(si_box)

        layout.addLayout(metrics, 5)

        return item

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
                background-color: {Theme.SURFACE_ALT};
            }}
        """)
        card.setGraphicsEffect(Theme.shadow_card())
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda e: self._on_card_clicked(account)
        card.setMinimumHeight(190)

        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        # Bank + status
        header = QHBoxLayout()
        bank_label = QLabel(account.get('bank_display_name', account['bank_name']))
        bank_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bank_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=14, weight=700))
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
        info.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=13))
        layout.addWidget(info)

        if account.get("account_number_masked"):
            acc_lbl = QLabel(f"Account: {account['account_number_masked']}")
            acc_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=12))
            layout.addWidget(acc_lbl)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {Theme.DIVIDER}; border: none;")
        layout.addWidget(div)

        # Balance
        bal_row = QHBoxLayout()
        bal_lbl = QLabel("Current Balance")
        bal_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
        bal_row.addWidget(bal_lbl)
        bal_row.addStretch()
        bal_val = QLabel(f"₹ {account['current_balance']:,.2f}")
        bal_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        bal_val.setStyleSheet(Theme.text_style(color=Theme.SUCCESS, size=16, weight=700))
        bal_row.addWidget(bal_val)
        layout.addLayout(bal_row)

        # IFSC / branch
        parts = []
        if account.get("ifsc_code"):    parts.append(f"IFSC: {account['ifsc_code']}")
        if account.get("branch_name"):  parts.append(account["branch_name"])
        if parts:
            det = QLabel("  ·  ".join(parts))
            det.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=11))
            det.setWordWrap(True)
            layout.addWidget(det)

        if account.get("debit_card_enabled"):
            dc = QLabel(f"Debit Card — ₹{account.get('debit_card_charges',0):.0f}/yr")
            dc.setStyleSheet(Theme.text_style(color=Theme.WARNING, size=11, weight=600))
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

    def set_person_filter(self, person_id):
        """Update person filter and reload."""
        self.selected_person_id = person_id
        self._load_accounts()

    def set_fy_filter(self, fy):
        """Update financial year filter and reload."""
        self.selected_fy = fy
        self._load_accounts()

    def refresh_theme(self):
        """Called after a live theme switch — cards are rebuilt fresh on every
        _load_accounts() call, so simply reloading picks up the new colours."""
        if hasattr(self, 'bank_chart') and self.bank_chart:
            self.bank_chart.refresh_theme()
        self._load_accounts()

    def _refresh_bank_chart(self):
        """Refresh the bank-wise balance chart."""
        if not hasattr(self, 'bank_chart') or not self.bank_chart:
            return

        if self.selected_person_id is not None:
            accounts = [a for a in get_all_accounts() if a["person_id"] == self.selected_person_id]
        else:
            accounts = get_all_accounts()

        if not accounts:
            self.bank_chart.show_empty_state("No bank accounts found")
            return

        # Sort by balance descending
        accounts = sorted(accounts, key=lambda a: a["current_balance"], reverse=True)

        labels = [
            f"{a.get('bank_display_name', a['bank_name'])}\n({a['account_type']})"
            for a in accounts
        ]
        values = [a["current_balance"] for a in accounts]

        if all(v == 0 for v in values):
            self.bank_chart.show_empty_state("All account balances are zero")
            return

        self.bank_chart.plot_bar(
            categories=labels,
            values=values,
            title="Balance by Bank Account",
            ylabel="Balance (₹)",
            color=Theme.TEAL,
        )

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
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
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
        title = QLabel(self.account.get('bank_display_name', self.account['bank_name']))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(Theme.text_style(color=Theme.PRIMARY_TEXT, size=16, weight=700))
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

        btn_edit = Theme.btn(" Edit", "edit", height=40, min_width=110)
        set_btn_icon(btn_edit, "edit")
        btn_edit.clicked.connect(self._on_edit)
        fl.addWidget(btn_edit)

        btn_del = Theme.btn(" Delete", "danger", height=40, min_width=110)
        set_btn_icon(btn_del, "delete")
        btn_del.clicked.connect(self._on_delete)
        fl.addWidget(btn_del)

        btn_close = Theme.btn("Close", "secondary", height=40, min_width=110)
        btn_close.clicked.connect(self.reject)
        fl.addWidget(btn_close)
        return f

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _tab_basic(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: transparent;")
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
        w = QWidget(); w.setStyleSheet("background: transparent;")
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
        w = QWidget(); w.setStyleSheet("background: transparent;")
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
        w = QWidget(); w.setStyleSheet("background: transparent;")
        l = QVBoxLayout(w); l.setContentsMargins(10,12,10,12); l.setSpacing(14)
        if self.account.get("debit_card_enabled"):
            l.addWidget(self._section("Debit Card", [
                ("Status",          "Enabled ✓"),
                ("Annual Charges",  f"₹ {self.account.get('debit_card_charges',0):,.2f}"),
                ("Effective From",  self.account.get("debit_card_effective_from","—")),
            ]))
        else:
            no = QLabel("No debit card enabled for this account.")
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
        t.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=700))
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
            lbl.setStyleSheet(Theme.section_label_style())
            val = QLabel(field[1])
            val.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13))
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
