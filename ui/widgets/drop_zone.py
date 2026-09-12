"""
ui/widgets/drop_zone.py — Reusable drag-and-drop file input widget.

A themed QWidget supporting:
- Drag-and-drop file input
- Browse button (QFileDialog)
- Hover and drag-over states
- Emits fileSelected(str) signal carrying the file path
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QFont, QDragEnterEvent, QDragMoveEvent, QDropEvent

from ui.theme import Theme
from ui.icons import icon_label


class DropZone(QWidget):
    """
    Reusable drag-and-drop file input widget with browse button.

    Emits fileSelected(str) signal carrying the selected file path.
    """
    fileSelected = pyqtSignal(str)  # Emits file path (str)

    def __init__(
        self,
        title: str = "Drag and drop your file here",
        subtitle: str = "or click Browse to select",
        accepted_extensions: list[str] | None = None,
        filter_text: str = "All Files (*.*)",
        parent=None
    ):
        """
        Initialize the DropZone widget.

        Args:
            title: Primary text (e.g. "Drag and drop your file here")
            subtitle: Hint text (e.g. "PDF or Excel format")
            accepted_extensions: List of allowed extensions (e.g. [".pdf", ".xlsx"])
            filter_text: QFileDialog filter string (e.g. "PDF files (*.pdf)")
            parent: Parent widget
        """
        super().__init__(parent)
        self.title_text = title
        self.subtitle_text = subtitle
        self.accepted_extensions = accepted_extensions or []
        self.filter_text = filter_text
        self.setAcceptDrops(True)
        self._is_dragging_over = False
        # Optional data storage (used by tax_documents_screen)
        self.pdf_data = None
        self.pdf_path = None
        self._build_ui()

    def _build_ui(self):
        """Build the widget layout."""
        # Set unique object name to scope stylesheet to this widget only (not descendants)
        self.setObjectName("dropZoneRoot")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon
        self.icon_label = icon_label("import", size=32, color=Theme.PRIMARY)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Primary text
        self.title_label = QLabel(self.title_text)
        self.title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setProperty("textrole", "emphasis-md")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title_label)

        # Inline text with browse link
        inline_layout = QHBoxLayout()
        inline_layout.setContentsMargins(0, 0, 0, 0)
        inline_layout.setSpacing(4)

        self.subtitle_label = QLabel(self.subtitle_text)
        self.subtitle_label.setFont(QFont("Segoe UI", 12))
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setProperty("textrole", "muted-md")
        self.subtitle_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.subtitle_label)

        # Browse link (styled as a link, not a separate button)
        # We'll use a QLabel with link-style stylesheet
        browse_text = QLabel('<a href="#" style="color: ' + Theme.PRIMARY + '; text-decoration: none;">Browse</a>')
        browse_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        browse_text.setFont(QFont("Segoe UI", 12))
        browse_text.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_text.setProperty("textrole", "link-sm")
        browse_text.linkActivated.connect(self._on_browse_click)
        layout.addWidget(browse_text)

        layout.addStretch()

        # Apply base styling with dashed border
        self._update_style()

        # Set accessible properties
        self.setAccessibleName("File drop zone")
        self.setAccessibleDescription("Drag a file here or click Browse to select a file.")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _update_style(self):
        """Update stylesheet based on drag state."""
        if self._is_dragging_over:
            bg_color = Theme.PRIMARY_LIGHT
            border_color = Theme.PRIMARY
        else:
            bg_color = Theme.SURFACE
            border_color = Theme.BORDER

        style = f"""
            QWidget#dropZoneRoot {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: {Theme.RADIUS_CARD}px;
            }}
            QWidget#dropZoneRoot:hover {{
                background-color: {Theme.PRIMARY_LIGHT};
                border-color: {Theme.PRIMARY};
            }}
        """
        self.setStyleSheet(style)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._is_dragging_over = True
            self._update_style()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move event (maintain drag-over state)."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self._is_dragging_over = False
        self._update_style()

    def dropEvent(self, event: QDropEvent):
        """Handle file drop event."""
        self._is_dragging_over = False
        self._update_style()

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path:
                    # Validate file extension if specified
                    if self.accepted_extensions:
                        import os
                        _, ext = os.path.splitext(file_path)
                        if ext.lower() not in [e.lower() for e in self.accepted_extensions]:
                            # Emit with the path anyway; let caller validate
                            pass
                    self.fileSelected.emit(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _on_browse_click(self):
        """Open file dialog when browse link is clicked."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            self.filter_text
        )
        if path:
            self.fileSelected.emit(path)

    def mousePressEvent(self, event):
        """Allow clicking on the entire widget to open browse dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_browse_click()
        super().mousePressEvent(event)

    def setEnabled(self, enabled: bool):
        """Override setEnabled to properly disable drop/drag and click handlers."""
        super().setEnabled(enabled)
        self.setAcceptDrops(enabled)
        # Cursor changes based on enabled state
        if enabled:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_status(self, status: str, fy: str = "", error: bool = False):
        """
        Update status display (for compatibility with tax_documents_screen).

        Args:
            status: Status text to display
            fy: Financial year text (optional)
            error: If True, display in error color
        """
        # Update title to show status
        status_color = "color: " + Theme.DANGER + ";" if error else ""
        self.title_label.setText(status)
        if error:
            self.title_label.setStyleSheet(f"color: {Theme.DANGER};")
        else:
            self.title_label.setStyleSheet("")

        # Update subtitle to show FY if provided
        if fy:
            self.subtitle_label.setText(fy)
        else:
            self.subtitle_label.setText(self.subtitle_text)
