"""
ui/theme/theme_manager.py — Runtime theme switcher.

Loads saved theme preference from a JSON config file,
applies it to the Theme class by monkey-patching all color
attributes, then regenerates the QApplication stylesheet.

Usage:
    from ui.theme.theme_manager import ThemeManager
    ThemeManager.apply("Midnight Pro")
    ThemeManager.current_name()          # -> "Midnight Pro"
    ThemeManager.available_themes()      # -> [{"name":..., "description":..., "is_dark":...}]
"""

from __future__ import annotations
import json
import os

# ── Config path ───────────────────────────────────────────────────────────────
_CONFIG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "data")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "theme_prefs.json")

# ── Available theme modules ── add new themes here only ──────────────────────
_THEME_MODULES: dict[str, str] = {
    "Ocean Blue":   "ui.theme.theme_ocean_blue",
    "Midnight Pro": "ui.theme.theme_midnight_pro",
    "Forest Light": "ui.theme.theme_forest_light",
}

_DEFAULT_THEME = "Ocean Blue"

# ── All color / shadow attributes patched from theme modules ──────────────────
_COLOR_ATTRS = [
    "PRIMARY", "PRIMARY_DARK", "PRIMARY_LIGHT", "PRIMARY_TEXT",
    "PRIMARY_GRADIENT_START", "PRIMARY_GRADIENT_END",
    "PRIMARY_GRADIENT_HOVER_START", "PRIMARY_GRADIENT_HOVER_END",
    "SUCCESS", "SUCCESS_DARK", "SUCCESS_LIGHT",
    "SUCCESS_GRADIENT_START", "SUCCESS_GRADIENT_END",
    "DANGER", "DANGER_DARK", "DANGER_LIGHT",
    "DANGER_GRADIENT_START", "DANGER_GRADIENT_END",
    "WARNING", "WARNING_DARK", "WARNING_LIGHT",
    "WARNING_GRADIENT_START", "WARNING_GRADIENT_END",
    "INFO", "INFO_DARK", "INFO_LIGHT",
    "INFO_GRADIENT_START", "INFO_GRADIENT_END",
    "EDIT", "EDIT_DARK", "EDIT_LIGHT",
    "EDIT_GRADIENT_START", "EDIT_GRADIENT_END",
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


class ThemeManager:
    _active: str = _DEFAULT_THEME

    # ── Public API ────────────────────────────────────────────────────────────

    @classmethod
    def load_and_apply(cls) -> None:
        """Call once at startup — reads saved pref and applies it (no re-save)."""
        name = cls._read_pref()
        cls.apply(name, save=False)

    # kept for backward compat
    @classmethod
    def load_saved(cls) -> None:
        cls.load_and_apply()

    @classmethod
    def apply(cls, name: str, save: bool = True) -> None:
        """Switch active theme, patch Theme class, refresh QApplication QSS."""
        if name not in _THEME_MODULES:
            name = _DEFAULT_THEME
        mod = cls._load_module(name)
        cls._patch_theme(mod)
        cls._refresh_stylesheet()
        cls._active = name
        if save:
            cls._write_pref(name)

    @classmethod
    def save_preference(cls, name: str) -> None:
        """Persist preference without re-applying (use after apply())."""
        cls._write_pref(name)

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
        result = []
        for name in _THEME_MODULES:
            mod = cls._load_module(name)
            result.append({
                "name":        name,
                "description": getattr(mod, "DESCRIPTION", ""),
                "is_dark":     getattr(mod, "IS_DARK", False),
            })
        return result

    @classmethod
    def theme_names(cls) -> list[str]:
        return list(_THEME_MODULES.keys())

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _load_module(name: str):
        import importlib
        mod_path = _THEME_MODULES.get(name, _THEME_MODULES[_DEFAULT_THEME])
        return importlib.import_module(mod_path)

    @staticmethod
    def _patch_theme(mod) -> None:
        from ui.theme.theme import Theme
        for attr in _COLOR_ATTRS:
            val = getattr(mod, attr, None)
            if val is not None:
                setattr(Theme, attr, val)

    @staticmethod
    def _refresh_stylesheet() -> None:
        try:
            from PyQt6.QtWidgets import QApplication
            from ui.theme.theme import Theme
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(Theme.get_stylesheet())
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
