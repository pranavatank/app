"""
ui/icons.py — Unified icon registry.

PRIMARY  : PyQt6-Fluent-Widgets (qfluentwidgets) FluentIcon SVG icons.
           Uses FluentIconBase.icon(theme, color) directly — qfluentwidgets
           already handles SVG recolouring internally via writeSvg(), so we
           don't need to rasterise manually.
FALLBACK : qtawesome mdi6 Material Design icon font.
EMOJI    : plain-text Unicode fallback when no library is available.

Registry tuple format: (fluent_icon | None,  mdi6_name,  hex_color,  emoji)

Usage:
    from ui.icons import icon, pixmap, set_btn_icon, icon_label, tab_icon
"""
from __future__ import annotations

from PyQt6.QtGui     import QIcon, QPixmap, QColor
from PyQt6.QtWidgets import QLabel, QPushButton
from PyQt6.QtCore    import QSize

# -- Library availability ------------------------------------------------------
try:
    from qfluentwidgets import FluentIcon as _FI
    from qfluentwidgets.common.config import Theme as _FTheme
    _FLUENT_OK = True
except Exception:
    _FLUENT_OK = False

try:
    import qtawesome as qta
    _QTA_OK = True
except ImportError:
    _QTA_OK = False


def _fi(member):
    """Return a FluentIcon member only when the library loaded successfully."""
    return member if _FLUENT_OK else None


