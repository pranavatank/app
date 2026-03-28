"""
main.py — Application entry point for Personal Financial Manager.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from core.database import initialise_database
from core.auth import is_first_run
from config import APP_NAME, APP_VERSION, DATA_DIR, BACKUP_DIR


def bootstrap():
    os.makedirs(DATA_DIR,   exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    initialise_database()


def launch_app():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    app.setFont(QFont("Segoe UI", 10))

    from ui.theme import Theme
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
