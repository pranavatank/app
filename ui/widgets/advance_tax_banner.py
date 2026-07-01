"""
ui/widgets/advance_tax_banner.py — Quarterly Advance Tax Reminder Banner.

Displays upcoming/overdue advance tax installments with amount and due date.
"""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import icon as app_icon, is_available as icons_available
from engines.advance_tax_engine import AdvanceTaxResult


class AdvanceTaxBanner(QFrame):
    """Banner widget showing advance tax reminder with dismiss capability."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AdvanceTaxBanner")
        self._result: AdvanceTaxResult | None = None
        self._build_ui()
        self.hide()  # Hidden by default
    
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(28, 28)
        self.icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.icon_label)
        
        # Message area
        msg_layout = QVBoxLayout()
        msg_layout.setSpacing(4)
        
        self.title_label = QLabel("Advance Tax Reminder")
        self.title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.title_label.setStyleSheet("background: transparent;")
        msg_layout.addWidget(self.title_label)
        
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("background: transparent; font-size: 12px;")
        msg_layout.addWidget(self.message_label)
        
        layout.addLayout(msg_layout, 1)
        
        # Action button
        self.btn_view = Theme.btn("View Details", "secondary", height=32, min_width=110)
        self.btn_view.clicked.connect(self._on_view_details)
        layout.addWidget(self.btn_view)
        
        # Dismiss button
        self.btn_dismiss = QPushButton()
        self.btn_dismiss.setFixedSize(28, 28)
        if icons_available():
            self.btn_dismiss.setIcon(app_icon("close", color=Theme.TEXT_SECONDARY, size=14))
        else:
            self.btn_dismiss.setText("x")
        self.btn_dismiss.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_SECONDARY};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {Theme.TEXT_PRIMARY};
                background: rgba(0,0,0,0.05);
                border-radius: 14px;
            }}
        """)
        self.btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dismiss.clicked.connect(self.hide)
        layout.addWidget(self.btn_dismiss)
    
    def update_reminder(self, result: AdvanceTaxResult):
        """Update banner with advance tax calculation result."""
        self._result = result
        
        if not result or not result.banner_message:
            self.hide()
            return
        
        # Update styling based on level
        level_map = {
            "success": Theme.SUCCESS,
            "info": Theme.INFO,
            "warning": Theme.WARNING,
            "danger": Theme.DANGER,
        }
        
        from ui.theme.components import banner_style
        self.setStyleSheet(banner_style(Theme, result.banner_level, radius=10))
        
        # Update icon
        _ICON_MAP = {
            "success": ("success_badge", "#4ADE80"),
            "info":    ("calendar",       "#60A5FA"),
            "warning": ("notification",   "#FBBF24"),
            "danger":  ("overdue",        "#F87171"),
        }
        ic_name, ic_color = _ICON_MAP.get(result.banner_level, ("notification", "#FBBF24"))
        if icons_available():
            pm = app_icon(ic_name, color=ic_color, size=22).pixmap(22, 22)
            self.icon_label.setPixmap(pm)
        else:
            _fb = {"success": "ok", "info": "i", "warning": "!", "danger": "!"}
            self.icon_label.setText(_fb.get(result.banner_level, "!"))
        
        # Update message
        self.message_label.setText(result.banner_message)
        
        # Show banner
        self.show()
    
    def _on_view_details(self):
        """Navigate to tax screen or show detailed dialog."""
        if self.parent() and hasattr(self.parent(), 'parent_window'):
            parent_window = self.parent().parent_window
            if hasattr(parent_window, '_navigate'):
                # Navigate to Tax screen (index 7 in dashboard)
                parent_window._navigate(7)
        self.hide()
    
    def clear(self):
        """Clear and hide the banner."""
        self._result = None
        self.message_label.setText("")
        self.hide()
