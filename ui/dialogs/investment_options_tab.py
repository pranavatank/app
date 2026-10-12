"""ui/dialogs/investment_options_tab.py — FD planner tab comparing government-backed alternatives to bank FDs."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices

from ui.theme import Theme
from ui.widgets.money_label import format_inr
from config import DICGC_INSURANCE_LIMIT
from engines.investment_options import (
    SCHEMES_PERIOD, INDIA_POST_RATES_URL, eligible_options, format_lock_in, project_option, schemes_outdated
)

_CAPPED_NOTE = " Capped at the scheme limit."
_NO_SELECTION_TEXT = "Select a scheme to see how it pays out."


def _right_aligned_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


def _info_text() -> str:
    text = (
        f"Government-backed rates for the {SCHEMES_PERIOD} quarter. These are guaranteed by the "
        f"Government of India, so the {format_inr(DICGC_INSURANCE_LIMIT)} bank-insurance cap does not apply."
    )
    if schemes_outdated():
        text += f" These rates were set for {SCHEMES_PERIOD} — check the official page for the current quarter."
    return text


class InvestmentOptionsTab(QWidget):
    COLUMNS = ["Scheme", "Rate %", "Lock-in", "Who Can Invest", "Max", "Tax", "You'd Invest", "Interest Earned"]
    RIGHT_ALIGNED_COLUMNS = {1, 6, 7}
    STRETCH_COLUMNS = {5}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh(0, False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addLayout(self._build_header())

        self.amount_lbl = QLabel()
        self.amount_lbl.setProperty("textrole", "emphasis-sm")
        layout.addWidget(self.amount_lbl)

        self._build_table(layout)

        self.details_lbl = QLabel(_NO_SELECTION_TEXT)
        self.details_lbl.setProperty("textrole", "muted-sm")
        self.details_lbl.setWordWrap(True)
        layout.addWidget(self.details_lbl)

        footnote = QLabel(
            "Market-linked options such as liquid or arbitrage mutual funds and Treasury Bills "
            "(through RBI Retail Direct) can also hold surplus cash, but their returns are not fixed or guaranteed."
        )
        footnote.setProperty("textrole", "muted-sm")
        footnote.setWordWrap(True)
        layout.addWidget(footnote)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()

        self.info_lbl = QLabel(_info_text())
        self.info_lbl.setProperty("textrole", "muted-sm")
        self.info_lbl.setWordWrap(True)
        header.addWidget(self.info_lbl, stretch=1)

        btn_official = Theme.btn("Official Rates", "secondary", height=Theme.HEIGHT_MD, min_width=140)
        btn_official.setAccessibleName("Open official small savings rates")
        btn_official.clicked.connect(self._on_open_official_rates)
        header.addWidget(btn_official)
        return header

    def _build_table(self, layout: QVBoxLayout) -> None:
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.currentCellChanged.connect(self._on_row_changed)

        header = self.table.horizontalHeader()
        for column in range(self.table.columnCount()):
            mode = QHeaderView.ResizeMode.Stretch if column in self.STRETCH_COLUMNS else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)

        self.table.setAccessibleName("Government-backed investment options")
        layout.addWidget(self.table, stretch=1)

    def refresh(self, amount: float, is_senior: bool, best_bank_rate: float | None = None) -> None:
        amount = max(float(amount or 0), 0)
        self.amount_lbl.setText(
            f"Projected for {format_inr(amount)}" if amount > 0
            else "Enter an amount on the Split Savings tab to see projected values."
        )
        self.details_lbl.setText(_NO_SELECTION_TEXT)
        options = sorted(eligible_options(is_senior), key=lambda option: -option["rate"])
        self._row_details = []
        self.table.blockSignals(True)
        self.table.setRowCount(len(options))
        for row, option in enumerate(options):
            self._set_row(row, option, amount, best_bank_rate)
        self.table.blockSignals(False)

    def _set_row(self, row: int, option: dict, amount: float, best_bank_rate: float | None) -> None:
        projection = project_option(option, amount) if amount > 0 else None
        details = option["notes"] + (_CAPPED_NOTE if projection and projection["capped"] else "")
        self._row_details.append(f"{option['name']}: {details}")
        cells = [
            option["name"],
            f"{option['rate']:.2f}",
            format_lock_in(option["tenure_months"]),
            option["eligibility"],
            format_inr(option["max_amount"]) if option["max_amount"] else "No limit",
            option["tax"],
            format_inr(projection["invested"]) if projection else "—",
            format_inr(projection["interest"]) if projection else "—",
        ]
        for column, text in enumerate(cells):
            item = _right_aligned_item(text) if column in self.RIGHT_ALIGNED_COLUMNS else QTableWidgetItem(text)
            self.table.setItem(row, column, item)
        self.table.item(row, 0).setToolTip(details)

        if best_bank_rate is not None and option["rate"] > best_bank_rate:
            self._highlight_beating_rate(row, details)

    def _highlight_beating_rate(self, row: int, details: str) -> None:
        name_item = self.table.item(row, 0)
        rate_item = self.table.item(row, 1)
        for item in (name_item, rate_item):
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setForeground(QColor(Theme.SUCCESS))
        name_item.setToolTip(f"{details}\nBeats the best bank FD rate for this tenure")

    def _on_row_changed(self, row: int, *_) -> None:
        if 0 <= row < len(self._row_details):
            self.details_lbl.setText(self._row_details[row])
        else:
            self.details_lbl.setText(_NO_SELECTION_TEXT)

    def _on_open_official_rates(self) -> None:
        QDesktopServices.openUrl(QUrl(INDIA_POST_RATES_URL))
