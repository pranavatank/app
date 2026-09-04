"""
ui/icons.py — Unified icon registry with theme-aware semantic roles.

PRIMARY  : qtawesome mdi6 Material Design icon font.
FALLBACK : plain-text Unicode emoji when qtawesome is unavailable.

Registry tuple format: (mdi6_name,  role,  emoji)

Role palette (theme-aware at render time):
  - "default"    : Theme.ICON_DEFAULT (primary text color, adapts to light/dark)
  - "muted"      : Theme.ICON_MUTED (secondary/disabled text)
  - "on_primary" : Theme.ICON_ON_PRIMARY (white/light text on coloured fills)
  - "success"    : Theme.SUCCESS_TEXT (semantic green)
  - "danger"     : Theme.DANGER_TEXT (semantic red)
  - "warning"    : Theme.WARNING_TEXT (semantic yellow)
  - "info"       : Theme.INFO_TEXT (semantic blue)
  - "accent"     : from Theme.CHART_COLORS, cycling by icon name hash (categorical)

Usage:
    from ui.icons import icon, pixmap, set_btn_icon, icon_label, tab_icon
"""
from __future__ import annotations

import os
import tempfile
import functools

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
# Tuple format: (mdi6_name,  role,  emoji)
#
# - mdi6_name : qtawesome name
# - role      : semantic colour role (resolved to Theme colour at render time)
# - emoji     : plain-text fallback when qtawesome is unavailable
_R: dict[str, tuple] = {

    # -- Sidebar / nav (all default) -----------------------------------------------
    "overview":         ("mdi6.view-dashboard",         "default", "\U0001F3E0"),
    "accounts":         ("mdi6.bank",                   "default", "\U0001F3DB"),
    "transactions":     ("mdi6.swap-horizontal-bold",   "default", "\U0001F4B8"),
    "income":           ("mdi6.cash-multiple",          "default", "\U0001F4B0"),
    "fixed_deposits":   ("mdi6.piggy-bank",             "default", "\U0001F3E6"),
    "statement_import": ("mdi6.file-import",            "default", "\U0001F4C4"),
    "ais_tis":          ("mdi6.file-document-multiple", "default", "\U0001F4D1"),
    "tax":              ("mdi6.calculator-variant",     "default", "\U0001F4CB"),
    "reconciliation":   ("mdi6.scale-balance",          "default", "⚖"),
    "reports":          ("mdi6.chart-areaspline",       "default", "\U0001F4CA"),
    "settings":         ("mdi6.cog-outline",            "default", "⚙"),

    # -- CRUD actions --------------------------------------------------------------
    "add":              ("mdi6.plus-circle",            "success", "➕"),
    "edit":             ("mdi6.pencil",                 "info", "✏"),
    "delete":           ("mdi6.trash-can",              "danger", "\U0001F5D1"),
    "save":             ("mdi6.content-save",           "success", "\U0001F4BE"),
    "refresh":          ("mdi6.refresh",                "info", "\U0001F504"),
    "link":             ("mdi6.link-variant",           "accent", "\U0001F517"),
    "unlink":           ("mdi6.link-variant-off",       "danger", "\U0001F517"),
    "auto_link":        ("mdi6.flash",                  "warning", "⚡"),
    "recalculate":      ("mdi6.calculator",             "accent", "\U0001F522"),
    "import":           ("mdi6.file-upload",            "info", "\U0001F4C2"),
    "import_pdf":       ("mdi6.file-pdf-box",           "danger", "\U0001F4C4"),
    "import_json":      ("mdi6.code-json",              "warning", "\U0001F4E4"),
    "backup":           ("mdi6.database-export",        "success", "\U0001F4BE"),
    "restore":          ("mdi6.database-import",        "warning", "\U0001F504"),
    "logout":           ("mdi6.logout",                 "danger", "\U0001F6AA"),
    "filter":           ("mdi6.filter-variant",         "accent", "\U0001F50D"),
    "search":           ("mdi6.magnify",                "info", "\U0001F50D"),
    "close":            ("mdi6.close-circle",           "danger", "✕"),
    "check":            ("mdi6.check-bold",             "success", "✓"),
    "browse":           ("mdi6.folder-open",            "warning", "\U0001F4C2"),
    "copy":             ("mdi6.content-copy",           "info", "\U0001F4CB"),
    "export":           ("mdi6.file-export",            "success", "\U0001F4E4"),
    "bulk_edit":        ("mdi6.table-edit",             "info", "\U0001F9E9"),
    "shift_dates":      ("mdi6.calendar-arrow-right",   "accent", "\U0001F5D3"),
    "split":            ("mdi6.scissors-cutting",       "warning", "✂"),
    "merge":            ("mdi6.merge",                  "success", "\U0001F500"),
    "debug":            ("mdi6.bug",                    "danger", "\U0001F41E"),
    "sidebar_expand":   ("mdi6.chevron-right",          "muted", "▶"),
    "sidebar_collapse": ("mdi6.chevron-left",           "muted", "◀"),
    "list_view":        ("mdi6.view-list",              "info", "\U0001F4CB"),
    "card_view":        ("mdi6.view-grid",              "accent", "\U0001FA9F"),
    "calculate":        ("mdi6.lightning-bolt",         "warning", "⚡"),
    "select_all":       ("mdi6.checkbox-multiple-marked","success","✓"),
    "clear_sel":        ("mdi6.checkbox-multiple-blank-outline","muted","✗"),
    "show":             ("mdi6.chevron-down",           "info", "▼"),
    "hide":             ("mdi6.chevron-up",             "info", "▲"),
    "reconcile":        ("mdi6.compare",                "accent", "\U0001F504"),

    # -- Auth / security -------------------------------------------------------------
    "lock":             ("mdi6.lock",                   "warning", "\U0001F512"),
    "unlock":           ("mdi6.lock-open-variant",      "success", "\U0001F513"),
    "key":              ("mdi6.key-variant",            "warning", "\U0001F511"),
    "password":         ("mdi6.form-textbox-password",  "muted", "\U0001F510"),
    "two_fa":           ("mdi6.shield-check",           "success", "\U0001F6E1"),
    "privacy":          ("mdi6.eye-off",                "muted", "\U0001F441"),
    "privacy_active":   ("mdi6.eye-lock",               "warning", "\U0001F512"),
    "device":           ("mdi6.laptop",                 "info", "\U0001F4BB"),
    "create_account":   ("mdi6.account-plus",           "success", "✅"),

    # -- Status / feedback -------------------------------------------------------------
    "warning":          ("mdi6.alert",                  "warning", "⚠"),
    "info_circle":      ("mdi6.information",            "info", "ℹ"),
    "success_badge":    ("mdi6.check-decagram",         "success", "✅"),
    "error_badge":      ("mdi6.close-octagon",          "danger", "❌"),
    "trophy":           ("mdi6.trophy",                 "warning", "\U0001F3C6"),
    "tip":              ("mdi6.lightbulb-on",           "warning", "\U0001F4A1"),
    "notification":     ("mdi6.bell-ring",              "warning", "\U0001F514"),
    "overdue":          ("mdi6.alarm",                  "danger", "⏰"),

    # -- Theme / appearance -------------------------------------------------------------
    "theme":            ("mdi6.palette",                "accent", "\U0001F3A8"),
    "light_theme":      ("mdi6.white-balance-sunny",    "warning", "☀"),
    "dark_theme":       ("mdi6.weather-night",          "accent", "\U0001F319"),
    "live":             ("mdi6.circle",                 "success", "\U0001F7E2"),

    # -- Domain -------------------------------------------------------------------------
    "bank":             ("mdi6.bank",                   "success", "\U0001F3E6"),
    "person":           ("mdi6.account",                "info", "\U0001F464"),
    "persons":          ("mdi6.account-group",          "info", "\U0001F465"),
    "calendar":         ("mdi6.calendar-month",         "info", "\U0001F4C5"),
    "chart_line":       ("mdi6.chart-line",             "success", "\U0001F4C8"),
    "chart_pie":        ("mdi6.chart-donut",            "accent", "\U0001F967"),
    "chart_overview":   ("mdi6.chart-bar",              "info", "\U0001F4CA"),
    "monthly":          ("mdi6.calendar-multiselect",   "info", "\U0001F4C5"),
    "trend":            ("mdi6.trending-up",            "success", "\U0001F4C8"),
    "interest":         ("mdi6.percent",                "success", "\U0001F4B9"),
    "income_src":       ("mdi6.cash-register",          "warning", "\U0001F4B0"),
    "debit_card":       ("mdi6.credit-card",            "info", "\U0001F4B3"),
    "briefcase":        ("mdi6.briefcase",              "muted", "\U0001F4BC"),
    "house":            ("mdi6.home-city",              "info", "\U0001F3E0"),
    "building":         ("mdi6.office-building",        "muted", "\U0001F3E2"),
    "no_data":          ("mdi6.inbox-arrow-down",       "muted", "\U0001F4ED"),
    "phone":            ("mdi6.phone",                  "muted", "\U0001F4DE"),
    "basic_info":       ("mdi6.information-outline",    "info", "\U0001F4CB"),
    "bank_details":     ("mdi6.bank-outline",           "success", "\U0001F3E6"),
    "contact":          ("mdi6.card-account-phone",     "muted", "\U0001F4DE"),
    "account_found":    ("mdi6.card-account-details",   "info", "\U0001F4C4"),
    "manage":           ("mdi6.cog-transfer",           "info", "\U0001F465"),

    # -- Chat / AI assistant ------------------------------------------------------------
    "send":             ("mdi6.send",                   "on_primary", "➤"),
    "attach":           ("mdi6.paperclip",              "muted", "\U0001F4CE"),
    "bot":              ("mdi6.robot-happy-outline",    "accent", "\U0001F916"),
}


