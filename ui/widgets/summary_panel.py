"""
ui/widgets/summary_panel.py — Summary card widget for dashboard panels.
Supports live theme switching via refresh_theme().
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ui.theme import Theme


class SummaryPanel(QFrame):
    """
    Styled card with coloured left-border accent, icon, title, and stat rows.

    API:
        add_stat(key, label, value, value_size, value_color, bold)
        add_divider()
        update_stat(key, value)
        clear_stats()
        refresh_theme()   ← call after a theme change
    """

    def __init__(self, title: str, icon: str = "",
                 accent: str = None,
                 scrollable: bool = False,
                 parent=None):
        super().__init__(parent)
        self._rows:      dict[str, QLabel] = {}
        self._scrollable = scrollable
        self._accent     = accent or Theme.PRIMARY

        # Keep refs to re-style on theme change
        self._title_lbl:  QLabel | None = None
        self._div:        QFrame | None = None
        self._icon_bg:    QLabel | None = None

        self.setObjectName("SummaryPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_card_style()
        self.setGraphicsEffect(Theme.shadow_card())

        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(20, 18, 20, 18)

        # ── Header ───────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        if icon:
            self._icon_bg = QLabel(icon)
            self._icon_bg.setFont(QFont("Segoe UI Emoji", 15))
            self._icon_bg.setFixedSize(38, 38)
            self._icon_bg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._icon_bg.setStyleSheet(self._icon_css())
            header_row.addWidget(self._icon_bg)

        self._title_lbl = QLabel(title)
        self._title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))
        header_row.addWidget(self._title_lbl)
        header_row.addStretch()
        outer.addLayout(header_row)
        outer.addSpacing(12)

        # ── Accent divider ────────────────────────────────────────────────────
        self._div = QFrame()
        self._div.setFixedHeight(1)
        self._div.setStyleSheet(f"background: {Theme.DIVIDER};")
        outer.addWidget(self._div)
        outer.addSpacing(12)

        # ── Stats area ────────────────────────────────────────────────────────
        if scrollable:
            self._stats_container = QWidget()
            self._stats_container.setStyleSheet("background: transparent; border: none;")
            self._stats_layout = QVBoxLayout(self._stats_container)
            self._stats_layout.setSpacing(10)
            self._stats_layout.setContentsMargins(0, 0, 0, 0)
            self._stats_layout.addStretch()

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(self._stats_container)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("background: transparent; border: none;")
            outer.addWidget(scroll)
        else:
            self._stats_layout = QVBoxLayout()
            self._stats_layout.setSpacing(10)
            outer.addLayout(self._stats_layout)
            outer.addStretch()

    # ── Style helpers ─────────────────────────────────────────────────────────

    def _apply_card_style(self):
        self.setStyleSheet(
            Theme.card_style(
                border_color=Theme.BORDER,
                left_accent=self._accent,
                radius=14,
                padding=0,
                selector="QFrame#SummaryPanel",
            )
        )

    def _icon_css(self) -> str:
        return (
            f"background-color: {self._accent}1A;"
            f"border-radius: 10px;"
            f"border: 1px solid {self._accent}30;"
        )

    # ── Live theme refresh ────────────────────────────────────────────────────

    def refresh_theme(self):
        """Re-apply all inline styles after a theme switch."""
        self._apply_card_style()
        self.setGraphicsEffect(Theme.shadow_card())
        if self._icon_bg:
            self._icon_bg.setStyleSheet(self._icon_css())
        if self._title_lbl:
            self._title_lbl.setStyleSheet(
                Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))
        if self._div:
            self._div.setStyleSheet(f"background: {Theme.DIVIDER};")
        self.update()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_stat(
        self,
        key: str,
        label: str,
        value: str = "—",
        value_size: int = 13,
        value_color: str = None,
        bold: bool = False,
    ) -> None:
        row_w = QWidget()
        row_w.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        lbl = QLabel(label)
        lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=12))
        lbl.setWordWrap(False)

        color  = value_color or Theme.TEXT_PRIMARY
        weight = "700" if bold else "500"
        val = QLabel(value)
        val.setStyleSheet(
            f"font-size: {value_size}px; font-weight: {weight};"
            f" color: {color}; background: transparent; border: none;"
        )
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(lbl, stretch=1)
        row.addWidget(val, stretch=0)
        self._insert_widget(row_w)
        self._rows[key] = val

    def add_divider(self) -> None:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {Theme.DIVIDER};")
        self._insert_widget(line)

    def _insert_widget(self, widget: QWidget):
        count = self._stats_layout.count()
        if count > 0:
            last = self._stats_layout.itemAt(count - 1)
            if last and last.spacerItem():
                self._stats_layout.insertWidget(count - 1, widget)
                return
        self._stats_layout.addWidget(widget)

    def update_stat(self, key: str, value: str) -> None:
        if key in self._rows:
            self._rows[key].setText(value)

    def clear_stats(self) -> None:
        self._rows.clear()
        while self._stats_layout.count():
            item = self._stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._scrollable:
            self._stats_layout.addStretch()
