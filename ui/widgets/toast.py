"""
ui/widgets/toast.py — Non-blocking inline notification widget.

Toasts appear anchored to the content area, stack vertically if multiple fire,
auto-dismiss after a timer, and do not steal focus.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme.theme import Theme


class Toast(QWidget):
    """Single toast notification."""

    closed = pyqtSignal()

    def __init__(self, message: str, variant: str = "info", duration_ms: int = 4000, parent=None):
        """
        Create a toast notification.

        Args:
            message: Text to display
            variant: "success", "info", "warning", or "danger"
            duration_ms: How long to show before auto-dismiss (0 = no auto-dismiss)
            parent: Parent widget (usually the content area)
        """
        super().__init__(parent)
        self.variant = variant
        self.duration_ms = duration_ms
        self._setup_ui()
        self._setup_style()
        self._set_message(message)

        # Auto-dismiss timer
        self.dismiss_timer = QTimer()
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self._auto_close)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 10, 12, 10)

        # Message label
        self.message_label = QLabel()
        self.message_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Normal))
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, stretch=1)

        # Close button
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._on_close)
        layout.addWidget(self.close_btn, stretch=0)

    def _setup_style(self):
        """Apply theme-aware styling via object name and dynamic property."""
        self.setObjectName("Toast")
        self.setProperty("variant", self.variant)

    def _set_message(self, text: str):
        self.message_label.setText(text)

    def show_toast(self):
        """Show the toast and start auto-dismiss timer if applicable."""
        self.show()
        if self.duration_ms > 0:
            self.dismiss_timer.start(self.duration_ms)

    def _auto_close(self):
        self._on_close()

    def _on_close(self):
        """Close and emit closed signal."""
        self.dismiss_timer.stop()
        self.hide()
        self.closed.emit()

    def closeEvent(self, event):
        """Handle close event."""
        self._on_close()
        event.accept()


class ToastContainer(QWidget):
    """Container that manages a stack of toasts anchored to a content area."""

    def __init__(self, content_area: QWidget):
        """
        Create a toast container.

        Args:
            content_area: The widget to anchor toasts to (usually self.content_area)
        """
        super().__init__(content_area)
        self.content_area = content_area
        self.toasts = []

        # Layout for stacking toasts
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addStretch()  # Push toasts to bottom

        self.setObjectName("toastContainer")
        # Don't paint a background; just contain the toasts
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def show_toast(self, message: str, variant: str = "info", duration_ms: int = 4000):
        """Show a new toast and manage its lifecycle."""
        toast = Toast(message, variant=variant, duration_ms=duration_ms, parent=self)

        # When toast closes, remove it from the list
        def on_closed():
            if toast in self.toasts:
                self.toasts.remove(toast)
            self.layout.removeWidget(toast)
            toast.deleteLater()

        toast.closed.connect(on_closed)
        self.toasts.append(toast)

        # Insert toast before the stretch (at the end, but before the final stretch)
        self.layout.insertWidget(len(self.toasts) - 1, toast)
        toast.show_toast()
