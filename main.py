"""
main.py — Application entry point for Personal Financial Manager.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import qInstallMessageHandler

from core.database import initialise_database
from core.auth import is_first_run
from config import APP_NAME, APP_VERSION, DATA_DIR, BACKUP_DIR
from ui.messagebox_utils import install_copyable_error_dialogs


def bootstrap():
    os.makedirs(DATA_DIR,   exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    initialise_database()


def _qt_message_handler(msg_type, context, message):
    # Filter known noisy font warning that does not affect rendering.
    if "QFont::setPointSize: Point size <= 0" in message:
        return
    print(message)


def launch_app():
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    install_copyable_error_dialogs()
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