# -- Role resolution (theme-aware at render time) ------

def _resolve_role(role: str, name: str) -> str:
    """
    Resolve a semantic role to an actual hex colour from the current theme.

    Imported lazily inside the function to avoid circular imports at module load:
    ui.theme and icons must not import each other at module-level.

    Args:
        role: One of "default", "muted", "on_primary", "success", "danger",
              "warning", "info", or "accent"
        name: Icon registry key (used for stable hash of accent colours)

    Returns:
        Hex colour string (e.g. "#FFFFFF")
    """
    from ui.theme.theme import Theme          # Lazy import: icons must not import theme at module load

    if role == "accent":
        # Accent: cycle through theme's chart colors by stable hash of icon name,
        # so a given icon always gets the same slot
        palette = getattr(Theme, "CHART_COLORS", None) or [Theme.PRIMARY]
        return palette[sum(name.encode()) % len(palette)]

    return {
        "default":    Theme.ICON_DEFAULT,
        "muted":      Theme.ICON_MUTED,
        "on_primary": Theme.ICON_ON_PRIMARY,
        "success":    Theme.SUCCESS_TEXT,
        "danger":     Theme.DANGER_TEXT,
        "warning":    Theme.WARNING_TEXT,
        "info":       Theme.INFO_TEXT,
    }.get(role, Theme.ICON_DEFAULT)


