"""Shared logo and icon helpers for consistent app branding."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

from config import BASE_DIR


_LOGO_PATH = Path(BASE_DIR) / "data" / "logo.png"


def logo_exists() -> bool:
    return _LOGO_PATH.is_file()


def logo_pixmap(size: int | None = None) -> QPixmap:
    if not logo_exists():
        return QPixmap()
    pixmap = QPixmap(str(_LOGO_PATH))
    if pixmap.isNull() or not size:
        return pixmap
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def app_icon() -> QIcon:
    if not logo_exists():
        return QIcon()
    return QIcon(str(_LOGO_PATH))


def set_app_icon(app) -> None:
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)


def set_window_icon(window) -> None:
    icon = app_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)


def set_windows_app_user_model_id() -> None:
    """Set Windows App User Model ID to prevent taskbar grouping with Python."""
    if sys.platform == "win32":
        try:
            import ctypes
            app_id = "FinancialApp.PersonalFinanceManager.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass  # Silently fail on non-Windows or if ctypes unavailable


def ensure_logo_assets() -> None:
    """Ensure logo assets exist. Create placeholder if needed."""
    # For now, just ensure the data directory exists
    _LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
