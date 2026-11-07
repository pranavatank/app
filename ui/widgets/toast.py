"""Compact, non-blocking notification cards."""
from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QApplication, QScrollArea
from ui.theme.theme import Theme


COLORS = {"success": "SUCCESS", "info": "INFO", "warning": "WARNING", "danger": "DANGER", "error": "DANGER"}
DEFAULTS = {"success": 3000, "info": 3000, "warning": 5000, "danger": 7000, "error": 7000}


class Toast(QWidget):
    closed = Signal()

    def __init__(self, message, variant="info", duration_ms=None, parent=None, title=None):
        super().__init__(parent)
        self.variant = variant if variant in COLORS else "info"
        self.duration_ms = DEFAULTS[self.variant] if duration_ms is None else max(0, int(duration_ms))
        self.remaining = self.duration_ms
        self._started = 0
        self._timer_started = False
        self._hovered = False
        self.message = str(message); self.title = title
        self.setObjectName("ToastCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        accent = getattr(Theme, COLORS[self.variant], Theme.INFO)
        surface = getattr(Theme, "SURFACE", "#ffffff"); foreground = getattr(Theme, "TEXT_PRIMARY", "#20242a"); border = getattr(Theme, "BORDER", "#d8dee5")
        hover = getattr(Theme, "SURFACE_ALT", surface)
        focus = getattr(Theme, "PRIMARY", accent); pressed = getattr(Theme, "PRIMARY_LIGHT", hover)
        self.setStyleSheet(f"QWidget#ToastCard {{ background:{surface}; border:1px solid {border}; border-left:4px solid {accent}; border-radius:12px; }} QLabel {{ color:{foreground}; }} QPushButton {{ color:{foreground}; background:transparent; border:1px solid transparent; border-radius:6px; padding:4px 7px; }} QPushButton:hover {{ background:{hover}; }} QPushButton:focus {{ border-color:{focus}; }} QPushButton:pressed {{ background:{pressed}; }}")
        row = QHBoxLayout(self); row.setContentsMargins(12, 9, 9, 9); row.setSpacing(9)
        icon = {"success":"\u2713", "info":"i", "warning":"!", "danger":"\u00d7", "error":"\u00d7"}[self.variant]
        icon_label = QLabel(icon); icon_label.setAccessibleName(self.variant.capitalize()); icon_label.setStyleSheet(f"color:{accent};font-weight:700;font-size:16px"); row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout(); col.setSpacing(3)
        if title:
            heading = QLabel(str(title)); heading.setTextFormat(Qt.TextFormat.PlainText); heading.setStyleSheet(f"font-weight:600; color:{foreground}"); col.addWidget(heading)
        self.message_label = QLabel(str(message)); self.message_label.setTextFormat(Qt.TextFormat.PlainText); self.message_label.setWordWrap(True); self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        area = QScrollArea(); area.setWidgetResizable(True); area.setFrameShape(QScrollArea.Shape.NoFrame); area.setMinimumHeight(0); area.setMaximumHeight(120); area.setWidget(self.message_label)
        self._message_area = area
        col.addWidget(area); row.addLayout(col, 1)
        col.setContentsMargins(0, 0, 0, 0)
        if self.variant in ("danger", "error"):
            copy = QPushButton("Copy"); copy.setToolTip("Copy notification text"); copy.setAccessibleName("Copy error details"); copy.clicked.connect(lambda: QApplication.clipboard().setText((str(title) + "\n" if title else "") + str(message))); row.addWidget(copy)
        close = QPushButton("\u00d7"); close.setFixedSize(26, 26); close.setAccessibleName("Dismiss notification"); close.clicked.connect(self.dismiss); row.addWidget(close)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.dismiss)
        self._layout_refresh = QTimer(self); self._layout_refresh.setSingleShot(True); self._layout_refresh.timeout.connect(self._refresh_after_show)
        self.setMaximumWidth(440); self.setMinimumSize(0, 0)

    def show_toast(self):
        self.show()
        if self.duration_ms:
            self._started = self.timer.remainingTime() if self.timer.isActive() else 0
            self.timer.start(self.remaining)
            self._timer_started = True

    def measure_height(self, width):
        self.setFixedWidth(width)
        self.ensurePolished()
        layout = self.layout()
        if layout is not None: layout.activate()
        self._message_area.ensurePolished()
        text_width = self._message_area.viewport().width()
        if text_width <= 0:
            text_width = max(1, self._message_area.width() - 2*self._message_area.frameWidth())
        body_height = self.message_label.heightForWidth(text_width)
        if body_height <= 0: body_height = self.message_label.fontMetrics().height()
        self._message_area.setFixedHeight(min(120, max(self.message_label.fontMetrics().height(), body_height)))
        self.adjustSize()
        if layout is not None: layout.activate()
        return self.sizeHint().height()

    def showEvent(self, event):
        super().showEvent(event)
        # The first measurement can happen before QScrollArea has its final
        # viewport geometry. Re-run the stack layout once Qt has polished it.
        self._layout_refresh.start(0)

    def _refresh_after_show(self):
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "_layout_cards"):
            parent._layout_cards()

    def enterEvent(self, event):
        self._hovered = True
        if self.timer.isActive():
            self.remaining = max(1, self.timer.remainingTime()); self.timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        if self.duration_ms and self._timer_started and not self.timer.isActive(): self.timer.start(self.remaining)
        super().leaveEvent(event)

    def dismiss(self):
        self.timer.stop(); self.closed.emit(); self.hide(); self.deleteLater()

    def closeEvent(self, event):
        self.timer.stop(); self.closed.emit(); event.accept(); self.deleteLater()


