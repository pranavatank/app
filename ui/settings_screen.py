"""
ui/settings_screen.py — Settings screen with live theme switching.

LIVE THEME SWITCHING:
  - Click a theme card → theme applies immediately, no dialog, no restart.
  - ThemeManager._deep_refresh() polishes every widget in the app.
  - SettingsScreen registers _on_theme_changed_externally() so its own
    inline-styled widgets (header, cards frame, description bar) are
    restyles correctly after the switch.

THEME CARDS:
  - Paint a tiny accurate UI mockup (sidebar, topbar, cards, chart bars, swatches).
  - Hover: card's own PRIMARY colour glow border.
  - Active: thick Theme.PRIMARY ring + filled ✓ badge top-right.
  - Grouped into ☀️ Light / 🌙 Dark rows.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QFormLayout, QLineEdit, QCheckBox, QFileDialog,
    QMessageBox, QScrollArea, QFrame, QGridLayout,
    QButtonGroup, QAbstractButton, QSizePolicy, QListWidget, QPushButton,
    QComboBox,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen

import os
from datetime import datetime

from ui.theme import Theme, ThemeManager
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
# ThemeCard — clickable mini UI preview card
# ══════════════════════════════════════════════════════════════════════════════

class ThemeCard(QAbstractButton):
    selected = pyqtSignal(str)

    W = 184
    H = 118

    # Map theme name → module suffix for colour loading
    _NAME_TO_SUFFIX = {
        "Ocean Blue":     "ocean_blue",
        "Forest Light":   "forest_light",
        "Rose Gold Luxe": "rose_gold",
        "Sunrise Warm":   "sunrise_warm",
        "Midnight Pro":   "midnight_pro",
        "Amethyst Dusk":  "amethyst_dusk",
        "Finance Pro":    "finance_pro",
    }

    def __init__(self, info: dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self._info      = info
        self._is_active = is_active
        self._hovered   = False
        self._colors    = self._load_colors()

        self.setCheckable(True)
        self.setChecked(is_active)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{info.get('emoji','🎨')} {info['name']}\n{info.get('description','')}")
        self.setAccessibleName(f"Theme card: {info['name']}")
        self.setAccessibleDescription(info.get('description', 'Theme preview card.'))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(lambda: self.selected.emit(self._info["name"]))

    def set_active(self, active: bool):
        self._is_active = active
        self.setChecked(active)
        self.update()

    def enterEvent(self, e): self._hovered = True;  self.update(); super().enterEvent(e)
    def leaveEvent(self, e): self._hovered = False; self.update(); super().leaveEvent(e)

    def _load_colors(self) -> dict:
        import importlib
        suffix = self._NAME_TO_SUFFIX.get(self._info["name"],
                     self._info["name"].lower().replace(" ", "_"))
        try:
            m = importlib.import_module(f"ui.theme.theme_{suffix}")
            return {
                "primary":  getattr(m, "PRIMARY",      "#2563EB"),
                "success":  getattr(m, "SUCCESS",      "#059669"),
                "warning":  getattr(m, "WARNING",      "#D97706"),
                "danger":   getattr(m, "DANGER",       "#DC2626"),
                "info":     getattr(m, "INFO",         "#0284C7"),
                "sidebar":  getattr(m, "SIDEBAR_BG",   "#0F172A"),
                "bg":       getattr(m, "BG",           "#F5F8FF"),
                "surface":  getattr(m, "SURFACE",      "#FFFFFF"),
                "surf_alt": getattr(m, "SURFACE_ALT",  "#F1F5FD"),
                "topbar":   getattr(m, "TOPBAR_BG",    "#FFFFFF"),
                "border":   getattr(m, "BORDER",       "#E2E8F0"),
                "text":     getattr(m, "TEXT_PRIMARY",  "#0F172A"),
                "text2":    getattr(m, "TEXT_SECONDARY","#475569"),
                "sa_active":getattr(m, "SIDEBAR_ACTIVE","#2563EB"),
            }
        except Exception:
            return {
                "primary": "#2563EB", "success": "#059669", "warning": "#D97706",
                "danger": "#DC2626", "info": "#0284C7",
                "sidebar": "#0F172A", "bg": "#F5F8FF", "surface": "#FFFFFF",
                "surf_alt": "#F1F5FD", "topbar": "#FFFFFF", "border": "#E2E8F0",
                "text": "#0F172A", "text2": "#475569", "sa_active": "#2563EB",
            }

    def paintEvent(self, event):
        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c   = self._colors
        W, H = self.W, self.H
        SB  = 24    # sidebar width
        TB  = 16    # topbar height

        # ── Clip to card shape ────────────────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(0, 0, W, H, 10, 10)
        p.setClipPath(path)

        # ── Background ────────────────────────────────────────────────────────
        p.fillRect(0, 0, W, H, QColor(c["bg"]))

        # ── Sidebar ───────────────────────────────────────────────────────────
        p.fillRect(0, 0, SB, H, QColor(c["sidebar"]))
        # 3 nav items
        for i, (y, active) in enumerate([(TB+4, False), (TB+16, True), (TB+28, False)]):
            col = QColor(c["sa_active"]) if active else QColor(c["sidebar"]).lighter(150)
            p.fillRect(3, y, SB - 6, 8, col)

        # ── Topbar ────────────────────────────────────────────────────────────
        p.fillRect(SB, 0, W - SB, TB, QColor(c["topbar"]))
        p.fillRect(SB, TB, W - SB, 1, QColor(c["border"]))
        # Topbar: brand text block + 2 small pill buttons
        p.fillRect(SB + 4, 4, 22, 8, QColor(c["primary"]))
        p.fillRect(W - 22, 4, 18, 8, QColor(c["surf_alt"]))

        # ── Stat cards (2 side by side) ───────────────────────────────────────
        cy   = TB + 6
        cw   = (W - SB - 10) // 2
        for j, accent in enumerate([c["primary"], c["success"]]):
            cx = SB + 3 + j * (cw + 4)
            p.fillRect(cx, cy, cw, 22, QColor(c["surface"]))
            p.fillRect(cx, cy, cw, 3, QColor(accent))          # accent top bar
            p.fillRect(cx + 3, cy + 7, cw - 6, 5, QColor(accent))   # value
            p.fillRect(cx + 3, cy + 14, cw // 2, 4, QColor(c["text2"]))  # label

        # ── Mini bar chart ────────────────────────────────────────────────────
        chy  = cy + 26
        chh  = H - chy - 18    # chart height
        p.fillRect(SB + 3, chy, W - SB - 6, chh + 2, QColor(c["surface"]))
        bar_colors = [c["primary"], c["success"], c["warning"],
                      c["danger"], c["info"], c["primary"], c["success"]]
        heights    = [0.8, 0.5, 0.9, 0.4, 0.7, 0.6, 0.85]
        bw = (W - SB - 14) // 7
        for k, (bc, bh_ratio) in enumerate(zip(bar_colors, heights)):
            bh  = max(3, int(chh * bh_ratio))
            bx  = SB + 5 + k * (bw + 2)
            by  = chy + chh - bh + 2
            p.fillRect(bx, by, bw, bh, QColor(bc))

        # ── Bottom swatch strip ───────────────────────────────────────────────
        sw_y  = H - 14
        sw_h  = 14
        sw_cols = [c["primary"], c["success"], c["warning"], c["danger"]]
        sw_w  = (W - SB) // 4
        for k, sc in enumerate(sw_cols):
            p.fillRect(SB + k * sw_w, sw_y, sw_w, sw_h, QColor(sc))

        # ── Border (hover / active) ───────────────────────────────────────────
        p.setClipping(False)
        pen = QPen()
        if self._is_active:
            pen.setWidth(3)
            pen.setColor(QColor(Theme.PRIMARY))
        elif self._hovered:
            pen.setWidth(2)
            pen.setColor(QColor(c["primary"]))
        else:
            pen.setWidth(1)
            pen.setColor(QColor(Theme.BORDER))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, W - 2, H - 2, 9, 9)

        # ── Active ✓ badge ────────────────────────────────────────────────────
        if self._is_active:
            r  = 13
            bx = W - r - 6
            by = 6
            p.setBrush(QColor(Theme.PRIMARY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(bx, by, r, r)
            check_pen = QPen(QColor("#FFFFFF"))
            check_pen.setWidth(2)
            p.setPen(check_pen)
            font = p.font(); font.setPixelSize(9); font.setBold(True)
            p.setFont(font)
            p.drawText(bx, by, r, r, Qt.AlignmentFlag.AlignCenter, "✓")

        p.end()

    def sizeHint(self) -> QSize:
        return QSize(self.W, self.H)


# ══════════════════════════════════════════════════════════════════════════════
# SettingsScreen
# ══════════════════════════════════════════════════════════════════════════════

class SettingsScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window   = parent
        self._theme_cards: dict[str, ThemeCard] = {}
        self._btn_group      = None

        # Widgets that need restyle after theme switch
        self._hdr_frame      = None
        self._cards_container= None
        self._desc_bar       = None
        self._theme_name_lbl = None
        self._theme_desc_lbl = None
        self._theme_mode_badge = None
        self.badge_totp      = None
        self.badge_privacy   = None
        self.badge_theme_lbl = None

        self._build_ui()
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

    # ── Header card ───────────────────────────────────────────────────────────

    def _build_header(self) -> QFrame:
        f = QFrame()
        f.setObjectName("SettingsHdr")
        f.setFixedHeight(76)
        f.setStyleSheet(self._hdr_style())
        f.setGraphicsEffect(Theme.shadow_elevated())

        layout = QHBoxLayout(f)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(14)

        icon = QLabel("⚙️")
        icon.setFont(QFont("Segoe UI Emoji", 20))
        icon.setStyleSheet("background: transparent; border: none;")
        icon.setAccessibleName("Settings icon")
        layout.addWidget(icon)

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

        # Status badges
        badge_row = QHBoxLayout(); badge_row.setSpacing(8)
        self.badge_totp      = self._hdr_badge("")
        self.badge_privacy   = self._hdr_badge("")
        self.badge_theme_lbl = self._hdr_badge("")
        badge_row.addWidget(self.badge_totp)
        badge_row.addWidget(self.badge_privacy)
        badge_row.addWidget(self.badge_theme_lbl)
        layout.addLayout(badge_row)

        btn_backup = Theme.btn("💾 Backup", "success", height=34, min_width=106)
        btn_backup.clicked.connect(self._on_create_backup)
        btn_backup.setAccessibleName("Create backup")
        btn_backup.setAccessibleDescription("Create a backup copy of the database.")
        btn_backup.setToolTip("Create a backup copy of the database.")
        btn_backup.setShortcut("Alt+B")
        layout.addWidget(btn_backup)

        self._refresh_badges()
        return f

    def _hdr_style(self) -> str:
        return f"""
            QFrame#SettingsHdr {{
                background: {Theme.gradient(Theme.HERO_GRADIENT_START, Theme.HERO_GRADIENT_END)};
                border-radius: 14px; border: none;
            }}
        """

    def _hdr_badge(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            "background: rgba(255,255,255,0.22); color: white; "
            "border-radius: 10px; padding: 3px 10px; "
            "font-size: 11px; font-weight: 600; border: none;"
        )
        return l

    def _refresh_badges(self):
        if self.badge_totp:
            self.badge_totp.setText("🔒 2FA On" if is_totp_enabled() else "🔓 2FA Off")
        if self.badge_privacy:
            self.badge_privacy.setText("👁 Privacy On" if session.privacy_mode else "👁 Privacy Off")
        if self.badge_theme_lbl:
            self.badge_theme_lbl.setText(f"🎨 {ThemeManager.current_name()}")

    # ── Theme section ─────────────────────────────────────────────────────────

    def _build_theme_section(self) -> QWidget:
        outer = QWidget(); outer.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(outer); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(10)

        # Section header
        hdr = QHBoxLayout()
        ic = QLabel("🎨"); ic.setFont(QFont("Segoe UI Emoji", 14))
        ic.setStyleSheet("background: transparent;")
        hdr.addWidget(ic)
        title = QLabel("Color Theme")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(Theme.text_style(color=Theme.TEXT_HEADING, size=14, weight=700))
        hdr.addWidget(title)
        hdr.addSpacing(10)
        live_badge = QLabel("● Live — no restart needed")
        live_badge.setStyleSheet(
            f"color: {Theme.SUCCESS}; font-size: 11px; font-weight: 700; background: transparent;")
        hdr.addWidget(live_badge)
        hdr.addStretch()
        sub = QLabel("Click any card to switch instantly")
        sub.setStyleSheet(Theme.muted_style(12))
        hdr.addWidget(sub)
        vl.addLayout(hdr)

        # White container card
        container = QFrame()
        container.setObjectName("ThemeContainer")
        container.setStyleSheet(self._cards_container_style())
        container.setGraphicsEffect(Theme.shadow_card())
        self._cards_container = container

        fl = QVBoxLayout(container)
        fl.setContentsMargins(20, 18, 20, 18)
        fl.setSpacing(16)

        # ── Light themes row ──────────────────────────────────────────────────
        fl.addWidget(self._theme_group_label("☀️  Light Themes"))
        light_row = QHBoxLayout(); light_row.setSpacing(12); light_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        fl.addLayout(light_row)

        # ── Dark themes row ───────────────────────────────────────────────────
        fl.addWidget(self._theme_group_label("🌙  Dark Themes"))
        dark_row = QHBoxLayout(); dark_row.setSpacing(12); dark_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        fl.addLayout(dark_row)

        # Create cards and place into correct row
        self._theme_cards = {}
        self._btn_group   = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        active = ThemeManager.current_name()

        for info in ThemeManager.available_themes():
            card = ThemeCard(info, is_active=(info["name"] == active))
            card.selected.connect(self._on_card_clicked)
            self._btn_group.addButton(card)
            self._theme_cards[info["name"]] = card

            # Cell: card + labels
            cell_w = QWidget(); cell_w.setStyleSheet("background: transparent;")
            cell   = QVBoxLayout(cell_w); cell.setSpacing(3); cell.setContentsMargins(0,0,0,0)
            cell.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)

            n_lbl = QLabel(f"{info.get('emoji','🎨')} {info['name']}")
            n_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n_lbl.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=600))
            cell.addWidget(n_lbl)

            row = light_row if not info["is_dark"] else dark_row
            row.addWidget(cell_w)

        light_row.addStretch()
        dark_row.addStretch()

        # ── Description bar ───────────────────────────────────────────────────
        desc_bar = QFrame(); desc_bar.setObjectName("ThemeDescBar")
        desc_bar.setStyleSheet(self._desc_bar_style())
        self._desc_bar = desc_bar

        dl = QHBoxLayout(desc_bar); dl.setContentsMargins(14, 8, 14, 8); dl.setSpacing(10)
        self._theme_name_lbl = QLabel("")
        self._theme_name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        dl.addWidget(self._theme_name_lbl)

        self._theme_mode_badge = QLabel("")
        self._theme_mode_badge.setFixedHeight(22)
        dl.addWidget(self._theme_mode_badge)

        self._theme_desc_lbl = QLabel("")
        dl.addWidget(self._theme_desc_lbl)
        dl.addStretch()

        fl.addWidget(desc_bar)
        self._update_desc(active)
        vl.addWidget(container)
        return outer

    def _theme_group_label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_SECONDARY, size=12, weight=700) +
            f" background: {Theme.SURFACE_ALT}; border-radius: 6px; padding: 4px 10px;"
        )
        return l

    def _cards_container_style(self) -> str:
        return f"""
            QFrame#ThemeContainer {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 14px;
            }}
        """

    def _desc_bar_style(self) -> str:
        return f"""
            QFrame#ThemeDescBar {{
                background-color: {Theme.SURFACE_ALT};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """

    def _update_desc(self, name: str):
        themes = {t["name"]: t for t in ThemeManager.available_themes()}
        info   = themes.get(name, {})
        if self._theme_name_lbl:
            self._theme_name_lbl.setText(f"{info.get('emoji','🎨')}  {name}")
            self._theme_name_lbl.setStyleSheet(
                Theme.text_style(color=Theme.PRIMARY, size=12, weight=700))
        if self._theme_desc_lbl:
            self._theme_desc_lbl.setText(info.get("description", ""))
            self._theme_desc_lbl.setStyleSheet(Theme.muted_style(12))
        if self._theme_mode_badge:
            mode = "🌙 Dark" if info.get("is_dark") else "☀️ Light"
            self._theme_mode_badge.setText(mode)
            self._theme_mode_badge.setStyleSheet(
                Theme.badge_style(Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK,
                                  radius=8, padding="3px 12px", size=11))

    def _on_card_clicked(self, name: str):
        """Apply theme immediately — no popup, no restart, fully live."""
        ThemeManager.apply(name)   # → triggers _on_theme_changed via listener

    def _on_theme_changed(self, name: str):
        """Called by ThemeManager after every switch — restyle inline widgets."""
        # Update card states
        for n, card in self._theme_cards.items():
            card.set_active(n == name)

        # Restyle inline-built widgets
        if self._hdr_frame:
            self._hdr_frame.setStyleSheet(self._hdr_style())
        if self._cards_container:
            self._cards_container.setStyleSheet(self._cards_container_style())
        if self._desc_bar:
            self._desc_bar.setStyleSheet(self._desc_bar_style())

        self._update_desc(name)
        self._refresh_badges()

        # Flash the badge briefly to confirm
        if self.badge_theme_lbl:
            self.badge_theme_lbl.setText(f"✅ {name}")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, self._refresh_badges)

    # ── Sections ──────────────────────────────────────────────────────────────

    def _section_security(self) -> QGroupBox:
        g = self._group("🔐  Security"); gl = QVBoxLayout(g); gl.setSpacing(10)

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
        self.totp_checkbox.setAccessibleName("Two-factor authentication toggle")
        self.totp_checkbox.setAccessibleDescription("Enable or disable TOTP-based two-factor authentication.")
        l2.addWidget(self.totp_checkbox)
        l2.addWidget(self._muted("Required at every login when enabled."))
        gl.addWidget(c2)
        return g

    def _section_data(self) -> QGroupBox:
        g = self._group("🗂  Data Management"); gl = QVBoxLayout(g); gl.setSpacing(10)
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
        g = self._group("🕵️  Privacy"); gl = QVBoxLayout(g)
        c = self._card(); lc = QVBoxLayout(c)
        lc.addWidget(self._card_title("Privacy Mode"))
        self.privacy_checkbox = QCheckBox("Mask all financial amounts  (₹ ****)")
        self.privacy_checkbox.setChecked(session.privacy_mode)
        self.privacy_checkbox.stateChanged.connect(self._on_privacy_toggle)
        self.privacy_checkbox.setAccessibleName("Privacy mode toggle")
        self.privacy_checkbox.setAccessibleDescription("Mask financial amounts across the app.")
        lc.addWidget(self.privacy_checkbox)
        lc.addWidget(self._muted("Toggle any time. All screens reflect immediately."))
        gl.addWidget(c)
        return g

    def _section_backup(self) -> QGroupBox:
        g = self._group("💾  Backup & Restore"); gl = QVBoxLayout(g); gl.setSpacing(10)
        # Create backup card
        c1 = self._card(); l1 = QVBoxLayout(c1)
        l1.addWidget(self._card_title("Create Backup"))
        l1.addWidget(self._muted("Copies database to the backups folder."))
        b1 = Theme.btn("💾  Create Backup", "success", height=36, min_width=155)
        b1.clicked.connect(self._on_create_backup)
        l1.addWidget(b1)
        gl.addWidget(c1)

        # Scheduled backups card
        c_sched = self._card(); ls = QVBoxLayout(c_sched)
        ls.addWidget(self._card_title("Scheduled Backups"))
        self.sched_checkbox = QCheckBox("Enable scheduled backups")
        from core.settings import get_setting
        enabled = bool(get_setting("scheduled_backups_enabled", True))
        self.sched_checkbox.setChecked(enabled)
        self.sched_checkbox.stateChanged.connect(self._on_scheduled_backup_toggle)
        self.sched_checkbox.setAccessibleName("Scheduled backups toggle")
        self.sched_checkbox.setAccessibleDescription("Enable or disable automatic periodic backups.")
        ls.addWidget(self.sched_checkbox)
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["6 hours", "12 hours", "24 hours", "48 hours"])
        self.interval_combo.setFixedWidth(140)
        self.interval_combo.setAccessibleName("Backup interval")
        self.interval_combo.setAccessibleDescription("Choose how often automatic backups run.")
        self.interval_combo.setToolTip("Choose how often automatic backups run.")
        # Map stored interval to index
        interval_hours = int(get_setting("scheduled_backups_interval_hours", 24))
        idx_map = {6:0, 12:1, 24:2, 48:3}
        self.interval_combo.setCurrentIndex(idx_map.get(interval_hours, 2))
        self.interval_combo.currentIndexChanged.connect(self._on_backup_interval_changed)
        h = QHBoxLayout(); h.addWidget(self.interval_combo); h.addStretch()
        ls.addLayout(h)
        ls.addWidget(self._muted("Automatic backups run in the background and are stored in the backups folder."))
        gl.addWidget(c_sched)

        # Restore card
        c2 = self._card(); l2 = QVBoxLayout(c2)
        l2.addWidget(self._card_title("Restore from Backup"))
        w = QLabel("⚠  Replaces your current database — all data will be lost!")
        w.setStyleSheet(Theme.text_style(color=Theme.WARNING_DARK, size=12, weight=600))
        l2.addWidget(w)
        b2 = Theme.btn("🔄  Restore Backup", "danger", height=36, min_width=155)
        b2.clicked.connect(self._on_restore_backup)
        b2.setAccessibleName("Restore backup")
        b2.setAccessibleDescription("Restore the database from a selected backup file.")
        b2.setToolTip("Restore the database from a selected backup file.")
        l2.addWidget(b2)
        gl.addWidget(c2)

        # Onboarding controls (show now / enable on startup)
        c_onb = self._card(); lo = QVBoxLayout(c_onb)
        lo.addWidget(self._card_title("Onboarding"))
        self.onb_startup_chk = QCheckBox("Show onboarding on first launch / after updates")
        self.onb_startup_chk.setChecked(bool(get_setting("show_onboarding_on_startup", True)))
        self.onb_startup_chk.stateChanged.connect(self._on_onboarding_toggle)
        self.onb_startup_chk.setAccessibleName("Onboarding on startup toggle")
        self.onb_startup_chk.setAccessibleDescription("Show onboarding when the app starts or after updates.")
        lo.addWidget(self.onb_startup_chk)
        btn_show = Theme.btn("Show Onboarding Now", "primary", height=36, min_width=160)
        btn_show.clicked.connect(self._on_show_onboarding_now)
        btn_show.setAccessibleName("Show onboarding now")
        btn_show.setAccessibleDescription("Open the onboarding walkthrough immediately.")
        btn_show.setToolTip("Open the onboarding walkthrough immediately.")
        lo.addWidget(btn_show)
        gl.addWidget(c_onb)

        # Manage Backups card (list existing backups + actions)
        c_manage = self._card(); lm = QVBoxLayout(c_manage)
        lm.addWidget(self._card_title("Manage Backups"))
        self.backup_list = QListWidget()
        self.backup_list.setMinimumHeight(140)
        self.backup_list.setAccessibleName("Backup list")
        self.backup_list.setAccessibleDescription("List of saved database backups.")
        self.backup_list.setToolTip("List of saved database backups.")
        lm.addWidget(self.backup_list)
        btn_row = QHBoxLayout()
        btn_refresh = Theme.btn("Refresh", "secondary", height=32, min_width=90)
        btn_refresh.clicked.connect(self._on_refresh_backups)
        btn_refresh.setAccessibleName("Refresh backups list")
        btn_refresh.setAccessibleDescription("Reload the list of available backups.")
        btn_open = Theme.btn("Open Folder", "secondary", height=32, min_width=110)
        btn_open.clicked.connect(self._on_open_backups_folder)
        btn_open.setAccessibleName("Open backups folder")
        btn_open.setAccessibleDescription("Open the folder containing backup files.")
        btn_delete = Theme.btn("Delete Selected", "danger", height=32, min_width=120)
        btn_delete.clicked.connect(self._on_delete_backup)
        btn_delete.setAccessibleName("Delete selected backup")
        btn_delete.setAccessibleDescription("Delete the selected backup file.")
        btn_row.addWidget(btn_refresh)
        btn_row.addWidget(btn_open)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        lm.addLayout(btn_row)
        lm.addWidget(self._muted("Select a backup and choose an action. Restoring will also appear above."))
        gl.addWidget(c_manage)
        return g

    def _section_device(self) -> QGroupBox:
        g = self._group("💻  Device Information"); gl = QVBoxLayout(g)
        c = self._card(); fl = QFormLayout(c)
        fl.setSpacing(8)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info = _device_info()
        dev = QLabel(info["device_id"][:34] + "…")
        dev.setStyleSheet(
            Theme.text_style(color=Theme.TEXT_PRIMARY, size=11) +
            " font-family: 'Consolas','Courier New',monospace; background:transparent;")
        dev.setAccessibleName("Device identifier")
        fl.addRow(self._form_lbl("Device ID"), dev)
        platform_lbl = QLabel(info["platform"][:60])
        platform_lbl.setAccessibleName("Platform")
        hostname_lbl = QLabel(info.get("hostname", "—"))
        hostname_lbl.setAccessibleName("Hostname")
        fl.addRow(self._form_lbl("Platform"),  platform_lbl)
        fl.addRow(self._form_lbl("Hostname"),  hostname_lbl)
        fl.addRow("", self._muted("This app is cryptographically bound to this device."))
        gl.addWidget(c)
        return g

    # ── Widget factories ──────────────────────────────────────────────────────

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
        f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return f

    def _card_title(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        l.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=700))
        return l

    def _muted(self, text: str) -> QLabel:
        l = QLabel(text); l.setStyleSheet(Theme.muted_style(11)); return l

    def _pwd_field(self, placeholder: str) -> QLineEdit:
        e = QLineEdit()
        e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(36)
        e.setAccessibleName(placeholder)
        e.setAccessibleDescription(f"Enter the {placeholder.lower()}.")
        e.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return e

    def _form_lbl(self, text: str) -> QLabel:
        l = QLabel(f"{text}:"); l.setStyleSheet(Theme.section_label_style(12)); return l

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_change_password(self):
        cur, new, conf = (self.current_pwd.text(),
                          self.new_pwd.text(), self.confirm_pwd.text())
        if not all([cur, new, conf]):
            QMessageBox.warning(self, "Missing", "Please fill all password fields."); return
        if new != conf:
            QMessageBox.warning(self, "Mismatch", "New passwords do not match."); return
        if len(new) < 8:
            QMessageBox.warning(self, "Too Short", "Password must be at least 8 characters."); return
        ok, msg = change_password(cur, new)
        if ok:
            QMessageBox.information(self, "Success", "Password changed successfully!")
            for f in [self.current_pwd, self.new_pwd, self.confirm_pwd]:
                f.clear()
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
            if self.parent_window:
                self.parent_window.refresh_overview()
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

    def _on_scheduled_backup_toggle(self, state):
        enabled = bool(state)
        try:
            from core.settings import set_setting
            set_setting("scheduled_backups_enabled", enabled)
            from core.backup_manager import schedule_periodic_backups, stop_scheduler
            if enabled:
                # read interval
                idx = self.interval_combo.currentIndex()
                hours = [6, 12, 24, 48][idx]
                schedule_periodic_backups(interval_hours=hours)
            else:
                stop_scheduler()
            QMessageBox.information(self, "Saved", "Scheduled backup preference saved.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_backup_interval_changed(self, idx: int):
        hours = [6, 12, 24, 48][idx]
        try:
            from core.settings import set_setting
            set_setting("scheduled_backups_interval_hours", hours)
            from core.backup_manager import schedule_periodic_backups, stop_scheduler
            if self.sched_checkbox.isChecked():
                # restart scheduler with new interval
                schedule_periodic_backups(interval_hours=hours)
            QMessageBox.information(self, "Saved", f"Backup interval set to {hours} hours.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_onboarding_toggle(self, state):
        enabled = bool(state)
        try:
            from core.settings import set_setting
            set_setting("show_onboarding_on_startup", enabled)
            QMessageBox.information(self, "Saved", "Onboarding preference saved.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_show_onboarding_now(self):
        try:
            from ui.onboarding import OnboardingDialog
            dlg = OnboardingDialog(self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_restore_backup(self):
        reply = QMessageBox.warning(
            self, "Confirm Restore",
            "WARNING: This will REPLACE your current database.\nAll data will be lost!\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        # If user selected a file in the backup list, prefer that
        path = None
        try:
            if hasattr(self, 'backup_list') and self.backup_list.currentItem():
                sel = self.backup_list.currentItem().text()
                cand = os.path.join(BACKUP_DIR, sel)
                if os.path.exists(cand):
                    path = cand
        except Exception:
            path = None
        if not path:
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

    def _on_refresh_backups(self):
        try:
            files = []
            if os.path.exists(BACKUP_DIR):
                for fn in os.listdir(BACKUP_DIR):
                    if fn.lower().endswith('.db'):
                        files.append(fn)
            # sort by name (timestamp prefix) desc
            files.sort(reverse=True)
            self.backup_list.clear()
            for f in files:
                self.backup_list.addItem(f)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_delete_backup(self):
        try:
            item = self.backup_list.currentItem()
            if not item:
                QMessageBox.warning(self, "No Selection", "Please select a backup to delete.")
                return
            fn = item.text()
            path = os.path.join(BACKUP_DIR, fn)
            reply = QMessageBox.warning(
                self, "Confirm Delete",
                f"Delete backup '{fn}'? This cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            os.remove(path)
            QMessageBox.information(self, "Deleted", f"Deleted: {fn}")
            self._on_refresh_backups()
        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", str(e))

    def _on_open_backups_folder(self):
        try:
            import subprocess, sys
            folder = os.path.abspath(BACKUP_DIR)
            if sys.platform.startswith('win'):
                subprocess.Popen(['explorer', folder])
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

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

    # ── Refresh (called by dashboard on nav) ──────────────────────────────────

    def refresh(self):
        self.totp_checkbox.setChecked(is_totp_enabled())
        priv = get_privacy_mode()
        session.set_privacy_mode(priv)
        self.privacy_checkbox.setChecked(priv)
        active = ThemeManager.current_name()
        for name, card in self._theme_cards.items():
            card.set_active(name == active)
        self._update_desc(active)
        self._refresh_badges()
        # Ensure backup scheduler state matches settings
        try:
            from core.settings import get_setting
            from core.backup_manager import schedule_periodic_backups, stop_scheduler, is_scheduler_running
            enabled = bool(get_setting("scheduled_backups_enabled", True))
            self.sched_checkbox.setChecked(enabled)
            interval = int(get_setting("scheduled_backups_interval_hours", 24))
            idx_map = {6:0, 12:1, 24:2, 48:3}
            self.interval_combo.setCurrentIndex(idx_map.get(interval, 2))
            if enabled and not is_scheduler_running():
                schedule_periodic_backups(interval_hours=interval)
            if not enabled and is_scheduler_running():
                stop_scheduler()
            # Onboarding checkbox
            from core.settings import get_setting as _gs
            self.onb_startup_chk.setChecked(bool(_gs("show_onboarding_on_startup", True)))
            # Refresh backup list
            try:
                if hasattr(self, 'backup_list'):
                    self._on_refresh_backups()
            except Exception:
                pass
        except Exception:
            pass
