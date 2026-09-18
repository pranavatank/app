"""
ui/widgets/motion.py — Shared motion helpers.

Motion explains state change; it never decorates data. Durations and easing
come from Theme.MOTION_*, so callers pass a widget, not a duration.

Set ENABLED = False to turn every animation into an instant final-value set
(used for offscreen rendering and future reduced-motion support).
"""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QWidget

from ui.theme import Theme

ENABLED = True

_MAX_HEIGHT = 16777215


def _curve() -> QEasingCurve:
    return QEasingCurve(getattr(QEasingCurve.Type, Theme.MOTION_EASING))


def _start(widget: QWidget, anim: QPropertyAnimation) -> QPropertyAnimation:
    """Keep the animation alive for its lifetime, replacing any running one."""
    previous = getattr(widget, "_motion_anim", None)
    # DeleteWhenStopped frees the C++ object while this Python reference lives on,
    # so the stale wrapper has to be checked before it is touched. Stopping it
    # mid-flight would strand the widget at the interrupted value, so it is
    # snapped to its end value first.
    if previous is not None and shiboken6.isValid(previous):
        end = previous.endValue()
        previous.stop()
        if end is not None:
            previous.targetObject().setProperty(previous.propertyName().data().decode(), end)
    widget._motion_anim = anim
    anim.setEasingCurve(_curve())
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def _opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect | None:
    """Reuse an existing opacity effect; never replace a drop shadow with one."""
    effect = widget.graphicsEffect()
    if isinstance(effect, QGraphicsOpacityEffect):
        return effect
    if isinstance(effect, QGraphicsDropShadowEffect):
        return None
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    return effect


def fade_in(widget: QWidget, duration: int | None = None) -> QPropertyAnimation | None:
    """Fade a widget from transparent to opaque."""
    widget.show()
    if not ENABLED:
        return None
    effect = _opacity_effect(widget)
    if effect is None:
        return None
    effect.setOpacity(0.0)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(Theme.MOTION_BASE if duration is None else duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    # A starved event loop would otherwise leave the widget stuck at opacity 0,
    # i.e. laid out and "visible" but painting nothing.
    anim.finished.connect(lambda: effect.setOpacity(1.0))
    return _start(widget, anim)


def fade_out(
    widget: QWidget, duration: int | None = None, hide_on_finish: bool = True
) -> QPropertyAnimation | None:
    """Fade a widget to transparent, optionally hiding it when done."""
    effect = _opacity_effect(widget) if ENABLED else None
    if effect is None:
        if hide_on_finish:
            widget.hide()
        return None
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(Theme.MOTION_BASE if duration is None else duration)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    if hide_on_finish:
        anim.finished.connect(widget.hide)
    return _start(widget, anim)


def slide_in(
    widget: QWidget, dx: int = 0, dy: int = 12, duration: int | None = None
) -> QPropertyAnimation | None:
    """Animate a widget from an offset back to its laid-out position."""
    widget.show()
    if not ENABLED:
        return None
    end = widget.geometry()
    start = end.translated(dx, dy)
    anim = QPropertyAnimation(widget, b"geometry", widget)
    anim.setDuration(Theme.MOTION_BASE if duration is None else duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    return _start(widget, anim)


def animate_width(
    widget: QWidget, target: int, duration: int | None = None
) -> QPropertyAnimation | None:
    """Animate a widget's width. Drives both bounds so setFixedWidth can't pin it."""
    if not ENABLED:
        widget.setFixedWidth(target)
        return None
    start = widget.width()
    widget.setMinimumWidth(min(start, target))
    widget.setMaximumWidth(max(start, target))
    anim = QPropertyAnimation(widget, b"maximumWidth", widget)
    anim.setDuration(Theme.MOTION_FAST if duration is None else duration)
    anim.setStartValue(start)
    anim.setEndValue(target)
    anim.finished.connect(lambda: widget.setFixedWidth(target))
    return _start(widget, anim)


def animate_height(
    widget: QWidget, target: int, duration: int | None = None
) -> QPropertyAnimation | None:
    """Animate a widget's maximum height (collapsible sections)."""
    if not ENABLED:
        widget.setMaximumHeight(target)
        return None
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(Theme.MOTION_FAST if duration is None else duration)
    anim.setStartValue(widget.height())
    anim.setEndValue(target)
    if target > 0:
        # Unclamp once expanded so later relayouts are not capped.
        anim.finished.connect(lambda: widget.setMaximumHeight(_MAX_HEIGHT))
    return _start(widget, anim)