# -- Registry --------------------------------------------------------------------
# Tuple format: (fluent_icon | None,  mdi6_name,  hex_color,  emoji)
#
# - fluent_icon : _FI.MEMBER -> rendered via FluentIconBase.icon(color=...)
# - mdi6_name   : qtawesome name -> used when fluent_icon is None or fails
# - hex_color   : colour applied to both renders ('auto' reads this)
# - emoji       : last-resort plain-text fallback
_R: dict[str, tuple] = {

    # -- Sidebar / nav -----------------------------------------------------------
    "overview":         (_fi(_FI.HOME)           if _FLUENT_OK else None, "mdi6.view-dashboard",         "#60A5FA", "\U0001F3E0"),
    "accounts":         (None,                                             "mdi6.bank",                   "#34D399", "\U0001F3DB"),
    "transactions":     (_fi(_FI.SYNC)           if _FLUENT_OK else None, "mdi6.swap-horizontal-bold",   "#A78BFA", "\U0001F4B8"),
    "income":           (_fi(_FI.MARKET)         if _FLUENT_OK else None, "mdi6.cash-multiple",          "#4ADE80", "\U0001F4B0"),
    "fixed_deposits":   (None,                                             "mdi6.piggy-bank",             "#FBBF24", "\U0001F3E6"),
    "statement_import": (_fi(_FI.DOWNLOAD)       if _FLUENT_OK else None, "mdi6.file-import",            "#38BDF8", "\U0001F4C4"),
    "ais_tis":          (_fi(_FI.DOCUMENT)       if _FLUENT_OK else None, "mdi6.file-document-multiple", "#818CF8", "\U0001F4D1"),
    "tax":              (_fi(_FI.CERTIFICATE)    if _FLUENT_OK else None, "mdi6.calculator-variant",     "#FB923C", "\U0001F4CB"),
    "reconciliation":   (_fi(_FI.COMPLETED)      if _FLUENT_OK else None, "mdi6.scale-balance",          "#E879F9", "\u2696"),
    "reports":          (_fi(_FI.PIE_SINGLE)     if _FLUENT_OK else None, "mdi6.chart-areaspline",       "#22D3EE", "\U0001F4CA"),
    "settings":         (_fi(_FI.SETTING)        if _FLUENT_OK else None, "mdi6.cog-outline",            "#94A3B8", "\u2699"),

    # -- CRUD actions --------------------------------------------------------------
    "add":              (_fi(_FI.ADD)            if _FLUENT_OK else None, "mdi6.plus-circle",            "#4ADE80", "\u2795"),
    "edit":             (_fi(_FI.EDIT)           if _FLUENT_OK else None, "mdi6.pencil",                 "#60A5FA", "\u270F"),
    "delete":           (_fi(_FI.DELETE)         if _FLUENT_OK else None, "mdi6.trash-can",              "#F87171", "\U0001F5D1"),
    "save":             (_fi(_FI.SAVE)           if _FLUENT_OK else None, "mdi6.content-save",           "#34D399", "\U0001F4BE"),
    "refresh":          (_fi(_FI.SYNC)           if _FLUENT_OK else None, "mdi6.refresh",                "#38BDF8", "\U0001F504"),
    "link":             (_fi(_FI.LINK)           if _FLUENT_OK else None, "mdi6.link-variant",           "#818CF8", "\U0001F517"),
    "unlink":           (_fi(_FI.REMOVE)         if _FLUENT_OK else None, "mdi6.link-variant-off",       "#F87171", "\U0001F517"),
    "auto_link":        (_fi(_FI.ACCEPT)         if _FLUENT_OK else None, "mdi6.flash",                  "#FBBF24", "\u26A1"),
    "recalculate":      (_fi(_FI.UPDATE)         if _FLUENT_OK else None, "mdi6.calculator",             "#A78BFA", "\U0001F522"),
    "import":           (_fi(_FI.DOWNLOAD)       if _FLUENT_OK else None, "mdi6.file-upload",            "#38BDF8", "\U0001F4C2"),
    "import_pdf":       (_fi(_FI.DOCUMENT)       if _FLUENT_OK else None, "mdi6.file-pdf-box",           "#F87171", "\U0001F4C4"),
    "import_json":      (_fi(_FI.CODE)           if _FLUENT_OK else None, "mdi6.code-json",              "#FBBF24", "\U0001F4E4"),
    "backup":           (_fi(_FI.SAVE_AS)        if _FLUENT_OK else None, "mdi6.database-export",        "#34D399", "\U0001F4BE"),
    "restore":          (_fi(_FI.CLOUD_DOWNLOAD) if _FLUENT_OK else None, "mdi6.database-import",        "#FB923C", "\U0001F504"),
    "logout":           (None,                                             "mdi6.logout",                 "#F87171", "\U0001F6AA"),
    "filter":           (_fi(_FI.FILTER)         if _FLUENT_OK else None, "mdi6.filter-variant",         "#A78BFA", "\U0001F50D"),
    "search":           (_fi(_FI.SEARCH)         if _FLUENT_OK else None, "mdi6.magnify",                "#60A5FA", "\U0001F50D"),
    "close":            (_fi(_FI.CLOSE)          if _FLUENT_OK else None, "mdi6.close-circle",           "#F87171", "\u2715"),
    "check":            (_fi(_FI.ACCEPT)         if _FLUENT_OK else None, "mdi6.check-bold",             "#4ADE80", "\u2713"),
    "browse":           (_fi(_FI.FOLDER)         if _FLUENT_OK else None, "mdi6.folder-open",            "#FBBF24", "\U0001F4C2"),
    "copy":             (_fi(_FI.COPY)           if _FLUENT_OK else None, "mdi6.content-copy",           "#60A5FA", "\U0001F4CB"),
    "export":           (_fi(_FI.SHARE)          if _FLUENT_OK else None, "mdi6.file-export",            "#34D399", "\U0001F4E4"),
    "bulk_edit":        (_fi(_FI.EDIT)           if _FLUENT_OK else None, "mdi6.table-edit",             "#60A5FA", "\U0001F9E9"),
    "shift_dates":      (_fi(_FI.CALENDAR)       if _FLUENT_OK else None, "mdi6.calendar-arrow-right",   "#A78BFA", "\U0001F5D3"),
    "split":            (_fi(_FI.CUT)            if _FLUENT_OK else None, "mdi6.scissors-cutting",       "#FB923C", "\u2702"),
    "merge":            (_fi(_FI.ADD_TO)         if _FLUENT_OK else None, "mdi6.merge",                  "#34D399", "\U0001F500"),
    "debug":            (None,                                             "mdi6.bug",                    "#F87171", "\U0001F41E"),
    # Fluent slot intentionally None (not confident these FluentIcon members
    # exist) — falls straight through to the reliable qtawesome mdi6 set.
    "sidebar_expand":   (None,                                             "mdi6.chevron-right",          "#94A3B8", "▶"),
    "sidebar_collapse": (None,                                             "mdi6.chevron-left",           "#94A3B8", "◀"),
    "list_view":        (_fi(_FI.TILES)          if _FLUENT_OK else None, "mdi6.view-list",              "#60A5FA", "\U0001F4CB"),
    "card_view":        (_fi(_FI.VIEW)           if _FLUENT_OK else None, "mdi6.view-grid",              "#A78BFA", "\U0001FA9F"),
    "calculate":        (_fi(_FI.ASTERISK)       if _FLUENT_OK else None, "mdi6.lightning-bolt",         "#FBBF24", "\u26A1"),
    "select_all":       (_fi(_FI.COMPLETED)      if _FLUENT_OK else None, "mdi6.checkbox-multiple-marked","#4ADE80","\u2713"),
    "clear_sel":        (_fi(_FI.REMOVE_FROM)    if _FLUENT_OK else None, "mdi6.checkbox-multiple-blank-outline","#94A3B8","\u2717"),
    "show":             (_fi(_FI.ARROW_DOWN)     if _FLUENT_OK else None, "mdi6.chevron-down",           "#60A5FA", "\u25BC"),
    "hide":             (_fi(_FI.PAGE_LEFT)      if _FLUENT_OK else None, "mdi6.chevron-up",             "#60A5FA", "\u25B2"),
    "reconcile":        (_fi(_FI.COMPLETED)      if _FLUENT_OK else None, "mdi6.compare",                "#E879F9", "\U0001F504"),

    # -- Auth / security -------------------------------------------------------------
    "lock":             (_fi(_FI.FINGERPRINT)    if _FLUENT_OK else None, "mdi6.lock",                   "#FBBF24", "\U0001F512"),
    "unlock":           (_fi(_FI.FINGERPRINT)    if _FLUENT_OK else None, "mdi6.lock-open-variant",      "#4ADE80", "\U0001F513"),
    "key":              (None,                                             "mdi6.key-variant",            "#FBBF24", "\U0001F511"),
    "password":         (_fi(_FI.HIDE)           if _FLUENT_OK else None, "mdi6.form-textbox-password",  "#94A3B8", "\U0001F510"),
    "two_fa":           (_fi(_FI.CERTIFICATE)    if _FLUENT_OK else None, "mdi6.shield-check",           "#4ADE80", "\U0001F6E1"),
    "privacy":          (_fi(_FI.HIDE)           if _FLUENT_OK else None, "mdi6.eye-off",                "#94A3B8", "\U0001F441"),
    "privacy_active":   (_fi(_FI.VIEW)           if _FLUENT_OK else None, "mdi6.lock-eye",               "#FBBF24", "\U0001F512"),
    "device":           (_fi(_FI.APPLICATION)    if _FLUENT_OK else None, "mdi6.laptop",                 "#60A5FA", "\U0001F4BB"),
    "create_account":   (_fi(_FI.ACCEPT_MEDIUM)  if _FLUENT_OK else None, "mdi6.account-plus",           "#4ADE80", "\u2705"),

    # -- Status / feedback -------------------------------------------------------------
    "warning":          (_fi(_FI.ASTERISK)       if _FLUENT_OK else None, "mdi6.alert",                  "#FBBF24", "\u26A0"),
    "info_circle":      (_fi(_FI.INFO)           if _FLUENT_OK else None, "mdi6.information",            "#60A5FA", "\u2139"),
    "success_badge":    (_fi(_FI.COMPLETED)      if _FLUENT_OK else None, "mdi6.check-decagram",         "#4ADE80", "\u2705"),
    "error_badge":      (_fi(_FI.CANCEL)         if _FLUENT_OK else None, "mdi6.close-octagon",          "#F87171", "\u274C"),
    "trophy":           (_fi(_FI.CERTIFICATE)    if _FLUENT_OK else None, "mdi6.trophy",                 "#FBBF24", "\U0001F3C6"),
    "tip":              (_fi(_FI.MEGAPHONE)      if _FLUENT_OK else None, "mdi6.lightbulb-on",           "#FBBF24", "\U0001F4A1"),
    "notification":     (_fi(_FI.RINGER)         if _FLUENT_OK else None, "mdi6.bell-ring",              "#FBBF24", "\U0001F514"),
    "overdue":          (_fi(_FI.CANCEL_MEDIUM)  if _FLUENT_OK else None, "mdi6.alarm",                  "#F87171", "\u23F0"),

    # -- Theme / appearance -------------------------------------------------------------
    "theme":            (_fi(_FI.PALETTE)        if _FLUENT_OK else None, "mdi6.palette",                "#A78BFA", "\U0001F3A8"),
    "light_theme":      (_fi(_FI.BRIGHTNESS)     if _FLUENT_OK else None, "mdi6.white-balance-sunny",    "#FBBF24", "\u2600"),
    "dark_theme":       (_fi(_FI.CONSTRACT)      if _FLUENT_OK else None, "mdi6.weather-night",          "#818CF8", "\U0001F319"),
    "live":             (None,                                             "mdi6.circle",                 "#4ADE80", "\U0001F7E2"),

    # -- Domain -------------------------------------------------------------------------
    "bank":             (None,                                             "mdi6.bank",                   "#34D399", "\U0001F3E6"),
    "person":           (_fi(_FI.PEOPLE)         if _FLUENT_OK else None, "mdi6.account",                "#60A5FA", "\U0001F464"),
    "persons":          (_fi(_FI.PEOPLE)         if _FLUENT_OK else None, "mdi6.account-group",          "#60A5FA", "\U0001F465"),
    "calendar":         (_fi(_FI.CALENDAR)       if _FLUENT_OK else None, "mdi6.calendar-month",         "#60A5FA", "\U0001F4C5"),
    "chart_line":       (None,                                             "mdi6.chart-line",             "#4ADE80", "\U0001F4C8"),
    "chart_pie":        (_fi(_FI.PIE_SINGLE)     if _FLUENT_OK else None, "mdi6.chart-donut",            "#A78BFA", "\U0001F967"),
    "chart_overview":   (None,                                             "mdi6.chart-bar",              "#22D3EE", "\U0001F4CA"),
    "monthly":          (_fi(_FI.CALENDAR)       if _FLUENT_OK else None, "mdi6.calendar-multiselect",   "#60A5FA", "\U0001F4C5"),
    "trend":            (None,                                             "mdi6.trending-up",            "#4ADE80", "\U0001F4C8"),
    "interest":         (_fi(_FI.UNIT)           if _FLUENT_OK else None, "mdi6.percent",                "#4ADE80", "\U0001F4B9"),
    "income_src":       (_fi(_FI.MARKET)         if _FLUENT_OK else None, "mdi6.cash-register",          "#FBBF24", "\U0001F4B0"),
    "debit_card":       (_fi(_FI.SHOPPING_CART)  if _FLUENT_OK else None, "mdi6.credit-card",            "#60A5FA", "\U0001F4B3"),
    "briefcase":        (_fi(_FI.LIBRARY)        if _FLUENT_OK else None, "mdi6.briefcase",              "#94A3B8", "\U0001F4BC"),
    "house":            (_fi(_FI.HOME)           if _FLUENT_OK else None, "mdi6.home-city",              "#60A5FA", "\U0001F3E0"),
    "building":         (_fi(_FI.APPLICATION)    if _FLUENT_OK else None, "mdi6.office-building",        "#94A3B8", "\U0001F3E2"),
    "no_data":          (_fi(_FI.SCROLL)         if _FLUENT_OK else None, "mdi6.inbox-arrow-down",       "#94A3B8", "\U0001F4ED"),
    "phone":            (_fi(_FI.PHONE)          if _FLUENT_OK else None, "mdi6.phone",                  "#94A3B8", "\U0001F4DE"),
    "basic_info":       (_fi(_FI.INFO)           if _FLUENT_OK else None, "mdi6.information-outline",    "#60A5FA", "\U0001F4CB"),
    "bank_details":     (None,                                             "mdi6.bank-outline",           "#34D399", "\U0001F3E6"),
    "contact":          (_fi(_FI.PEOPLE)         if _FLUENT_OK else None, "mdi6.card-account-phone",     "#94A3B8", "\U0001F4DE"),
    "account_found":    (_fi(_FI.DOCUMENT)       if _FLUENT_OK else None, "mdi6.card-account-details",   "#60A5FA", "\U0001F4C4"),
    "manage":           (_fi(_FI.SETTING)        if _FLUENT_OK else None, "mdi6.cog-transfer",           "#60A5FA", "\U0001F465"),

    # -- Chat / AI assistant ------------------------------------------------------------
    # Fluent slot intentionally None (not confident these FluentIcon members
    # exist) — falls straight through to the reliable qtawesome mdi6 set.
    "send":             (None,                                             "mdi6.send",                   "#FFFFFF", "➤"),
    "attach":           (None,                                             "mdi6.paperclip",              "#94A3B8", "\U0001F4CE"),
    "bot":              (None,                                             "mdi6.robot-happy-outline",    "#A78BFA", "\U0001F916"),
}


