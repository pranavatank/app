"""
ui/reports_screen.py — Reports & Analytics with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTabWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from core.session import session
from config import get_all_financial_years
from models.transaction import get_income_total, get_expense_total, get_category_summary
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.bank_account import get_accounts_for_person, get_all_accounts
from ui.widgets.chart_widget import ChartWidget


class ReportsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Header
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
        self.fy_combo.setFixedWidth(100); self.fy_combo.setFixedHeight(34)
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.fy_combo.addItem(fy)
        self.fy_combo.setCurrentText(session.selected_fy)
        self.fy_combo.currentTextChanged.connect(lambda _: self.refresh())
        header.addWidget(self.fy_combo)

        btn = Theme.btn("🔄  Refresh", "primary", height=34, min_width=105)
        btn.clicked.connect(self.refresh)
        header.addWidget(btn)
        layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_overview_tab(),  "📊 Overview")
        self.tabs.addTab(self._build_category_tab(),  "🥧 Categories")
        self.tabs.addTab(self._build_bank_tab(),       "🏦 Bank-wise")
        self.tabs.addTab(self._build_interest_tab(),   "📈 Interest Trend")
        layout.addWidget(self.tabs)

    def _build_overview_tab(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w); layout.setSpacing(16); layout.setContentsMargins(16,16,16,16)

        cards_row = QHBoxLayout(); cards_row.setSpacing(14)
        self.income_card  = self._metric_card("Total Credit",  "₹ 0", Theme.SUCCESS, Theme.SUCCESS_LIGHT)
        self.expense_card = self._metric_card("Total Debit", "₹ 0", Theme.DANGER,  Theme.DANGER_LIGHT)
        self.net_card     = self._metric_card("Net Savings",   "₹ 0", Theme.PRIMARY, Theme.PRIMARY_LIGHT)
        cards_row.addWidget(self.income_card)
        cards_row.addWidget(self.expense_card)
        cards_row.addWidget(self.net_card)
        layout.addLayout(cards_row)

        self.overview_chart = ChartWidget()
        layout.addWidget(self.overview_chart)
        return w

    def _build_category_tab(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16)
        lbl = QLabel("Debit breakdown by category")
        lbl.setStyleSheet(Theme.muted_style(12) + " margin-bottom: 8px;")
        layout.addWidget(lbl)
        self.category_chart = ChartWidget()
        layout.addWidget(self.category_chart)
        return w

    def _build_bank_tab(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16)
        lbl = QLabel("Balance distribution across bank accounts")
        lbl.setStyleSheet(Theme.muted_style(12) + " margin-bottom: 8px;")
        layout.addWidget(lbl)
        self.bank_chart = ChartWidget()
        layout.addWidget(self.bank_chart)
        return w

    def _build_interest_tab(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background: {Theme.BG};")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16)
        lbl = QLabel("Interest income over financial years")
        lbl.setStyleSheet(Theme.muted_style(12) + " margin-bottom: 8px;")
        layout.addWidget(lbl)
        self.interest_chart = ChartWidget()
        layout.addWidget(self.interest_chart)
        return w

    def _metric_card(self, title: str, value: str, accent: str, bg: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(Theme.card_style(bg=bg, border_color=accent, left_accent=accent, padding=16))
        layout = QVBoxLayout(card); layout.setContentsMargins(16,14,16,14); layout.setSpacing(6)

        t = QLabel(title)
        t.setStyleSheet(Theme.text_style(color=accent, size=12, weight=600))
        layout.addWidget(t)

        v = QLabel(value)
        v.setObjectName("value")
        v.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        v.setStyleSheet(Theme.text_style(color=accent, size=20, weight=700))
        layout.addWidget(v)
        return card

    def _update_card(self, card: QFrame, value: str):
        v = card.findChild(QLabel, "value")
        if v: v.setText(value)

    def refresh(self):
        pid = session.selected_person_id
        fy  = self.fy_combo.currentText()
        self._refresh_overview(pid, fy)
        self._refresh_category(pid, fy)
        self._refresh_bank(pid)
        self._refresh_interest(pid)

    def _refresh_overview(self, pid, fy):
        income  = get_income_total(pid, fy)
        expense = get_expense_total(pid, fy)
        net     = income - expense
        self._update_card(self.income_card,  f"₹ {income:,.2f}")
        self._update_card(self.expense_card, f"₹ {expense:,.2f}")
        self._update_card(self.net_card,     f"₹ {net:,.2f}")
        self.overview_chart.plot_comparison(
            categories=["Credit","Debit"],
            values1=[income, 0], values2=[0, expense],
            label1="Credit", label2="Debit",
            title=f"Credit vs Debit — FY {fy}", ylabel="Amount (₹)")

    def _refresh_category(self, pid, fy):
        cats = get_category_summary(pid, fy)
        if not cats: self.category_chart.clear(); return
        self.category_chart.plot_pie(
            labels=[c["category"] for c in cats[:10]],
            values=[c["total"]    for c in cats[:10]],
            title=f"Debit by Category — FY {fy}")

    def _refresh_bank(self, pid):
        accounts = get_accounts_for_person(pid) if pid else get_all_accounts()
        if not accounts: self.bank_chart.clear(); return
        self.bank_chart.plot_bar(
            categories=[f"{a.get('bank_display_name', a['bank_name'])}\n{a['account_type']}" for a in accounts],
            values=[a["current_balance"] for a in accounts],
            title="Balance by Bank Account", ylabel="Balance (₹)")

    def _refresh_interest(self, pid):
        fys = get_all_financial_years(since_year=2020)
        self.interest_chart.plot_comparison(
            categories=fys,
            values1=[get_total_fd_interest(fy, pid) for fy in fys],
            values2=[get_total_savings_interest(fy, pid) for fy in fys],
            label1="FD Interest", label2="Savings Interest",
            title="Interest Income Trend", xlabel="Financial Year", ylabel="Interest (₹)")
