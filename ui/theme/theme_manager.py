"""
ui/theme/theme_manager.py — Runtime theme switcher.

HOW LIVE SWITCHING WORKS:
  1. _patch_theme()    — overwrites all Theme.COLOR_TOKEN class attrs
  2. _set_stylesheet() — pushes regenerated QSS to QApplication
  3. _fire_listeners() — rebuilds inline setStyleSheet() widgets FIRST
                         (inline styles can't be updated by polish alone)
  4. _deep_refresh()   — unpolish/polish/update/repaint every live QWidget
"""

from __future__ import annotations
import json
import os

_CONFIG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "theme_prefs.json")

_THEME_MODULES: dict[str, str] = {
    # Light
    "Aurora":       "ui.theme.theme_aurora_light",
    "Slate":        "ui.theme.theme_slate_light",
    # Dark
    "Nova":         "ui.theme.theme_nova_dark",
    "Midnight Pro": "ui.theme.theme_midnight_pro",
}

_DEFAULT_THEME = "Aurora"

_RENAMED_THEMES: dict[str, str] = {
    "Ocean Blue":     "Slate",
    "Arctic Breeze":  "Slate",
    "Forest Light":   "Slate",
    "Rose Gold Luxe": "Aurora",
    "Sunrise Warm":   "Aurora",
    "Amethyst Dusk":  "Nova",
    "Finance Pro":    "Midnight Pro",
}

_COLOR_ATTRS = [
    "PRIMARY","PRIMARY_DARK","PRIMARY_LIGHT","PRIMARY_TEXT",
    "PRIMARY_GRADIENT_START","PRIMARY_GRADIENT_END",
    "PRIMARY_GRADIENT_HOVER_START","PRIMARY_GRADIENT_HOVER_END",
    "SUCCESS","SUCCESS_DARK","SUCCESS_LIGHT","SUCCESS_GRADIENT_START","SUCCESS_GRADIENT_END",
    "DANGER","DANGER_DARK","DANGER_LIGHT","DANGER_GRADIENT_START","DANGER_GRADIENT_END",
    "WARNING","WARNING_DARK","WARNING_LIGHT","WARNING_GRADIENT_START","WARNING_GRADIENT_END",
    "INFO","INFO_DARK","INFO_LIGHT","INFO_GRADIENT_START","INFO_GRADIENT_END",
    "EDIT","EDIT_DARK","EDIT_LIGHT","EDIT_GRADIENT_START","EDIT_GRADIENT_END",
    "HERO_GRADIENT_START","HERO_GRADIENT_END",
    "HERO_GRADIENT_HOVER_START","HERO_GRADIENT_HOVER_END",
    "PURPLE","PURPLE_LIGHT","TEAL","TEAL_LIGHT","ORANGE","ORANGE_LIGHT","PINK","PINK_LIGHT",
    "BG","SURFACE","SURFACE_ALT","SURFACE_TINT_START","SURFACE_TINT_END",
    "SIDEBAR_BG","SIDEBAR_TEXT","SIDEBAR_ACTIVE","SIDEBAR_ACTIVE_TEXT","SIDEBAR_HOVER",
    "TOPBAR_BG","TOPBAR_BORDER",
    "TEXT_PRIMARY","TEXT_SECONDARY","TEXT_MUTED","TEXT_ON_PRIMARY","TEXT_HEADING",
    # ── Text on colored fills ───────────────────────────────────────────────
    "TEXT_ON_SUCCESS","TEXT_ON_DANGER","TEXT_ON_WARNING","TEXT_ON_INFO","TEXT_ON_EDIT",
    # ── Semantic text colors ────────────────────────────────────────────────
    "DANGER_TEXT","SUCCESS_TEXT","WARNING_TEXT","INFO_TEXT",
    # ── Icon colors ────────────────────────────────────────────────────────
    "ICON_DEFAULT","ICON_MUTED","ICON_ON_PRIMARY",
    # ── Overlays and focus ────────────────────────────────────────────────
    "TOOLTIP_BG","TOOLTIP_FG","FOCUS_RING","SCRIM",
    "BORDER","BORDER_FOCUS","DIVIDER",
    "SHADOW_BLUR_CARD","SHADOW_BLUR_ELEVATED",
    "SHADOW_OFFSET_Y","SHADOW_OFFSET_Y_ELEVATED",
    "SHADOW_RGBA_CARD","SHADOW_RGBA_ELEVATED","SHADOW_RGBA_PRIMARY",
    "CHART_COLORS","CHART_COLORS_LIGHT",
]

_on_change_listeners: list = []


class ThemeManager:
    _active: str = _DEFAULT_THEME

    @classmethod
    def load_and_apply(cls) -> None:
        """Call ONCE at startup."""
        name = cls._read_pref()
        cls.apply(name, save=False, notify=False)

    @classmethod
    def load_saved(cls) -> None:
        cls.load_and_apply()

    @classmethod
    def apply(cls, name: str, save: bool = True, notify: bool = True) -> None:
        """
        Full live theme switch — no restart needed.
        Order matters:
          patch → stylesheet → listeners (rebuild inline) → deep_refresh (repaint)
        """
        if name not in _THEME_MODULES:
            name = _DEFAULT_THEME
        mod = cls._load_module(name)
        cls._patch_theme(mod)
        cls._set_stylesheet()
        cls._active = name
        if notify:
            cls._fire_listeners(name)  # rebuild inline styles BEFORE repaint
        cls._deep_refresh()            # repaint everything
        if save:
            cls._write_pref(name)

    @classmethod
    def register_on_change(cls, callback) -> None:
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
        return getattr(cls._load_module(cls._active), "IS_DARK", False)

    @classmethod
    def available_themes(cls) -> list[dict]:
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

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _load_module(name: str):
        import importlib
        return importlib.import_module(
            _THEME_MODULES.get(name, _THEME_MODULES[_DEFAULT_THEME]))

    @staticmethod
    def _patch_theme(mod) -> None:
        from ui.theme.theme import Theme
        for attr in _COLOR_ATTRS:
            val = getattr(mod, attr, None)
            if val is not None:
                setattr(Theme, attr, val)

    @staticmethod
    def _set_stylesheet() -> None:
        try:
            from PyQt6.QtWidgets import QApplication
            from ui.theme.theme import Theme
            app = QApplication.instance()
            if app:
                app.setStyleSheet(Theme.get_stylesheet())
        except Exception:
            pass

    @staticmethod
    def _deep_refresh() -> None:
        """
        Walk every live QWidget and call unpolish/polish/update/repaint.
        This re-evaluates the new QSS for every widget without a restart.
        Inline setStyleSheet() widgets are handled by _fire_listeners BEFORE this.
        """
        try:
            from PyQt6.QtWidgets import QApplication, QWidget
            app = QApplication.instance()
            if not app:
                return
            style = app.style()
            for top in app.topLevelWidgets():
                for w in [top] + top.findChildren(QWidget):
                    try:
                        style.unpolish(w)
                        style.polish(w)
                        w.update()
                    except Exception:
                        pass
                try:
                    top.repaint()
                except Exception:
                    pass
            app.processEvents()
            # Second pass — some widgets need two cycles to fully repaint
            for top in app.topLevelWidgets():
                try:
                    top.update()
                    top.repaint()
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
                import traceback
                traceback.print_exc()

    @staticmethod
    def _read_pref() -> str:
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("theme", _DEFAULT_THEME)
            # Check if it's a renamed theme
            if name in _RENAMED_THEMES:
                return _RENAMED_THEMES[name]
            # Return if valid, else fall back to default
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
