"""
main.py — Application entry point for Personal Financial Manager.
"""

import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Dependency check must run before PyQt6 imports, so failures produce readable
# dialogs instead of tracebacks. Defined here so it can be called before imports.
def check_dependencies():
    """Verify all required dependencies are installed, with readable error reporting."""

    # Mapping of module names to their pip package names
    required_modules = {
        'PyQt6.QtWidgets': 'PyQt6',
        'qtawesome': 'qtawesome',
        'pdfplumber': 'pdfplumber',
        'pypdf': 'pypdf',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'dateutil': 'python-dateutil',
    }

    missing = []

    # Check each module
    for module_name, pip_name in required_modules.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append((module_name, pip_name))

    # Special case: if PyQt6.QtWidgets is missing, check if it's the namespace package issue
    if any(m == 'PyQt6.QtWidgets' for m, _ in missing):
        try:
            import PyQt6
            if PyQt6.__file__ is None:
                error_msg = (
                    "PyQt6 installation is incomplete (namespace package with no bindings).\n\n"
                    "This usually happens on Microsoft Store Python or after a failed install.\n\n"
                    "Fix: Run this command:\n"
                    "  python -m pip install --force-reinstall --no-cache-dir PyQt6 qtawesome\n\n"
                    "If that fails, install Python from python.org and use a virtual environment."
                )
                _show_error_dialog(error_msg)
                sys.exit(1)
        except ImportError:
            pass

    # Report any missing dependencies
    if missing:
        pip_packages = [pip_name for _, pip_name in missing]
        error_msg = (
            f"Missing required dependencies:\n\n"
            f"{', '.join(pip_packages)}\n\n"
            f"Install with:\n"
            f"  python -m pip install {' '.join(pip_packages)}\n\n"
            f"Or install all dependencies:\n"
            f"  python -m pip install -r requirements.txt"
        )
        _show_error_dialog(error_msg)
        sys.exit(1)


def _show_error_dialog(message):
    """Display error message via dialog, with fallbacks if Qt is unavailable."""
    # Always print to stderr first
    print(message, file=sys.stderr)

    # Try PyQt6 dialog
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Dependency Error", message)
        return
    except Exception:
        pass

    # Try tkinter dialog
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Dependency Error", message)
        return
    except Exception:
        pass


# Call check at module import time only when this is the entry point
if __name__ == "__main__":
    check_dependencies()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import qInstallMessageHandler

from core.database import initialise_database
from core.auth import is_first_run
from config import APP_NAME, APP_VERSION, DATA_DIR, BACKUP_DIR
from ui.messagebox_utils import install_copyable_error_dialogs
from ui.logo import set_app_icon, set_windows_app_user_model_id


def _unload_local_ai_model():
    try:
        from engines.statement_parser import unload_ollama_model
        unload_ollama_model(only_if_used=True)
    except Exception:
        pass


def bootstrap():
    check_dependencies()
    os.makedirs(DATA_DIR,   exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    initialise_database()


def _qt_message_handler(msg_type, context, message):
    # Filter known noisy font warning that does not affect rendering.
    if "QFont::setPointSize: Point size <= 0" in message:
        return
    print(message)


def launch_app():
    # CRITICAL: Set Windows App User Model ID BEFORE creating QApplication
    # This must be done first to prevent Windows from grouping with Python
    set_windows_app_user_model_id()
    
    # Ensure icon assets exist before creating QApplication
    from ui.logo import ensure_logo_assets
    ensure_logo_assets()
    
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    # Force Fusion: the native Windows style only partially honours QSS
    # subcontrol overrides (QSpinBox/QComboBox arrows, stepper dots, etc.),
    # which is why those icons render blank/inconsistent under some themes.
    app.setStyle("Fusion")
    app.aboutToQuit.connect(_unload_local_ai_model)
    install_copyable_error_dialogs()
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    
    # Set app icon immediately
    set_app_icon(app)

    app.setFont(QFont("Segoe UI", 10))

    # Load saved theme before applying stylesheet
    from ui.theme import Theme, ThemeManager
    ThemeManager.load_and_apply()
    app.setStyleSheet(Theme.get_stylesheet())

    if is_first_run():
        from ui.setup_screen import SetupScreen
        window = SetupScreen()
    else:
        from ui.login_screen import LoginScreen
        window = LoginScreen()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    bootstrap()
    launch_app()