# -- Render helpers (with bounded in-memory cache) ----

@functools.lru_cache(maxsize=512)
def _qta_icon_cached(mdi6_name: str, color_hex: str, size: int) -> QIcon:
    """
    Render a qtawesome mdi6 icon with in-memory caching.

    Cached by (mdi6_name, color_hex, size) — QIcon is safe to share across
    callers. LRU cache bounds memory to 512 rendered icons.
    """
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

      color='auto'              -> resolve role from registry, adapts to theme
      color='role_name'         -> resolve role (e.g. 'info', 'danger'), adapts to theme
      color='#hex' or other str -> use literal hex colour (overrides registry)
      color=None                -> no colour hint
    """
    entry = _R.get(name)
    if not entry:
        return QIcon()
    mdi6, role, _ = entry

    # Resolve the effective colour to render with
    if color == "auto":
        # "auto" resolves the role from registry
        resolved = _resolve_role(role, name)
    elif color in ("default", "muted", "on_primary", "success", "danger", "warning", "info", "accent"):
        # If color is a known role name, resolve it
        resolved = _resolve_role(color, name)
    else:
        # Explicit hex or None
        resolved = color

    # qtawesome mdi6 - Material Design icon font
    if _QTA_OK and mdi6 and resolved:
        ic = _qta_icon_cached(mdi6, resolved, size)
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


# -- QSS image: url() support (with bounded cache) ----
# Qt Style Sheets can't embed a QPixmap/QIcon directly (`image: url(...)`
# needs a real file path or Qt resource) — this renders a registry icon to a
# small cached PNG on disk (OS temp dir) so global QSS
# (combobox/spinbox/date-edit arrows)
# can reference a real icon instead of the old CSS zero-size-box border
# triangle, which renders as an unstyled little rectangle in this app's Qt6
# build rather than an actual arrow shape.
#
# Cache is bounded: after writing a new file, prune to keep only the 400 most
# recently modified PNG files. This prevents unbounded growth when theme
# switching adds new files (e.g. theme A uses colours 1–8, theme B uses 9–16,
# and switching back and forth would accumulate all files indefinitely).
_icon_cache_dir: str | None = None


def _icon_cache_dir_path() -> str:
    global _icon_cache_dir
    if _icon_cache_dir is None:
        _icon_cache_dir = os.path.join(tempfile.gettempdir(), "FinancialApp", "icon_cache")
        os.makedirs(_icon_cache_dir, exist_ok=True)
    return _icon_cache_dir


def _prune_icon_cache(max_files: int = 400) -> None:
    """
    Prune the icon cache directory to keep only the most recent max_files PNG files.

    Called after writing a new icon file. Deletes the oldest files by mtime
    until count <= max_files. Errors are silently ignored (a locked file
    cannot break icon rendering).
    """
    cache_dir = _icon_cache_dir_path()
    try:
        files = [
            os.path.join(cache_dir, f)
            for f in os.listdir(cache_dir)
            if f.endswith(".png")
        ]
        if len(files) > max_files:
            # Sort by mtime, oldest first, and delete the excess
            files_by_mtime = sorted(files, key=lambda f: os.path.getmtime(f))
            for f in files_by_mtime[:-max_files]:
                try:
                    os.remove(f)
                except Exception:
                    pass  # Ignore locked/permission errors
    except Exception:
        pass  # Ignore any errors that don't affect rendering


def icon_file(name: str, color: str, size: int = 16) -> str:
    """
    Render a registry icon to a cached PNG and return its path (forward
    slashes, safe for direct use inside a QSS `url(...)`).

    Cached by (name, color, size). When theme changes, new colours generate
    new cache files; old files are automatically pruned to keep the directory
    bounded at ~400 files by mtime.

    Args:
        name: Icon registry key
        color: Hex colour or a role name (e.g. "info"), resolved at render time
        size: Icon size in pixels (default 16)

    Returns:
        Forward-slash path to cached PNG, or empty string if rendering failed
    """
    safe_color = (color or "").lstrip("#").upper() or "AUTO"
    path = os.path.join(_icon_cache_dir_path(), f"{name}_{safe_color}_{size}.png")
    if not os.path.exists(path):
        pm = pixmap(name, size=size, color=color)
        if not pm.isNull():
            pm.save(path, "PNG")
            _prune_icon_cache()  # Prune after writing a new file
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
                 color: str | None = "on_primary") -> None:
    """
    Attach an icon to a button.

    Defaults to 'on_primary' — the theme's icon colour for text on coloured fills,
    correct for primary/danger/success/info buttons.

    Args:
        btn: QPushButton to attach icon to
        name: Icon registry key
        size: Icon size in pixels (default 15)
        color: Colour to render with (default "on_primary" role, adapts to theme)
               - 'on_primary', 'default', 'muted', 'success', etc.: role name
               - '#hex': literal hex colour
               - None: no colour hint
               - 'auto': resolve from registry role
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
