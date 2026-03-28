"""
ui/dashboard_screen.py — Main application window with beautiful sidebar + top bar.
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
from ui.theme import Theme
from ui.widgets.summary_panel import SummaryPanel

_NAV_ITEMS = [
    ("Overview",         "🏠"),
    ("Accounts",         "🏛️"),
    ("Transactions",     "💸"),
    ("Fixed Deposits",   "🏦"),
    ("Statement Import", "📄"),
    ("Tax",              "📋"),
    ("Reports",          "📊"),
    ("Settings",         "⚙️"),
]


class DashboardScreen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
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

        # Right side: topbar + content
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
        sidebar.setFixedWidth(210)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Brand header
        brand = QWidget()
        brand.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {Theme.PRIMARY}, stop:1 {Theme.PRIMARY_DARK});
        """)
        brand.setFixedHeight(64)
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(20, 0, 20, 0)

        brand_icon = QLabel("💰")
        brand_icon.setFont(QFont("Segoe UI Emoji", 20))
        brand_layout.addWidget(brand_icon)

        brand_text = QLabel("FinManager")
        brand_text.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        brand_text.setStyleSheet("color: white; background: transparent;")
        brand_layout.addWidget(brand_text)
        brand_layout.addStretch()

        layout.addWidget(brand)
        layout.addSpacing(12)

        # Nav section label
        nav_lbl = QLabel("  NAVIGATION")
        nav_lbl.setStyleSheet(f"""
            color: rgba(148,163,184,0.6);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            background: transparent;
            padding-left: 20px;
        """)
        layout.addWidget(nav_lbl)
        layout.addSpacing(6)

        # Nav buttons
        self._nav_buttons: list[QPushButton] = []
        for idx, (label, icon) in enumerate(_NAV_ITEMS):
            btn = self._make_nav_btn(icon, label)
            btn.clicked.connect(lambda checked, i=idx: self._navigate(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        # Version badge
        ver_lbl = QLabel("v1.0.0  ·  Offline")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_lbl.setStyleSheet(f"""
            color: rgba(148,163,184,0.5);
            font-size: 10px;
            background: transparent;
            padding-bottom: 12px;
        """)
        layout.addWidget(ver_lbl)

        self._nav_buttons[0].setProperty("active", True)
        self._nav_buttons[0].setStyleSheet(self._nav_active_style())
        return sidebar

    def _make_nav_btn(self, icon: str, label: str) -> QPushButton:
        btn = QPushButton(f"   {icon}   {label}")
        btn.setFixedHeight(44)
        btn.setFont(QFont("Segoe UI", 12))
        btn.setCheckable(False)
        btn.setStyleSheet(self._nav_normal_style())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    @staticmethod
    def _nav_normal_style() -> str:
        return f"""
            QPushButton {{
                background: transparent;
                color: {Theme.SIDEBAR_TEXT};
                border: none;
                border-radius: 0;
                text-align: left;
                padding-left: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Theme.SIDEBAR_HOVER};
                color: white;
            }}
        """

    @staticmethod
    def _nav_active_style() -> str:
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.PRIMARY}, stop:1 rgba(37,99,235,0.4));
                color: white;
                border: none;
                border-left: 3px solid {Theme.PRIMARY_LIGHT};
                border-radius: 0;
                text-align: left;
                padding-left: 8px;
                font-size: 13px;
                font-weight: 700;
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

        # Page title (updated on navigate)
        self.page_title_lbl = QLabel("Overview")
        self.page_title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.page_title_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(self.page_title_lbl)

        layout.addStretch()

        # ── Selectors ─────────────────────────────────────────────────────
        def _sep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setStyleSheet(f"color: {Theme.BORDER};")
            s.setFixedHeight(28)
            return s

        def _combo_lbl(text):
            l = QLabel(text)
            l.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
            return l

        layout.addWidget(_combo_lbl("Person"))
        self.person_combo = QComboBox()
        self.person_combo.setFixedWidth(155)
        self.person_combo.setFixedHeight(34)
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        layout.addWidget(self.person_combo)

        layout.addWidget(_sep())

        layout.addWidget(_combo_lbl("Account"))
        self.account_combo = QComboBox()
        self.account_combo.setFixedWidth(200)
        self.account_combo.setFixedHeight(34)
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        layout.addWidget(self.account_combo)

        layout.addWidget(_sep())

        layout.addWidget(_combo_lbl("FY"))
        self.fy_combo = QComboBox()
        self.fy_combo.setFixedWidth(95)
        self.fy_combo.setFixedHeight(34)
        self.fy_combo.currentTextChanged.connect(self._on_fy_changed)
        layout.addWidget(self.fy_combo)

        layout.addSpacing(8)

        btn_logout = QPushButton("Logout")
        btn_logout.setObjectName("secondaryBtn")
        btn_logout.setFixedHeight(34)
        btn_logout.setFixedWidth(102)
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

        from ui.fixed_deposits_screen import FixedDepositsScreen
        self.fd_page = FixedDepositsScreen(self)
        self.stack.addWidget(self.fd_page)

        from ui.statement_import_screen import StatementImportScreen
        self.import_page = StatementImportScreen(self)
        self.stack.addWidget(self.import_page)

        from ui.tax_screen import TaxScreen
        self.tax_page = TaxScreen(self)
        self.stack.addWidget(self.tax_page)

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

        # ── FY banner ─────────────────────────────────────────────────────
        banner = QFrame()
        banner.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {Theme.PRIMARY}, stop:1 {Theme.PRIMARY_DARK});
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
        self.banner_fy_lbl.setStyleSheet("color: rgba(255,255,255,0.75); font-size: 13px; background: transparent;")
        b_layout.addWidget(self.banner_fy_lbl)

        outer.addWidget(banner)

        # ── 2×2 Summary grid ──────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(18)

        self.panel_financial = SummaryPanel("Financial Summary", "💰", accent=Theme.PRIMARY)
        self.panel_financial.add_stat("balance",  "Total Balance",      "₹ —", value_size=16)
        self.panel_financial.add_stat("income",   "Total Income (FY)",  "₹ —", value_color=Theme.SUCCESS)
        self.panel_financial.add_stat("expense",  "Total Expenses (FY)","₹ —", value_color=Theme.DANGER)
        self.panel_financial.add_divider()
        self.panel_financial.add_stat("savings",  "Net Savings",        "₹ —", value_size=14, bold=True)
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
        self.panel_tax.add_stat("gross",      "Gross Total Income",  "₹ —")
        self.panel_tax.add_stat("deductions", "Total Deductions",    "₹ —")
        self.panel_tax.add_divider()
        self.panel_tax.add_stat("tax_old",    "Tax — Old Regime",    "₹ —")
        self.panel_tax.add_stat("tax_new",    "Tax — New Regime",    "₹ —")
        self.panel_tax.add_divider()
        self.panel_tax.add_stat("regime",     "Recommended Regime",  "—", bold=True)
        grid.addWidget(self.panel_tax, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
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
        self._reload_persons()

    def _reload_persons(self, select_id=None):
        self.person_combo.blockSignals(True)
        self.person_combo.clear()
        self._persons = get_all_persons()
        self.person_combo.addItem("All Persons", userData=None)
        for p in self._persons:
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])
        if select_id:
            for i in range(self.person_combo.count()):
                if self.person_combo.itemData(i) == select_id:
                    self.person_combo.setCurrentIndex(i)
                    break
        self.person_combo.blockSignals(False)
        self._reload_accounts()

    def _reload_accounts(self):
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        pid = self.person_combo.currentData()
        if pid is None:
            self._accounts = get_all_accounts()
            self.account_combo.addItem("All Accounts", userData=None)
            for a in self._accounts:
                self.account_combo.addItem(
                    f"{a['person_name']} — {a['bank_name']} ({a['account_type']})",
                    userData=a["account_id"])
        else:
            self._accounts = get_accounts_for_person(pid)
            self.account_combo.addItem("All Accounts", userData=None)
            for a in self._accounts:
                self.account_combo.addItem(
                    f"{a['bank_name']} ({a['account_type']})",
                    userData=a["account_id"])
        session.set_account(None)
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
            self.panel_bank.add_stat("_e", "No accounts added yet", "")
            return
        for acc in accounts:
            self.panel_bank.add_stat(
                f"acc_{acc['account_id']}",
                f"{acc['bank_name']}  ·  {acc['account_type']}",
                session.mask(acc["current_balance"])
            )

    def _refresh_interest_panel(self, fy, pid):
        next_start = int(fy.split("-")[0]) + 1
        next_fy    = f"{next_start}-{str(next_start + 1)[2:]}"
        fd_curr    = get_total_fd_interest(fy,      person_id=pid)
        fd_next    = get_total_fd_interest(next_fy, person_id=pid)
        sav_curr   = get_total_savings_interest(fy, person_id=pid)
        self.panel_interest.update_stat("fd_curr",   session.mask(fd_curr))
        self.panel_interest.update_stat("fd_next",   session.mask(fd_next))
        self.panel_interest.update_stat("sav_curr",  session.mask(sav_curr))
        self.panel_interest.update_stat("total_int", session.mask(fd_curr + sav_curr))

    def _refresh_tax_panel(self, fy, pid):
        if pid is None:
            for key in ["gross","deductions","tax_old","tax_new","regime"]:
                self.panel_tax.update_stat(key, "Select a person" if key=="gross" else "—")
            return
        profile = get_tax_profile(pid, fy)
        if not profile:
            for key in ["gross","deductions","tax_old","tax_new","regime"]:
                self.panel_tax.update_stat(key, "No data" if key=="gross" else "—")
            return
        ded = sum(profile.get(k,0) for k in [
            "deductions_80c","deductions_80d","home_loan_interest",
            "hra_exemption","standard_deduction"])
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
        for i, btn in enumerate(self._nav_buttons):
            btn.setStyleSheet(
                self._nav_active_style() if i == index else self._nav_normal_style()
            )
        self.stack.setCurrentIndex(index)
        self.page_title_lbl.setText(_NAV_ITEMS[index][0])
        self._on_refresh_all()

    def _on_refresh_all(self):
        idx = self.stack.currentIndex()
        pages = [
            lambda: self._refresh_overview(),
            lambda: self.accounts_page._load_accounts(),
            lambda: self.transactions_page.refresh(),
            lambda: self.fd_page.refresh(),
            lambda: self.import_page.refresh(),
            lambda: self.tax_page.refresh(),
            lambda: self.reports_page.refresh(),
            lambda: self.settings_page.refresh(),
        ]
        if 0 <= idx < len(pages):
            pages[idx]()

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
        self._refresh_overview()

    def _on_logout(self):
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to log out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            session.logout()
            from ui.login_screen import LoginScreen
            self.login = LoginScreen()
            self.login.show()
            self.close()
