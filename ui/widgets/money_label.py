"""
ui/widgets/money_label.py — Reusable widget for displaying currency with Indian grouping.

Features:
- Shows ₹ prefix
- Formats with Indian digit grouping (e.g., 256642 -> "₹2,56,642")
- Colors by sign (positive=SUCCESS_TEXT, negative=DANGER_TEXT)
- Integrates with privacy mode (shows "₹ ****" when privacy_mode is on)
- Uses tabular figures for digit alignment
"""

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from ui.theme import Theme
from core.session import session


def format_inr(amount: float) -> str:
    """
    Format a currency amount in Indian style with rupee symbol and grouping.

    Indian grouping: last 3 digits, then groups of 2 from the right.
    Examples:
        256642      -> "₹2,56,642"
        1234567     -> "₹12,34,567"
        100         -> "₹100"
        1234.56     -> "₹1,234.56"
        -5000       -> "₹-5,000"

    Args:
        amount: Numeric value to format

    Returns:
        Formatted string with ₹ prefix and Indian grouping
    """
    # Handle sign
    is_negative = amount < 0
    abs_amount = abs(amount)

    # Split into integer and decimal parts
    if isinstance(abs_amount, float):
        int_part = int(abs_amount)
        dec_part = abs_amount - int_part
        has_decimals = dec_part > 0
    else:
        int_part = int(abs_amount)
        has_decimals = False

    # Convert to string and apply Indian grouping to the integer part
    int_str = str(int_part)

    if len(int_str) <= 3:
        grouped_int = int_str
    else:
        # Indian grouping: last 3 digits, then groups of 2
        # e.g., 1234567 -> "12,34,567"
        last_three = int_str[-3:]
        remaining = int_str[:-3]

        # Group remaining digits in pairs from the right
        groups = []
        for i in range(len(remaining), 0, -2):
            start = max(0, i - 2)
            groups.insert(0, remaining[start:i])

        grouped_int = ",".join(groups) + "," + last_three

    # Reconstruct with decimals if needed
    if has_decimals:
        dec_str = f"{dec_part:.2f}"[2:]  # Get ".56" part and remove the dot
        result = f"{grouped_int}.{dec_str}"
    else:
        result = grouped_int

    # Add sign if negative
    if is_negative:
        result = f"-{result}"

    return f"₹{result}"


class MoneyLabel(QLabel):
    """
    A QLabel subclass for displaying currency amounts with Indian grouping,
    sign-based coloring, and privacy mode support.

    Features:
    - Indian digit grouping (2,56,642 style)
    - Color by sign: positive=SUCCESS_TEXT, negative=DANGER_TEXT
    - Privacy mode: shows "₹ ****" when session.privacy_mode is True
    - Tabular figures for digit alignment
    """

    def __init__(self, amount: float = 0, parent=None):
        super().__init__(parent)
        self.amount = amount
        self._setup_font()
        self._update_display()

    def _setup_font(self):
        """Configure font with tabular figures for aligned digits."""
        font = QFont()
        if hasattr(font, "setFeature"):
            # Qt 6.7+: real tabular figures in the app font beat a monospace fallback.
            font.setFamily("Segoe UI")
            font.setFeature(QFont.Tag("tnum"), 1)
        else:
            font.setFamily("Courier New")
        font.setPointSize(11)
        self.setFont(font)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def set_amount(self, amount: float) -> None:
        """
        Update the displayed amount.

        Args:
            amount: The new amount to display
        """
        self.amount = amount
        self._update_display()

    def set_masked(self, masked: bool) -> None:
        """
        Manually set masked state (overrides privacy mode for this widget).

        Args:
            masked: True to show "₹ ****", False to show actual value
        """
        if masked:
            self.setText("₹ ****")
            self.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        else:
            self._update_display()

    def _update_display(self) -> None:
        """Update the label text and color based on amount and privacy mode."""
        # Check privacy mode from session
        if session.privacy_mode:
            self.setText("₹ ****")
            self.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        else:
            # Format the amount with Indian grouping
            formatted = format_inr(self.amount)
            self.setText(formatted)

            # Color by sign
            if self.amount > 0:
                color = Theme.SUCCESS_TEXT
            elif self.amount < 0:
                color = Theme.DANGER_TEXT
            else:
                color = Theme.TEXT_SECONDARY

            self.setStyleSheet(f"color: {color};")
