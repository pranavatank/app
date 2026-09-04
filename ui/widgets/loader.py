"""
ui/widgets/loader.py — Universal interactive loading overlay.

This is a plain in-window overlay: `Loader` is a QWidget CHILD of the
parent widget you pass in (not a QDialog / separate top-level window).
It covers the parent's own geometry and paints a translucent scrim, so
visually it looks like the current screen "dims and shows a spinner" —
it never spawns a new OS window.

Usage (anywhere in the app):

    from ui.widgets.loader import Loader

    # For long-running work (parsing, heavy computation): use Loader.run() to run in a worker thread.
    # This keeps the UI responsive and allows you to show progress updates.
    def do_heavy_work():
        return parse_statement()

    Loader.run(parent_widget, fn=do_heavy_work, message="Parsing…",
               on_done=callback)

    # For quick operations (backup, file operations), you can use context manager:
    # WARNING: The blocking form BLOCKS the entire UI thread. Only use for fast operations (<1s).
    with Loader(parent_widget, "Backing up database…"):
        backup_database()

    # Or manually:
    loader = Loader(parent_widget, "Calculating…")
    loader.show()
    ...
    loader.hide()

    # With custom subtitle:
    with Loader(parent_widget, "Quick operation", subtitle="Almost done"):
        fast_operation()
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QObject, QRect
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QPainterPath, QConicalGradient, QPixmap
)

from ui.theme import Theme
from ui.logo import logo_pixmap


# ══════════════════════════════════════════════════════════════════════════════
# Logo ring spinner
# ══════════════════════════════════════════════════════════════════════════════

class _LogoRingSpinner(QWidget):
    """
    Big circular app logo sitting still in the center, wrapped by a
    smoothly rotating gradient progress ring (same visual idea as a
    social-app "story" ring) — replaces the old bare arc + text dots.
    """

    def __init__(self, size: int = 96, parent=None):
        super().__init__(parent)
        self._size  = size
        self._angle = 0
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._logo_pm = self._build_center_logo(size)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(14)   # ~70 fps

    def _build_center_logo(self, size: int):
        """Pre-render the app logo, clipped to a circle, sized to sit
        inside the ring. Returns None if no logo asset is available —
        paintEvent then falls back to a colored initials circle."""
        pen_w   = max(4, size // 16)
        inner_d = size - 2 * (pen_w + 6)   # small gap between ring and logo
        pm = logo_pixmap(int(inner_d * 0.82))
        if pm.isNull():
            return None

        circular = QPixmap(inner_d, inner_d)
        circular.fill(Qt.GlobalColor.transparent)
        p = QPainter(circular)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Circular backdrop so transparent-PNG logos still read as a clean disc
        p.setBrush(QBrush(QColor(Theme.SURFACE)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, inner_d, inner_d)
        clip = QPainterPath()
        clip.addEllipse(0, 0, inner_d, inner_d)
        p.setClipPath(clip)
        x = (inner_d - pm.width()) // 2
        y = (inner_d - pm.height()) // 2
        p.drawPixmap(x, y, pm)
        p.end()
        return circular

    def _tick(self):
        self._angle = (self._angle + 5) % 360
        self.update()

    def stop(self):
        self._timer.stop()

    def paintEvent(self, event):
        s = self._size
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen_w  = max(4, s // 16)
        margin = pen_w // 2 + 1
        rect   = QRect(margin, margin, s - 2 * margin, s - 2 * margin)

        # Dim background ring (full circle, always visible)
        bg_color = QColor(Theme.BORDER)
        bg_color.setAlpha(160)
        painter.setPen(QPen(bg_color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(rect)

        # Rotating gradient arc (primary color, sweeps 270°) — the "progress" motion
        primary   = QColor(Theme.PRIMARY); primary.setAlpha(255)
        primary_t = QColor(Theme.PRIMARY); primary_t.setAlpha(0)
        cg = QConicalGradient(s / 2, s / 2, -self._angle)
        cg.setColorAt(0.0,  primary)
        cg.setColorAt(0.75, primary_t)
        cg.setColorAt(1.0,  primary_t)
        painter.setPen(QPen(QBrush(cg), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        start_angle = int(self._angle * 16)
        span_angle  = int(270 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        # Center: circular logo, or a colored initials disc as fallback
        cx, cy = s // 2, s // 2
        if self._logo_pm is not None:
            lx = cx - self._logo_pm.width() // 2
            ly = cy - self._logo_pm.height() // 2
            painter.drawPixmap(lx, ly, self._logo_pm)
        else:
            r = (s - 2 * (pen_w + 6)) // 2
            painter.setBrush(QBrush(QColor(Theme.PRIMARY)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", max(10, r // 2), QFont.Weight.Bold))
            painter.drawText(QRect(cx - r, cy - r, r * 2, r * 2),
                              Qt.AlignmentFlag.AlignCenter, "FA")

        painter.end()


# ══════════════════════════════════════════════════════════════════════════════
# Loader overlay
# ══════════════════════════════════════════════════════════════════════════════

class Loader(QWidget):
    """
    Semi-transparent full-parent overlay with a centered spinner card.
    A plain child widget of `parent` — never a QDialog / new window.
    Supports context manager and static Loader.run() for threaded ops.
    """

    def __init__(self, parent: QWidget, message: str = "Loading…",
                 subtitle: str = "", spinner_size: int = 88):
        super().__init__(parent)
        self._parent   = parent
        self._message  = message
        self._subtitle = subtitle

        # Cover the parent completely
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setObjectName("LoaderOverlay")

        self._build_ui(spinner_size)
        self._opacity = 0.0
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_in_step)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, spinner_size: int):
        # Full overlay layout
        overlay_layout = QVBoxLayout(self)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Card
        card = QFrame()
        card.setObjectName("LoaderCard")
        # Use Theme tokens for card bg and border
        card_bg = Theme.SURFACE
        card.setStyleSheet(f"""
            QFrame#LoaderCard {{
                background-color: {card_bg};
                border: 1px solid {Theme.BORDER};
                border-radius: 20px;
            }}
        """)
        card.setFixedWidth(300)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 28)
        card_layout.setSpacing(18)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo + progress ring
        spinner_row = QHBoxLayout()
        spinner_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner = _LogoRingSpinner(size=spinner_size)
        spinner_row.addWidget(self._spinner)
        card_layout.addLayout(spinner_row)

        # Message
        self._msg_label = QLabel(self._message)
        self._msg_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        self._msg_label.setProperty("textrole", "emphasis-md")
        card_layout.addWidget(self._msg_label)

        # Subtitle — always created (even if empty) so set_subtitle() can
        # reveal/update it later for callers that only know the detail text
        # once work is underway (e.g. "Importing... 5/20 processed").
        self._sub_label = QLabel(self._subtitle)
        self._sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_label.setWordWrap(True)
        self._sub_label.setProperty("textrole", "muted-sm")
        self._sub_label.setVisible(bool(self._subtitle))
        card_layout.addWidget(self._sub_label)

        overlay_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        # Give card a shadow
        self._spinner.setGraphicsEffect(None)
        try:
            card.setGraphicsEffect(Theme.shadow_elevated())
        except Exception:
            pass

    # ── Overlay painting ──────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Semi-transparent dark/light overlay
        overlay_color = QColor(0, 0, 0, int(self._opacity * 140))
        painter.fillRect(self.rect(), overlay_color)
        painter.end()

    # ── Fade in ───────────────────────────────────────────────────────────────

    def _fade_in_step(self):
        self._opacity = min(1.0, self._opacity + 0.1)
        self.update()
        if self._opacity >= 1.0:
            self._fade_timer.stop()

    # ── Show/hide ─────────────────────────────────────────────────────────────

    def show(self):
        self._opacity = 0.0
        self.setGeometry(self._parent.rect())
        self.raise_()
        super().show()
        self._fade_timer.start(16)
        QApplication.processEvents()

    def hide(self):
        self._spinner.stop()
        self._fade_timer.stop()
        super().hide()

    def set_message(self, message: str):
        self._msg_label.setText(message)
        QApplication.processEvents()

    def set_subtitle(self, subtitle: str):
        self._subtitle = subtitle
        self._sub_label.setText(subtitle)
        self._sub_label.setVisible(bool(subtitle))
        QApplication.processEvents()

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self.show()
        return self

    def __exit__(self, *args):
        self.hide()

    # ── Static threaded runner ────────────────────────────────────────────────

    @staticmethod
    def run(
        parent: QWidget,
        fn,
        message: str = "Processing…",
        subtitle: str = "",
        on_done=None,
        on_error=None,
    ) -> "Loader":
        """
        Run fn() in a background QThread while showing the loader.
        on_done(result) is called on the main thread when done.
        on_error(exc) is called if fn raises.

        Returns the Loader instance (already shown).
        """
        loader = Loader(parent, message, subtitle)
        worker = _Worker(fn)

        def _done(result):
            loader.hide()
            if on_done:
                on_done(result)
            worker.thread().quit()

        def _error(exc):
            loader.hide()
            if on_error:
                on_error(exc)
            worker.thread().quit()

        thread = QThread(parent)
        worker.moveToThread(thread)
        worker.finished.connect(_done)
        worker.error.connect(_error)
        thread.started.connect(worker.run)
        thread.start()
        loader.show()
        return loader


# ══════════════════════════════════════════════════════════════════════════════
# Background worker
# ══════════════════════════════════════════════════════════════════════════════

class _Worker(QObject):
    finished = pyqtSignal(object)
    error    = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)
