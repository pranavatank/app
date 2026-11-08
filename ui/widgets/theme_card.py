"""Clickable theme preview card widget."""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton

from ui.theme import Theme


class ThemeCard(QAbstractButton):
    """
    Clickable card that paints a mini UI mockup of a theme.
    Loads colours directly from the theme module so preview
    is always accurate regardless of active theme.
    """
    selected = Signal(str)

    W, H = 280, 150

    # theme name → module file suffix
    _SUFFIX = {
        "Aurora":       "aurora_light",
        "Slate":        "slate_light",
        "Nova":         "nova_dark",
        "Midnight Pro": "midnight_pro",
    }

    def __init__(self, info: dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self._info      = info
        self._is_active = is_active
        self._hovered   = False
        self._c         = self._load()
        self.setCheckable(True)
        self.setChecked(is_active)
        self.setMinimumSize(self.W, self.H)
        self.setMaximumHeight(self.H)
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{info.get('emoji','🎨')} {info['name']}\n{info.get('description','')}")
        self.clicked.connect(lambda: self.selected.emit(self._info["name"]))

    def set_active(self, active: bool):
        self._is_active = active
        self.setChecked(active)
        self.update()

    def enterEvent(self, e): self._hovered = True;  self.update(); super().enterEvent(e)
    def leaveEvent(self, e): self._hovered = False; self.update(); super().leaveEvent(e)

    def _load(self) -> dict:
        import importlib
        suffix = self._SUFFIX.get(self._info["name"],
                     self._info["name"].lower().replace(" ", "_"))
        try:
            m = importlib.import_module(f"ui.theme.theme_{suffix}")
            g = lambda a, d: getattr(m, a, d)
            return {
                "pri": g("PRIMARY",        "#4F6EF7"),
                "suc": g("SUCCESS",        "#059669"),
                "war": g("WARNING",        "#D97706"),
                "dan": g("DANGER",         "#DC2626"),
                "inf": g("INFO",           "#0284C7"),
                "sb":  g("SIDEBAR_BG",     "#1E2D5C"),
                "bg":  g("BG",             "#F4F7FF"),
                "sf":  g("SURFACE",        "#FAFCFF"),
                "sa":  g("SURFACE_ALT",    "#EDF1FB"),
                "tb":  g("TOPBAR_BG",      "#FAFCFF"),
                "br":  g("BORDER",         "#D9E2FF"),
                "t2":  g("TEXT_SECONDARY", "#4B5563"),
                "nav": g("SIDEBAR_ACTIVE", "#4F6EF7"),
            }
        except Exception:
            return {
                "pri":"#4F6EF7","suc":"#059669","war":"#D97706","dan":"#DC2626",
                "inf":"#0284C7","sb":"#1E2D5C","bg":"#F4F7FF","sf":"#FAFCFF",
                "sa":"#EDF1FB","tb":"#FAFCFF","br":"#D9E2FF","t2":"#4B5563","nav":"#4F6EF7",
            }

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._c
        W = self.width()
        H = self.height()
        SB = 20  # sidebar width
        TB = 18  # topbar height

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, W, H, 10, 10)
        p.setClipPath(clip)

        # Background
        p.fillRect(0, 0, W, H, QColor(c["bg"]))

        # SIDEBAR (thin left strip)
        p.fillRect(0, 0, SB, H, QColor(c["sb"]))
        # Sidebar nav items (3 indicators)
        for i, is_active in enumerate([False, True, False]):
            y = TB + 6 + i * 12
            col = QColor(c["nav"]) if is_active else QColor(c["sb"]).lighter(120)
            p.fillRect(4, y, SB - 8, 8, col)

        # TOPBAR (horizontal strip)
        p.fillRect(SB, 0, W - SB, TB, QColor(c["tb"]))
        p.fillRect(SB, TB - 1, W - SB, 1, QColor(c["br"]))

        # TOPBAR CONTENT: small icon area + menu icon
        p.fillRect(SB + 4, 4, 10, 10, QColor(c["pri"]))
        p.fillRect(W - 16, 4, 10, 10, QColor(c["sa"]))

        content_y = TB + 6

        # KPI TILE (colored card with accent bar)
        kpi_w = (W - SB - 14) // 2
        kpi_h = 28
        p.fillRect(SB + 4, content_y, kpi_w, kpi_h, QColor(c["sf"]))
        # Accent bar (using primary color)
        p.fillRect(SB + 4, content_y, kpi_w, 3, QColor(c["pri"]))
        # Small text placeholder
        p.fillRect(SB + 7, content_y + 10, kpi_w - 10, 4, QColor(c["t2"]))

        # TABLE ROW (using success accent for variety)
        row_y = content_y + kpi_h + 6
        row_h = 18
        p.fillRect(SB + 4, row_y, W - SB - 8, row_h, QColor(c["sf"]))
        p.fillRect(SB + 4, row_y, 3, row_h, QColor(c["suc"]))
        # Row cell separators
        cell_w = (W - SB - 12) // 3
        for i in range(1, 3):
            p.fillRect(SB + 4 + i * cell_w, row_y, 1, row_h, QColor(c["br"]))

        # BUTTON (primary color)
        btn_y = row_y + row_h + 6
        btn_w = 60
        btn_h = 14
        p.fillRect(SB + 4, btn_y, btn_w, btn_h, QColor(c["pri"]))

        # COLOR SWATCH STRIP (accent colors at bottom)
        swatch_y = H - 12
        swatch_h = 12
        swatch_colors = [c["pri"], c["suc"], c["war"], c["dan"]]
        swatch_w = (W - SB) // 4
        for i, col in enumerate(swatch_colors):
            p.fillRect(SB + i * swatch_w, swatch_y, swatch_w, swatch_h, QColor(col))

        # Border
        p.setClipping(False)
        pen = QPen()
        if self._is_active:
            pen.setWidth(3); pen.setColor(QColor(Theme.PRIMARY))
        elif self._hovered:
            pen.setWidth(2); pen.setColor(QColor(c["pri"]))
        else:
            pen.setWidth(1); pen.setColor(QColor(Theme.BORDER))
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, W - 2, H - 2, 9, 9)

        # Active badge
        if self._is_active:
            r = 13; bx = W - r - 6; by = 6
            p.setBrush(QColor(Theme.PRIMARY)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(bx, by, r, r)
            cp = QPen(QColor(Theme.TEXT_ON_PRIMARY)); cp.setWidth(2); p.setPen(cp)
            f = p.font(); f.setPixelSize(9); f.setBold(True); p.setFont(f)
            p.drawText(bx, by, r, r, Qt.AlignmentFlag.AlignCenter, "✓")
        p.end()

    def sizeHint(self): return QSize(self.W, self.H)

    def minimumSizeHint(self): return QSize(self.W, self.H)


# ══════════════════════════════════════════════════════════════════════════════
# SettingsScreen
# ══════════════════════════════════════════════════════════════════════════════
