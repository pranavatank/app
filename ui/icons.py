"""
ui/icons.py — Unified icon registry.

PRIMARY  : qtawesome mdi6 Material Design icon font.
FALLBACK : plain-text Unicode emoji when qtawesome is unavailable.

Registry tuple format: (mdi6_name,  hex_color,  emoji)

Usage:
    from ui.icons import icon, pixmap, set_btn_icon, icon_label, tab_icon
"""
from __future__ import annotations

import os
import tempfile

from PyQt6.QtGui     import QIcon, QPixmap, QColor
from PyQt6.QtWidgets import QLabel, QPushButton
from PyQt6.QtCore    import QSize

# -- Library availability ------------------------------------------------------
try:
    import qtawesome as qta
    _QTA_OK = True
except ImportError:
    _QTA_OK = False


# -- Registry --------------------------------------------------------------------
# Tuple format: (mdi6_name,  hex_color,  emoji)
#
# - mdi6_name : qtawesome name
# - hex_color : colour to apply to icon ('auto' reads this)
# - emoji     : plain-text fallback when qtawesome is unavailable
_R: dict[str, tuple] = {

    # -- Sidebar / nav -----------------------------------------------------------
    "overview":         ("mdi6.view-dashboard",         "#60A5FA", "\U0001F3E0"),
    "accounts":         ("mdi6.bank",                   "#34D399", "\U0001F3DB"),
    "transactions":     ("mdi6.swap-horizontal-bold",   "#A78BFA", "\U0001F4B8"),
    "income":           ("mdi6.cash-multiple",          "#4ADE80", "\U0001F4B0"),
    "fixed_deposits":   ("mdi6.piggy-bank",             "#FBBF24", "\U0001F3E6"),
    "statement_import": ("mdi6.file-import",            "#38BDF8", "\U0001F4C4"),
    "ais_tis":          ("mdi6.file-document-multiple", "#818CF8", "\U0001F4D1"),
    "tax":              ("mdi6.calculator-variant",     "#FB923C", "\U0001F4CB"),
    "reconciliation":   ("mdi6.scale-balance",          "#E879F9", "⚖"),
    "reports":          ("mdi6.chart-areaspline",       "#22D3EE", "\U0001F4CA"),
    "settings":         ("mdi6.cog-outline",            "#94A3B8", "⚙"),

    # -- CRUD actions --------------------------------------------------------------
    "add":              ("mdi6.plus-circle",            "#4ADE80", "➕"),
    "edit":             ("mdi6.pencil",                 "#60A5FA", "✏"),
    "delete":           ("mdi6.trash-can",              "#F87171", "\U0001F5D1"),
    "save":             ("mdi6.content-save",           "#34D399", "\U0001F4BE"),
    "refresh":          ("mdi6.refresh",                "#38BDF8", "\U0001F504"),
    "link":             ("mdi6.link-variant",           "#818CF8", "\U0001F517"),
    "unlink":           ("mdi6.link-variant-off",       "#F87171", "\U0001F517"),
    "auto_link":        ("mdi6.flash",                  "#FBBF24", "⚡"),
    "recalculate":      ("mdi6.calculator",             "#A78BFA", "\U0001F522"),
    "import":           ("mdi6.file-upload",            "#38BDF8", "\U0001F4C2"),
    "import_pdf":       ("mdi6.file-pdf-box",           "#F87171", "\U0001F4C4"),
    "import_json":      ("mdi6.code-json",              "#FBBF24", "\U0001F4E4"),
    "backup":           ("mdi6.database-export",        "#34D399", "\U0001F4BE"),
    "restore":          ("mdi6.database-import",        "#FB923C", "\U0001F504"),
    "logout":           ("mdi6.logout",                 "#F87171", "\U0001F6AA"),
    "filter":           ("mdi6.filter-variant",         "#A78BFA", "\U0001F50D"),
    "search":           ("mdi6.magnify",                "#60A5FA", "\U0001F50D"),
    "close":            ("mdi6.close-circle",           "#F87171", "✕"),
    "check":            ("mdi6.check-bold",             "#4ADE80", "✓"),
    "browse":           ("mdi6.folder-open",            "#FBBF24", "\U0001F4C2"),
    "copy":             ("mdi6.content-copy",           "#60A5FA", "\U0001F4CB"),
    "export":           ("mdi6.file-export",            "#34D399", "\U0001F4E4"),
    "bulk_edit":        ("mdi6.table-edit",             "#60A5FA", "\U0001F9E9"),
    "shift_dates":      ("mdi6.calendar-arrow-right",   "#A78BFA", "\U0001F5D3"),
    "split":            ("mdi6.scissors-cutting",       "#FB923C", "✂"),
    "merge":            ("mdi6.merge",                  "#34D399", "\U0001F500"),
    "debug":            ("mdi6.bug",                    "#F87171", "\U0001F41E"),
    "sidebar_expand":   ("mdi6.chevron-right",          "#94A3B8", "▶"),
    "sidebar_collapse": ("mdi6.chevron-left",           "#94A3B8", "◀"),
    "list_view":        ("mdi6.view-list",              "#60A5FA", "\U0001F4CB"),
    "card_view":        ("mdi6.view-grid",              "#A78BFA", "\U0001FA9F"),
    "calculate":        ("mdi6.lightning-bolt",         "#FBBF24", "⚡"),
    "select_all":       ("mdi6.checkbox-multiple-marked","#4ADE80","✓"),
    "clear_sel":        ("mdi6.checkbox-multiple-blank-outline","#94A3B8","✗"),
    "show":             ("mdi6.chevron-down",           "#60A5FA", "▼"),
    "hide":             ("mdi6.chevron-up",             "#60A5FA", "▲"),
    "reconcile":        ("mdi6.compare",                "#E879F9", "\U0001F504"),

    # -- Auth / security -------------------------------------------------------------
    "lock":             ("mdi6.lock",                   "#FBBF24", "\U0001F512"),
    "unlock":           ("mdi6.lock-open-variant",      "#4ADE80", "\U0001F513"),
    "key":              ("mdi6.key-variant",            "#FBBF24", "\U0001F511"),
    "password":         ("mdi6.form-textbox-password",  "#94A3B8", "\U0001F510"),
    "two_fa":           ("mdi6.shield-check",           "#4ADE80", "\U0001F6E1"),
    "privacy":          ("mdi6.eye-off",                "#94A3B8", "\U0001F441"),
    "privacy_active":   ("mdi6.eye-lock",               "#FBBF24", "\U0001F512"),
    "device":           ("mdi6.laptop",                 "#60A5FA", "\U0001F4BB"),
    "create_account":   ("mdi6.account-plus",           "#4ADE80", "✅"),

    # -- Status / feedback -------------------------------------------------------------
    "warning":          ("mdi6.alert",                  "#FBBF24", "⚠"),
    "info_circle":      ("mdi6.information",            "#60A5FA", "ℹ"),
    "success_badge":    ("mdi6.check-decagram",         "#4ADE80", "✅"),
    "error_badge":      ("mdi6.close-octagon",          "#F87171", "❌"),
    "trophy":           ("mdi6.trophy",                 "#FBBF24", "\U0001F3C6"),
    "tip":              ("mdi6.lightbulb-on",           "#FBBF24", "\U0001F4A1"),
    "notification":     ("mdi6.bell-ring",              "#FBBF24", "\U0001F514"),
    "overdue":          ("mdi6.alarm",                  "#F87171", "⏰"),

    # -- Theme / appearance -------------------------------------------------------------
    "theme":            ("mdi6.palette",                "#A78BFA", "\U0001F3A8"),
    "light_theme":      ("mdi6.white-balance-sunny",    "#FBBF24", "☀"),
    "dark_theme":       ("mdi6.weather-night",          "#818CF8", "\U0001F319"),
    "live":             ("mdi6.circle",                 "#4ADE80", "\U0001F7E2"),

    # -- Domain -------------------------------------------------------------------------
    "bank":             ("mdi6.bank",                   "#34D399", "\U0001F3E6"),
    "person":           ("mdi6.account",                "#60A5FA", "\U0001F464"),
    "persons":          ("mdi6.account-group",          "#60A5FA", "\U0001F465"),
    "calendar":         ("mdi6.calendar-month",         "#60A5FA", "\U0001F4C5"),
    "chart_line":       ("mdi6.chart-line",             "#4ADE80", "\U0001F4C8"),
    "chart_pie":        ("mdi6.chart-donut",            "#A78BFA", "\U0001F967"),
    "chart_overview":   ("mdi6.chart-bar",              "#22D3EE", "\U0001F4CA"),
    "monthly":          ("mdi6.calendar-multiselect",   "#60A5FA", "\U0001F4C5"),
    "trend":            ("mdi6.trending-up",            "#4ADE80", "\U0001F4C8"),
    "interest":         ("mdi6.percent",                "#4ADE80", "\U0001F4B9"),
    "income_src":       ("mdi6.cash-register",          "#FBBF24", "\U0001F4B0"),
    "debit_card":       ("mdi6.credit-card",            "#60A5FA", "\U0001F4B3"),
    "briefcase":        ("mdi6.briefcase",              "#94A3B8", "\U0001F4BC"),
    "house":            ("mdi6.home-city",              "#60A5FA", "\U0001F3E0"),
    "building":         ("mdi6.office-building",        "#94A3B8", "\U0001F3E2"),
    "no_data":          ("mdi6.inbox-arrow-down",       "#94A3B8", "\U0001F4ED"),
    "phone":            ("mdi6.phone",                  "#94A3B8", "\U0001F4DE"),
    "basic_info":       ("mdi6.information-outline",    "#60A5FA", "\U0001F4CB"),
    "bank_details":     ("mdi6.bank-outline",           "#34D399", "\U0001F3E6"),
    "contact":          ("mdi6.card-account-phone",     "#94A3B8", "\U0001F4DE"),
    "account_found":    ("mdi6.card-account-details",   "#60A5FA", "\U0001F4C4"),
    "manage":           ("mdi6.cog-transfer",           "#60A5FA", "\U0001F465"),

    # -- Chat / AI assistant ------------------------------------------------------------
    "send":             ("mdi6.send",                   "#FFFFFF", "➤"),
    "attach":           ("mdi6.paperclip",              "#94A3B8", "\U0001F4CE"),
    "bot":              ("mdi6.robot-happy-outline",    "#A78BFA", "\U0001F916"),
}


