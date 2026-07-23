"""
ui/theme/checkbox_asset.py — Pre-rendered checkmark glyph for QCheckBox.

Qt stylesheets can't draw an arbitrary vector checkmark on
QCheckBox::indicator:checked directly — the `image` property needs a real
file path. This module renders a small white checkmark PNG once (cached
under data/, the same convention already used for logo.png and
theme_prefs.json) and returns a QSS-safe url() path for it.

White is used regardless of theme because the checked indicator's
background is always Theme.PRIMARY (a saturated color across every theme),
so a white checkmark reads clearly on all of them.
"""
from __future__ import annotations
import os

_ASSET_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
_ASSET_PATH = os.path.join(_ASSET_DIR, "checkbox_check.png")


def checkmark_url() -> str:
    """Ensure the checkmark PNG exists on disk, return a QSS url() path."""
    try:
        if not os.path.isfile(_ASSET_PATH):
            _generate()
        return _ASSET_PATH.replace("\\", "/")
    except Exception:
        return ""


def _generate() -> None:
    from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
    from PyQt6.QtCore import Qt, QPoint

    os.makedirs(_ASSET_DIR, exist_ok=True)
    size = 14
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPolyline(QPoint(3, 7), QPoint(6, 10), QPoint(11, 3))
    p.end()
    pm.save(_ASSET_PATH, "PNG")
