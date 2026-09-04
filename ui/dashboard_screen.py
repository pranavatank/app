"""
ui/dashboard_screen.py — Main application window with beautiful sidebar + top bar.
FIX: _nav_active_style now uses Theme.SIDEBAR_ACTIVE/HOVER tokens (no hardcoded rgba).
FIX: Brand header uses Theme.gradient() so all themes look correct.
"""

import os
import traceback

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QStackedWidget,
    QFrame, QGridLayout, QSizePolicy, QMessageBox, QScrollArea, QToolButton
)
from PyQt6.QtCore import Qt, QSize, QEvent, QObject
from PyQt6.QtGui import QFont, QColor, QIcon, QFontMetrics

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
from ui.theme import Theme, ThemeManager
from ui.icons import icon as app_icon, fallback as icon_fallback, is_available as icons_available
from ui.widgets.summary_panel import SummaryPanel

_NAV_ITEMS = [
    ("Overview",              "overview"),
    ("Accounts",              "accounts"),
    ("Transactions",          "transactions"),
    ("Income & Expectations", "income"),
    ("Fixed Deposits",        "fixed_deposits"),
    ("Statement Import",      "statement_import"),
    ("Tax Documents",         "ais_tis"),
    ("Tax",                   "tax"),
    ("Settings",              "settings"),
]


class NavLabelElisionFilter(QObject):
    """Event filter for nav labels to apply text elision when resized."""
    def __init__(self, full_text: str, label_widget: QLabel):
        super().__init__()
        self.full_text = full_text
        self.label_widget = label_widget

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize:
            metrics = QFontMetrics(self.label_widget.font())
            elided = metrics.elidedText(self.full_text, Qt.TextElideMode.ElideRight,
                                       self.label_widget.width() - 4)
            self.label_widget.setText(elided)
        return False


