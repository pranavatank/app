"""Inclusive date filters for transaction pickers."""

from datetime import date

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QCheckBox, QDateEdit, QHBoxLayout, QLabel, QWidget


class TransactionDateRange(QWidget):
    changed = Signal()

    def __init__(self, start: date, end: date, *, enabled: bool = True, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.enabled = QCheckBox("Filter by date")
        self.enabled.setChecked(enabled)
        layout.addWidget(self.enabled)
        self.start = QDateEdit(QDate(start.year, start.month, start.day), self)
        self.end = QDateEdit(QDate(end.year, end.month, end.day), self)
        for label, edit in (("From", self.start), ("To", self.end)):
            edit.setDisplayFormat("dd MMM yyyy")
            edit.setCalendarPopup(True)
            edit.setAccessibleName(f"{label} transaction date")
            edit.setEnabled(enabled)
            layout.addWidget(QLabel(label))
            layout.addWidget(edit)
            edit.dateChanged.connect(self.changed)
        layout.addStretch()
        self.enabled.toggled.connect(self._toggle)

    def _toggle(self, enabled):
        self.start.setEnabled(enabled)
        self.end.setEnabled(enabled)
        self.changed.emit()

    def contains(self, value: str) -> bool:
        try:
            day = date.fromisoformat(value)
        except (TypeError, ValueError):
            return False
        return not self.enabled.isChecked() or self.start.date().toPython() <= day <= self.end.date().toPython()
