"""
ui/settings_screen.py — Settings screen with live theme switching.

LIVE THEME SWITCHING — HOW IT WORKS:
  QSS-driven widgets (inputs, tables, combos) update automatically when
  ThemeManager._deep_refresh() runs polish()/update() on them.

  Widgets with inline setStyleSheet() calls (QFrames with f-string styles)
  are frozen — polish() cannot update them. These must be explicitly
  re-styled in _on_theme_changed(), which is registered via
  ThemeManager.register_on_change().

  Order in ThemeManager.apply():
    1. _patch_theme()    — update Theme.* token values
    2. _set_stylesheet() — push new QSS to QApplication
    3. _fire_listeners() — call _on_theme_changed() to rebuild inline styles
    4. _deep_refresh()   — polish + repaint every widget
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QFormLayout, QLineEdit, QCheckBox, QFileDialog,
    QMessageBox, QScrollArea, QFrame, QGridLayout,
    QButtonGroup, QAbstractButton,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen

import os
from datetime import datetime

from ui.theme import Theme, ThemeManager
from ui.icons import icon as app_icon, icon_label, is_available as icons_available
from core.session import session
from core.auth import (
    change_password, is_totp_enabled, enable_totp, disable_totp,
    set_privacy_mode, get_privacy_mode,
)
from config import BACKUP_DIR


def _device_info() -> dict:
    try:
        from core.auth import get_device_fingerprint
        import platform, socket
        return {
            "device_id": get_device_fingerprint(),
            "platform":  f"{platform.system()} {platform.release()}",
            "hostname":  socket.gethostname(),
        }
    except Exception:
        return {"device_id": "Unknown", "platform": "Unknown", "hostname": "Unknown"}


# ══════════════════════════════════════════════════════════════════════════════
# ThemeCard
# ══════════════════════════════════════════════════════════════════════════════

class ThemeCard(QAbstractButton):
    """
    Clickable card that paints a mini UI mockup of a theme.
    Loads colours directly from the theme module so preview
    is always accurate regardless of active theme.
    """
    selected = pyqtSignal(str)

    W, H = 184, 118

    # theme name → module file suffix
    _SUFFIX = {
        "Aurora":        "aurora_light",
        "Ocean Blue":    "ocean_blue",
        "Arctic Breeze": "arctic_breeze",
        "Forest Light":  "forest_light",
        "Rose Gold Luxe":"rose_gold",
        "Sunrise Warm":  "sunrise_warm",
        "Nova":          "nova_dark",
        "Midnight Pro":  "midnight_pro",
        "Amethyst Dusk": "amethyst_dusk",
        "Finance Pro":   "finance_pro",
    }

    def __init__(self, info: dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self._info      = info
        self._is_active = is_active
        self._hovered   = False
        self._c         = self._load()
        self.setCheckable(True)
        self.setChecked(is_active)
        self.setFixedSize(self.W, self.H)
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
        W, H, SB, TB = self.W, self.H, 24, 16

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, W, H, 10, 10)
        p.setClipPath(clip)

        # bg
        p.fillRect(0, 0, W, H, QColor(c["bg"]))
        # sidebar
        p.fillRect(0, 0, SB, H, QColor(c["sb"]))
        for y, active in [(TB+4,False),(TB+16,True),(TB+28,False)]:
            col = QColor(c["nav"]) if active else QColor(c["sb"]).lighter(160)
            p.fillRect(3, y, SB-6, 8, col)
        # topbar
        p.fillRect(SB, 0, W-SB, TB, QColor(c["tb"]))
        p.fillRect(SB, TB, W-SB, 1, QColor(c["br"]))
        p.fillRect(SB+4, 4, 22, 8, QColor(c["pri"]))
        p.fillRect(W-22, 4, 18, 8, QColor(c["sa"]))
        # stat cards
        cy = TB+6; cw = (W-SB-10)//2
        for j, acc in enumerate([c["pri"], c["suc"]]):
            cx = SB+3+j*(cw+4)
            p.fillRect(cx, cy, cw, 22, QColor(c["sf"]))
            p.fillRect(cx, cy, cw, 3, QColor(acc))
            p.fillRect(cx+3, cy+7, cw-6, 5, QColor(acc))
            p.fillRect(cx+3, cy+14, cw//2, 4, QColor(c["t2"]))
        # bar chart
        chy = cy+26; chh = H-chy-14
        p.fillRect(SB+3, chy, W-SB-6, chh+2, QColor(c["sf"]))
        bcolors = [c["pri"],c["suc"],c["war"],c["dan"],c["inf"],c["pri"],c["suc"]]
        bheights= [0.8,0.5,0.9,0.4,0.7,0.6,0.85]
        bw = (W-SB-14)//7
        for k,(bc,bhr) in enumerate(zip(bcolors,bheights)):
            bh=max(3,int(chh*bhr)); bx=SB+5+k*(bw+2); by=chy+chh-bh+2
            p.fillRect(bx, by, bw, bh, QColor(bc))
        # swatch strip
        sw_y=H-12; sw_h=12
        sw_w=(W-SB)//4
        for k,sc in enumerate([c["pri"],c["suc"],c["war"],c["dan"]]):
            p.fillRect(SB+k*sw_w, sw_y, sw_w, sw_h, QColor(sc))

        # border
        p.setClipping(False)
        pen = QPen()
        if self._is_active:
            pen.setWidth(3); pen.setColor(QColor(Theme.PRIMARY))
        elif self._hovered:
            pen.setWidth(2); pen.setColor(QColor(c["pri"]))
        else:
            pen.setWidth(1); pen.setColor(QColor(Theme.BORDER))
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, W-2, H-2, 9, 9)

        # active badge
        if self._is_active:
            r=13; bx=W-r-6; by=6
            p.setBrush(QColor(Theme.PRIMARY)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(bx, by, r, r)
            cp = QPen(QColor("#FFFFFF")); cp.setWidth(2); p.setPen(cp)
            f=p.font(); f.setPixelSize(9); f.setBold(True); p.setFont(f)
            p.drawText(bx, by, r, r, Qt.AlignmentFlag.AlignCenter, "✓")
        p.end()

    def sizeHint(self): return QSize(self.W, self.H)


# ══════════════════════════════════════════════════════════════════════════════
# SettingsScreen
# ══════════════════════════════════════════════════════════════════════════════

class SettingsScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window    = parent
        self._theme_cards: dict[str, ThemeCard] = {}
        self._btn_group       = None
        # refs for inline-styled widgets that need rebuilding on theme change
        self._hdr_frame       = None
        self._cards_container = None
        self._desc_bar        = None
        self._theme_name_lbl  = None
        self._theme_desc_lbl  = None
        self._theme_mode_badge= None
        self.badge_totp       = None
        self.badge_privacy    = None
        self.badge_theme_lbl  = None
        # security fields
        self.current_pwd = None
        self.new_pwd     = None
        self.confirm_pwd = None
        self.totp_checkbox    = None
        self.privacy_checkbox = None

        self._build_ui()
        # Register AFTER build so callback has valid widget refs
        ThemeManager.register_on_change(self._on_theme_changed)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        self._hdr_frame = self._build_header()
        layout.addWidget(self._hdr_frame)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setSpacing(18)
        cl.setContentsMargins(0, 0, 0, 0)

        cl.addWidget(self._build_theme_section())

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.addWidget(self._section_security(), 0, 0)
        grid.addWidget(self._section_data(),     0, 1)
        grid.addWidget(self._section_privacy(),  1, 0)
        grid.addWidget(self._section_backup(),   1, 1)
        grid.addWidget(self._section_device(),   2, 0, 1, 2)
        cl.addLayout(grid)
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> QFrame:
        f = QFrame()
        f.setObjectName("SettingsHdr")
        f.setFixedHeight(76)
        f.setStyleSheet(self._hdr_css())
        f.setGraphicsEffect(Theme.shadow_elevated())

        layout = QHBoxLayout(f)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(32, 32)
        if icons_available():
            pm = app_icon("settings", color="#FFFFFF", size=24).pixmap(24, 24)
            icon_lbl.setPixmap(pm)
        else:
            icon_lbl.setText("⚙️")
            icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        col = QVBoxLayout(); col.setSpacing(2)
        t = QLabel("Settings")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        t.setStyleSheet("color: white; background: transparent; border: none;")
        col.addWidget(t)
        s = QLabel("Security  ·  Privacy  ·  Theme  ·  Data  ·  Backup")
        s.setStyleSheet("color: rgba(255,255,255,0.82); font-size: 12px; background: transparent; border: none;")
        col.addWidget(s)
        layout.addLayout(col)
        layout.addStretch()

        badge_row = QHBoxLayout(); badge_row.setSpacing(8)
        self.badge_totp      = self._hdr_badge("")
        self.badge_privacy   = self._hdr_badge("")
        self.badge_theme_lbl = self._hdr_badge("")
        badge_row.addWidget(self.badge_totp)
        badge_row.addWidget(self.badge_privacy)
        badge_row.addWidget(self.badge_theme_lbl)
        layout.addLayout(badge_row)

        btn_backup = Theme.btn("  Backup", "success", height=34, min_width=106)
        btn_backup.setIcon(app_icon("backup", color="#FFFFFF", size=16))
        btn_backup.clicked.connect(self._on_create_backup)
        layout.addWidget(btn_backup)

        self._refresh_badges()
        return f

    def _hdr_css(self) -> str:
        return Theme.hero_header_style(radius=14, selector="QFrame#SettingsHdr")

    def _hdr_badge(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            "background: rgba(255,255,255,0.22); color: white; border-radius: 10px; "
            "padding: 3px 10px; font-size: 11px; font-weight: 600; border: none;")
        return l

    def _refresh_badges(self):
        if self.badge_totp:
            self.badge_totp.setText("2FA On" if is_totp_enabled() else "2FA Off")
        if self.badge_privacy:
            self.badge_privacy.setText("Privacy On" if session.privacy_mode else "Privacy Off")
        if self.badge_theme_lbl:
            self.badge_theme_lbl.setText(f"{ThemeManager.current_name()}")

    # ── Theme section ─────────────────────────────────────────────────────────

    def _build_theme_section(self) -> QWidget:
        outer = QWidget(); outer.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(outer); vl.setContentsMargins(0,0,0,0); vl.setSpacing(10)

        # Section header
        hdr = QHBoxLayout()
        ic = QLabel("🎨"); ic.setFont(QFont("Segoe UI Emoji", 14))
        ic.setStyleSheet("background: transparent;"); hdr.addWidget(ic)
        title = QLabel("Color Theme")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(Theme.text_style(color=Theme.TEXT_HEADING, size=14, weight=700))
        hdr.addWidget(title); hdr.addSpacing(10)
        live = QLabel("● Live — no restart needed")
        live.setStyleSheet(f"color:{Theme.SUCCESS};font-size:11px;font-weight:700;background:transparent;")
        hdr.addWidget(live); hdr.addStretch()
        sub = QLabel("Click any card to switch instantly")
        sub.setStyleSheet(Theme.muted_style(12)); hdr.addWidget(sub)
        vl.addLayout(hdr)

        # Container
        container = QFrame(); container.setObjectName("ThemeContainer")
        container.setStyleSheet(self._cards_css())
        container.setGraphicsEffect(Theme.shadow_card())
        self._cards_container = container

        fl = QVBoxLayout(container); fl.setContentsMargins(20,18,20,18); fl.setSpacing(14)

        # Light / dark rows
        fl.addWidget(self._row_label("☀️  Light Themes"))
        light_row = QHBoxLayout(); light_row.setSpacing(12)
        light_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        fl.addLayout(light_row)

        fl.addWidget(self._row_label("🌙  Dark Themes"))
        dark_row = QHBoxLayout(); dark_row.setSpacing(12)
        dark_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        fl.addLayout(dark_row)

        self._theme_cards = {}
        self._btn_group   = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        active = ThemeManager.current_name()

        for info in ThemeManager.available_themes():
            card = ThemeCard(info, is_active=(info["name"] == active))
            card.selected.connect(self._on_card_clicked)
            self._btn_group.addButton(card)
            self._theme_cards[info["name"]] = card

            cell_w = QWidget(); cell_w.setStyleSheet("background: transparent;")
            cell   = QVBoxLayout(cell_w); cell.setSpacing(3); cell.setContentsMargins(0,0,0,0)
            cell.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
            n = QLabel(f"{info.get('emoji','🎨')} {info['name']}")
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=600))
            cell.addWidget(n)

            (light_row if not info["is_dark"] else dark_row).addWidget(cell_w)

        light_row.addStretch(); dark_row.addStretch()

        # Description bar
        desc = QFrame(); desc.setObjectName("ThemeDescBar")
        desc.setStyleSheet(self._desc_css())
        self._desc_bar = desc
        dl = QHBoxLayout(desc); dl.setContentsMargins(14,8,14,8); dl.setSpacing(10)
        self._theme_name_lbl = QLabel("")
        self._theme_name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        dl.addWidget(self._theme_name_lbl)
        self._theme_mode_badge = QLabel(""); self._theme_mode_badge.setFixedHeight(22)
        dl.addWidget(self._theme_mode_badge)
        self._theme_desc_lbl = QLabel("")
        dl.addWidget(self._theme_desc_lbl); dl.addStretch()
        fl.addWidget(desc)

        self._update_desc(active)
        vl.addWidget(container)
        return outer

    def _cards_css(self) -> str:
        return (f"QFrame#ThemeContainer{{background-color:{Theme.SURFACE};"
                f"border:1px solid {Theme.BORDER};border-radius:14px;}}")

    def _desc_css(self) -> str:
        return (f"QFrame#ThemeDescBar{{background-color:{Theme.SURFACE_ALT};"
                f"border:1px solid {Theme.BORDER};border-radius:8px;}}")

    def _row_label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_SECONDARY, size=12, weight=700) +
            f" background:{Theme.SURFACE_ALT};border-radius:6px;padding:4px 10px;")
        return l

    def _update_desc(self, name: str):
        themes = {t["name"]: t for t in ThemeManager.available_themes()}
        info = themes.get(name, {})
        if self._theme_name_lbl:
            self._theme_name_lbl.setText(f"{info.get('emoji','🎨')}  {name}")
            self._theme_name_lbl.setStyleSheet(
                Theme.text_style(color=Theme.PRIMARY, size=12, weight=700))
        if self._theme_desc_lbl:
            self._theme_desc_lbl.setText(info.get("description", ""))
            self._theme_desc_lbl.setStyleSheet(Theme.muted_style(12))
        if self._theme_mode_badge:
            self._theme_mode_badge.setText("🌙 Dark" if info.get("is_dark") else "☀️ Light")
            self._theme_mode_badge.setStyleSheet(
                Theme.badge_style(Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK,
                                  radius=8, padding="3px 12px", size=11))

    def _on_card_clicked(self, name: str):
        """Apply immediately — no popup, no restart."""
        ThemeManager.apply(name)

    def _on_theme_changed(self, name: str):
        """
        Rebuild every inline-styled widget after a theme switch.
        Called by ThemeManager BEFORE _deep_refresh() so widgets have
        correct styles when Qt repaints them.
        """
        # Update card active states
        for n, card in self._theme_cards.items():
            card.set_active(n == name)

        # Rebuild inline CSS for frozen widgets
        if self._hdr_frame:
            self._hdr_frame.setStyleSheet(self._hdr_css())
        if self._cards_container:
            self._cards_container.setStyleSheet(self._cards_css())
        if self._desc_bar:
            self._desc_bar.setStyleSheet(self._desc_css())

        self._update_desc(name)
        self._refresh_badges()

        # Flash badge
        if self.badge_theme_lbl:
            self.badge_theme_lbl.setText(f"✅ {name}")
            QTimer.singleShot(2200, self._refresh_badges)

    # ── Sections ──────────────────────────────────────────────────────────────

    def _section_security(self) -> QGroupBox:
        g = self._group("Security"); gl = QVBoxLayout(g); gl.setSpacing(10)

        c1 = self._card(); l1 = QVBoxLayout(c1); l1.setSpacing(10)
        l1.addWidget(self._card_title("Change Master Password"))
        form = QFormLayout(); form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.current_pwd = self._pwd_field("Current password")
        self.new_pwd     = self._pwd_field("New password")
        self.confirm_pwd = self._pwd_field("Confirm new password")
        form.addRow(self._form_lbl("Current"), self.current_pwd)
        form.addRow(self._form_lbl("New"),     self.new_pwd)
        form.addRow(self._form_lbl("Confirm"), self.confirm_pwd)
        l1.addLayout(form)
        b = Theme.btn("Change Password", "primary", height=36, min_width=160)
        b.clicked.connect(self._on_change_password)
        l1.addWidget(b)
        gl.addWidget(c1)

        c2 = self._card(); l2 = QVBoxLayout(c2); l2.setSpacing(8)
        l2.addWidget(self._card_title("Two-Factor Authentication"))
        self.totp_checkbox = QCheckBox("Enable TOTP (Google Authenticator)")
        self.totp_checkbox.setChecked(is_totp_enabled())
        self.totp_checkbox.stateChanged.connect(self._on_totp_toggle)
        l2.addWidget(self.totp_checkbox)
        l2.addWidget(self._muted("Required at every login when enabled."))
        gl.addWidget(c2)
        return g

    def _section_data(self) -> QGroupBox:
        g = self._group("Data Management"); gl = QVBoxLayout(g); gl.setSpacing(10)
        for title, desc, variant, handler in [
            ("Family Members", "Add or manage persons for tracking.",    "primary",   self._on_manage_persons),
            ("Bank Accounts",  "Manage accounts per family member.",     "info",      self._on_manage_accounts),
            ("Banks (Master)", "Master bank list used across the app.",  "secondary", self._on_manage_banks),
        ]:
            c = self._card(); lc = QVBoxLayout(c); lc.setSpacing(6)
            lc.addWidget(self._card_title(title))
            lc.addWidget(self._muted(desc))
            b = Theme.btn(f"Manage {title.split()[0]}", variant, height=36, min_width=155)
            b.clicked.connect(handler)
            lc.addWidget(b)
            gl.addWidget(c)
        return g

    def _section_privacy(self) -> QGroupBox:
        g = self._group("Privacy"); gl = QVBoxLayout(g)
        c = self._card(); lc = QVBoxLayout(c)
        lc.addWidget(self._card_title("Privacy Mode"))
        self.privacy_checkbox = QCheckBox("Mask all financial amounts  (₹ ****)")
        self.privacy_checkbox.setChecked(session.privacy_mode)
        self.privacy_checkbox.stateChanged.connect(self._on_privacy_toggle)
        lc.addWidget(self.privacy_checkbox)
        lc.addWidget(self._muted("Toggle any time. All screens reflect immediately."))
        gl.addWidget(c)
        return g

    def _section_backup(self) -> QGroupBox:
        g = self._group("Backup & Restore"); gl = QVBoxLayout(g); gl.setSpacing(10)

        c1 = self._card(); l1 = QVBoxLayout(c1)
        l1.addWidget(self._card_title("Create Backup"))
        l1.addWidget(self._muted("Copies database to the backups folder."))
        b1 = Theme.btn("  Create Backup", "success", height=36, min_width=155)
        b1.setIcon(app_icon("backup", color="#FFFFFF", size=16))
        b1.clicked.connect(self._on_create_backup)
        l1.addWidget(b1)
        gl.addWidget(c1)

        c2 = self._card(); l2 = QVBoxLayout(c2)
        l2.addWidget(self._card_title("Restore from Backup"))
        w = QLabel("⚠  Replaces your current database — all data will be lost!")
        w.setStyleSheet(Theme.text_style(color=Theme.WARNING_DARK, size=12, weight=600))
        l2.addWidget(w)
        b2 = Theme.btn("  Restore Backup", "danger", height=36, min_width=155)
        b2.setIcon(app_icon("restore", color="#FFFFFF", size=16))
        b2.clicked.connect(self._on_restore_backup)
        l2.addWidget(b2)
        gl.addWidget(c2)
        return g

    def _section_device(self) -> QGroupBox:
        g = self._group("Device Information"); gl = QVBoxLayout(g)
        c = self._card(); fl = QFormLayout(c)
        fl.setSpacing(8)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info = _device_info()
        dev = QLabel(info["device_id"][:34] + "…")
        dev.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_PRIMARY, size=11) +
            " font-family: 'Consolas','Courier New',monospace; background:transparent;")
        fl.addRow(self._form_lbl("Device ID"), dev)
        fl.addRow(self._form_lbl("Platform"),  QLabel(info["platform"][:60]))
        fl.addRow(self._form_lbl("Hostname"),  QLabel(info.get("hostname","—")))
        fl.addRow("", self._muted("This app is cryptographically bound to this device."))
        gl.addWidget(c)
        return g

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet(f"""
            QGroupBox {{
                border: none; margin-top: 4px; background: transparent;
                font-size: 13px; font-weight: 700; color: {Theme.PRIMARY_DARK};
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 2px; padding: 0 6px; }}
        """)
        return g

    def _card(self) -> QFrame:
        f = QFrame(); f.setObjectName("SettingsCard")
        f.setStyleSheet(Theme.card_style(
            bg=Theme.SURFACE, border_color=Theme.BORDER,
            radius=12, padding=14, selector="QFrame#SettingsCard"))
        f.setGraphicsEffect(Theme.shadow_card())
        f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return f

    def _card_title(self, text: str) -> QLabel:
        l = QLabel(text); l.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        l.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=700))
        return l

    def _muted(self, text: str) -> QLabel:
        l = QLabel(text); l.setStyleSheet(Theme.muted_style(11)); return l

    def _pwd_field(self, placeholder: str) -> QLineEdit:
        e = QLineEdit(); e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setPlaceholderText(placeholder); e.setFixedHeight(36); return e

    def _form_lbl(self, text: str) -> QLabel:
        l = QLabel(f"{text}:"); l.setStyleSheet(Theme.section_label_style(12)); return l

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_change_password(self):
        cur, new, conf = self.current_pwd.text(), self.new_pwd.text(), self.confirm_pwd.text()
        if not all([cur, new, conf]):
            QMessageBox.warning(self, "Missing", "Please fill all password fields."); return
        if new != conf:
            QMessageBox.warning(self, "Mismatch", "New passwords do not match."); return
        if len(new) < 8:
            QMessageBox.warning(self, "Too Short", "Password must be at least 8 characters."); return
        ok, msg = change_password(cur, new)
        if ok:
            QMessageBox.information(self, "Success", "Password changed successfully!")
            for f in [self.current_pwd, self.new_pwd, self.confirm_pwd]: f.clear()
        else:
            QMessageBox.warning(self, "Failed", msg)

    def _on_totp_toggle(self, state):
        enabled = bool(state)
        try:
            if enabled:
                uri = enable_totp()
                QMessageBox.information(self, "TOTP Enabled",
                    f"Scan this URI with your authenticator app:\n\n{uri}")
            else:
                disable_totp()
                QMessageBox.information(self, "TOTP Disabled", "2FA has been disabled.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            self.totp_checkbox.setChecked(not enabled)
        finally:
            self._refresh_badges()

    def _on_privacy_toggle(self, state):
        enabled = bool(state)
        try:
            set_privacy_mode(enabled)
            session.set_privacy_mode(enabled)
            self._refresh_badges()
            if self.parent_window: self.parent_window.refresh_overview()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            self.privacy_checkbox.setChecked(not enabled)

    def _on_create_backup(self):
        try:
            from ui.widgets.loader import Loader
            from core.database import backup_database
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"backup_{ts}.db")
            with Loader(self, "Creating backup…", subtitle="Copying database file"):
                backup_database(dest)
            QMessageBox.information(self, "Backup Created", f"Saved to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def _on_restore_backup(self):
        reply = QMessageBox.warning(
            self, "Confirm Restore",
            "WARNING: This will REPLACE your current database.\nAll data will be lost!\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File", BACKUP_DIR, "Database Files (*.db)")
        if not path: return
        try:
            from ui.widgets.loader import Loader
            from core.database import restore_database
            with Loader(self, "Restoring backup…", subtitle="Please do not close the app"):
                restore_database(path)
            QMessageBox.information(self, "Restored",
                "Database restored. Please restart the app.")
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", str(e))

    def _on_manage_persons(self):
        from ui.dialogs.person_dialog import PersonManagementDialog
        PersonManagementDialog(self).exec()

    def _on_manage_accounts(self):
        from ui.dialogs.account_dialog import AccountManagementDialog
        AccountManagementDialog(self).exec()

    def _on_manage_banks(self):
        try:
            from ui.dialogs.bank_dialog import BankManagementDialog
            BankManagementDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def refresh(self):
        if self.totp_checkbox:
            self.totp_checkbox.setChecked(is_totp_enabled())
        priv = get_privacy_mode()
        session.set_privacy_mode(priv)
        if self.privacy_checkbox:
            self.privacy_checkbox.setChecked(priv)
        active = ThemeManager.current_name()
        for name, card in self._theme_cards.items():
            card.set_active(name == active)
        self._update_desc(active)
        self._refresh_badges()
