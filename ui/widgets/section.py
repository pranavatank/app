"""
ui/widgets/section.py — CollapsibleSection widget for tax sections.

A QWidget-based collapsible section with:
- A clickable header row with chevron icon, title, and optional summary value
- A content area that toggles visibility
- Keyboard accessible (Enter/Space to toggle, visible focus ring)
- Theme-aware styling
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.theme import Theme
from ui.icons import icon as app_icon, pixmap as app_pixmap, is_available as icons_available
from ui.widgets.motion import animate_height


class CollapsibleSection(QWidget):
    """A collapsible section widget with a clickable header and content area."""

    def __init__(self, title: str, summary_value: str | None = None, expanded: bool = True, parent=None):
        """
        Initialize a CollapsibleSection.

        Args:
            title: The section title text
            summary_value: Optional summary to show when collapsed (e.g., total/subtotal)
            expanded: Initial expand state (default True)
            parent: Parent widget
        """
        super().__init__(parent)
        self.title_text = title
        self.summary_value_text = summary_value or ""
        self._expanded = expanded
        self._build_ui()
        self._update_header_style()

    def _build_ui(self):
        """Build the section UI with header and content area."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header row
        self._header = QWidget()
        self._header.setObjectName("CollapsibleSectionHeader")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.mousePressEvent = self._on_header_click
        self._header.keyPressEvent = self._on_header_key_press
        self._header.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)

        # Chevron icon
        self._chevron_label = QLabel()
        self._chevron_label.setFixedSize(20, 20)
        self._chevron_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chevron_label.setStyleSheet("background: transparent; border: none;")
        header_layout.addWidget(self._chevron_label)

        # Title
        self._title_label = QLabel(self.title_text)
        self._title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._title_label.setProperty("textrole", "emphasis-md")
        self._title_label.setStyleSheet("background: transparent; border: none;")
        header_layout.addWidget(self._title_label)

        # Summary value (when collapsed)
        self._summary_label = QLabel(self.summary_value_text)
        self._summary_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Normal))
        self._summary_label.setProperty("textrole", "muted-sm")
        self._summary_label.setStyleSheet("background: transparent; border: none;")
        self._summary_label.setVisible(self.summary_value_text != "")
        header_layout.addWidget(self._summary_label)

        # Stretch to fill
        header_layout.addStretch()

        main_layout.addWidget(self._header)

        # Content area
        self._content_widget = QWidget()
        self._content_widget.setObjectName("CollapsibleSectionContent")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(14, 0, 14, 12)
        self._content_layout.setSpacing(12)

        main_layout.addWidget(self._content_widget)

        # Set initial state
        self._set_expanded(self._expanded)

    def _update_header_style(self):
        """Update the header styling based on theme and focus state."""
        t = Theme
        self._header.setStyleSheet(f"""
            #CollapsibleSectionHeader {{
                background-color: {t.SURFACE};
                border: 1px solid {t.BORDER};
                border-radius: {t.RADIUS_CARD}px;
                margin: 0px;
                padding: 0px;
            }}
            #CollapsibleSectionHeader:hover {{
                background-color: {t.SURFACE_ALT};
                border-color: {t.BORDER_FOCUS};
            }}
            #CollapsibleSectionHeader:focus {{
                outline: 2px solid {t.FOCUS_RING};
                outline-offset: 2px;
                border-color: {t.PRIMARY};
            }}
        """)

    def _update_chevron(self):
        """Update the chevron icon based on expanded state."""
        if self._expanded:
            # Expanded: chevron-down
            icon_name = "show"
            color = Theme.PRIMARY
        else:
            # Collapsed: chevron-right
            icon_name = "sidebar_expand"
            color = Theme.TEXT_SECONDARY

        if icons_available():
            pm = app_pixmap(icon_name, size=18, color=color)
            if not pm.isNull():
                self._chevron_label.setPixmap(pm)
                return

        # Fallback to text
        self._chevron_label.setText("▼" if self._expanded else "▶")

    def _set_expanded(self, expanded: bool, animate: bool = False):
        """Set the expanded state, optionally animating the content height."""
        self._expanded = expanded
        self._summary_label.setVisible(not expanded and self.summary_value_text != "")
        self._update_chevron()

        if not animate:
            self._content_widget.setMaximumHeight(16777215)
            self._content_widget.setVisible(expanded)
            return

        if expanded:
            self._content_widget.setMaximumHeight(0)
            self._content_widget.show()
            animate_height(self._content_widget, self._content_widget.sizeHint().height())
        else:
            anim = animate_height(self._content_widget, 0)
            if anim is None:
                self._content_widget.hide()
            else:
                anim.finished.connect(self._content_widget.hide)

    def _on_header_click(self, event):
        """Handle header click to toggle expand/collapse."""
        self.toggle()

    def _on_header_key_press(self, event):
        """Handle keyboard input on header (Enter/Space to toggle)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.toggle()
            event.accept()
        else:
            super().keyPressEvent(event)

    def toggle(self):
        """Toggle the expanded state (animated - this is user-initiated)."""
        self._set_expanded(not self._expanded, animate=True)

    def set_expanded(self, expanded: bool):
        """Set the expanded state explicitly."""
        self._set_expanded(expanded)

    def is_expanded(self) -> bool:
        """Return whether the section is expanded."""
        return self._expanded

    def content_layout(self) -> QVBoxLayout:
        """Return the content layout for adding widgets."""
        return self._content_layout

    def set_content_widget(self, widget: QWidget):
        """Set a widget as the content (replaces existing layout contents)."""
        # Clear existing widgets
        while self._content_layout.count() > 0:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new widget
        self._content_layout.addWidget(widget)

    def set_summary_value(self, value: str):
        """Update the summary value shown when collapsed."""
        self.summary_value_text = value
        self._summary_label.setText(value)
        self._summary_label.setVisible(value != "" and not self._expanded)