class ToastContainer(QWidget):
    """Full-host overlay. Cards are children, so they remain clickable."""
    host_unavailable = Signal(object, object)
    host_destroyed = Signal(object, object)
    host_available = Signal()
    def __init__(self, content_area):
        super().__init__(content_area)
        self.content_area = content_area; self.toasts = []
        self.setObjectName("toastContainer")
        content_area.installEventFilter(self)
        self.setGeometry(content_area.rect()); self.hide()

    def eventFilter(self, obj, event):
        if obj is self.content_area and event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show):
            self.setGeometry(self.content_area.rect()); self._layout_cards()
            if event.type() == QEvent.Type.Show: self.host_available.emit()
        elif obj is self.content_area and event.type() == QEvent.Type.Hide:
            self.hide()
            self.host_unavailable.emit(self.drain_requests(), self.content_area)
        elif obj is self.content_area and event.type() == QEvent.Type.Destroy:
            self.host_destroyed.emit(self.drain_requests(), self.content_area)
        return False

    def show_toast(self, message, variant="info", duration_ms=None, title=None):
        card = Toast(message, variant, duration_ms, self, title)
        card.closed.connect(lambda c=card: self._remove(c))
        self.toasts.append(card); self.show(); self.raise_(); self._layout_cards()

    def _remove(self, card):
        if card in self.toasts: self.toasts.remove(card)
        self._layout_cards()
        if not self.toasts: self.hide()

    def drain_requests(self):
        requests = []
        for card in list(self.toasts):
            remaining = card.timer.remainingTime() if card.timer.isActive() else card.remaining
            card.timer.stop()
            requests.append((card.message, card.variant, max(0, remaining), card.title))
            card.closed.disconnect()
            card.hide(); card.deleteLater()
        self.toasts.clear(); self.hide()
        return requests

    def _layout_cards(self):
        right = max(12, self.width()-20); y = 16; maxh = max(40, self.height()-16)
        usable_height = max(20, maxh-y)
        hit_region = QRegion()
        waiting = False
        for c in self.toasts:
            maxw = min(440, max(100, self.width()-24))
            natural_height = c.measure_height(maxw)
            available_height = maxh-y
            oversized_first = y == 16 and natural_height > usable_height
            if waiting or (natural_height > available_height and not oversized_first):
                waiting = True
                if c.timer.isActive():
                    c.remaining = max(1, c.timer.remainingTime()); c.timer.stop()
                c.hide(); continue
            # Adapt a single card only when it is taller than the entire host;
            # otherwise preserve its readable height and queue it behind the stack.
            h = min(natural_height, max(20, available_height))
            c.setFixedHeight(h)
            c.setGeometry(max(0, right-maxw+1), y, maxw, h); c.show()
            hit_region = hit_region.united(QRegion(c.geometry()))
            if c.duration_ms and not c.timer.isActive() and not c._hovered:
                c.timer.start(c.remaining); c._timer_started = True
            y += h+8
        self.setMask(hit_region)
