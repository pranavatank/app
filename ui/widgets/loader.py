"""
ui/widgets/loader.py — Universal interactive loading overlay.

Usage (anywhere in the app):

    from ui.widgets.loader import Loader

    # Show while doing slow work:
    with Loader(parent_widget, "Parsing statement…"):
        do_heavy_work()

    # Or manually:
    loader = Loader(parent_widget, "Calculating tax…")
    loader.show()
    ...
    loader.hide()

    # With custom subtitle:
    with Loader(parent_widget, "Importing PDF", subtitle="This may take a moment"):
        parse()

    # Run a callable in a QThread and auto-show/hide:
    Loader.run(parent_widget, fn=my_fn, message="Loading…", on_done=callback)
"""

from __future__ import annotations
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QObject, QPropertyAnimation,
    QEasingCurve, QRect
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont,
    QLinearGradient, QConicalGradient
)

from ui.theme import Theme


# ══════════════════════════════════════════════════════════════════════════════
# Spinner canvas
# ══════════════════════════════════════════════════════════════════════════════

class _SpinnerCanvas(QWidget):
    """
    Smooth animated ring spinner that:
    • Rotates a gradient arc (primary color)
    • Has a dimmer background ring
    • Pulses size slightly
    """

    def __init__(self, size: int = 52, parent=None):
        super().__init__(parent)
        self._size     = size
        self._angle    = 0
        self._pulse    = 0.0
        self._pulse_dir = 1
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(14)   # ~70 fps

    def _tick(self):
        self._angle = (self._angle + 6) % 360
        self._pulse += 0.04 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1
        self.update()

    def stop(self):
        self._timer.stop()

    def paintEvent(self, event):
        s = self._size
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen_w = max(4, s // 10)
        margin = pen_w // 2 + 1
        rect = QRect(margin, margin, s - 2 * margin, s - 2 * margin)

        # Background ring
        bg_color = QColor(Theme.BORDER)
        bg_color.setAlpha(180)
        pen_bg = QPen(bg_color, pen_w, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawEllipse(rect)

        # Gradient arc (primary color, sweeps 270°)
        primary   = QColor(Theme.PRIMARY)
        primary.setAlpha(255)
        primary_t = QColor(Theme.PRIMARY)
        primary_t.setAlpha(0)

        # Use conical gradient for the smooth sweep
        cg = QConicalGradient(s / 2, s / 2, -self._angle)
        cg.setColorAt(0.0,  primary)
        cg.setColorAt(0.75, primary_t)
        cg.setColorAt(1.0,  primary_t)

        arc_pen = QPen(QBrush(cg), pen_w, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        # Draw 270° sweep starting at current angle
        start_angle = int(self._angle * 16)
        span_angle  = int(270 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        painter.end()


# ══════════════════════════════════════════════════════════════════════════════
# Loader overlay
# ══════════════════════════════════════════════════════════════════════════════

class Loader(QWidget):
    """
    Semi-transparent full-parent overlay with centered spinner card.
    Supports context manager and static Loader.run() for threaded ops.
    """

    def __init__(self, parent: QWidget, message: str = "Loading…",
                 subtitle: str = "", spinner_size: int = 52):
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
        is_dark = Theme.BG < "#888888"  # rough dark detection by hex value
        card_bg = Theme.SURFACE
        card.setStyleSheet(f"""
            QFrame#LoaderCard {{
                background-color: {card_bg};
                border: 1px solid {Theme.BORDER};
                border-radius: 20px;
            }}
        """)
        card.setFixedWidth(280)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(16)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Spinner
        spinner_row = QHBoxLayout()
        spinner_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner = _SpinnerCanvas(size=spinner_size)
        spinner_row.addWidget(self._spinner)
        card_layout.addLayout(spinner_row)

        # Message
        self._msg_label = QLabel(self._message)
        self._msg_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        self._msg_label.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=700) +
            " background: transparent; border: none;"
        )
        card_layout.addWidget(self._msg_label)

        # Subtitle
        if self._subtitle:
            sub = QLabel(self._subtitle)
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setWordWrap(True)
            sub.setStyleSheet(Theme.muted_style(11) + " background: transparent; border: none;")
            card_layout.addWidget(sub)

        # Progress dots
        self._dots_label = QLabel("●  ●  ●")
        self._dots_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dots_label.setStyleSheet(
            f"color: {Theme.PRIMARY}; font-size: 10px; letter-spacing: 2px; "
            "background: transparent; border: none;"
        )
        card_layout.addWidget(self._dots_label)
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._animate_dots)
        self._dot_state = 0
        self._dot_timer.start(500)

        overlay_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        # Give card a shadow
        self._spinner.setGraphicsEffect(None)
        try:
            card.setGraphicsEffect(Theme.shadow_elevated())
        except Exception:
            pass

    def _animate_dots(self):
        patterns = ["●  ○  ○", "○  ●  ○", "○  ○  ●"]
        self._dot_state = (self._dot_state + 1) % 3
        self._dots_label.setText(patterns[self._dot_state])

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
        self._dot_timer.stop()
        self._fade_timer.stop()
        super().hide()

    def set_message(self, message: str):
        self._msg_label.setText(message)
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
