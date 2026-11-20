"""
ui/accounts_screen.py — Account management with card/list view toggle.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QGridLayout, QDialog, QMessageBox,
    QTabWidget, QFormLayout, QPushButton
)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont

from ui.theme.theme import Theme
from ui.icons import set_btn_icon, icon_label as app_icon_label, pixmap as app_pixmap, is_available as icons_available, tab_icon
from ui.widgets.states import EmptyState
from ui.widgets.toast_utils import show_success, show_warning
from ui.widgets.money_label import MoneyLabel, format_inr
from ui.dialogs.account_dialog import AccountDialog
from ui.dialogs.account_details_dialog import AccountDetailsPanel
from models.bank_account import get_all_accounts, add_account, update_account, delete_account, get_account
from models.bank import get_or_create_bank, update_bank_tan_code_if_exists
from models.person import get_all_persons
from models.account_holder import add_account_holder, set_primary_holder
from models.fixed_deposit import get_all_fds
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest


class AccountsScreen(QWidget):
    """Account management with card/list view toggle."""

    view_transactions_requested = Signal(int)
    import_statement_requested = Signal(int)

    def __init__(self, selected_person_id=None, selected_fy=None):
        super().__init__()
        self.selected_person_id = selected_person_id
        self.selected_fy = selected_fy or "2024-25"
        settings = QSettings("FinManager", "FinManager")
        self.view_mode = settings.value("accounts/view_mode", "card", type=str)
        if self.view_mode not in {"card", "list"}:
            self.view_mode = "card"
        self.selected_account_id = None
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
        self.header_frame = QFrame()
        self.header_frame.setObjectName("pageHeader")
        self.header_frame.setStyleSheet(Theme.page_header_style())
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(16, 10, 16, 10)
        header.setSpacing(8)
        title = QLabel("Bank Accounts")
        title.setProperty("textrole", "title-md")
        header.addWidget(title)
        header.addStretch()

        # View toggle button
        self.btn_toggle = Theme.btn(" Card View" if self.view_mode == "list" else " List View", "secondary", height=Theme.HEIGHT_MD, min_width=134)
        set_btn_icon(self.btn_toggle, "card_view" if self.view_mode == "list" else "list_view", color=Theme.TEXT_SECONDARY)
        self.btn_toggle.setAccessibleName("Toggle account view")
        self.btn_toggle.setAccessibleDescription("Switch between card and list view.")
        self.btn_toggle.clicked.connect(self._toggle_view)
        header.addWidget(self.btn_toggle)

        btn_add = Theme.btn(" Add Account", "primary", height=Theme.HEIGHT_MD, min_width=154)
        set_btn_icon(btn_add, "add")
        btn_add.setAccessibleName("Add account")
        btn_add.setAccessibleDescription("Open the dialog to add a new bank account.")
        btn_add.clicked.connect(self._on_add_account)
        header.addWidget(btn_add)
        layout.addWidget(self.header_frame)

        # Master-detail layout: list on left, details panel on right
        master_detail = QHBoxLayout()
        master_detail.setSpacing(16)
        master_detail.setContentsMargins(0, 0, 0, 0)

        # Container for accounts list (left side)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("transparentBg")
        self.accounts_scroll = scroll

        self.container = QWidget()
        self.container.setObjectName("transparentSurface")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(0)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self.container)
        master_detail.addWidget(scroll, stretch=3)

        # Details panel (right side) — collapsed by default, expands when account selected
        self.detail_frame = QFrame()
        self.detail_frame.setObjectName("detailPanel")
        self.detail_frame.setStyleSheet(f"""
            QFrame#detailPanel {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)
        self.detail_frame.setMinimumWidth(0)
        self.detail_frame.setMaximumWidth(0)
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_panel = AccountDetailsPanel(
            self, on_updated=self._on_account_updated,
            on_deleted=self._on_accounts_reload, on_closed=self._on_detail_panel_closed,
            on_view_transactions=self._request_view_transactions,
            on_import_statement=self._request_import_statement,
        )
        detail_layout.addWidget(self.detail_panel)
        master_detail.addWidget(self.detail_frame, stretch=0)

        layout.addLayout(master_detail, stretch=1)

        self.setAccessibleName("Accounts screen")
        self.setAccessibleDescription("Manage bank accounts in card or list view.")

    def _toggle_view(self):
        self.view_mode = "list" if self.view_mode == "card" else "card"
        self.btn_toggle.setText(" Card View" if self.view_mode == "list" else " List View")
        set_btn_icon(self.btn_toggle, "card_view" if self.view_mode == "list" else "list_view", color=Theme.TEXT_SECONDARY)
        QSettings("FinManager", "FinManager").setValue("accounts/view_mode", self.view_mode)
        self._load_accounts()

    def _load_accounts(self):
        scroll_position = self.accounts_scroll.verticalScrollBar().value() if hasattr(self, "accounts_scroll") else 0
        focused = self.focusWidget()
        focused_name = focused.objectName() if focused else ""
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        accounts = get_all_accounts()
        if self.selected_person_id:
            accounts = [a for a in accounts if a["person_id"] == self.selected_person_id]

        visible_account_ids = {int(a["account_id"]) for a in accounts}
        if self.selected_account_id is not None and int(self.selected_account_id) not in visible_account_ids:
            self.selected_account_id = None
            self.detail_panel.clear_account()
            self._on_detail_panel_closed()

        if not accounts:
            empty_state = EmptyState(
                icon_name="bank",
                headline="No accounts yet",
                explanation="Add your first bank account to start tracking.",
                action_text="Add Account",
                parent=self.container
            )
            empty_state.action_clicked.connect(self._on_add_account)
            # Override button variant to secondary since header already has primary
            Theme.style_button(empty_state.btn_action, "secondary")
            self.container_layout.addWidget(empty_state)
            return

        if self.view_mode == "card":
            self._render_card_view(accounts)
        else:
            self._render_list_view(accounts)
        self.accounts_scroll.verticalScrollBar().setValue(scroll_position)
        if focused_name:
            replacement = self.findChild(QWidget, focused_name)
            if replacement:
                replacement.setFocus(Qt.FocusReason.OtherFocusReason)
        # Keep detail selection bound to its database identity across rebuilds.
        if self.selected_account_id is not None:
            account = next(a for a in accounts if a["account_id"] == self.selected_account_id)
            details = get_account(self.selected_account_id)
            if details:
                self._show_account_details({**account, **details})
            else:
                self.selected_account_id = None
                self.detail_panel.clear_account()
                self._on_detail_panel_closed()

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
        section.setObjectName("transparentBg")
        layout = QVBoxLayout(section)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 16)

        # Bank header
        header = QLabel(bank_name)
        header.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.setProperty("textrole", "label")
        header.setProperty("color", "primary")
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
        item.setGraphicsEffect(Theme.shadow_card())
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        item.setAccessibleName(
            f"Account {account.get('bank_display_name', account['bank_name'])} "
            f"{account.get('account_number_masked') or 'number unavailable'}"
        )
        item.setAccessibleDescription("Open detailed account information.")
        item.mousePressEvent = lambda e: self._on_card_clicked(account)
        item.setMinimumHeight(80)

        layout = QVBoxLayout(item)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Left: Bank + Person info
        left = QVBoxLayout()
        left.setSpacing(4)
        
        bank_lbl = QLabel(account.get("bank_display_name", account["bank_name"]))
        bank_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bank_lbl.setProperty("textrole", "emphasis-lg")
        bank_lbl.setWordWrap(True)
        left.addWidget(bank_lbl)

        person_lbl = QLabel(account.get('person_name', '—'))
        person_lbl.setProperty("textrole", "secondary-sm")
        left.addWidget(person_lbl)

        type_lbl = QLabel(account['account_type'])
        type_lbl.setProperty("textrole", "muted-md")
        left.addWidget(type_lbl)
        account_lbl = QLabel(f"Account: {account.get('account_number_masked') or '—'}")
        account_lbl.setProperty("textrole", "muted-sm")
        left.addWidget(account_lbl)

        identity = QHBoxLayout()
        identity.addLayout(left, 1)
        layout.addLayout(identity)

        # Right: Metrics
        metrics = QHBoxLayout()
        metrics.setSpacing(12)

        # Current Balance
        bal_box = QVBoxLayout()
        bal_box.setSpacing(2)
        bal_label = QLabel("Current Balance")
        bal_label.setProperty("textrole", "muted-sm")
        bal_box.addWidget(bal_label)
        bal_val = QLabel(format_inr(account['current_balance']))
        bal_val.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        bal_val.setProperty("textrole", "metric")
        bal_box.addWidget(bal_val)
        metrics.addLayout(bal_box)

        # FD Value
        fd_box = QVBoxLayout()
        fd_box.setSpacing(2)
        fd_label = QLabel("Open FDs")
        fd_label.setProperty("textrole", "muted-sm")
        fd_box.addWidget(fd_label)
        fd_val = QLabel(format_inr(fd_value))
        fd_val.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        fd_val.setProperty("textrole", "metric")
        fd_box.addWidget(fd_val)
        metrics.addLayout(fd_box)

        # FD Interest (FY)
        fdi_box = QVBoxLayout()
        fdi_box.setSpacing(2)
        fdi_label = QLabel(f"FD Interest ({self.selected_fy})")
        fdi_label.setProperty("textrole", "muted-sm")
        fdi_box.addWidget(fdi_label)
        fdi_val = QLabel(format_inr(fd_interest))
        fdi_val.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        fdi_val.setProperty("textrole", "metric")
        fdi_box.addWidget(fdi_val)
        metrics.addLayout(fdi_box)

        # Savings Interest (FY)
        si_box = QVBoxLayout()
        si_box.setSpacing(2)
        si_label = QLabel(f"Savings Interest ({self.selected_fy})")
        si_label.setProperty("textrole", "muted-sm")
        si_box.addWidget(si_label)
        si_val = QLabel(format_inr(savings_interest))
        si_val.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        si_val.setProperty("textrole", "metric")
        si_box.addWidget(si_val)
        metrics.addLayout(si_box)

        layout.addLayout(metrics)

        btn_details = Theme.btn("View details", "secondary", height=Theme.HEIGHT_SM)
        btn_details.setAccessibleName(
            f"View details for {account.get('bank_display_name') or account['bank_name']} "
            f"{account.get('account_number_masked') or account['account_id']}"
        )
        btn_details.setObjectName(f"accountDetails-{account['account_id']}")
        btn_details.clicked.connect(lambda _=False, acc=account: self._on_card_clicked(acc))
        identity.addWidget(btn_details, alignment=Qt.AlignmentFlag.AlignTop)

        return item

    def _create_card(self, account: dict) -> QFrame:
        accent_map = {
            "Savings":   "savings",
            "Current":   "current",
            "Salary":    "salary",
            "FD-linked": "fd-linked",
        }
        variant = accent_map.get(account.get("account_type", "Savings"), "current")

        card = QFrame()
        card.setObjectName("accountCard")
        card.setAccessibleName(
            f"Account {account.get('bank_display_name', account['bank_name'])} "
            f"{account.get('account_number_masked') or 'number unavailable'}"
        )
        card.setProperty("variant", variant)
        card.setGraphicsEffect(Theme.shadow_card())
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda e: self._on_card_clicked(account)
        card.setMinimumHeight(190)

        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        # BALANCE — most prominent element (LARGEST FONT, TOP)
        bal_lbl = QLabel("Balance")
        bal_lbl.setProperty("textrole", "muted-sm")
        layout.addWidget(bal_lbl)

        bal_val = MoneyLabel(account['current_balance'], parent=card)
        bal_val.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        bal_val.setProperty("textrole", "metric")
        layout.addWidget(bal_val)

        # Bank name + status
        header = QHBoxLayout()
        bank_label = QLabel(account.get('bank_display_name', account['bank_name']))
        bank_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bank_label.setProperty("textrole", "emphasis-lg")
        header.addWidget(bank_label)
        header.addStretch()

        # Status pill — only show if NOT Active
        status = account.get("account_status", "Active")
        if status != "Active":
            sc = {
                "Inactive": (Theme.WARNING,  Theme.WARNING_LIGHT),
                "Closed":   (Theme.DANGER,   Theme.DANGER_LIGHT),
            }.get(status, (Theme.TEXT_SECONDARY, Theme.SURFACE_ALT))
            status_lbl = QLabel(status)
            status_lbl.setStyleSheet(f"""
                background: {sc[1]}; color: {sc[0]};
                padding: 4px 12px; border-radius: 12px;
                font-size: 11px; font-weight: 700; border: none;
            """)
            status_lbl.setMinimumHeight(24)
            header.addWidget(status_lbl)
        layout.addLayout(header)

        # Type + person + account (smaller metadata)
        info = QLabel(f"{account['account_type']}  ·  {account.get('person_name','—')}")
        info.setProperty("textrole", "secondary-md")
        layout.addWidget(info)

        if account.get("account_number_masked"):
            acc_lbl = QLabel(f"Account: {account['account_number_masked']}")
            acc_lbl.setProperty("textrole", "muted-md")
            layout.addWidget(acc_lbl)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setObjectName("divider")
        layout.addWidget(div)

        # IFSC / branch
        parts = []
        if account.get("ifsc_code"):    parts.append(f"IFSC: {account['ifsc_code']}")
        if account.get("branch_name"):  parts.append(account["branch_name"])
        if parts:
            det = QLabel("  ·  ".join(parts))
            det.setProperty("textrole", "muted-sm")
            det.setWordWrap(True)
            layout.addWidget(det)

        if account.get("debit_card_enabled"):
            dc = QLabel(f"Debit Card — ₹{account.get('debit_card_charges',0):.0f}/yr")
            dc.setProperty("textrole", "emphasis-sm")
            dc.setProperty("color", "warning")
            layout.addWidget(dc)

        btn_details = Theme.btn("View details", "secondary", height=Theme.HEIGHT_SM)
        btn_details.setAccessibleName(
            f"View details for {account.get('bank_display_name') or account['bank_name']} "
            f"{account.get('account_number_masked') or account['account_id']}"
        )
        btn_details.setObjectName(f"accountDetails-{account['account_id']}")
        btn_details.clicked.connect(lambda _=False, acc=account: self._on_card_clicked(acc))
        layout.addWidget(btn_details)
        layout.addStretch()
        return card

    def _on_card_clicked(self, account: dict):
        """Show account details in the detail panel (non-modal) and expand the panel."""
        self.selected_account_id = int(account["account_id"])
        details = get_account(self.selected_account_id)
        if details:
            self._show_account_details({**account, **details})
        else:
            self._on_detail_panel_closed()

    def _show_account_details(self, account):
        self._fit_detail_layout()
        if self.detail_panel.account != account:
            self.detail_panel.update_account(account)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.selected_account_id is not None:
            self._fit_detail_layout()

    def _fit_detail_layout(self):
        compact = self.width() < 1060
        self.accounts_scroll.setVisible(not compact)
        self.detail_frame.setMaximumWidth(16777215 if compact else 440)
        self.detail_frame.setMinimumWidth(0 if compact else 380)

    def _on_detail_panel_closed(self):
        account_id = self.selected_account_id
        self.selected_account_id = None
        self.accounts_scroll.show()
        self.detail_frame.setMinimumWidth(0)
        self.detail_frame.setMaximumWidth(0)
        if account_id is not None:
            details_button = self.findChild(QPushButton, f"accountDetails-{account_id}")
            if details_button:
                self.accounts_scroll.ensureWidgetVisible(details_button)
                details_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_account_updated(self, account_id):
        """Reload when account is updated in the detail panel."""
        self.selected_account_id = int(account_id)
        updated = get_account(self.selected_account_id)
        if updated:
            visible_row = next((row for row in get_all_accounts() if row["account_id"] == account_id), {})
            self.detail_panel.update_account({**visible_row, **updated})
        self._load_accounts()

    def _on_accounts_reload(self):
        """Reload when account is deleted in the detail panel."""
        self._on_detail_panel_closed()
        self._load_accounts()

    def _request_view_transactions(self, account_id):
        self.view_transactions_requested.emit(int(account_id))

    def _request_import_statement(self, account_id):
        self.import_statement_requested.emit(int(account_id))

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
        self.header_frame.setStyleSheet(Theme.page_header_style())
        self._load_accounts()

    def _on_add_account(self):
        persons = get_all_persons()
        if not persons:
            show_warning("Please add a family member first before adding accounts.")
            return
        dlg = AccountDialog(self, persons)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.get_data()
            tan_code = payload.pop("tan_code", None)
            account_id = add_account(**payload)
            get_or_create_bank(payload.get("bank_name") or "")
            if tan_code:
                update_bank_tan_code_if_exists(payload.get("bank_name") or "", tan_code)

            # Save account holders
            for holder in dlg._holders_data:
                add_account_holder(account_id, holder["person_id"], holder["is_primary"])

            # Set primary holder if specified in dialog
            primary = next((h["person_id"] for h in dlg._holders_data if h["is_primary"]), None)
            if primary:
                set_primary_holder(account_id, primary)

            self._load_accounts()
