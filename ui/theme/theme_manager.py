"""
ui/theme/theme_manager.py — Runtime theme switcher.

To add a new theme: create ui/theme/theme_xxx.py, then add ONE line to _THEME_MODULES.
No other file needs changing.

LIVE SWITCHING (no restart needed):
  apply() patches Theme class attributes → pushes new QSS to QApplication
  → recursively polishes every live QWidget → fires registered callbacks.
"""

from __future__ import annotations
import json
import os

_CONFIG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "theme_prefs.json")

# ── Register themes HERE ONLY ─────────────────────────────────────────────────
# Order determines display order in Settings.
_THEME_MODULES: dict[str, str] = {
    # ── Light themes ──────────────────────────────────────────────────────────
    "Ocean Blue":     "ui.theme.theme_ocean_blue",
    "Forest Light":   "ui.theme.theme_forest_light",
    "Rose Gold Luxe": "ui.theme.theme_rose_gold",
    "Sunrise Warm":   "ui.theme.theme_sunrise_warm",
    # ── Dark themes ───────────────────────────────────────────────────────────
    "Midnight Pro":   "ui.theme.theme_midnight_pro",
    "Amethyst Dusk":  "ui.theme.theme_amethyst_dusk",
    "Finance Pro":    "ui.theme.theme_finance_pro",
}

_DEFAULT_THEME = "Ocean Blue"

_COLOR_ATTRS = [
    "PRIMARY", "PRIMARY_DARK", "PRIMARY_LIGHT", "PRIMARY_TEXT",
    "PRIMARY_GRADIENT_START", "PRIMARY_GRADIENT_END",
    "PRIMARY_GRADIENT_HOVER_START", "PRIMARY_GRADIENT_HOVER_END",
    "SUCCESS", "SUCCESS_DARK", "SUCCESS_LIGHT", "SUCCESS_GRADIENT_START", "SUCCESS_GRADIENT_END",
    "DANGER",  "DANGER_DARK",  "DANGER_LIGHT",  "DANGER_GRADIENT_START",  "DANGER_GRADIENT_END",
    "WARNING", "WARNING_DARK", "WARNING_LIGHT", "WARNING_GRADIENT_START", "WARNING_GRADIENT_END",
    "INFO",    "INFO_DARK",    "INFO_LIGHT",    "INFO_GRADIENT_START",    "INFO_GRADIENT_END",
    "EDIT",    "EDIT_DARK",    "EDIT_LIGHT",    "EDIT_GRADIENT_START",    "EDIT_GRADIENT_END",
    "HERO_GRADIENT_START", "HERO_GRADIENT_END",
    "HERO_GRADIENT_HOVER_START", "HERO_GRADIENT_HOVER_END",
    "PURPLE", "PURPLE_LIGHT", "TEAL", "TEAL_LIGHT",
    "ORANGE", "ORANGE_LIGHT", "PINK", "PINK_LIGHT",
    "BG", "SURFACE", "SURFACE_ALT", "SURFACE_TINT_START", "SURFACE_TINT_END",
    "SIDEBAR_BG", "SIDEBAR_TEXT", "SIDEBAR_ACTIVE", "SIDEBAR_ACTIVE_TEXT", "SIDEBAR_HOVER",
    "TOPBAR_BG", "TOPBAR_BORDER",
    "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "TEXT_ON_PRIMARY", "TEXT_HEADING",
    "BORDER", "BORDER_FOCUS", "DIVIDER",
    "SHADOW_BLUR_CARD", "SHADOW_BLUR_ELEVATED",
    "SHADOW_OFFSET_Y", "SHADOW_OFFSET_Y_ELEVATED",
    "SHADOW_RGBA_CARD", "SHADOW_RGBA_ELEVATED", "SHADOW_RGBA_PRIMARY",
    "CHART_COLORS", "CHART_COLORS_LIGHT",
]

# Callbacks fired after every theme switch — registered by UI screens that
# need to rebuild inline-styled widgets (e.g. SettingsScreen header).
_on_change_listeners: list = []


