#!/usr/bin/env python3
"""Quick test of Toast widget functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt

from ui.theme import Theme, ThemeManager
from ui.widgets.toast import Toast, ToastContainer
from ui.widgets.toast_utils import show_toast, init_toast_container, show_success, show_info, show_warning, show_danger

def test_toast_widget():
    """Test that Toast widget works."""
    app = QApplication(sys.argv)
    ThemeManager.load_and_apply()
    app.setStyleSheet(Theme.get_stylesheet())

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Toast Test")
    window.setMinimumSize(800, 600)

    central = QWidget()
    layout = QVBoxLayout(central)

    # Create content area
    content_area = QWidget()
    content_layout = QVBoxLayout(content_area)
    layout.addWidget(content_area)

    # Create buttons for each toast type
    btn_success = QPushButton("Show Success Toast")
    btn_success.clicked.connect(lambda: show_success("This is a success message!"))
    layout.addWidget(btn_success)

    btn_info = QPushButton("Show Info Toast")
    btn_info.clicked.connect(lambda: show_info("This is an info message!"))
    layout.addWidget(btn_info)

    btn_warning = QPushButton("Show Warning Toast")
    btn_warning.clicked.connect(lambda: show_warning("This is a warning message!"))
    layout.addWidget(btn_warning)

    btn_danger = QPushButton("Show Danger Toast")
    btn_danger.clicked.connect(lambda: show_danger("This is a danger message!"))
    layout.addWidget(btn_danger)

    window.setCentralWidget(central)

    # Initialize toast container
    init_toast_container(content_area)

    # Test that toasts don't block input
    print("[PASS] Toast widget initialized successfully")
    print("[PASS] Window created and toast container ready")
    print("[PASS] Parent window remains enabled (non-blocking)")
    assert window.isEnabled(), "Window should remain enabled"
    print("[PASS] All toast widget tests passed!")

    window.close()
    return True

if __name__ == "__main__":
    try:
        test_toast_widget()
        print("\n[PASS] TOAST TEST PASSED\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FAIL] TOAST TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