# -- Render helpers --------------------------------------------------------------------

def _fluent_icon(fi, color_hex: str, size: int) -> QIcon:
    """
    Render a FluentIcon SVG tinted with color_hex using the library's own
    icon() method (which internally calls writeSvg + SvgIconEngine — no
    manual rasterisation needed).
    """
    if not _FLUENT_OK or fi is None or not color_hex:
        return QIcon()
    try:
        qicon = fi.icon(theme=_FTheme.AUTO, color=QColor(color_hex))
        return qicon if qicon and not qicon.isNull() else QIcon()
    except Exception:
        return QIcon()


def _qta_icon(mdi6_name: str, color_hex: str | None, size: int) -> QIcon:
    """Render a qtawesome mdi6 icon."""
    if not _QTA_OK or not mdi6_name:
        return QIcon()
    opts: dict = {"scale_factor": max(size / 16, 1.0)}
    if color_hex:
        opts["color"] = color_hex
    try:
        return qta.icon(mdi6_name, **opts)
    except Exception:
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
    fi, mdi6, default_color, _ = entry
    resolved = default_color if color == "auto" else color

    # 1) FluentIcon SVG - crisp, scalable, tinted
    if _FLUENT_OK and fi is not None and resolved:
        ic = _fluent_icon(fi, resolved, size)
        if not ic.isNull():
            return ic

    # 2) qtawesome mdi6 - excellent font-based fallback
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
    return entry[3] if entry else ""


def is_available() -> bool:
    """True when at least one icon library is usable."""
    return _FLUENT_OK or _QTA_OK


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
