"""
ui/reports_screen.py — Reports & Analytics.

Charts fixed:
  • Overview    : comparison bar (credit vs debit) + metric cards with shadows
  • Categories  : donut pie with legend
  • Bank-wise   : horizontal bar sorted by balance
  • Interest    : multi-line trend (FD + Savings per FY)
  • Monthly     : new tab — monthly side-by-side bars for selected FY
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QTabWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import set_btn_icon, icon as _app_icon, is_available as _icons_ok
from core.session import session

def _tab_icon(name): return _app_icon(name)
from config import get_all_financial_years
from models.transaction import get_income_total, get_expense_total, get_category_summary
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.bank_account import get_account, get_accounts_for_person, get_all_accounts
from ui.widgets.chart_widget import ChartWidget


# Month names for monthly tab
_MONTHS = [
    ("Apr", 4), ("May", 5), ("Jun", 6),
    ("Jul", 7), ("Aug", 8), ("Sep", 9),
    ("Oct", 10), ("Nov", 11), ("Dec", 12),
    ("Jan", 1), ("Feb", 2), ("Mar", 3),
]


def _monthly_data(person_id, financial_year: str, account_id: int | None = None):
    """Return (month_labels, income_list, expense_list) for a FY."""
    from core.database import get_connection
    fy_year = int(financial_year.split("-")[0])

    labels, income_vals, expense_vals = [], [], []
    conn = get_connection()
    for name, month in _MONTHS:
        year = fy_year if month >= 4 else fy_year + 1
        from calendar import monthrange
        last_day = monthrange(year, month)[1]
        m_start = f"{year}-{month:02d}-01"
        m_end   = f"{year}-{month:02d}-{last_day:02d}"

        q = """
            SELECT transaction_type, SUM(amount) AS total
            FROM Transactions
            WHERE transaction_date BETWEEN ? AND ?
              AND COALESCE(is_internal_transfer, 0) = 0
        """
        params = [m_start, m_end]
        if person_id:
            q += " AND person_id = ?"
            params.append(person_id)
        if account_id:
            q += " AND account_id = ?"
            params.append(account_id)
        q += " GROUP BY transaction_type"

        rows = conn.execute(q, params).fetchall()
        row_map = {r["transaction_type"]: r["total"] or 0 for r in rows}

        labels.append(name)
        income_vals.append(row_map.get("Income", 0))
        expense_vals.append(row_map.get("Expense", 0))

    conn.close()
    return labels, income_vals, expense_vals


class ReportsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # ── Header ───────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Reports & Analytics")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(15))
        header.addWidget(title)
        header.addStretch()

        fy_lbl = QLabel("FY:")
        fy_lbl.setStyleSheet(Theme.section_label_style())
        header.addWidget(fy_lbl)

        self.fy_combo = QComboBox()
        self.fy_combo.setFixedWidth(100)
        self.fy_combo.setFixedHeight(36)
        self.fy_combo.setAccessibleName("Reports financial year selector")
        self.fy_combo.setAccessibleDescription("Choose the financial year for the report tabs.")
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.fy_combo.addItem(fy)
        self.fy_combo.setCurrentText(session.selected_fy)
        self.fy_combo.currentTextChanged.connect(self._on_fy_change)
        header.addWidget(self.fy_combo)

        btn = Theme.btn("  Refresh", "primary", height=36, min_width=105)
        set_btn_icon(btn, "refresh")
        btn.setAccessibleName("Refresh reports")
        btn.setAccessibleDescription("Reload the charts for the selected financial year.")
        btn.clicked.connect(self.refresh)
        header.addWidget(btn)
        layout.addLayout(header)

        # ── Tabs ─────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Reports tabs")
        self.tabs.setAccessibleDescription("Switch between overview, monthly, category, bank-wise, and interest charts.")
        self.tabs.addTab(self._build_overview_tab(),   "Overview")
        self.tabs.addTab(self._build_monthly_tab(),    "Monthly")
        self.tabs.addTab(self._build_category_tab(),   "Categories")
        self.tabs.addTab(self._build_bank_tab(),       "Bank-wise")
        self.tabs.addTab(self._build_interest_tab(),   "Interest Trend")
        if _icons_ok():
            self.tabs.setTabIcon(0, _tab_icon("chart_overview"))
            self.tabs.setTabIcon(1, _tab_icon("monthly"))
            self.tabs.setTabIcon(2, _tab_icon("chart_pie"))
            self.tabs.setTabIcon(3, _tab_icon("bank"))
            self.tabs.setTabIcon(4, _tab_icon("trend"))
        layout.addWidget(self.tabs)

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _build_overview_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Metric cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        self.income_card  = self._metric_card("Total Credit",  "₹ —", Theme.SUCCESS, Theme.SUCCESS_LIGHT)
        self.expense_card = self._metric_card("Total Debit",   "₹ —", Theme.DANGER,  Theme.DANGER_LIGHT)
        self.net_card     = self._metric_card("Net Savings",   "₹ —", Theme.PRIMARY, Theme.PRIMARY_LIGHT)
        cards_row.addWidget(self.income_card)
        cards_row.addWidget(self.expense_card)
        cards_row.addWidget(self.net_card)
        layout.addLayout(cards_row)

        self.overview_chart = ChartWidget()
        layout.addWidget(self.overview_chart)
        return w

    def _build_monthly_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        lbl = QLabel("Month-wise Credit vs Debit for selected FY")
        lbl.setStyleSheet(Theme.muted_style(12) + " margin-bottom: 6px;")
        layout.addWidget(lbl)
        self.monthly_chart = ChartWidget()
        layout.addWidget(self.monthly_chart)
        return w

    def _build_category_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        lbl = QLabel("Debit breakdown by category (top 8)")
        lbl.setStyleSheet(Theme.muted_style(12) + " margin-bottom: 6px;")
        layout.addWidget(lbl)
        self.category_chart = ChartWidget()
        layout.addWidget(self.category_chart)
        return w

    def _build_bank_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        lbl = QLabel("Current balance distribution across bank accounts")
        lbl.setStyleSheet(Theme.muted_style(12) + " margin-bottom: 6px;")
        layout.addWidget(lbl)
        self.bank_chart = ChartWidget()
        layout.addWidget(self.bank_chart)
        return w

    def _build_interest_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        lbl = QLabel("FD Interest & Savings Interest trend across financial years")
        lbl.setStyleSheet(Theme.muted_style(12) + " margin-bottom: 6px;")
        layout.addWidget(lbl)
        self.interest_chart = ChartWidget()
        layout.addWidget(self.interest_chart)
        return w

    # ── Metric card ───────────────────────────────────────────────────────────

    def _metric_card(self, title: str, value: str, accent: str, bg: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(Theme.stat_tile_style(accent, radius=14))
        card.setGraphicsEffect(Theme.shadow_card())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(
            Theme.text_style(color=accent, size=12, weight=600)
            + " border: none; background: transparent; padding: 0; margin: 0;"
        )
        layout.addWidget(t_lbl)

        v_lbl = QLabel(value)
        v_lbl.setObjectName("value")
        v_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        v_lbl.setStyleSheet(
            Theme.text_style(color=accent, size=20, weight=700)
            + " border: none; background: transparent; padding: 0; margin: 0;"
        )
        layout.addWidget(v_lbl)

        return card

    def _update_card(self, card: QFrame, value: str):
        v = card.findChild(QLabel, "value")
        if v:
            v.setText(value)

    def _on_fy_change(self, fy: str):
        if not fy:
            return
        if self.parent_window and hasattr(self.parent_window, "_on_fy_changed"):
            self.parent_window._on_fy_changed(fy)
        else:
            session.set_financial_year(fy)
            self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        pid = session.selected_person_id
        aid = session.selected_account_id
        fy  = session.selected_fy or self.fy_combo.currentText()
        if fy and self.fy_combo.currentText() != fy:
            self.fy_combo.blockSignals(True)
            self.fy_combo.setCurrentText(fy)
            self.fy_combo.blockSignals(False)
        if not fy:
            return
        self._refresh_overview(pid, aid, fy)
        self._refresh_monthly(pid, aid, fy)
        self._refresh_category(pid, aid, fy)
        self._refresh_bank(pid, aid)
        self._refresh_interest(pid, aid)

    def _refresh_overview(self, pid, aid, fy):
        income  = get_income_total(person_id=pid, financial_year=fy, account_id=aid)
        expense = get_expense_total(person_id=pid, financial_year=fy, account_id=aid)
        net     = income - expense

        self._update_card(self.income_card,  f"₹ {income:,.2f}")
        self._update_card(self.expense_card, f"₹ {expense:,.2f}")

        net_color = Theme.SUCCESS if net >= 0 else Theme.DANGER
        net_label = card = self.net_card.findChild(QLabel, "value")
        if net_label:
            net_label.setText(f"₹ {net:,.2f}")
            net_label.setStyleSheet(Theme.text_style(color=net_color, size=20, weight=700))

        if income == 0 and expense == 0:
            self.overview_chart.show_empty_state("No transactions found for this period")
            return

        self.overview_chart.plot_comparison(
            categories=["Credit", "Debit"],
            values1=[income, 0],
            values2=[0, expense],
            label1="Credit",
            label2="Debit",
            title=f"Credit vs Debit — FY {fy}",
            ylabel="Amount (₹)",
        )

    def _refresh_monthly(self, pid, aid, fy):
        try:
            months, income, expense = _monthly_data(pid, fy, aid)
            if all(v == 0 for v in income) and all(v == 0 for v in expense):
                self.monthly_chart.show_empty_state("No monthly data for this period")
                return
            self.monthly_chart.plot_monthly_bar(
                months=months,
                income=income,
                expense=expense,
                title=f"Monthly Overview — FY {fy}",
            )
        except Exception:
            self.monthly_chart.show_empty_state("Could not load monthly data")

    def _refresh_category(self, pid, aid, fy):
        cats = get_category_summary(person_id=pid, financial_year=fy, account_id=aid)
        if not cats:
            self.category_chart.show_empty_state("No category data for this period")
            return
        top = cats[:8]
        self.category_chart.plot_pie(
            labels=[c["category"] or "Uncategorised" for c in top],
            values=[c["total"] for c in top],
            title=f"Debit by Category — FY {fy}",
        )

    def _refresh_bank(self, pid, aid):
        if aid is not None:
            acc = get_account(aid)
            accounts = [acc] if acc else []
        else:
            accounts = get_accounts_for_person(pid) if pid else get_all_accounts()
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

    def _refresh_interest(self, pid, aid):
        fys = list(reversed(get_all_financial_years(since_year=2020)))

        fd_interests  = [get_total_fd_interest(fy, pid, aid)      for fy in fys]
        sav_interests = [get_total_savings_interest(fy, pid, aid)  for fy in fys]

        if all(v == 0 for v in fd_interests) and all(v == 0 for v in sav_interests):
            self.interest_chart.show_empty_state("No interest records found")
            return

        self.interest_chart.plot_trend_line(
            categories=fys,
            series={
                "FD Interest":      fd_interests,
                "Savings Interest": sav_interests,
            },
            title="Interest Income Trend",
            xlabel="Financial Year",
            ylabel="Amount (₹)",
        )