class ThemeManager:
    _active: str = _DEFAULT_THEME

    # ── Public API ────────────────────────────────────────────────────────────

    @classmethod
    def load_and_apply(cls) -> None:
        """Call ONCE at startup — reads saved pref and applies without re-saving."""
        name = cls._read_pref()
        cls.apply(name, save=False, notify=False)

    @classmethod
    def load_saved(cls) -> None:
        """Backward-compat alias for load_and_apply()."""
        cls.load_and_apply()

    @classmethod
    def apply(cls, name: str, save: bool = True, notify: bool = True) -> None:
        """
        Switch the active theme — no restart required.
        Steps:
          1. Patch all Theme.* class attributes from the new theme module.
          2. Push regenerated QSS to QApplication.
          3. Recursively polish + update every live QWidget.
          4. Fire registered change-listeners (e.g. SettingsScreen).
          5. Persist the new preference to disk.
        """
        if name not in _THEME_MODULES:
            name = _DEFAULT_THEME

        mod = cls._load_module(name)
        cls._patch_theme(mod)
        cls._set_stylesheet()
        cls._deep_refresh()
        cls._active = name

        if save:
            cls._write_pref(name)
        if notify:
            cls._fire_listeners(name)

    @classmethod
    def register_on_change(cls, callback) -> None:
        """
        Register callback(theme_name: str).
        Called on the main thread after every successful theme switch.
        Use this in screens that build inline-style strings at __init__ time
        so they can restyle themselves after a theme change.
        """
        if callback not in _on_change_listeners:
            _on_change_listeners.append(callback)

    @classmethod
    def unregister_on_change(cls, callback) -> None:
        if callback in _on_change_listeners:
            _on_change_listeners.remove(callback)

    @classmethod
    def current_name(cls) -> str:
        return cls._active

    @classmethod
    def get_active_name(cls) -> str:
        return cls._active

    @classmethod
    def is_dark(cls) -> bool:
        mod = cls._load_module(cls._active)
        return getattr(mod, "IS_DARK", False)

    @classmethod
    def available_themes(cls) -> list[dict]:
        """Returns list of dicts with name, description, is_dark, emoji for each theme."""
        result = []
        for name in _THEME_MODULES:
            mod = cls._load_module(name)
            result.append({
                "name":        name,
                "description": getattr(mod, "DESCRIPTION", ""),
                "is_dark":     getattr(mod, "IS_DARK", False),
                "emoji":       getattr(mod, "EMOJI", "🎨"),
            })
        return result

    @classmethod
    def light_themes(cls) -> list[dict]:
        return [t for t in cls.available_themes() if not t["is_dark"]]

    @classmethod
    def dark_themes(cls) -> list[dict]:
        return [t for t in cls.available_themes() if t["is_dark"]]

    @classmethod
    def theme_names(cls) -> list[str]:
        return list(_THEME_MODULES.keys())

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _load_module(name: str):
        import importlib
        mod_path = _THEME_MODULES.get(name, _THEME_MODULES[_DEFAULT_THEME])
        return importlib.import_module(mod_path)

    @staticmethod
    def _patch_theme(mod) -> None:
        """Monkey-patch every color token onto the live Theme class."""
        from ui.theme.theme import Theme
        for attr in _COLOR_ATTRS:
            val = getattr(mod, attr, None)
            if val is not None:
                setattr(Theme, attr, val)

    @staticmethod
    def _set_stylesheet() -> None:
        """Regenerate and push QSS to QApplication."""
        try:
            from PyQt6.QtWidgets import QApplication
            from ui.theme.theme import Theme
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(Theme.get_stylesheet())
        except Exception:
            pass

    @staticmethod
    def _deep_refresh() -> None:
        """
        Recursively call unpolish/polish/update on every live QWidget so the
        new stylesheet takes immediate visual effect without restarting.
        """
        try:
            from PyQt6.QtWidgets import QApplication, QWidget
            app = QApplication.instance()
            if app is None:
                return
            style = app.style()
            for top in app.topLevelWidgets():
                # Include the top-level window itself
                for w in [top] + top.findChildren(QWidget):
                    try:
                        style.unpolish(w)
                        style.polish(w)
                        w.update()
                    except Exception:
                        pass
            app.processEvents()
        except Exception:
            pass

    @staticmethod
    def _fire_listeners(name: str) -> None:
        for cb in list(_on_change_listeners):
            try:
                cb(name)
            except Exception:
                pass

    @staticmethod
    def _read_pref() -> str:
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("theme", _DEFAULT_THEME)
            return name if name in _THEME_MODULES else _DEFAULT_THEME
        except Exception:
            return _DEFAULT_THEME

    @staticmethod
    def _write_pref(name: str) -> None:
        try:
            os.makedirs(_CONFIG_DIR, exist_ok=True)
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"theme": name}, f, indent=2)
        except Exception:
            pass
