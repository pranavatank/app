"""ui/dialogs/fd_coverage_tab.py — FD planner tab showing how much of each bank's deposit-insurance cover is used."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ui.theme import Theme
from ui.widgets.money_label import format_inr
from engines.fd_allocation_engine import get_coverage_report, COVERAGE_OVER, COVERAGE_NEAR, COVERAGE_OK


def _status_color(status: str) -> str:
    colors = {COVERAGE_OVER: Theme.DANGER, COVERAGE_NEAR: Theme.WARNING_DARK, COVERAGE_OK: Theme.SUCCESS}
    return colors[status]


def _bank_count(n: int) -> str:
    return "1 bank" if n == 1 else f"{n} banks"


def _right_aligned_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


class CoverageTab(QWidget):
    COLUMNS = ["Person", "Bank", "Savings", "FDs (incl. interest)", "Total", "Room Left", "Used", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.summary_lbl = QLabel()
        self.summary_lbl.setProperty("textrole", "emphasis-sm")
        self.summary_lbl.setWordWrap(True)
        layout.addWidget(self.summary_lbl)

        self.explain_lbl = QLabel()
        self.explain_lbl.setProperty("textrole", "muted-sm")
        self.explain_lbl.setWordWrap(True)
        layout.addWidget(self.explain_lbl)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._size_columns(self.table, stretch_columns={1})
        self.table.setAccessibleName("Deposit insurance coverage by bank")
        layout.addWidget(self.table, stretch=1)

        self.empty_lbl = QLabel(
            "No savings or FD balances recorded yet. Import statements or add FDs to see your coverage."
        )
        self.empty_lbl.setProperty("textrole", "muted-sm")
        self.empty_lbl.setWordWrap(True)
        self.empty_lbl.setVisible(False)
        layout.addWidget(self.empty_lbl)

    @staticmethod
    def _size_columns(table: QTableWidget, stretch_columns: set[int]) -> None:
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            mode = QHeaderView.ResizeMode.Stretch if column in stretch_columns else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)

    def refresh(self, persons: list[dict], per_bank_limit: float) -> None:
        self.explain_lbl.setText(
            f"DICGC insures up to {format_inr(per_bank_limit)} per person per bank — savings, FDs and interest added together. "
            "Anything above that at one bank is not insured."
        )
        rows = get_coverage_report(persons, per_bank_limit)
        self.table.setColumnHidden(0, len(persons) <= 1)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self._set_row(row_index, row)
        self.table.setVisible(bool(rows))
        self.empty_lbl.setVisible(not rows)
        self._update_summary(rows, per_bank_limit)

    def _set_row(self, row_index: int, row: dict) -> None:
        cells = [
            row["person_name"],
            row["bank_name"],
            format_inr(row["savings_amount"]),
            format_inr(row["fd_amount"]),
            format_inr(row["total"]),
            format_inr(row["headroom"]),
            f"{row['used_pct']:.0f}%",
        ]
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text) if column in (0, 1) else _right_aligned_item(text)
            self.table.setItem(row_index, column, item)

        status_item = QTableWidgetItem(row["status"])
        status_item.setForeground(QColor(_status_color(row["status"])))
        status_font = status_item.font()
        status_font.setBold(True)
        status_item.setFont(status_font)
        self.table.setItem(row_index, 7, status_item)

    def _update_summary(self, rows: list[dict], per_bank_limit: float) -> None:
        text = self._summary_text(rows, per_bank_limit)
        self.summary_lbl.setText(text)
        self.summary_lbl.setVisible(bool(text))

    @staticmethod
    def _summary_text(rows: list[dict], per_bank_limit: float) -> str:
        if not rows:
            return ""
        over = [row for row in rows if row["status"] == COVERAGE_OVER]
        near = [row for row in rows if row["status"] == COVERAGE_NEAR]
        if over:
            uninsured = sum(max(row["total"] - per_bank_limit, 0) for row in over)
            near_part = f" and {_bank_count(len(near))} close to it" if near else ""
            return (
                f"{_bank_count(len(over))} above the insured limit{near_part} — "
                f"{format_inr(uninsured)} is currently uninsured. Move the excess to another bank or family member."
            )
        if near:
            return f"{_bank_count(len(near))} close to the insured limit — put new deposits elsewhere."
        return "All your deposits are within the insured limit."