class DashboardScreen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        set_window_icon(self)
        self.setMinimumSize(1200, 720)
        self._persons: list[dict] = []
        self._accounts: list[dict] = []
        # Lazy-load screen pages: index -> screen instance or error message
        self._screen_pages: dict[int, QWidget | None] = {}
        self._screen_errors: dict[int, str] = {}
        self._build_ui()
        self._populate_selectors()
        self._refresh_overview()
        # Register live theme change listener
        ThemeManager.register_on_change(self._on_theme_changed)

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
        self.content_area = self._build_content_area()
        right_layout.addWidget(self.content_area, stretch=1)

        root_layout.addWidget(right, stretch=1)

        # Initialize toast container anchored to content area
        from ui.widgets.toast_utils import init_toast_container
        init_toast_container(self.content_area)

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        # Start expanded; will collapse if persisted preference says so
        self.sidebar_expanded = session.is_sidebar_open()
        sidebar.setFixedWidth(248 if self.sidebar_expanded else 76)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Brand header
        brand = QWidget()
        self._brand_widget = brand  # keep ref for theme refresh
        brand.setObjectName("brand")
        brand.setMinimumHeight(64)
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(12, 0, 12, 0)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        brand_icon = QLabel()
        brand_icon.setObjectName("brandIcon")
        brand_icon.setFixedSize(44, 44)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_pm = logo_pixmap(38)
        if not brand_pm.isNull():
            brand_icon.setPixmap(brand_pm)
        else:
            brand_icon.setText("PF")
        brand_layout.addWidget(brand_icon)

        self.brand_text = QLabel("FinManager")
        self.brand_text.setObjectName("brandText")
        self.brand_text.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.brand_text.setVisible(False)  # Hidden when collapsed
        brand_layout.addWidget(self.brand_text)
        brand_layout.addStretch()

        layout.addWidget(brand)
        layout.addSpacing(12)

        # Nav label (hidden when collapsed)
        self.nav_lbl = QLabel("  NAVIGATION")
        self.nav_lbl.setObjectName("navLabel")
        self.nav_lbl.setVisible(False)
        layout.addWidget(self.nav_lbl)
        layout.addSpacing(6)

        # Nav buttons (QToolButton in checkable + autoExclusive mode)
        self._nav_buttons: list[QToolButton] = []
        nav_button_group_id = 1  # for autoExclusive
        for idx, (label, icon) in enumerate(_NAV_ITEMS):
            btn = self._make_nav_btn(icon, label)
            btn.clicked.connect(lambda checked, i=idx: self._navigate(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        self.ver_lbl = QLabel("v1.0")
        self.ver_lbl.setObjectName("verLabel")
        self.ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.ver_lbl)

        # Toggle button - expands/collapses the sidebar on click (no hover, no pin)
        self._sidebar_toggle_btn = QPushButton()
        self._sidebar_toggle_btn.setObjectName("sidebarToggle")
        self._sidebar_toggle_btn.setMinimumHeight(40)
        self._sidebar_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sidebar_toggle_btn.setIconSize(QSize(16, 16))
        self._sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self._sidebar_toggle_btn)

        self._set_nav_active(0)

        # Apply current sidebar state visibility
        if self.sidebar_expanded:
            self.brand_text.setVisible(True)
            self.nav_lbl.setVisible(True)
            for btn in self._nav_buttons:
                text_label = btn.findChild(QLabel, "nav_label")
                if text_label:
                    text_label.setVisible(True)
        self._update_sidebar_toggle_btn()
        return sidebar

    def _make_nav_btn(self, icon_name: str, label: str) -> QToolButton:
        """Create a nav button as QToolButton in checkable + autoExclusive mode.
        Uses a container widget to maintain icon + label layout."""
        # Container widget to hold the layout (replaces previous QWidget approach)
        container = QToolButton()
        container.setCheckable(True)
        container.setAutoExclusive(True)
        container.setMinimumHeight(44)
        # Expand horizontally to fill the sidebar; fixed height keeps consistent spacing
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        container.setToolTip(label)  # Tooltip for accessibility when collapsed
        container.setAccessibleName(f"Navigate to {label}")
        container.setAccessibleDescription(f"Open the {label} page.")
        container.setProperty("nav_item", True)
        container.setProperty("active", False)

        # Use QToolButton's layout capability
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Icon label: width depends on sidebar state
        # In collapsed mode (76px rail), icon fills the width for centered display
        # In expanded mode (248px), icon takes natural width (~24px); text label expands to fill remaining space
        icon_label = QLabel()
        icon_label.setObjectName("navIcon")
        # 76px for collapsed (centers the icon), 24px for expanded (icon sizeHint + padding)
        icon_width = 76 if not self.sidebar_expanded else 24
        icon_label.setFixedWidth(icon_width)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icons_available():
            pm = app_icon(icon_name, color="auto", size=22).pixmap(22, 22)
            if not pm.isNull():
                icon_label.setPixmap(pm)
            else:
                icon_label.setText(icon_fallback(icon_name))
                icon_label.setFont(QFont("Segoe UI Emoji", 18))
        else:
            icon_label.setText(icon_fallback(icon_name))
            icon_label.setFont(QFont("Segoe UI Emoji", 18))
        layout.addWidget(icon_label, stretch=0)

        # Text label (hidden when collapsed)
        text_label = QLabel(label)
        text_label.setObjectName("nav_label")
        text_label.setFont(QFont("Segoe UI", 12))
        text_label.setVisible(False)
        # Expand horizontally to fill ALL remaining space in the button (no trailing stretch)
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Keep full text in tooltip for accessibility
        text_label.setToolTip(label)
        # Install event filter for text elision on resize
        elision_filter = NavLabelElisionFilter(label, text_label)
        text_label.installEventFilter(elision_filter)
        # Store the filter to keep it alive
        text_label._elision_filter = elision_filter
        layout.addWidget(text_label)

        # Store icon name for theme refresh
        container._icon_name = icon_name
        container._icon_label = icon_label
        container._text_label = text_label

        return container

    def _set_nav_active(self, index: int):
        """Set active state for navigation item using dynamic properties and style updates"""
        for i, btn in enumerate(self._nav_buttons):
            is_active = (i == index)
            btn.setProperty("active", is_active)
            btn.setChecked(is_active)  # Update checked state for QToolButton
            # Use dynamic property for styling instead of reassigning stylesheet
            btn.style().unpolish(btn)
            btn.style().polish(btn)

            icon_label = btn._icon_label
            text_label = btn._text_label
            # Active items get a crisp icon in the active-text token colour
            icon_color = Theme.SIDEBAR_ACTIVE_TEXT if is_active else "auto"

            if icons_available():
                icon_name = btn._icon_name
                pm = app_icon(icon_name, color=icon_color, size=22).pixmap(22, 22)
                if not pm.isNull():
                    icon_label.setPixmap(pm)

            # Update text label active property for dynamic styling
            text_label.setProperty("active", is_active)
            text_label.style().unpolish(text_label)
            text_label.style().polish(text_label)


    def _on_theme_changed(self, name: str) -> None:
        """
        Called by ThemeManager after a theme switch.
        Rebuilds nav icon pixmaps (colors are baked in) and refreshes
        delegated components. Global QSS now handles layout/border/bg changes.
        """
        # Nav icon colors are baked into QPixmap, so refresh those
        if hasattr(self, '_nav_buttons'):
            current_idx = self.stack.currentIndex() if hasattr(self, 'stack') else 0
            self._set_nav_active(current_idx)

        # Update sidebar toggle button icon
        if hasattr(self, '_sidebar_toggle_btn') and self._sidebar_toggle_btn:
            self._update_sidebar_toggle_btn()

        # Refresh all SummaryPanel cards (left-accent + card border are inline)
        for panel_name in ('panel_financial', 'panel_bank', 'panel_interest', 'panel_tax'):
            panel = getattr(self, panel_name, None)
            if panel is not None:
                panel.refresh_theme()

        # Refresh stacked pages that carry baked-in colours (inline styles,
        # QColor table-row foregrounds, etc.) and won't update via the
        # global QSS unpolish/polish pass alone.
        for page_name in ('accounts_page', 'transactions_page', 'fd_page',
                          'income_page', 'import_page', 'ais_tis_page', 'tax_page'):
            page = getattr(self, page_name, None)
            if page is not None and hasattr(page, 'refresh_theme'):
                try:
                    page.refresh_theme()
                except Exception:
                    pass

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setMinimumHeight(60)

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
        layout.addWidget(logo_chip)

        self.page_title_lbl = QLabel("Overview")
        self.page_title_lbl.setObjectName("pageTitle")
        self.page_title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.page_title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.page_title_lbl)

        layout.addStretch()

        def _sep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setObjectName("divider")
            s.setMinimumHeight(28)
            return s

        def _combo_lbl(text):
            l = QLabel(text)
            l.setStyleSheet(Theme.section_label_style())
            return l

        layout.addWidget(_combo_lbl("Person"))
        self.person_combo = QComboBox()
        self.person_combo.setMinimumWidth(120)
        self.person_combo.setMinimumHeight(34)
        self.person_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.person_combo.setAccessibleName("Dashboard person selector")
        self.person_combo.setAccessibleDescription("Filter the dashboard by family member.")
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        self.person_combo.currentIndexChanged.connect(lambda: self._update_combo_tooltip(self.person_combo))
        layout.addWidget(self.person_combo)

        layout.addWidget(_sep())
        layout.addWidget(_combo_lbl("Account"))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(160)
        self.account_combo.setMinimumHeight(34)
        self.account_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.account_combo.setAccessibleName("Dashboard account selector")
        self.account_combo.setAccessibleDescription("Switch the dashboard to a specific bank account.")
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        self.account_combo.currentIndexChanged.connect(lambda: self._update_combo_tooltip(self.account_combo))
        layout.addWidget(self.account_combo)

        layout.addWidget(_sep())
        layout.addWidget(_combo_lbl("FY"))
        self.fy_combo = QComboBox()
        self.fy_combo.setMinimumWidth(100)
        self.fy_combo.setMinimumHeight(34)
        self.fy_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.fy_combo.setAccessibleName("Dashboard financial year selector")
        self.fy_combo.setAccessibleDescription("Choose the financial year shown in summaries.")
        self.fy_combo.currentTextChanged.connect(self._on_fy_changed)
        self.fy_combo.currentIndexChanged.connect(lambda: self._update_combo_tooltip(self.fy_combo))
        layout.addWidget(self.fy_combo)

        layout.addSpacing(8)
        btn_refresh = Theme.btn("⟳ Refresh", "secondary", height=34, min_width=102)
        btn_refresh.setToolTip("Hard refresh — reload all screens without logging out")
        btn_refresh.setAccessibleName("Hard Refresh")
        btn_refresh.clicked.connect(self._on_hard_refresh)
        layout.addWidget(btn_refresh)

        btn_logout = Theme.btn("Logout", "secondary", height=34, min_width=102)
        btn_logout.setAccessibleName("Logout")
        btn_logout.setAccessibleDescription("Sign out of the application.")
        btn_logout.clicked.connect(self._on_logout)
        layout.addWidget(btn_logout)

        return bar

    # ── Content stack ─────────────────────────────────────────────────────────

    def _build_content_area(self) -> QWidget:
        """Build content area with lazy-loaded screens. Only overview is built immediately."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()

        # Overview page (index 0) is built immediately since __init__ expects it
        overview = self._build_overview_page()
        self.stack.addWidget(overview)
        self._screen_pages[0] = overview

        # Add placeholders for remaining pages (will be replaced on first navigation)
        for i in range(1, len(_NAV_ITEMS)):
            placeholder = self._build_placeholder_page(i)
            self.stack.addWidget(placeholder)
            self._screen_pages[i] = None  # Mark as not yet loaded

        layout.addWidget(self.stack)
        return container

    def _build_placeholder_page(self, index: int) -> QWidget:
        """Build a lightweight placeholder page."""
        page = QWidget()
        page.setObjectName(f"placeholder_{index}")
        return page

    def _get_screen_page(self, index: int) -> QWidget:
        """Get or lazy-load the screen page at the given index."""
        if index in self._screen_pages and self._screen_pages[index] is not None:
            return self._screen_pages[index]

        if index in self._screen_errors:
            return self._build_error_page(index, self._screen_errors[index])

        # Try to load the screen
        try:
            page = self._load_screen_page(index)
            self._screen_pages[index] = page
            return page
        except Exception as e:
            error_msg = f"{_NAV_ITEMS[index][0]}: {type(e).__name__}: {str(e)}"
            self._screen_errors[index] = error_msg
            return self._build_error_page(index, error_msg)

    def _load_screen_page(self, index: int) -> QWidget:
        """Load a screen page at the given index. Raises if construction fails."""
        if index == 0:  # Overview
            return self._build_overview_page()
        elif index == 1:  # Accounts
            from ui.accounts_screen import AccountsScreen
            self.accounts_page = AccountsScreen()
            return self.accounts_page
        elif index == 2:  # Transactions
            from ui.transactions_screen import TransactionsScreen
            self.transactions_page = TransactionsScreen(self)
            return self.transactions_page
        elif index == 3:  # Income
            from ui.income_management_screen import IncomeManagementScreen
            self.income_page = IncomeManagementScreen(self)
            return self.income_page
        elif index == 4:  # Fixed Deposits
            from ui.fixed_deposits_screen import FixedDepositsScreen
            self.fd_page = FixedDepositsScreen(self)
            return self.fd_page
        elif index == 5:  # Statement Import
            from ui.statement_import_screen_modern import StatementImportScreen
            self.import_page = StatementImportScreen(self)
            return self.import_page
        elif index == 6:  # AIS/TIS
            from ui.ais_tis_import_screen_v2 import AISTISImportScreenV2
            self.ais_tis_page = AISTISImportScreenV2(self)
            return self.ais_tis_page
        elif index == 7:  # Tax
            from ui.tax_screen import TaxScreen
            self.tax_page = TaxScreen(self)
            return self.tax_page
        elif index == 8:  # Settings
            from ui.settings_screen import SettingsScreen
            self.settings_page = SettingsScreen(self)
            return self.settings_page
        else:
            raise ValueError(f"Unknown screen index: {index}")

    def _build_error_page(self, index: int, error_msg: str) -> QWidget:
        """Build an error page to display inline when screen construction fails."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()

        error_frame = QFrame()
        error_frame.setObjectName("errorFrame")
        error_layout = QVBoxLayout(error_frame)

        title = QLabel("Screen Load Error")
        title.setObjectName("errorTitle")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        error_layout.addWidget(title)

        msg = QLabel(error_msg)
        msg.setObjectName("errorMessage")
        msg.setFont(QFont("Segoe UI", 12))
        msg.setWordWrap(True)
        error_layout.addWidget(msg)

        error_layout.addStretch()

        error_container = QWidget()
        error_container_layout = QHBoxLayout(error_container)
        error_container_layout.addStretch()
        error_container_layout.addWidget(error_frame, stretch=1)
        error_container_layout.addStretch()

        layout.addWidget(error_container, stretch=1)
        layout.addStretch()

        return page

    # ── Overview page ─────────────────────────────────────────────────────────

    def _build_overview_page(self) -> QWidget:
        page = QWidget()

        scroll = QScrollArea()
        scroll.setObjectName("transparentSurface")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner.setObjectName("transparentSurface")
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(20)

        # FY banner
        banner = QFrame()
        self._overview_banner = banner  # keep ref for theme refresh
        banner.setObjectName("overviewBanner")
        banner.setMinimumHeight(70)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(24, 0, 24, 0)

        b_title = QLabel("Financial Overview")
        b_title.setObjectName("bannerTitle")
        b_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        b_layout.addWidget(b_title)
        b_layout.addStretch()

        self.banner_fy_lbl = QLabel("")
        self.banner_fy_lbl.setObjectName("bannerFyLabel")
        b_layout.addWidget(self.banner_fy_lbl)
        outer.addWidget(banner)

        # 2×2 Summary grid
        grid = QGridLayout()
        grid.setSpacing(18)

        self.panel_financial = SummaryPanel("Financial Summary", "chart_overview", accent=Theme.PRIMARY)
        self.panel_financial.add_stat("balance", "Total Balance",      "₹ —", value_size=16)
        self.panel_financial.add_stat("income",  "Total Credit (FY)",  "₹ —", value_color_role="SUCCESS")
        self.panel_financial.add_stat("expense", "Total Debit (FY)",   "₹ —", value_color_role="DANGER")
        self.panel_financial.add_divider()
        self.panel_financial.add_stat("savings", "Net Savings",        "₹ —", value_size=14, bold=True)
        grid.addWidget(self.panel_financial, 0, 0)

        self.panel_bank = SummaryPanel("Bank Accounts", "bank", accent=Theme.TEAL, scrollable=True)
        grid.addWidget(self.panel_bank, 0, 1)

        self.panel_interest = SummaryPanel("Interest Summary", "trend", accent=Theme.SUCCESS)
        self.panel_interest.add_stat("fd_curr",   "FD Interest (Current FY)",   "₹ —")
        self.panel_interest.add_stat("fd_next",   "FD Interest (Next FY est.)", "₹ —")
        self.panel_interest.add_divider()
        self.panel_interest.add_stat("sav_curr",  "Savings Interest (FY)",      "₹ —")
        self.panel_interest.add_stat("total_int", "Total Interest Income",      "₹ —", bold=True)
        grid.addWidget(self.panel_interest, 1, 0)

        self.panel_tax = SummaryPanel("Tax Summary", "tax", accent=Theme.WARNING)
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
            return
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
        regime  = "Old Regime" if tax_old < tax_new else ("New Regime" if tax_new < tax_old else "Either")
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

        # Lazy-load screen if not yet loaded
        screen = self._get_screen_page(index)
        if self._screen_pages.get(index) != screen:
            # First time loading - replace placeholder
            old_widget = self.stack.widget(index)
            self.stack.removeWidget(old_widget)
            self.stack.insertWidget(index, screen)
            self._screen_pages[index] = screen

        self._set_nav_active(index)
        self.stack.setCurrentIndex(index)
        self.page_title_lbl.setText(_NAV_ITEMS[index][0])
        self.page_title_lbl.updateGeometry()
        self._on_refresh_all()

    def _on_refresh_all(self):
        self._sync_context_selectors()
        idx = self.stack.currentIndex()
        pages = [
            lambda: self._refresh_overview(),
            lambda: self._refresh_accounts_page() if hasattr(self, 'accounts_page') else None,
            lambda: self.transactions_page.refresh() if hasattr(self, 'transactions_page') else None,
            lambda: self.income_page.refresh() if hasattr(self, 'income_page') else None,
            lambda: self.fd_page.refresh() if hasattr(self, 'fd_page') else None,
            lambda: self.import_page.refresh() if hasattr(self, 'import_page') else None,
            lambda: self.ais_tis_page.refresh() if hasattr(self, 'ais_tis_page') else None,
            lambda: self.tax_page.refresh() if hasattr(self, 'tax_page') else None,
            lambda: self.settings_page.refresh() if hasattr(self, 'settings_page') else None,
        ]
        if 0 <= idx < len(pages):
            try:
                pages[idx]()
            except Exception:
                pass  # If a page raises during refresh, silently skip

    def _refresh_accounts_page(self):
        """Update accounts page with current filters."""
        self.accounts_page.selected_person_id = session.selected_person_id
        self.accounts_page.selected_fy = session.selected_fy
        self.accounts_page._load_accounts()

    def _update_combo_tooltip(self, combo: QComboBox):
        """Set tooltip to the full current text so elided text is still visible on hover."""
        if combo.count() > 0:
            combo.setToolTip(combo.currentText())

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

    def _on_hard_refresh(self):
        """Reload all Python modules and rebuild the dashboard in-place."""
        import importlib, sys
        # Reload every app module (skip stdlib / site-packages)
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name, mod in list(sys.modules.items()):
            spec = getattr(mod, "__spec__", None)
            origin = getattr(spec, "origin", None) or ""
            if origin.startswith(app_root) and name not in ("__main__",):
                try:
                    importlib.reload(mod)
                except Exception:
                    pass
        # Re-apply theme stylesheet
        from PyQt6.QtWidgets import QApplication
        from ui.theme import Theme, ThemeManager
        ThemeManager.load_and_apply()
        QApplication.instance().setStyleSheet(Theme.get_stylesheet())
        # Rebuild the whole UI in-place
        self._build_ui()
        self._populate_selectors()
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

    def _toggle_sidebar(self):
        """Manually expand/collapse the sidebar via the bottom toggle button."""
        if self.sidebar_expanded:
            self._collapse_sidebar()
        else:
            self._expand_sidebar()
        session.set_sidebar_open(self.sidebar_expanded)
        self._update_sidebar_toggle_btn()

    def _update_sidebar_toggle_btn(self):
        """Sync the toggle button's icon/tooltip to the current sidebar state."""
        if not hasattr(self, '_sidebar_toggle_btn') or not self._sidebar_toggle_btn:
            return
        if self.sidebar_expanded:
            name, tip = "sidebar_collapse", "Collapse sidebar"
        else:
            name, tip = "sidebar_expand", "Expand sidebar"
        self._sidebar_toggle_btn.setToolTip(tip)
        self._sidebar_toggle_btn.setAccessibleName(tip)
        if icons_available():
            self._sidebar_toggle_btn.setIcon(app_icon(name, color=Theme.SIDEBAR_TEXT, size=16))
            self._sidebar_toggle_btn.setText("")
        else:
            self._sidebar_toggle_btn.setIcon(QIcon())
            self._sidebar_toggle_btn.setText(icon_fallback(name))

    def _expand_sidebar(self):
        """Expand sidebar to show labels"""
        if self.sidebar_expanded:
            return
        self.sidebar_expanded = True
        sidebar = self.findChild(QWidget, "sidebar")
        if sidebar:
            sidebar.setFixedWidth(248)

        # Show text elements
        if hasattr(self, 'brand_text'):
            self.brand_text.setVisible(True)
        if hasattr(self, 'nav_lbl'):
            self.nav_lbl.setVisible(True)
        if hasattr(self, 'ver_lbl'):
            self.ver_lbl.setText("v1.0.0  ·  Offline")

        # Resize icons to natural width (24px) and show all nav labels
        for btn in self._nav_buttons:
            icon_label = btn._icon_label
            if icon_label:
                icon_label.setFixedWidth(24)
            text_label = btn._text_label
            if text_label:
                text_label.setVisible(True)

    def _collapse_sidebar(self):
        """Collapse sidebar to show only icons"""
        if not self.sidebar_expanded:
            return
        self.sidebar_expanded = False
        sidebar = self.findChild(QWidget, "sidebar")
        if sidebar:
            sidebar.setFixedWidth(76)

        # Hide text elements
        if hasattr(self, 'brand_text'):
            self.brand_text.setVisible(False)
        if hasattr(self, 'nav_lbl'):
            self.nav_lbl.setVisible(False)
        if hasattr(self, 'ver_lbl'):
            self.ver_lbl.setText("v1.0")

        # Resize icons to fill rail (76px) and hide all nav labels
        for btn in self._nav_buttons:
            icon_label = btn._icon_label
            if icon_label:
                icon_label.setFixedWidth(76)
            text_label = btn._text_label
            if text_label:
                text_label.setVisible(False)
