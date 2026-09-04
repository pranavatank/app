"""
ui/widgets/states.py — Reusable empty, loading, and error state widgets.

Three widgets for consistent handling of transient states across the app:
  - EmptyState: Icon, headline, explanation, and a PRIMARY ACTION button
  - LoadingState: Spinner with label (uses the app's logo + ring animation)
  - ErrorState: Error message + RETRY affordance

All three are theme-aware via QSS (no inline setStyleSheet calls).
Icons resolve by semantic role from the registry (ui/icons.py).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import icon_label, set_btn_icon, pixmap as icon_pixmap, is_available as icons_available, fallback as icon_fallback
from ui.widgets.loader import _LogoRingSpinner


class EmptyState(QFrame):
    """
    A centered empty-state card with icon, headline, explanation, and action button.

    Signals:
        action_clicked: Emitted when the action button is clicked
    """
    action_clicked = pyqtSignal()

    def __init__(
        self,
        icon_name: str = "no_data",
        headline: str = "No data",
        explanation: str = "Add content to get started.",
        action_text: str = "Add",
        parent=None
    ):
        """
        Args:
            icon_name: Registry key for icon (e.g. "no_data", "add", "import")
            headline: Main heading text
            explanation: Subheading / explanation text
            action_text: Button label
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self._build_ui(icon_name, headline, explanation, action_text)

    def _build_ui(self, icon_name: str, headline: str, explanation: str, action_text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon (large, muted)
        icon_w = QLabel()
        icon_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_w.setObjectName("EmptyStateIcon")
        if icons_available():
            pm = icon_pixmap(icon_name, size=64, color="muted")
            if not pm.isNull():
                icon_w.setPixmap(pm)
            else:
                icon_w.setText(icon_fallback(icon_name) or "📭")
                icon_w.setFont(QFont("Segoe UI Emoji", 48))
        else:
            icon_w.setText(icon_fallback(icon_name) or "📭")
            icon_w.setFont(QFont("Segoe UI Emoji", 48))
        layout.addWidget(icon_w, alignment=Qt.AlignmentFlag.AlignCenter)

        # Headline
        headline_lbl = QLabel(headline)
        headline_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        headline_lbl.setProperty("textrole", "title-lg")
        headline_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline_lbl.setWordWrap(True)
        layout.addWidget(headline_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # Explanation
        explanation_lbl = QLabel(explanation)
        explanation_lbl.setFont(QFont("Segoe UI", 13))
        explanation_lbl.setProperty("textrole", "secondary-md")
        explanation_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        explanation_lbl.setWordWrap(True)
        explanation_lbl.setMaximumWidth(400)
        layout.addWidget(explanation_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # Action button
        self.btn_action = Theme.btn(action_text, "primary", height=40, min_width=140)
        self.btn_action.setObjectName("EmptyStateActionButton")
        self.btn_action.clicked.connect(self.action_clicked.emit)
        layout.addSpacing(12)
        layout.addWidget(self.btn_action, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    def set_action_callback(self, callback):
        """Connect the action button to a callback (for convenience)."""
        self.action_clicked.connect(callback)


class LoadingState(QFrame):
    """
    A centered loading card with spinner and message.

    Uses the app's animated logo ring spinner (from ui.widgets.loader).
    """

    def __init__(
        self,
        message: str = "Loading…",
        subtitle: str = "",
        spinner_size: int = 88,
        parent=None
    ):
        """
        Args:
            message: Main loading message
            subtitle: Optional secondary message
            spinner_size: Size of the spinner in pixels
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("LoadingState")
        self._build_ui(message, subtitle, spinner_size)

    def _build_ui(self, message: str, subtitle: str, spinner_size: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Spinner
        self._spinner = _LogoRingSpinner(size=spinner_size, parent=self)
        spinner_container = QHBoxLayout()
        spinner_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_container.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(spinner_container)

        # Message
        self._msg_label = QLabel(message)
        self._msg_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._msg_label.setProperty("textrole", "emphasis-md")
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        layout.addWidget(self._msg_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Subtitle (optional)
        self._sub_label = QLabel(subtitle)
        self._sub_label.setProperty("textrole", "secondary-md")
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_label.setWordWrap(True)
        self._sub_label.setVisible(bool(subtitle))
        layout.addWidget(self._sub_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    def set_message(self, message: str):
        """Update the main message."""
        self._msg_label.setText(message)

    def set_subtitle(self, subtitle: str):
        """Update the subtitle."""
        self._sub_label.setText(subtitle)
        self._sub_label.setVisible(bool(subtitle))


class ErrorState(QFrame):
    """
    A centered error card with message and retry button.

    Signals:
        retry_clicked: Emitted when the retry button is clicked
    """
    retry_clicked = pyqtSignal()

    def __init__(
        self,
        message: str = "An error occurred",
        details: str = "",
        show_retry: bool = True,
        retry_text: str = "Retry",
        parent=None
    ):
        """
        Args:
            message: Main error message
            details: Optional detailed error text
            show_retry: Whether to show the retry button
            retry_text: Button label
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("ErrorState")
        self._build_ui(message, details, show_retry, retry_text)

    def _build_ui(self, message: str, details: str, show_retry: bool, retry_text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Error icon (large, danger color)
        icon_w = QLabel()
        icon_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_w.setObjectName("ErrorStateIcon")
        if icons_available():
            pm = icon_pixmap("error_badge", size=64, color="danger")
            if not pm.isNull():
                icon_w.setPixmap(pm)
            else:
                icon_w.setText(icon_fallback("error_badge") or "❌")
                icon_w.setFont(QFont("Segoe UI Emoji", 48))
        else:
            icon_w.setText(icon_fallback("error_badge") or "❌")
            icon_w.setFont(QFont("Segoe UI Emoji", 48))
        layout.addWidget(icon_w, alignment=Qt.AlignmentFlag.AlignCenter)

        # Error message
        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        msg_lbl.setProperty("textrole", "title-lg")
        msg_lbl.setProperty("color", "danger")
        msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # Details (optional)
        if details:
            details_lbl = QLabel(details)
            details_lbl.setFont(QFont("Segoe UI", 12))
            details_lbl.setProperty("textrole", "secondary-md")
            details_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            details_lbl.setWordWrap(True)
            details_lbl.setMaximumWidth(400)
            layout.addWidget(details_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # Retry button
        if show_retry:
            self.btn_retry = Theme.btn(retry_text, "primary", height=40, min_width=140)
            self.btn_retry.setObjectName("ErrorStateRetryButton")
            self.btn_retry.clicked.connect(self.retry_clicked.emit)
            layout.addSpacing(12)
            layout.addWidget(self.btn_retry, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    def set_retry_callback(self, callback):
        """Connect the retry button to a callback (for convenience)."""
        self.retry_clicked.connect(callback)
