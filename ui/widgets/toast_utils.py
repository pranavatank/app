"""
ui/widgets/toast_utils.py — Global toast management utilities.

Provides a simple interface for showing toasts from anywhere in the app.
"""

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt

from .toast import ToastContainer


# Global toast container instance
_toast_container = None


def init_toast_container(content_area):
    """
    Initialize the global toast container.

    Must be called once after the main window and content area are created.

    Args:
        content_area: The QWidget area where toasts should be anchored
    """
    global _toast_container
    _toast_container = ToastContainer(content_area)
    # Position the container to fill the content area
    _toast_container.setGeometry(content_area.rect())
    _toast_container.raise_()
    # Allow mouse events to pass through to the content area for interactive elements
    _toast_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)


def show_toast(message: str, variant: str = "info", duration_ms: int = 4000):
    """
    Show a toast notification.

    Args:
        message: Text to display
        variant: "success", "info", "warning", or "danger"
        duration_ms: How long to show before auto-dismiss (0 = no auto-dismiss)

    Raises:
        RuntimeError: If toast container not initialized
    """
    if _toast_container is None:
        raise RuntimeError("Toast container not initialized. Call init_toast_container() first.")
    _toast_container.show_toast(message, variant=variant, duration_ms=duration_ms)


def show_success(message: str, duration_ms: int = 4000):
    """Show a success toast."""
    show_toast(message, variant="success", duration_ms=duration_ms)


def show_info(message: str, duration_ms: int = 4000):
    """Show an info toast."""
    show_toast(message, variant="info", duration_ms=duration_ms)


def show_warning(message: str, duration_ms: int = 4000):
    """Show a warning toast."""
    show_toast(message, variant="warning", duration_ms=duration_ms)


def show_danger(message: str, duration_ms: int = 4000):
    """Show a danger/error toast."""
    show_toast(message, variant="danger", duration_ms=duration_ms)
