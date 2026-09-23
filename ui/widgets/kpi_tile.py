"""
ui/widgets/kpi_tile.py — Reusable KPI tile component for dashboards.

Features:
- Small muted label text
- Large value text with tabular figures, colored by sign
- Optional delta chip (e.g., "+12%" in green or "-5%" in red)
- Optional sparkline (simple polyline with QPainter)
- Fixed height (100-110px) with no dead space below content
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PySide6.QtGui import QFont, QPainter, QPen, QColor
from PySide6.QtCore import Qt

from ui.theme import Theme
from ui.widgets.money_label import format_inr


class KpiTile(QFrame):
    """
    A reusable KPI tile component with label, value, optional delta, and optional sparkline.

    Constructor:
        label: str — Title text (e.g., "Total Balance")
        value: float or str — Value to display (numeric for currency, or string)
        delta: float or None — Percentage change (e.g., 12 for +12%, -5 for -5%)
        sparkline_data: list[float] or None — Points for a simple sparkline trend line
        is_currency: bool — If True, format value as currency with INR; if False, display as-is
    """

    def __init__(
        self,
        label: str,
        value,
        delta=None,
        sparkline_data=None,
        is_currency=True,
        parent=None,
        accent: str = "primary",
        icon: str = ""
    ):
        super().__init__(parent)
        self.label_text = label
        self.value = value
        self.delta = delta
        self.sparkline_data = sparkline_data
        self.is_currency = is_currency
        self._accent = accent
        self._icon_key = icon

        self.setObjectName("kpiTile")
        self.setProperty("accent", accent)
        self.setFixedHeight(105)  # Fixed height: 100-110px
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setGraphicsEffect(Theme.shadow_card())

        self._build_ui()

    def _build_ui(self):
        """Build the layout with label, value, delta, and optional sparkline. Built ONCE in __init__."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Icon label (if icon is provided)
        if self._icon_key:
            self._icon_lbl = QLabel()
            self._icon_lbl.setObjectName("kpiIcon")
            self._icon_lbl.setProperty("accent", self._accent)
            self._icon_lbl.setFixedSize(24, 24)
            self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._icon_lbl)
            self._render_icon()
        else:
            self._icon_lbl = None

        # Header: label on the left, optional delta chip on the right
        header = QHBoxLayout()
        header.setSpacing(8)

        # Label (small, muted)
        lbl = QLabel(self.label_text)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setProperty("textrole", "secondary")
        header.addWidget(lbl)

        header.addStretch()

        # Delta chip (ALWAYS create, visibility controlled by set_value)
        self._delta_lbl = QLabel("")
        self._delta_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._delta_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._delta_lbl.setVisible(self.delta is not None)
        header.addWidget(self._delta_lbl)
        # Set initial delta text and color
        if self.delta is not None:
            self._delta_lbl.setText(self._format_delta(self.delta))
            color = Theme.SUCCESS_TEXT if self.delta >= 0 else Theme.DANGER_TEXT
            self._delta_lbl.setStyleSheet(f"color: {color}; padding: 2px 6px; border-radius: 3px;")

        layout.addLayout(header)

        # Value (large, bold, colored by sign if currency)
        self._value_lbl = QLabel(self._format_value())
        self._value_lbl.setObjectName("kpiValue")
        self._value_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._apply_value_color()
        layout.addWidget(self._value_lbl)

        # Sparkline widget (ALWAYS create, visibility controlled by set_value)
        self._sparkline_widget = SparklineWidget(
            self.sparkline_data if self.sparkline_data else [],
            accent=self._accent
        )
        self._sparkline_widget.setFixedHeight(30)
        self._sparkline_widget.setVisible(self.sparkline_data is not None and len(self.sparkline_data) >= 2)
        layout.addWidget(self._sparkline_widget)

        # Add stretch if sparkline is not visible to maintain fixed height
        if not (self.sparkline_data and len(self.sparkline_data) >= 2):
            layout.addStretch()

    def _apply_value_color(self):
        """Apply color styling to the value label based on sign and currency mode."""
        if self.is_currency and isinstance(self.value, (int, float)):
            # Color by sign
            if self.value > 0:
                color = Theme.SUCCESS_TEXT
            elif self.value < 0:
                color = Theme.DANGER_TEXT
            else:
                color = Theme.TEXT_SECONDARY
            self._value_lbl.setStyleSheet(f"color: {color};")
        else:
            # Clear stylesheet for non-currency values
            self._value_lbl.setStyleSheet("")

    def _render_icon(self):
        """Render the icon onto the icon label, or fallback to emoji text."""
        if not self._icon_lbl or not self._icon_key:
            return
        from ui.icons import pixmap as icon_pixmap, fallback
        pm = icon_pixmap(self._icon_key, size=14, color=Theme.accent(self._accent))
        if pm and not pm.isNull():
            self._icon_lbl.setPixmap(pm)
        else:
            self._icon_lbl.setText(fallback(self._icon_key))

    def _format_value(self) -> str:
        """Format the value: currency with INR grouping or raw string."""
        if self.is_currency and isinstance(self.value, (int, float)):
            return format_inr(self.value)
        else:
            # For non-currency or string values, just return as-is
            return str(self.value)

    def _format_delta(self, delta: float) -> str:
        """Format delta as "+12%" or "-5%"."""
        if delta >= 0:
            return f"+{delta:.0f}%"
        else:
            return f"{delta:.0f}%"

    def _delta_css(self, delta: float | None) -> str:
        """Generate CSS for delta chip styling."""
        if delta is None:
            return ""
        color = Theme.SUCCESS_TEXT if delta >= 0 else Theme.DANGER_TEXT
        return f"color: {color}; padding: 2px 6px; border-radius: 3px;"

    def set_value(self, value, delta=None, is_currency=None):
        """Update the displayed value and optional delta. Does NOT rebuild layout."""
        self.value = value
        self.delta = delta
        if is_currency is not None:
            self.is_currency = is_currency

        # Update value label text and color
        self._value_lbl.setText(self._format_value())
        self._apply_value_color()

        # Update delta chip text, color, and visibility
        if self.delta is not None:
            self._delta_lbl.setText(self._format_delta(self.delta))
            self._delta_lbl.setStyleSheet(self._delta_css(self.delta))
            self._delta_lbl.setVisible(True)
        else:
            self._delta_lbl.setVisible(False)

    def refresh_theme(self):
        """Refresh theme-dependent styling (called when theme changes)."""
        self.setGraphicsEffect(Theme.shadow_card())
        if self._icon_lbl:
            self._render_icon()
        self._apply_value_color()
        if self.delta is not None:
            self._delta_lbl.setStyleSheet(self._delta_css(self.delta))
        if hasattr(self, "_sparkline_widget") and self._sparkline_widget:
            self._sparkline_widget.update()

    def enterEvent(self, event):
        """Apply accent shadow on hover."""
        self.setGraphicsEffect(Theme.shadow_accent(self._accent))
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Restore default shadow on hover leave."""
        self.setGraphicsEffect(Theme.shadow_card())
        super().leaveEvent(event)


class SparklineWidget(QWidget):
    """
    A simple inline sparkline widget that draws a trend line using QPainter.

    Displays a minimal polyline chart: no axes, no labels, just the line.
    """

    def __init__(self, data: list[float], parent=None, accent: str = "primary"):
        super().__init__(parent)
        self.data = data
        self.accent = accent
        self.setMinimumHeight(30)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        """Paint the sparkline as a simple polyline."""
        if not self.data or len(self.data) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dimensions
        w = self.width()
        h = self.height()
        padding = 4

        # Normalize data to fit within the widget
        min_val = min(self.data)
        max_val = max(self.data)
        val_range = max_val - min_val if max_val != min_val else 1

        # Build points
        points = []
        n = len(self.data)
        for i, val in enumerate(self.data):
            x = padding + (i / (n - 1)) * (w - 2 * padding)
            # Invert y so higher values go up
            y = h - (padding + (val - min_val) / val_range * (h - 2 * padding))
            points.append((x, y))

        # Draw the line
        accent_color = Theme.accent(self.accent)
        pen = QPen(accent_color)
        pen.setWidth(2)
        painter.setPen(pen)

        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw small dots at each point
        dot_color = QColor(accent_color)
        dot_color.setAlpha(180)
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        for x, y in points:
            painter.drawEllipse(int(x) - 2, int(y) - 2, 4, 4)

        painter.end()
