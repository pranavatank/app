"""
ui/dashboard_screen.py — Main application window with beautiful sidebar + top bar.
FIX: _nav_active_style now uses Theme.SIDEBAR_ACTIVE/HOVER tokens (no hardcoded rgba).
FIX: Brand header uses Theme.gradient() so all themes look correct.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QStackedWidget,
    QFrame, QGridLayout, QSizePolicy, QMessageBox, QScrollArea
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

from core.session import session
from config import (
    APP_NAME, get_current_financial_year,
    get_all_financial_years, get_assessment_year
)
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person, get_all_accounts, get_total_balance
from models.transaction import get_income_total, get_expense_total
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.tax_profile import get_tax_profile
from ui.logo import logo_pixmap, set_window_icon
from ui.theme import Theme
from ui.widgets.summary_panel import SummaryPanel

_NAV_ITEMS = [
    ("Overview",          "🏠"),
    ("Accounts",          "🏛️"),
    ("Transactions",      "💸"),
    ("Income Management", "💰"),
    ("Fixed Deposits",    "🏦"),
    ("Statement Import",  "📄"),
    ("AIS/TIS Import",    "📑"),
    ("Tax",               "📋"),
    ("26AS vs AIS",       "⚖️"),
    ("Reports",           "📊"),
    ("Settings",          "⚙️"),
]


class DashboardScreen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        set_window_icon(self)
        self.setMinimumSize(1200, 720)
        self._persons: list[dict] = []
        self._accounts: list[dict] = []
        self._build_ui()
        self._populate_selectors()
        self._refresh_overview()

    # ═══════════════════════════════════════════════════════════════════════
    # Layout
    # ═══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)

        root_layout.addWidget(self._build_sidebar())

        right = QWidget()
        right.setObjectName("contentArea")
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._build_topbar())
        right_layout.addWidget(self._build_content_area(), stretch=1)

        root_layout.addWidget(right, stretch=1)

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        self.sidebar_expanded = False
        sidebar.setFixedWidth(70)  # Collapsed width (icons only)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Brand header
        brand = QWidget()
        brand.setStyleSheet(f"""
            background: {Theme.gradient(Theme.HERO_GRADIENT_START, Theme.HERO_GRADIENT_END, diagonal=True)};
        """)
        brand.setFixedHeight(64)
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(12, 0, 12, 0)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        brand_icon = QLabel()
        brand_icon.setFixedSize(44, 44)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_pm = logo_pixmap(38)
        if not brand_pm.isNull():
            brand_icon.setPixmap(brand_pm)
        else:
            brand_icon.setText("PF")
            brand_icon.setStyleSheet("color: white; font-size: 14px; font-weight: 700; background: transparent;")
        brand_layout.addWidget(brand_icon)

        self.brand_text = QLabel("FinManager")
        self.brand_text.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.brand_text.setStyleSheet("color: white; background: transparent;")
        self.brand_text.setVisible(False)  # Hidden when collapsed
        brand_layout.addWidget(self.brand_text)
        # Pin button to persist expanded sidebar
        from PyQt6.QtWidgets import QToolButton
        self._pin_btn = QToolButton()
        self._pin_btn.setCheckable(True)
        self._pin_btn.setAutoRaise(True)
        self._pin_btn.setToolTip("Pin sidebar")
        self._pin_btn.setFixedSize(28, 28)
        self._pin_btn.clicked.connect(self._on_pin_toggled)
        brand_layout.addWidget(self._pin_btn)
        brand_layout.addStretch()

        layout.addWidget(brand)
        layout.addSpacing(12)

        # Nav label (hidden when collapsed)
        self.nav_lbl = QLabel("  NAVIGATION")
        self.nav_lbl.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_MUTED, size=10, weight=700) +
            " letter-spacing: 1.5px; padding-left: 20px;"
        )
        self.nav_lbl.setVisible(False)
        layout.addWidget(self.nav_lbl)
        layout.addSpacing(6)

        # Nav buttons
        self._nav_buttons: list[QWidget] = []  # Store container widgets
        for idx, (label, icon) in enumerate(_NAV_ITEMS):
            btn_container = self._make_nav_btn(icon, label)
            btn_container.mousePressEvent = lambda e, i=idx: self._navigate(i)
            layout.addWidget(btn_container)
            self._nav_buttons.append(btn_container)

        layout.addStretch()

        self.ver_lbl = QLabel("v1.0")
        self.ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ver_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=10) + " padding-bottom: 12px;")
        layout.addWidget(self.ver_lbl)

        self._set_nav_active(0)
        
        # Install event filter for hover
        sidebar.installEventFilter(self)
        # Apply pinned state from session
        if session.is_sidebar_pinned():
            self.sidebar_expanded = True
            sidebar.setFixedWidth(210)
            if hasattr(self, 'brand_text'):
                self.brand_text.setVisible(True)
            if hasattr(self, 'nav_lbl'):
                self.nav_lbl.setVisible(True)
            self._pin_btn.setChecked(True)
        return sidebar

    def _make_nav_btn(self, icon: str, label: str) -> QWidget:
        """Create a nav button with separate icon and label components"""
        container = QWidget()
        container.setFixedHeight(44)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        container.setAccessibleName(f"Navigate to {label}")
        container.setAccessibleDescription(f"Open the {label} page.")
        container.setProperty("nav_item", True)
        container.setProperty("active", False)

        def _key_press(event, idx_label=label, idx_icon=icon):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self._navigate(_NAV_ITEMS.index((idx_label, idx_icon)))
                event.accept()
                return
            QWidget.keyPressEvent(container, event)

        container.keyPressEvent = _key_press
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Icon label (always visible)
        icon_label = QLabel(icon)
        icon_label.setObjectName("nav_icon")
        icon_label.setFixedWidth(70)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFont(QFont("Segoe UI Emoji", 22))
        icon_label.setStyleSheet(f"color: {Theme.SIDEBAR_TEXT}; background: transparent;")
        layout.addWidget(icon_label)
        
        # Text label (hidden when collapsed)
        text_label = QLabel(label)
        text_label.setObjectName("nav_label")
        text_label.setFont(QFont("Segoe UI", 12))
        text_label.setStyleSheet(f"color: {Theme.SIDEBAR_TEXT}; background: transparent; padding-right: 12px;")
        text_label.setVisible(False)
        layout.addWidget(text_label)
        layout.addStretch()
        
        container.setStyleSheet(self._nav_normal_style())
        return container

    def _set_nav_active(self, index: int):
        """Set active state for navigation item"""
        for i, container in enumerate(self._nav_buttons):
            is_active = (i == index)
            container.setProperty("active", is_active)
            container.setStyleSheet(self._nav_active_style() if is_active else self._nav_normal_style())
            
            # Update colors
            icon_label = container.findChild(QLabel, "nav_icon")
            text_label = container.findChild(QLabel, "nav_label")
            
            if is_active:
                if icon_label:
                    icon_label.setStyleSheet(f"color: {Theme.SIDEBAR_ACTIVE_TEXT}; background: transparent;")
                if text_label:
                    text_label.setStyleSheet(f"color: {Theme.SIDEBAR_ACTIVE_TEXT}; background: transparent; padding-right: 12px; font-weight: 700;")
            else:
                if icon_label:
                    icon_label.setStyleSheet(f"color: {Theme.SIDEBAR_TEXT}; background: transparent;")
                if text_label:
                    text_label.setStyleSheet(f"color: {Theme.SIDEBAR_TEXT}; background: transparent; padding-right: 12px;")

    @staticmethod
    def _nav_normal_style() -> str:
        return f"""
            QWidget[nav_item="true"] {{
                background: transparent;
                border: none;
                border-radius: 0;
            }}
            QWidget[nav_item="true"]:hover {{
                background-color: {Theme.SIDEBAR_HOVER};
            }}
        """

    @staticmethod
    def _nav_active_style() -> str:
        """Active nav — fully theme-token driven, no hardcoded rgba."""
        return f"""
            QWidget[nav_item="true"] {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.SIDEBAR_ACTIVE},
                    stop:1 {Theme.SIDEBAR_HOVER});
                border: none;
                border-left: 3px solid {Theme.PRIMARY_LIGHT};
                border-radius: 0;
            }}
        """

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(60)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(10)

        logo_chip = QLabel()
        logo_chip.setFixedSize(40, 40)
        logo_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        topbar_pm = logo_pixmap(30)
        if not topbar_pm.isNull():
            logo_chip.setPixmap(topbar_pm)
        else:
            logo_chip.setText("PF")
            logo_chip.setStyleSheet(Theme.text_style(color=Theme.PRIMARY_DARK, size=11, weight=700))
        layout.addWidget(logo_chip)

        self.page_title_lbl = QLabel("Overview")
        self.page_title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.page_title_lbl.setStyleSheet(Theme.title_style(15))
        layout.addWidget(self.page_title_lbl)

        layout.addStretch()

        def _sep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setStyleSheet(f"color: {Theme.BORDER};")
            s.setFixedHeight(28)
            return s

        def _combo_lbl(text):
            l = QLabel(text)
            l.setStyleSheet(Theme.section_label_style())
            return l

        layout.addWidget(_combo_lbl("Person"))
        self.person_combo = QComboBox()
        self.person_combo.setFixedWidth(155)
        self.person_combo.setFixedHeight(34)
        self.person_combo.setAccessibleName("Dashboard person selector")
        self.person_combo.setAccessibleDescription("Filter the dashboard by family member.")
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        layout.addWidget(self.person_combo)

        layout.addWidget(_sep())
        layout.addWidget(_combo_lbl("Account"))
        self.account_combo = QComboBox()
        self.account_combo.setFixedWidth(200)
        self.account_combo.setFixedHeight(34)
        self.account_combo.setAccessibleName("Dashboard account selector")
        self.account_combo.setAccessibleDescription("Switch the dashboard to a specific bank account.")
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        layout.addWidget(self.account_combo)

        layout.addWidget(_sep())
        layout.addWidget(_combo_lbl("FY"))
        self.fy_combo = QComboBox()
        self.fy_combo.setFixedWidth(95)
        self.fy_combo.setFixedHeight(34)
        self.fy_combo.setAccessibleName("Dashboard financial year selector")
        self.fy_combo.setAccessibleDescription("Choose the financial year shown in summaries.")
        self.fy_combo.currentTextChanged.connect(self._on_fy_changed)
        layout.addWidget(self.fy_combo)

        layout.addSpacing(8)
        btn_logout = Theme.btn("Logout", "secondary", height=34, min_width=102)
        btn_logout.setAccessibleName("Logout")
        btn_logout.setAccessibleDescription("Sign out of the application.")
        btn_logout.clicked.connect(self._on_logout)
        layout.addWidget(btn_logout)

        return bar

    # ── Content stack ─────────────────────────────────────────────────────────

    def _build_content_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_overview_page())

        from ui.accounts_screen import AccountsScreen
        self.accounts_page = AccountsScreen()
        self.stack.addWidget(self.accounts_page)

        from ui.transactions_screen import TransactionsScreen
        self.transactions_page = TransactionsScreen(self)
        self.stack.addWidget(self.transactions_page)

        from ui.income_management_screen import IncomeManagementScreen
        self.income_page = IncomeManagementScreen(self)
        self.stack.addWidget(self.income_page)

        from ui.fixed_deposits_screen import FixedDepositsScreen
        self.fd_page = FixedDepositsScreen(self)
        self.stack.addWidget(self.fd_page)

        from ui.statement_import_screen_modern import StatementImportScreen
        self.import_page = StatementImportScreen(self)
        self.stack.addWidget(self.import_page)

        from ui.ais_tis_import_screen_v2 import AISTISImportScreenV2
        self.ais_tis_page = AISTISImportScreenV2(self)
        self.stack.addWidget(self.ais_tis_page)

        from ui.tax_screen import TaxScreen
        self.tax_page = TaxScreen(self)
        self.stack.addWidget(self.tax_page)

        from ui.reconciliation_screen import ReconciliationScreen
        self.reconciliation_page = ReconciliationScreen(self)
        self.stack.addWidget(self.reconciliation_page)

        from ui.reports_screen import ReportsScreen
        self.reports_page = ReportsScreen(self)
        self.stack.addWidget(self.reports_page)

        from ui.settings_screen import SettingsScreen
        self.settings_page = SettingsScreen(self)
        self.stack.addWidget(self.settings_page)

        layout.addWidget(self.stack)
        return container

    # ── Overview page ─────────────────────────────────────────────────────────

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {Theme.BG};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(20)

        # FY banner
        banner = QFrame()
        banner.setStyleSheet(f"""
            QFrame {{
                background: {Theme.gradient(Theme.PRIMARY_GRADIENT_START, Theme.PRIMARY_DARK)};
                border-radius: 14px;
            }}
        """)
        banner.setFixedHeight(70)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(24, 0, 24, 0)

        b_title = QLabel("Financial Overview")
        b_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        b_title.setStyleSheet("color: white; background: transparent;")
        b_layout.addWidget(b_title)
        b_layout.addStretch()

        self.banner_fy_lbl = QLabel("")
        self.banner_fy_lbl.setStyleSheet("color: rgba(255,255,255,0.82); font-size: 13px; background: transparent;")
        b_layout.addWidget(self.banner_fy_lbl)
        outer.addWidget(banner)

        # 2×2 Summary grid
        grid = QGridLayout()
        grid.setSpacing(18)

        self.panel_financial = SummaryPanel("Financial Summary", "💰", accent=Theme.PRIMARY)
        self.panel_financial.add_stat("balance", "Total Balance",      "₹ —", value_size=16)
        self.panel_financial.add_stat("income",  "Total Credit (FY)",  "₹ —", value_color=Theme.SUCCESS)
        self.panel_financial.add_stat("expense", "Total Debit (FY)",   "₹ —", value_color=Theme.DANGER)
        self.panel_financial.add_divider()
        self.panel_financial.add_stat("savings", "Net Savings",        "₹ —", value_size=14, bold=True)
        grid.addWidget(self.panel_financial, 0, 0)

        self.panel_bank = SummaryPanel("Bank Accounts", "🏦", accent=Theme.TEAL, scrollable=True)
        grid.addWidget(self.panel_bank, 0, 1)

        self.panel_interest = SummaryPanel("Interest Summary", "📈", accent=Theme.SUCCESS)
        self.panel_interest.add_stat("fd_curr",   "FD Interest (Current FY)",   "₹ —")
        self.panel_interest.add_stat("fd_next",   "FD Interest (Next FY est.)", "₹ —")
        self.panel_interest.add_divider()
        self.panel_interest.add_stat("sav_curr",  "Savings Interest (FY)",      "₹ —")
        self.panel_interest.add_stat("total_int", "Total Interest Income",      "₹ —", bold=True)
        grid.addWidget(self.panel_interest, 1, 0)

        self.panel_tax = SummaryPanel("Tax Summary", "📋", accent=Theme.WARNING)
        self.panel_tax.add_stat("gross",      "Gross Total Income", "₹ —")
        self.panel_tax.add_stat("deductions", "Total Deductions",   "₹ —")
        self.panel_tax.add_divider()
        self.panel_tax.add_stat("tax_old", "Tax — Old Regime", "₹ —")
        self.panel_tax.add_stat("tax_new", "Tax — New Regime", "₹ —")
        self.panel_tax.add_divider()
        self.panel_tax.add_stat("regime",  "Recommended Regime", "—", bold=True)
        grid.addWidget(self.panel_tax, 1, 1)

        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1);    grid.setRowStretch(1, 1)
        outer.addLayout(grid, stretch=1)

        scroll.setWidget(inner)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        return page

    # ═══════════════════════════════════════════════════════════════════════
    # Selectors
    # ═══════════════════════════════════════════════════════════════════════

    def _populate_selectors(self):
        self.fy_combo.blockSignals(True)
        self.fy_combo.clear()
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.fy_combo.addItem(fy)
        idx = self.fy_combo.findText(get_current_financial_year())
        if idx >= 0:
            self.fy_combo.setCurrentIndex(idx)
        self.fy_combo.blockSignals(False)
        session.set_financial_year(self.fy_combo.currentText())
        self._sync_context_selectors()

    def _sync_context_selectors(self):
        self._reload_persons(select_id=session.selected_person_id)
        if session.selected_person_id is None and self.person_combo.count() == 2:
            self.person_combo.setCurrentIndex(1)
            session.set_person(self.person_combo.currentData())
        self._reload_accounts(select_id=session.selected_account_id)
        if session.selected_account_id is None and self.account_combo.count() == 2:
            self.account_combo.setCurrentIndex(1)
            session.set_account(self.account_combo.currentData())

    def _reload_persons(self, select_id=None):
        previous_person  = session.selected_person_id
        previous_account = session.selected_account_id
        self.person_combo.blockSignals(True)
        self.person_combo.clear()
        self._persons = get_all_persons()
        self.person_combo.addItem("All Persons", userData=None)
        for p in self._persons:
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])
        if select_id is not None:
            for i in range(self.person_combo.count()):
                if self.person_combo.itemData(i) == select_id:
                    self.person_combo.setCurrentIndex(i); break
        else:
            self.person_combo.setCurrentIndex(0)
        session.selected_person_id = self.person_combo.currentData()
        self.person_combo.blockSignals(False)
        preferred = previous_account if session.selected_person_id == previous_person else None
        self._reload_accounts(select_id=preferred)

    def _reload_accounts(self, select_id=None):
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        pid = self.person_combo.currentData()
        if pid is None:
            self._accounts = get_all_accounts()
            self.account_combo.addItem("All Accounts", userData=None)
            for a in self._accounts:
                self.account_combo.addItem(
                    f"{a['person_name']} — {a.get('bank_display_name', a['bank_name'])} ({a['account_type']})",
                    userData=a["account_id"])
        else:
            self._accounts = get_accounts_for_person(pid)
            self.account_combo.addItem("All Accounts", userData=None)
            for a in self._accounts:
                self.account_combo.addItem(
                    f"{a.get('bank_display_name', a['bank_name'])} ({a['account_type']})",
                    userData=a["account_id"])
        selected = False
        if select_id is not None:
            for i in range(self.account_combo.count()):
                if self.account_combo.itemData(i) == select_id:
                    self.account_combo.setCurrentIndex(i); selected = True; break
        if not selected:
            self.account_combo.setCurrentIndex(0)
        session.set_account(self.account_combo.currentData())
        self.account_combo.blockSignals(False)

    # ═══════════════════════════════════════════════════════════════════════
    # Refresh
    # ═══════════════════════════════════════════════════════════════════════

    def _refresh_overview(self):
        fy  = session.selected_fy
        pid = session.selected_person_id
        aid = session.selected_account_id
        self.banner_fy_lbl.setText(f"FY {fy}  ·  AY {get_assessment_year(fy)}")
        self._refresh_financial_panel(fy, pid, aid)
        self._refresh_bank_panel(pid)
        self._refresh_interest_panel(fy, pid)
        self._refresh_tax_panel(fy, pid)

    def _refresh_financial_panel(self, fy, pid, aid):
        if aid is not None:
            from models.bank_account import get_account
            acc = get_account(aid)
            balance = acc["current_balance"] if acc else 0.0
        else:
            balance = get_total_balance(person_id=pid)
        income  = get_income_total(person_id=pid,  financial_year=fy)
        expense = get_expense_total(person_id=pid, financial_year=fy)
        net     = income - expense
        self.panel_financial.update_stat("balance", session.mask(balance))
        self.panel_financial.update_stat("income",  session.mask(income))
        self.panel_financial.update_stat("expense", session.mask(expense))
        self.panel_financial.update_stat("savings", session.mask(net))

    def _refresh_bank_panel(self, pid):
        self.panel_bank.clear_stats()
        accounts = get_accounts_for_person(pid) if pid else get_all_accounts()
        if not accounts:
            self.panel_bank.add_stat("_e", "No accounts added yet", ""); return
        for acc in accounts:
            self.panel_bank.add_stat(
                f"acc_{acc['account_id']}",
                f"{acc.get('bank_display_name', acc['bank_name'])}  ·  {acc['account_type']}",
                session.mask(acc["current_balance"]))

    def _refresh_interest_panel(self, fy, pid):
        next_start = int(fy.split("-")[0]) + 1
        next_fy    = f"{next_start}-{str(next_start + 1)[2:]}"
        fd_curr  = get_total_fd_interest(fy,      person_id=pid)
        fd_next  = get_total_fd_interest(next_fy, person_id=pid)
        sav_curr = get_total_savings_interest(fy,  person_id=pid)
        self.panel_interest.update_stat("fd_curr",   session.mask(fd_curr))
        self.panel_interest.update_stat("fd_next",   session.mask(fd_next))
        self.panel_interest.update_stat("sav_curr",  session.mask(sav_curr))
        self.panel_interest.update_stat("total_int", session.mask(fd_curr + sav_curr))

    def _refresh_tax_panel(self, fy, pid):
        if pid is None:
            for k in ["gross","deductions","tax_old","tax_new","regime"]:
                self.panel_tax.update_stat(k, "Select a person" if k=="gross" else "—")
            return
        profile = get_tax_profile(pid, fy)
        if not profile:
            for k in ["gross","deductions","tax_old","tax_new","regime"]:
                self.panel_tax.update_stat(k, "No data" if k=="gross" else "—")
            return
        ded = sum(profile.get(k,0) for k in [
            "deductions_80c","deductions_80d","home_loan_interest","hra_exemption","standard_deduction"])
        tax_old = profile.get("total_tax_old", 0)
        tax_new = profile.get("total_tax_new", 0)
        regime  = "🟢 Old Regime" if tax_old < tax_new else ("🟢 New Regime" if tax_new < tax_old else "Either")
        self.panel_tax.update_stat("gross",      session.mask(profile.get("gross_total_income",0)))
        self.panel_tax.update_stat("deductions", session.mask(ded))
        self.panel_tax.update_stat("tax_old",    session.mask(tax_old))
        self.panel_tax.update_stat("tax_new",    session.mask(tax_new))
        self.panel_tax.update_stat("regime",     regime)

    # ═══════════════════════════════════════════════════════════════════════
    # Navigation & signals
    # ═══════════════════════════════════════════════════════════════════════

    def _navigate(self, index: int):
        if not self._confirm_unsaved_transactions("switch pages"):
            return
        self._set_nav_active(index)
        self.stack.setCurrentIndex(index)
        self.page_title_lbl.setText(_NAV_ITEMS[index][0])
        self._on_refresh_all()

    def _on_refresh_all(self):
        self._sync_context_selectors()
        idx = self.stack.currentIndex()
        pages = [
            lambda: self._refresh_overview(),
            lambda: self._refresh_accounts_page(),
            lambda: self.transactions_page.refresh(),
            lambda: self.income_page.refresh(),
            lambda: self.fd_page.refresh(),
            lambda: self.import_page.refresh(),
            lambda: self.ais_tis_page.refresh(),
            lambda: self.tax_page.refresh(),
            lambda: self.reconciliation_page.refresh(),
            lambda: self.reports_page.refresh(),
            lambda: self.settings_page.refresh(),
        ]
        if 0 <= idx < len(pages):
            pages[idx]()

    def _refresh_accounts_page(self):
        """Update accounts page with current filters."""
        self.accounts_page.selected_person_id = session.selected_person_id
        self.accounts_page.selected_fy = session.selected_fy
        self.accounts_page._load_accounts()

    def _on_person_changed(self):
        session.set_person(self.person_combo.currentData())
        self._reload_accounts()
        self._on_refresh_all()

    def _on_account_changed(self):
        session.set_account(self.account_combo.currentData())
        self._on_refresh_all()

    def _on_fy_changed(self, fy: str):
        if fy:
            session.set_financial_year(fy)
            self._on_refresh_all()

    def refresh_overview(self):
        self._sync_context_selectors()
        self._refresh_overview()

    def _on_logout(self):
        if not self._confirm_unsaved_transactions("logout"):
            return
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            session.logout()
            from ui.login_screen import LoginScreen
            self.login = LoginScreen()
            self.login.show()
            self.close()

    def closeEvent(self, event):
        if not self._confirm_unsaved_transactions("close the app"):
            event.ignore()
            return
        super().closeEvent(event)

    def _confirm_unsaved_transactions(self, action_label: str) -> bool:
        if hasattr(self, "transactions_page") and hasattr(self.transactions_page, "_confirm_unsaved"):
            return self.transactions_page._confirm_unsaved(action_label)
        return True

    def eventFilter(self, obj, event):
        """Handle sidebar hover to expand/collapse"""
        if obj.objectName() == "sidebar":
            from PyQt6.QtCore import QEvent
            if event.type() == QEvent.Type.Enter:
                self._expand_sidebar()
            elif event.type() == QEvent.Type.Leave:
                self._collapse_sidebar()
        return super().eventFilter(obj, event)

    def _expand_sidebar(self):
        """Expand sidebar to show labels"""
        if self.sidebar_expanded:
            return
        self.sidebar_expanded = True
        sidebar = self.findChild(QWidget, "sidebar")
        if sidebar:
            sidebar.setFixedWidth(210)
        
        # Show text elements
        if hasattr(self, 'brand_text'):
            self.brand_text.setVisible(True)
        if hasattr(self, 'nav_lbl'):
            self.nav_lbl.setVisible(True)
        if hasattr(self, 'ver_lbl'):
            self.ver_lbl.setText("v1.0.0  ·  Offline")
        
        # Show all nav labels
        for container in self._nav_buttons:
            text_label = container.findChild(QLabel, "nav_label")
            if text_label:
                text_label.setVisible(True)

    def _collapse_sidebar(self):
        """Collapse sidebar to show only icons"""
        # Do not collapse if pinned by user
        if session.is_sidebar_pinned():
            return
        if not self.sidebar_expanded:
            return
        self.sidebar_expanded = False
        sidebar = self.findChild(QWidget, "sidebar")
        if sidebar:
            sidebar.setFixedWidth(70)
        
        # Hide text elements
        if hasattr(self, 'brand_text'):
            self.brand_text.setVisible(False)
        if hasattr(self, 'nav_lbl'):
            self.nav_lbl.setVisible(False)
        if hasattr(self, 'ver_lbl'):
            self.ver_lbl.setText("v1.0")
        
        # Hide all nav labels
        for container in self._nav_buttons:
            text_label = container.findChild(QLabel, "nav_label")
            if text_label:
                text_label.setVisible(False)

    def _on_pin_toggled(self, checked: bool):
        session.set_sidebar_pinned(bool(checked))
        if checked:
            self._expand_sidebar()
        else:
            # immediately collapse if mouse is not over sidebar
            from PyQt6.QtCore import QEvent
            sidebar = self.findChild(QWidget, "sidebar")
            if sidebar:
                pos = sidebar.mapFromGlobal(sidebar.cursor().pos())
                if not sidebar.rect().contains(pos):
                    self._collapse_sidebar()