# -- Render helpers --------------------------------------------------------------------

def _qta_icon(mdi6_name: str, color_hex: str | None, size: int) -> QIcon:
    """Render a qtawesome mdi6 icon."""
    if not _QTA_OK or not mdi6_name:
        return QIcon()
    opts: dict = {"scale_factor": max(size / 16, 1.0)}
    if color_hex:
        opts["color"] = color_hex
    try:
        return qta.icon(mdi6_name, **opts)
    except Exception as e:
        print(f"[icons] qtawesome render failed for '{mdi6_name}': {e}")
        return QIcon()


# -- Public API --------------------------------------------------------------------

def icon(name: str, color: str | None = "auto", size: int = 16) -> QIcon:
    """
    Return a QIcon for the given registry key.

      color='auto'  -> registry default colour  (colourful - for sidebar/labels)
      color='#hex'  -> override colour           (e.g. '#FFFFFF' on coloured buttons)
      color=None    -> no colour hint
    """
    entry = _R.get(name)
    if not entry:
        return QIcon()
    mdi6, default_color, _ = entry
    resolved = default_color if color == "auto" else color

    # qtawesome mdi6 - Material Design icon font
    if _QTA_OK and mdi6:
        ic = _qta_icon(mdi6, resolved, size)
        if not ic.isNull():
            return ic

    return QIcon()


def pixmap(name: str, size: int = 16, color: str | None = "auto") -> QPixmap:
    """Return a QPixmap for the given registry key."""
    ic = icon(name, color=color, size=size)
    return ic.pixmap(size, size) if not ic.isNull() else QPixmap()


def fallback(name: str) -> str:
    """Return the emoji fallback string."""
    entry = _R.get(name)
    return entry[2] if entry else ""


# -- QSS image: url() support ------------------------------------------------
# Qt Style Sheets can't embed a QPixmap/QIcon directly (`image: url(...)`
# needs a real file path or Qt resource) — this renders a registry icon to a
# small cached PNG on disk (OS temp dir) so global QSS
# (combobox/spinbox/date-edit arrows)
# can reference a real icon instead of the old CSS zero-size-box border
# triangle, which renders as an unstyled little rectangle in this app's Qt6
# build rather than an actual arrow shape.
_icon_cache_dir: str | None = None


def _icon_cache_dir_path() -> str:
    global _icon_cache_dir
    if _icon_cache_dir is None:
        _icon_cache_dir = os.path.join(tempfile.gettempdir(), "FinancialApp", "icon_cache")
        os.makedirs(_icon_cache_dir, exist_ok=True)
    return _icon_cache_dir


def icon_file(name: str, color: str, size: int = 16) -> str:
    """
    Render a registry icon to a cached PNG and return its path (forward
    slashes, safe for direct use inside a QSS `url(...)`). Cached by
    (name, color, size) — a new theme's colors just add new cache files,
    nothing to invalidate.
    """
    safe_color = (color or "").lstrip("#").upper() or "AUTO"
    path = os.path.join(_icon_cache_dir_path(), f"{name}_{safe_color}_{size}.png")
    if not os.path.exists(path):
        pm = pixmap(name, size=size, color=color)
        if not pm.isNull():
            pm.save(path, "PNG")
    return path.replace("\\", "/") if os.path.exists(path) else ""


def is_available() -> bool:
    """True when qtawesome is usable."""
    return _QTA_OK


def icon_label(name: str, size: int = 18, color: str | None = "auto") -> QLabel:
    """Return a QLabel showing the icon pixmap, or emoji text as last resort."""
    lbl = QLabel()
    lbl.setStyleSheet("background: transparent;")
    if is_available():
        pm = pixmap(name, size=size, color=color)
        if not pm.isNull():
            lbl.setPixmap(pm)
            return lbl
    lbl.setText(fallback(name))
    return lbl


def set_btn_icon(btn: QPushButton, name: str, size: int = 15,
                 color: str | None = "#FFFFFF") -> None:
    """
    Attach an icon to a button.
    Defaults to white - correct for coloured (primary/danger/success...) buttons.
    Pass color='auto' for the registry's colourful default on outline/ghost buttons.
    """
    if is_available():
        ic = icon(name, color=color, size=size)
        if not ic.isNull():
            btn.setIcon(ic)
            btn.setIconSize(QSize(size, size))


def set_btn_icon_auto(btn: QPushButton, name: str, size: int = 15) -> None:
    """Set icon using the registry colour - for secondary/outline buttons."""
    set_btn_icon(btn, name, size=size, color="auto")


def tab_icon(name: str) -> QIcon:
    """Icon for QTabWidget tabs (16 px, auto colour)."""
    return icon(name, color="auto", size=16)
