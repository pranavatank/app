"""
ui/theme/theme.py — Live Theme class. Color attributes are patched at runtime
by ThemeManager.apply(). All UI code imports Theme from here and calls
Theme.ATTRIBUTE or Theme.method() — never imports from theme_*.py directly.
"""

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect

from . import components as tc
from . import constants as c   # default (Aurora) values at import time


class Theme:
    # ── Color tokens (defaults = Aurora, overwritten by ThemeManager) ─────────
    PRIMARY                   = c.PRIMARY
    PRIMARY_DARK              = c.PRIMARY_DARK
    PRIMARY_LIGHT             = c.PRIMARY_LIGHT
    PRIMARY_TEXT              = c.PRIMARY_TEXT
    PRIMARY_GRADIENT_START    = c.PRIMARY_GRADIENT_START
    PRIMARY_GRADIENT_END      = c.PRIMARY_GRADIENT_END
    PRIMARY_GRADIENT_HOVER_START = c.PRIMARY_GRADIENT_HOVER_START
    PRIMARY_GRADIENT_HOVER_END   = c.PRIMARY_GRADIENT_HOVER_END

    SUCCESS                   = c.SUCCESS
    SUCCESS_DARK              = c.SUCCESS_DARK
    SUCCESS_LIGHT             = c.SUCCESS_LIGHT
    SUCCESS_GRADIENT_START    = c.SUCCESS_GRADIENT_START
    SUCCESS_GRADIENT_END      = c.SUCCESS_GRADIENT_END

    DANGER                    = c.DANGER
    DANGER_DARK               = c.DANGER_DARK
    DANGER_LIGHT              = c.DANGER_LIGHT
    DANGER_GRADIENT_START     = c.DANGER_GRADIENT_START
    DANGER_GRADIENT_END       = c.DANGER_GRADIENT_END

    WARNING                   = c.WARNING
    WARNING_DARK              = c.WARNING_DARK
    WARNING_LIGHT             = c.WARNING_LIGHT
    WARNING_GRADIENT_START    = c.WARNING_GRADIENT_START
    WARNING_GRADIENT_END      = c.WARNING_GRADIENT_END

    INFO                      = c.INFO
    INFO_DARK                 = c.INFO_DARK
    INFO_LIGHT                = c.INFO_LIGHT
    INFO_GRADIENT_START       = c.INFO_GRADIENT_START
    INFO_GRADIENT_END         = c.INFO_GRADIENT_END

    EDIT                      = c.EDIT
    EDIT_DARK                 = c.EDIT_DARK
    EDIT_LIGHT                = c.EDIT_LIGHT
    EDIT_GRADIENT_START       = c.EDIT_GRADIENT_START
    EDIT_GRADIENT_END         = c.EDIT_GRADIENT_END

    HERO_GRADIENT_START       = c.HERO_GRADIENT_START
    HERO_GRADIENT_END         = c.HERO_GRADIENT_END
    HERO_GRADIENT_HOVER_START = c.HERO_GRADIENT_HOVER_START
    HERO_GRADIENT_HOVER_END   = c.HERO_GRADIENT_HOVER_END

    PURPLE       = c.PURPLE;  PURPLE_LIGHT  = c.PURPLE_LIGHT
    TEAL         = c.TEAL;    TEAL_LIGHT    = c.TEAL_LIGHT
    ORANGE       = c.ORANGE;  ORANGE_LIGHT  = c.ORANGE_LIGHT
    PINK         = c.PINK;    PINK_LIGHT    = c.PINK_LIGHT

    BG                        = c.BG
    SURFACE                   = c.SURFACE
    SURFACE_ALT               = c.SURFACE_ALT
    SURFACE_TINT_START        = c.SURFACE_TINT_START
    SURFACE_TINT_END          = c.SURFACE_TINT_END

    SIDEBAR_BG                = c.SIDEBAR_BG
    SIDEBAR_TEXT              = c.SIDEBAR_TEXT
    SIDEBAR_ACTIVE            = c.SIDEBAR_ACTIVE
    SIDEBAR_ACTIVE_TEXT       = c.SIDEBAR_ACTIVE_TEXT
    SIDEBAR_HOVER             = c.SIDEBAR_HOVER

    TOPBAR_BG                 = c.TOPBAR_BG
    TOPBAR_BORDER             = c.TOPBAR_BORDER

    TEXT_PRIMARY              = c.TEXT_PRIMARY
    TEXT_SECONDARY            = c.TEXT_SECONDARY
    TEXT_MUTED                = c.TEXT_MUTED
    TEXT_ON_PRIMARY           = c.TEXT_ON_PRIMARY
    TEXT_HEADING              = c.TEXT_HEADING

    # ── Text on colored fills ───────────────────────────────────────────────
    TEXT_ON_SUCCESS           = c.TEXT_ON_SUCCESS
    TEXT_ON_DANGER            = c.TEXT_ON_DANGER
    TEXT_ON_WARNING           = c.TEXT_ON_WARNING
    TEXT_ON_INFO              = c.TEXT_ON_INFO
    TEXT_ON_EDIT              = c.TEXT_ON_EDIT
    TEXT_ON_HERO              = c.TEXT_ON_HERO

    # ── Semantic text colors ────────────────────────────────────────────────
    DANGER_TEXT               = c.DANGER_TEXT
    SUCCESS_TEXT              = c.SUCCESS_TEXT
    WARNING_TEXT              = c.WARNING_TEXT
    INFO_TEXT                 = c.INFO_TEXT

    # ── Icon colors ────────────────────────────────────────────────────────
    ICON_DEFAULT              = c.ICON_DEFAULT
    ICON_MUTED                = c.ICON_MUTED
    ICON_ON_PRIMARY           = c.ICON_ON_PRIMARY

    # ── Overlays and focus ────────────────────────────────────────────────
    TOOLTIP_BG                = c.TOOLTIP_BG
    TOOLTIP_FG                = c.TOOLTIP_FG
    FOCUS_RING                = c.FOCUS_RING
    SCRIM                     = c.SCRIM

    BORDER                    = c.BORDER
    BORDER_FOCUS              = c.BORDER_FOCUS
    DIVIDER                   = c.DIVIDER

    SHADOW_BLUR_CARD          = c.SHADOW_BLUR_CARD
    SHADOW_BLUR_ELEVATED      = c.SHADOW_BLUR_ELEVATED
    SHADOW_OFFSET_Y           = c.SHADOW_OFFSET_Y
    SHADOW_OFFSET_Y_ELEVATED  = c.SHADOW_OFFSET_Y_ELEVATED
    SHADOW_RGBA_CARD          = c.SHADOW_RGBA_CARD
    SHADOW_RGBA_ELEVATED      = c.SHADOW_RGBA_ELEVATED
    SHADOW_RGBA_PRIMARY       = c.SHADOW_RGBA_PRIMARY

    CHART_COLORS              = c.CHART_COLORS
    CHART_COLORS_LIGHT        = c.CHART_COLORS_LIGHT

    # ── Gradient helpers ──────────────────────────────────────────────────────
    @staticmethod
    def gradient(start: str, end: str, diagonal: bool = False) -> str:
        return tc.gradient(start, end, diagonal=diagonal)

    @staticmethod
    def gradient_v(start: str, end: str) -> str:
        return tc.gradient_v(start, end)

    # ── Shadow helpers (theme-aware) ──────────────────────────────────────────
    @staticmethod
    def shadow_card() -> QGraphicsDropShadowEffect:
        return tc.card_shadow(Theme)

    @staticmethod
    def shadow_elevated() -> QGraphicsDropShadowEffect:
        return tc.elevated_shadow(Theme)

    @staticmethod
    def shadow_primary() -> QGraphicsDropShadowEffect:
        return tc.primary_shadow(Theme)

    @staticmethod
    def shadow_success() -> QGraphicsDropShadowEffect:
        return tc.success_shadow()

    @staticmethod
    def shadow_danger() -> QGraphicsDropShadowEffect:
        return tc.danger_shadow()

    # ── Button factory ────────────────────────────────────────────────────────
    @staticmethod
    def btn(text: str, variant: str = "primary",
            height: int = 40, min_width: int = 116) -> QPushButton:
        b = QPushButton(text)
        b.setFixedHeight(max(height, 38))
        b.setMinimumWidth(max(min_width, 100))
        b.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        t = Theme
        styles = {
            "primary": f"""
                QPushButton {{
                    background: {t.gradient(t.PRIMARY_GRADIENT_START, t.PRIMARY_GRADIENT_END)};
                    color: {t.TEXT_ON_PRIMARY}; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.gradient(t.PRIMARY_GRADIENT_HOVER_START, t.PRIMARY_GRADIENT_HOVER_END)}; }}
                QPushButton:focus  {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
                QPushButton:pressed{{ background: {t.PRIMARY_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "secondary": f"""
                QPushButton {{
                    background: {t.SURFACE}; color: {t.TEXT_PRIMARY};
                    border: 1.5px solid {t.BORDER}; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 600;
                }}
                QPushButton:hover  {{ background: {t.PRIMARY_LIGHT}; border-color: {t.PRIMARY}; color: {t.PRIMARY_DARK}; }}
                QPushButton:pressed{{ background: {t.PRIMARY_LIGHT}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; border-color: {t.DIVIDER}; }}
            """,
            "success": f"""
                QPushButton {{
                    background: {t.gradient(t.SUCCESS_GRADIENT_START, t.SUCCESS_GRADIENT_END)};
                    color: {t.TEXT_ON_SUCCESS}; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.SUCCESS_DARK}; }}
                QPushButton:focus  {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
                QPushButton:pressed{{ background: {t.SUCCESS_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "danger": f"""
                QPushButton {{
                    background: {t.gradient(t.DANGER_GRADIENT_START, t.DANGER_GRADIENT_END)};
                    color: {t.TEXT_ON_DANGER}; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.DANGER_DARK}; }}
                QPushButton:focus  {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
                QPushButton:pressed{{ background: {t.DANGER_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "warning": f"""
                QPushButton {{
                    background: {t.gradient(t.WARNING_GRADIENT_START, t.WARNING_GRADIENT_END)};
                    color: {t.TEXT_ON_WARNING}; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.WARNING_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "info": f"""
                QPushButton {{
                    background: {t.gradient(t.INFO_GRADIENT_START, t.INFO_GRADIENT_END)};
                    color: {t.TEXT_ON_INFO}; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.INFO_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "edit": f"""
                QPushButton {{
                    background: {t.gradient(t.EDIT_GRADIENT_START, t.EDIT_GRADIENT_END)};
                    color: {t.TEXT_ON_EDIT}; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.EDIT_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "hero": f"""
                QPushButton {{
                    background: {t.gradient(t.HERO_GRADIENT_START, t.HERO_GRADIENT_END)};
                    color: {t.TEXT_ON_HERO}; border: none; border-radius: 12px;
                    padding: 4px 26px; font-size: 14px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.gradient(t.HERO_GRADIENT_HOVER_START, t.HERO_GRADIENT_HOVER_END)}; }}
                QPushButton:focus  {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
                QPushButton:pressed{{ background: {t.PRIMARY_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "ghost": f"""
                QPushButton {{
                    background: transparent; color: {t.PRIMARY};
                    border: none; border-radius: 10px;
                    padding: 4px 18px; font-size: 13px; font-weight: 600;
                }}
                QPushButton:hover  {{ background: {t.PRIMARY_LIGHT}; }}
                QPushButton:pressed{{ background: {t.PRIMARY_LIGHT}; }}
                QPushButton:disabled{{ color: {t.TEXT_MUTED}; }}
            """,
        }
        b.setStyleSheet(styles.get(variant, styles["primary"]))
        return b

    @staticmethod
    def style_button(button: QPushButton, variant: str = "primary",
                     height: int | None = None, min_width: int | None = None) -> QPushButton:
        themed = Theme.btn(button.text(), variant,
                           height=height or button.height() or 38,
                           min_width=min_width or button.minimumWidth() or 110)
        button.setFont(themed.font())
        button.setStyleSheet(themed.styleSheet())
        if height is not None:    button.setFixedHeight(height)
        if min_width is not None: button.setMinimumWidth(min_width)
        return button

    # ── Style string factories ─────────────────────────────────────────────────
    @staticmethod
    def text_style(color=None, size=14, weight=400, background="transparent") -> str:
        return tc.text_style(Theme, color=color, size=size, weight=weight, background=background)

    @staticmethod
    def title_style(size=15) -> str:
        return tc.title_style(Theme, size=size)

    @staticmethod
    def muted_style(size=12) -> str:
        return tc.muted_style(Theme, size=size)

    @staticmethod
    def section_label_style(size=12) -> str:
        return tc.section_label_style(Theme, size=size)

    @staticmethod
    def badge_style(bg, fg, radius=12, padding="5px 14px", size=12, weight=600) -> str:
        return tc.badge_style(Theme, bg=bg, fg=fg, radius=radius, padding=padding, size=size, weight=weight)

    @staticmethod
    def card_style(bg=None, border_color=None, radius=14, padding=14,
                   left_accent=None, selector="QFrame") -> str:
        return tc.card_style(Theme, bg=bg, border_color=border_color, radius=radius,
                             padding=padding, left_accent=left_accent, selector=selector)

    @staticmethod
    def metric_card_style(accent: str, bg: str, radius: int = 16) -> str:
        return tc.metric_card_style(Theme, accent=accent, bg=bg, radius=radius)

    @staticmethod
    def info_banner_style(accent: str = None, radius: int = 12) -> str:
        return tc.info_banner_style(Theme, accent=accent, radius=radius)

    @staticmethod
    def regime_card_style(accent: str, radius: int = 14) -> str:
        return tc.regime_card_style(Theme, accent=accent, radius=radius)

    @staticmethod
    def filter_bar_style(radius=12) -> str:
        return tc.filter_bar_style(Theme, radius=radius)

    @staticmethod
    def group_box_style() -> str:
        return tc.group_box_style(Theme)

    @staticmethod
    def panel_strip_style(start=None, end=None, radius=2) -> str:
        return tc.panel_strip_style(Theme, start=start, end=end, radius=radius)

    @staticmethod
    def tinted_surface_style(radius=14, border_color=None, selector="QFrame") -> str:
        return tc.tinted_surface_style(Theme, radius=radius, border_color=border_color, selector=selector)

    @staticmethod
    def banner_style(level: str = "info", radius: int = 12) -> str:
        return tc.banner_style(Theme, level=level, radius=radius)

    @staticmethod
    def hero_header_style(radius: int = 16, selector: str = "QFrame") -> str:
        return tc.hero_header_style(Theme, radius=radius, selector=selector)

    @staticmethod
    def page_header_style(radius: int = 14, selector: str = "QFrame#pageHeader") -> str:
        return tc.page_header_style(Theme, radius=radius, selector=selector)

    @staticmethod
    def stat_tile_style(accent: str, radius: int = 16, selector: str = "QFrame") -> str:
        return tc.stat_tile_style(Theme, accent=accent, radius=radius, selector=selector)

    @staticmethod
    def empty_state_style(radius: int = 14) -> str:
        return tc.empty_state_style(Theme, radius=radius)

    @staticmethod
    def icon_chip_style(accent: str, radius: int = 10) -> str:
        return tc.icon_chip_style(Theme, accent=accent, radius=radius)

    @staticmethod
    def action_bar_style(radius: int = 14, selector: str = "QFrame#actionBar") -> str:
        return tc.action_bar_style(Theme, radius=radius, selector=selector)

    @staticmethod
    def sidebar_nav_normal() -> str:
        return tc.sidebar_nav_normal()

    @staticmethod
    def sidebar_nav_active() -> str:
        return tc.sidebar_nav_active()

    @staticmethod
    def chat_bubble_user() -> str:
        return tc.chat_bubble_user(Theme)

    @staticmethod
    def chat_bubble_assistant() -> str:
        return tc.chat_bubble_assistant(Theme)

    @staticmethod
    def chat_input_box() -> str:
        return tc.chat_input_box(Theme)

    @staticmethod
    def attachment_chip() -> str:
        return tc.attachment_chip(Theme)

    # ── Legacy helpers ────────────────────────────────────────────────────────
    @staticmethod
    def get_colors(theme_name=None) -> dict:
        t = Theme
        return {
            "primary": t.PRIMARY, "primary_dark": t.PRIMARY_DARK, "primary_light": t.PRIMARY_LIGHT,
            "primary_gradient_start": t.PRIMARY_GRADIENT_START, "primary_gradient_end": t.PRIMARY_GRADIENT_END,
            "success": t.SUCCESS, "success_dark": t.SUCCESS_DARK, "success_light": t.SUCCESS_LIGHT,
            "success_gradient_start": t.SUCCESS_GRADIENT_START, "success_gradient_end": t.SUCCESS_GRADIENT_END,
            "danger": t.DANGER, "danger_dark": t.DANGER_DARK, "danger_light": t.DANGER_LIGHT,
            "danger_gradient_start": t.DANGER_GRADIENT_START, "danger_gradient_end": t.DANGER_GRADIENT_END,
            "warning": t.WARNING, "warning_dark": t.WARNING_DARK, "warning_light": t.WARNING_LIGHT,
            "warning_gradient_start": t.WARNING_GRADIENT_START, "warning_gradient_end": t.WARNING_GRADIENT_END,
            "info": t.INFO, "info_light": t.INFO_LIGHT,
            "info_gradient_start": t.INFO_GRADIENT_START, "info_gradient_end": t.INFO_GRADIENT_END,
            "edit": t.EDIT, "edit_dark": t.EDIT_DARK, "edit_light": t.EDIT_LIGHT,
            "hero_gradient_start": t.HERO_GRADIENT_START, "hero_gradient_end": t.HERO_GRADIENT_END,
            "purple": t.PURPLE, "purple_light": t.PURPLE_LIGHT,
            "teal": t.TEAL, "teal_light": t.TEAL_LIGHT,
            "orange": t.ORANGE, "orange_light": t.ORANGE_LIGHT,
            "pink": t.PINK, "pink_light": t.PINK_LIGHT,
            "bg": t.BG, "bg_primary": t.SURFACE, "bg_secondary": t.SURFACE_ALT,
            "surface": t.SURFACE, "surface_alt": t.SURFACE_ALT,
            "sidebar_bg": t.SIDEBAR_BG, "sidebar_text": t.SIDEBAR_TEXT,
            "text_primary": t.TEXT_PRIMARY, "text_secondary": t.TEXT_SECONDARY, "text_muted": t.TEXT_MUTED,
            "border": t.BORDER, "divider": t.DIVIDER,
            "chart_colors": t.CHART_COLORS, "chart_colors_light": t.CHART_COLORS_LIGHT,
            "chart_1": t.CHART_COLORS[0], "chart_2": t.CHART_COLORS[1],
            "chart_3": t.CHART_COLORS[2], "chart_4": t.CHART_COLORS[3],
            "chart_5": t.CHART_COLORS[4], "chart_6": t.CHART_COLORS[5],
            "chart_7": t.CHART_COLORS[6], "chart_8": t.CHART_COLORS[7],
        }

    @staticmethod
    def get_settings_styles() -> dict:
        t = Theme
        return {
            "section_group": (f"border: none; margin-top: 8px; background: transparent; "
                              f"font-size: 14px; font-weight: 700; color: {t.TEXT_PRIMARY};"),
            "card": (f"background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; "
                     "border-radius: 12px; padding: 16px;"),
            "card_title": f"color: {t.TEXT_PRIMARY}; font-size: 13px; font-weight: 700;",
            "text": f"color: {t.TEXT_PRIMARY}; font-size: 14px;",
            "muted": f"color: {t.TEXT_SECONDARY}; font-size: 13px;",
            "warning": f"color: {t.WARNING_DARK}; font-size: 13px; font-weight: 600;",
            "line_edit": (f"background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY}; "
                          f"border: 1px solid {t.BORDER}; border-radius: 10px; "
                          "padding: 8px 10px; font-size: 14px;"),
            "checkbox": f"color: {t.TEXT_PRIMARY}; font-size: 14px;",
        }

    @staticmethod
    def get_stylesheet() -> str:
        t = Theme
        from .checkbox_asset import checkmark_url
        _url = checkmark_url()
        _checkmark_rule = f"image: url({_url});" if _url else ""

        # Combobox/spinbox/date-edit arrows: rendered from the icon registry
        # instead of the old zero-size-box CSS border triangle, which this
        # app's Qt6 build paints as a small unstyled rectangle rather than an
        # actual arrow. Sized relative to the ~36px input height so they read
        # clearly instead of disappearing into the field.
        from ui.icons import icon_file
        _combo_arrow_url    = icon_file("show", color=t.TEXT_SECONDARY, size=16)
        _spin_up_arrow_url  = icon_file("hide", color=t.TEXT_SECONDARY, size=11)
        _spin_down_arrow_url = icon_file("show", color=t.TEXT_SECONDARY, size=11)
        _date_arrow_url     = icon_file("calendar", color=t.TEXT_SECONDARY, size=16)
        # Primary-tinted hover variants (mirrors the old border-color:hover feedback)
        _spin_up_arrow_hover_url   = icon_file("hide", color=t.PRIMARY, size=11)
        _spin_down_arrow_hover_url = icon_file("show", color=t.PRIMARY, size=11)
        _combo_arrow_rule = f"image: url({_combo_arrow_url}); width: 16px; height: 16px;" if _combo_arrow_url else ""
        _spin_up_rule     = f"image: url({_spin_up_arrow_url}); width: 11px; height: 11px;" if _spin_up_arrow_url else ""
        _spin_down_rule   = f"image: url({_spin_down_arrow_url}); width: 11px; height: 11px;" if _spin_down_arrow_url else ""
        _spin_up_hover_rule   = f"image: url({_spin_up_arrow_hover_url});" if _spin_up_arrow_hover_url else ""
        _spin_down_hover_rule = f"image: url({_spin_down_arrow_hover_url});" if _spin_down_arrow_hover_url else ""
        _date_arrow_rule  = f"image: url({_date_arrow_url}); width: 16px; height: 16px;" if _date_arrow_url else ""
        return f"""
/* ═══════════════════════════ BASE ══════════════════════════ */
QMainWindow, QWidget {{
    background-color: {t.BG};
    color: {t.TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
}}
QDialog {{ background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY}; }}
QLabel {{ color: {t.TEXT_PRIMARY}; background: transparent; border: none; }}

/* ═══════════════════════════ INPUTS ═════════════════════════ */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1.5px solid {t.BORDER}; border-radius: 10px;
    padding: 8px 12px; font-size: 14px;
    selection-background-color: {t.PRIMARY_LIGHT};
    selection-color: {t.PRIMARY_DARK};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 1.5px solid {t.PRIMARY}; outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
QLineEdit:hover, QTextEdit:hover {{ border-color: {t.BORDER_FOCUS}; }}
QLineEdit[readOnly="true"] {{ background-color: {t.SURFACE_ALT}; color: {t.TEXT_SECONDARY}; border-color: {t.DIVIDER}; }}
QSpinBox[readOnly="true"], QDoubleSpinBox[readOnly="true"] {{
    background-color: {t.SURFACE_ALT}; color: {t.TEXT_SECONDARY}; border-color: {t.DIVIDER};
}}

/* ═══════════════════════════ COMBO ══════════════════════════ */
QComboBox {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1.5px solid {t.BORDER}; border-radius: 10px;
    padding: 7px 12px; font-size: 14px; min-height: 18px;
}}
QComboBox:hover {{ border-color: {t.BORDER_FOCUS}; }}
QComboBox:focus {{ border-color: {t.PRIMARY}; outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ {_combo_arrow_rule} margin-right: 8px; }}
QComboBox QAbstractItemView {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER}; border-radius: 10px;
    selection-background-color: {t.PRIMARY_LIGHT};
    selection-color: {t.PRIMARY_DARK}; padding: 4px; outline: none;
}}

/* ═══════════════════════════ SPINBOX ════════════════════════ */
QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1.5px solid {t.BORDER}; border-radius: 10px;
    padding: 7px 10px; font-size: 14px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{ border-color: {t.PRIMARY}; outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover {{ border-color: {t.BORDER_FOCUS}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    border: none; width: 24px; height: 12px; background: {t.SURFACE_ALT};
    subcontrol-origin: border;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-position: top right; border-top-right-radius: 8px; margin: 1px 1px 0 0;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right; border-bottom-right-radius: 8px; margin: 0 1px 1px 0;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {t.PRIMARY_LIGHT}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ {_spin_up_rule} }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ {_spin_down_rule} }}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{ {_spin_up_hover_rule} }}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{ {_spin_down_hover_rule} }}
QDateEdit::drop-down {{ border: none; width: 28px; subcontrol-origin: border; subcontrol-position: right; }}
QDateEdit::down-arrow {{ {_date_arrow_rule} margin-right: 8px; }}
QCalendarWidget QToolButton {{ color: {t.TEXT_PRIMARY}; background: transparent; font-weight: 600; }}
QCalendarWidget QMenu {{ background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY}; }}
QCalendarWidget QAbstractItemView:enabled {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    selection-background-color: {t.PRIMARY}; selection-color: {t.TEXT_ON_PRIMARY};
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background-color: {t.SURFACE_ALT}; }}

/* ═══════════════════════════ BUTTONS ════════════════════════ */
QPushButton {{
    background: {t.gradient(t.PRIMARY_GRADIENT_START, t.PRIMARY_GRADIENT_END)};
    color: {t.TEXT_ON_PRIMARY}; border: none; border-radius: 10px;
    padding: 8px 18px; font-size: 14px; font-weight: 600; min-height: 22px;
}}
QPushButton:hover   {{ background: {t.gradient(t.PRIMARY_GRADIENT_HOVER_START, t.PRIMARY_GRADIENT_HOVER_END)}; }}
QPushButton:focus   {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
QPushButton:pressed {{ background-color: {t.PRIMARY_DARK}; }}
QPushButton:disabled {{ background-color: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; border: 1px solid {t.DIVIDER}; }}
QPushButton#primaryBtn   {{ background: {t.gradient(t.PRIMARY_GRADIENT_START,  t.PRIMARY_GRADIENT_END)};  color: {t.TEXT_ON_PRIMARY}; }}
QPushButton#primaryBtn:hover {{ background: {t.gradient(t.PRIMARY_GRADIENT_HOVER_START, t.PRIMARY_GRADIENT_HOVER_END)}; }}
QPushButton#secondaryBtn {{ background: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1.5px solid {t.BORDER}; }}
QPushButton#secondaryBtn:hover {{ background: {t.PRIMARY_LIGHT}; border-color: {t.PRIMARY}; color: {t.PRIMARY_DARK}; }}
QPushButton#successBtn {{ background: {t.gradient(t.SUCCESS_GRADIENT_START, t.SUCCESS_GRADIENT_END)}; color: {t.TEXT_ON_SUCCESS}; }}
QPushButton#dangerBtn  {{ background: {t.gradient(t.DANGER_GRADIENT_START,  t.DANGER_GRADIENT_END)};  color: {t.TEXT_ON_DANGER}; }}
QPushButton#warningBtn {{ background: {t.gradient(t.WARNING_GRADIENT_START, t.WARNING_GRADIENT_END)}; color: {t.TEXT_ON_WARNING}; }}
QPushButton#infoBtn    {{ background: {t.gradient(t.INFO_GRADIENT_START,    t.INFO_GRADIENT_END)};    color: {t.TEXT_ON_INFO}; }}
QPushButton#editBtn    {{ background: {t.gradient(t.EDIT_GRADIENT_START,    t.EDIT_GRADIENT_END)};    color: {t.TEXT_ON_EDIT}; }}

/* ═══════════════════════════ TABLE ══════════════════════════ */
QTableWidget {{
    background-color: {t.SURFACE}; alternate-background-color: {t.SURFACE_TINT_END};
    color: {t.TEXT_PRIMARY}; gridline-color: {t.DIVIDER};
    border: 1px solid {t.BORDER}; border-radius: 10px;
    selection-background-color: {t.PRIMARY_LIGHT};
    selection-color: {t.PRIMARY_DARK}; font-size: 14px;
    outline: none;
}}
QTableWidget::item {{ padding: 8px 10px; border: none; outline: none; }}
QTableWidget::item:selected {{
    background-color: {t.PRIMARY_LIGHT}; color: {t.PRIMARY_DARK};
    border: none; outline: none;
}}
QTableWidget::item:selected:focus {{
    background-color: {t.PRIMARY_LIGHT}; color: {t.PRIMARY_DARK};
    border: 2px solid {t.FOCUS_RING}; outline: none;
}}
QTableWidget::item:hover {{ background-color: {t.SURFACE_ALT}; }}
QTableView {{ outline: none; }}
QHeaderView::section {{
    background-color: {t.SURFACE_ALT}; color: {t.TEXT_SECONDARY};
    padding: 10px 8px; border: none;
    border-bottom: 2px solid {t.BORDER};
    font-weight: 700; font-size: 12px; letter-spacing: 0.5px;
}}

/* ═══════════════════════════ SCROLLBAR ══════════════════════ */
QScrollBar:vertical {{ background: transparent; width: 16px; margin: 0; padding: 0 2px; }}
QScrollBar::handle:vertical {{ background: {t.BORDER}; border-radius: 6px; min-height: 28px; min-width: 12px; }}
QScrollBar::handle:vertical:hover {{ background: {t.PRIMARY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 16px; margin: 0; padding: 2px 0; }}
QScrollBar::handle:horizontal {{ background: {t.BORDER}; border-radius: 6px; min-width: 28px; min-height: 12px; }}
QScrollBar::handle:horizontal:hover {{ background: {t.PRIMARY}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ═══════════════════════════ TABS ═══════════════════════════ */
QTabWidget::pane {{ border: 1px solid {t.BORDER}; border-radius: 10px; background-color: {t.SURFACE}; top: -1px; }}
QTabBar::tab {{
    background-color: {t.SURFACE_ALT}; color: {t.TEXT_SECONDARY};
    padding: 10px 22px; border-top-left-radius: 8px; border-top-right-radius: 8px;
    margin-right: 3px; font-weight: 500; font-size: 14px;
    border: 1px solid {t.BORDER}; border-bottom: none;
}}
QTabBar::tab:selected {{ background-color: {t.PRIMARY}; color: {t.TEXT_ON_PRIMARY}; font-weight: 700; border-color: {t.PRIMARY}; }}
QTabBar::tab:focus {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
QTabBar::tab:hover:!selected {{ background-color: {t.PRIMARY_LIGHT}; color: {t.PRIMARY_DARK}; border-color: {t.PRIMARY}; }}

/* ═══════════════════════════ GROUP BOX ══════════════════════ */
QGroupBox {{
    border: 1px solid {t.BORDER}; border-radius: 12px; margin-top: 18px;
    padding: 16px 16px 12px 16px; background-color: {t.SURFACE};
    font-weight: 700; font-size: 14px; color: {t.PRIMARY};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; background-color: {t.SURFACE}; color: {t.PRIMARY}; }}

/* ═══════════════════════════ CHECKBOX / RADIO ═══════════════ */
QCheckBox, QRadioButton {{ color: {t.TEXT_PRIMARY}; spacing: 8px; font-size: 14px; }}
QCheckBox:focus, QRadioButton:focus {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px; height: 18px; border: 2px solid {t.BORDER}; border-radius: 5px; background-color: {t.SURFACE};
}}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:checked {{
    background-color: {t.PRIMARY}; border-color: {t.PRIMARY};
    {_checkmark_rule}
}}
QRadioButton::indicator:checked {{ background-color: {t.PRIMARY}; border-color: {t.PRIMARY}; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {t.PRIMARY}; }}
QCheckBox::indicator:checked:hover {{ background-color: {t.PRIMARY_DARK}; border-color: {t.PRIMARY_DARK}; }}

/* ═══════════════════════════ PROGRESS BAR ═══════════════════ */
QProgressBar {{
    border: 1.5px solid {t.BORDER}; border-radius: 10px; background-color: {t.SURFACE_ALT};
    text-align: center; color: {t.TEXT_PRIMARY}; font-weight: 600; height: 22px;
}}
QProgressBar::chunk {{ background: {t.gradient(t.PRIMARY_GRADIENT_START, t.SUCCESS_GRADIENT_END)}; border-radius: 6px; }}

/* ═══════════════════════════ CALENDAR POPUP ═════════════════ */
QCalendarWidget {{
    background-color: {t.SURFACE}; border: 1px solid {t.BORDER};
    border-radius: 12px; outline: none;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {t.gradient(t.PRIMARY_GRADIENT_START, t.PRIMARY_GRADIENT_END)};
    border-top-left-radius: 12px; border-top-right-radius: 12px;
    min-height: 40px;
}}
QCalendarWidget QToolButton {{
    color: {t.TEXT_ON_PRIMARY}; background: transparent; border: none;
    border-radius: 8px; font-size: 13px; font-weight: 700;
    icon-size: 16px, 16px; padding: 4px 8px; margin: 4px 2px;
}}
QCalendarWidget QToolButton:hover {{ background: rgba(255,255,255,0.18); }}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QSpinBox {{
    color: {t.TEXT_ON_PRIMARY}; background: rgba(255,255,255,0.12);
    border: none; border-radius: 6px; padding: 2px 6px; font-weight: 700;
}}
QCalendarWidget QMenu {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER}; border-radius: 10px; padding: 4px;
}}
QCalendarWidget QAbstractItemView {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    selection-background-color: {t.PRIMARY}; selection-color: {t.TEXT_ON_PRIMARY};
    outline: none; border: none; font-size: 13px;
    gridline-color: transparent;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {t.TEXT_MUTED}; }}
QCalendarWidget QTableView {{ border: none; }}

/* ═══════════════════════════ MENU / TOOLTIP ═════════════════ */
QMenu {{ background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: {t.PRIMARY_LIGHT}; color: {t.PRIMARY_DARK}; }}
QToolTip {{ background-color: {t.TOOLTIP_BG}; color: {t.TOOLTIP_FG}; border: none; border-radius: 6px; padding: 6px 10px; font-size: 12px; }}

/* ═══════════════════════════ SCROLL AREA ════════════════════ */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ═══════════════════════════ MESSAGE BOX ════════════════════ */
QMessageBox {{ background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY}; }}
QMessageBox QLabel {{ color: {t.TEXT_PRIMARY}; }}
QMessageBox QPushButton {{ min-width: 88px; min-height: 34px; }}

/* ═══════════════════════════ SPLITTER ═══════════════════════ */
QSplitter::handle {{ background-color: {t.DIVIDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ═══════════════════════════ NAMED WIDGETS ══════════════════ */
QWidget#sidebar {{ background-color: {t.SIDEBAR_BG}; border-right: 1px solid {t.BORDER}; }}
QWidget#topBar {{ background-color: {t.TOPBAR_BG}; border-bottom: 1px solid {t.TOPBAR_BORDER}; }}
QWidget#topBar QComboBox {{ font-size: 13px; padding: 6px 10px; }}
QWidget#topBar QPushButton {{ font-size: 13px; padding: 6px 12px; }}
QWidget#contentArea {{ background-color: {t.BG}; }}
QFrame#card {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 12px; }}
QFrame#card:focus {{ border: 2px solid {t.FOCUS_RING}; }}
QFrame#filterBar {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 10px; padding: 6px 4px; }}
QFrame#stepCard {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 12px; }}
QFrame#dividerLine {{ background-color: {t.DIVIDER}; border: none; max-height: 1px; }}
QLabel#pageTitle    {{ color: {t.TEXT_HEADING}; font-size: 20px; font-weight: 700; }}
QLabel#sectionTitle {{ color: {t.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; }}
QLabel#errorLabel   {{ color: {t.DANGER};         font-size: 12px; }}
QLabel#warningLabel {{ color: {t.WARNING};        font-size: 12px; }}
QLabel#successLabel {{ color: {t.SUCCESS};        font-size: 12px; }}
QLabel#mutedLabel   {{ color: {t.TEXT_MUTED};     font-size: 12px; }}

/* Sidebar navigation items */
QToolButton[nav_item="true"] {{
    background: transparent;
    border: none;
    border-radius: 10px;
    margin: 2px 10px;
    padding: 0px;
}}
QToolButton[nav_item="true"]:hover {{
    background-color: {t.SIDEBAR_HOVER};
    border-radius: 10px;
    margin: 2px 10px;
}}
QToolButton[nav_item="true"]:checked {{
    background-color: {t.SIDEBAR_ACTIVE};
    border: none;
    border-radius: 10px;
    margin: 2px 10px;
}}
QWidget[nav_item="true"]:focus {{ outline: 2px solid {t.FOCUS_RING}; outline-offset: 2px; }}

/* ═══════════════════════════ TRANSPARENT CONTAINERS ══════════════ */
QWidget#transparentBg {{ background: transparent; border: none; }}
QFrame#transparentBg {{ background: transparent; border: none; }}
QWidget#transparentSurface {{ background: transparent; }}
QFrame#transparentSurface {{ background: transparent; }}

/* ═══════════════════════════ RESULT LABELS ════════════════════════ */
QLabel#resultLabel {{ color: {t.TEXT_PRIMARY}; font-size: 13px; border: none; background: transparent; padding: 0; margin: 0; }}
QLabel#resultLabelBold {{ color: {t.TEXT_PRIMARY}; font-size: 14px; font-weight: 700; border: none; background: transparent; padding: 0; margin: 0; }}

/* ═══════════════════════════ PAYABLE/REFUND LABELS ════════════════ */
QLabel#payableLabel {{ color: {t.TEXT_SECONDARY}; font-size: 15px; font-weight: 700; }}
QLabel#payableLabel[variant="danger"] {{ color: {t.DANGER}; }}
QLabel#payableLabel[variant="success"] {{ color: {t.SUCCESS}; }}
QLabel#payableLabel[variant="neutral"] {{ color: {t.TEXT_SECONDARY}; }}

/* ═══════════════════════════ ACCOUNT CARDS ════════════════════════ */
QFrame#listItem {{ background: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 10px; padding: 16px 20px; }}
QFrame#listItem:hover {{ background: {t.SURFACE_ALT}; border-color: {t.PRIMARY}; }}
QFrame#accountCard {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 12px; }}
QFrame#accountCard:hover {{ border-color: {t.PRIMARY}; background-color: {t.SURFACE_ALT}; }}

/* ═══════════════════════════ DIVIDERS ══════════════════════════════ */
QFrame#divider {{ background-color: {t.DIVIDER}; border: none; max-height: 1px; }}
QFrame#accentDivider {{ border: none; max-height: 1px; }}
QFrame#accentDivider[variant="primary"] {{ background-color: {t.PRIMARY}; }}
QFrame#accentDivider[variant="success"] {{ background-color: {t.SUCCESS}; }}
QFrame#accentDivider[variant="warning"] {{ background-color: {t.WARNING}; }}
QFrame#accentDivider[variant="info"] {{ background-color: {t.INFO}; }}

/* ═══════════════════════════ RESULT SECTIONS ═══════════════════════ */
QFrame#taxRegimeCard {{ border-left: 4px solid {t.PRIMARY}; }}
QFrame#taxRegimeCard[variant="primary"] {{ border-color: {t.PRIMARY}; }}
QFrame#taxRegimeCard[variant="accent"] {{ border-left: 4px solid {t.PRIMARY}; }}

/* ═══════════════════════════ ACCOUNT CARDS WITH ACCENTS ════════════ */
QFrame#accountCard[variant="savings"] {{ border-left: 4px solid {t.SUCCESS}; }}
QFrame#accountCard[variant="current"] {{ border-left: 4px solid {t.PRIMARY}; }}
QFrame#accountCard[variant="salary"] {{ border-left: 4px solid {t.TEAL}; }}
QFrame#accountCard[variant="fd-linked"] {{ border-left: 4px solid {t.WARNING}; }}
QFrame#accountCard[variant="savings"]:hover {{ border-color: {t.SUCCESS}; border-left-color: {t.SUCCESS}; }}
QFrame#accountCard[variant="current"]:hover {{ border-color: {t.PRIMARY}; border-left-color: {t.PRIMARY}; }}
QFrame#accountCard[variant="salary"]:hover {{ border-color: {t.TEAL}; border-left-color: {t.TEAL}; }}
QFrame#accountCard[variant="fd-linked"]:hover {{ border-color: {t.WARNING}; border-left-color: {t.WARNING}; }}

/* ═══════════════════════════ SETTINGS SCREEN ═════════════════════════ */
QLabel#themeLiveIndicator {{ color: {t.SUCCESS}; font-size: 11px; font-weight: 700; background: transparent; }}

/* ═══════════════════════════ TAX SCREEN — BADGES ════════════════════ */
QLabel#ctxBadge {{ border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 600; }}
QLabel#ctxBadge[variant="person"] {{ background: {t.PRIMARY_LIGHT}; color: {t.PRIMARY_DARK}; }}
QLabel#ctxBadge[variant="fy"] {{ background: {t.SURFACE_ALT}; color: {t.TEXT_SECONDARY}; }}
QLabel#ctxBadge[variant="source"] {{ background: {t.INFO_LIGHT}; color: {t.INFO_DARK}; }}

/* ═══════════════════════════ TAX SCREEN — CARDS ════════════════════ */
QFrame#TaxHeaderCard {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 14px; padding: 0; }}
QFrame#TaxContextPanel {{ background-color: {t.SURFACE_TINT_START}; border: 1px solid {t.BORDER}; border-radius: 12px; padding: 14px 12px; }}
QFrame#NetPayableCard {{ background-color: {t.SURFACE_ALT}; border: 1px solid {t.BORDER}; border-radius: 12px; padding: 16px; }}
QFrame#ProjSlabCard {{ background-color: {t.SURFACE_ALT}; border: 1px solid {t.BORDER}; border-radius: 12px; padding: 14px; }}

/* ═══════════════════════════ TAX SCREEN — REGIME CARDS WITH ACCENT ══ */
QFrame#TaxRegimeCard {{ border-radius: 12px; padding: 0; }}
QFrame#TaxRegimeCard[variant="primary"] {{ background-color: {t.PRIMARY_LIGHT}; border: 1px solid {t.PRIMARY}; border-left: 4px solid {t.PRIMARY}; }}

/* ═══════════════════════════ SETTINGS SCREEN ════════════════════════ */
QFrame#SettingsHdr {{ background: {t.gradient(t.HERO_GRADIENT_START, t.HERO_GRADIENT_END)}; border-radius: 14px; }}
QFrame#ThemeContainer {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 14px; }}
QFrame#ThemeDescBar {{ background-color: {t.SURFACE_ALT}; border: 1px solid {t.BORDER}; border-radius: 8px; }}
QFrame#SettingsCard {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 12px; padding: 14px; }}
QGroupBox#SettingsGroup {{ border: none; margin-top: 4px; background: transparent; font-size: 13px; font-weight: 700; color: {t.PRIMARY_DARK}; }}
QGroupBox#SettingsGroup::title {{ subcontrol-origin: margin; left: 2px; padding: 0 6px; }}
QLabel#hdrTitle {{ color: white; background: transparent; border: none; }}
QLabel#hdrSubtitle {{ color: rgba(255,255,255,0.82); font-size: 12px; background: transparent; border: none; }}
QLabel#rowLabel {{ color: {t.TEXT_SECONDARY}; font-size: 12px; font-weight: 700; background: {t.SURFACE_ALT}; border-radius: 6px; padding: 4px 10px; }}

/* ═══════════════════════════ ACCOUNTS SCREEN ═══════════════════════ */
QLabel#accountMetricLabel {{ font-size: 11px; color: {t.TEXT_MUTED}; }}
QLabel#accountMetricValue {{ font-size: 15px; font-weight: 700; }}
QLabel#accountMetricValue[variant="success"] {{ color: {t.SUCCESS}; }}
QLabel#accountMetricValue[variant="warning"] {{ color: {t.WARNING}; }}
QLabel#accountMetricValue[variant="info"] {{ color: {t.INFO}; }}
QLabel#accountMetricValue[variant="teal"] {{ color: {t.TEAL}; }}

/* ═══════════════════════════ DASHBOARD SCREEN ════════════════════════ */
QWidget#brand {{ background: {t.gradient(t.HERO_GRADIENT_START, t.HERO_GRADIENT_END, diagonal=True)}; }}
QLabel#navLabel {{ color: {t.TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; padding-left: 20px; }}
QLabel[objectName="nav_label"] {{ color: {t.SIDEBAR_TEXT}; background: transparent; padding-right: 12px; }}
QLabel[objectName="nav_label"][active="true"] {{ color: {t.SIDEBAR_ACTIVE_TEXT}; font-weight: 700; }}
QLabel#verLabel {{ color: {t.TEXT_MUTED}; font-size: 10px; }}
QLabel#brandText {{ color: white; background: transparent; }}
QLabel#brandIcon {{ color: white; font-size: 14px; font-weight: 700; background: transparent; }}
QLabel#navIcon {{ background: transparent; }}
QLabel#pageTitle {{ color: {t.TEXT_HEADING}; font-size: 15px; font-weight: 700; }}
QPushButton#sidebarToggle {{ background: transparent; border: none; border-top: 1px solid {t.SIDEBAR_HOVER}; margin: 0px; }}
QPushButton#sidebarToggle:hover {{ background-color: {t.SIDEBAR_HOVER}; }}
QFrame#overviewBanner {{ background: {t.gradient(t.HERO_GRADIENT_START, t.HERO_GRADIENT_END)}; border-radius: 16px; }}
QLabel#bannerTitle {{ color: white; background: transparent; }}
QLabel#bannerFyLabel {{ color: rgba(255,255,255,0.82); font-size: 13px; background: transparent; }}
QFrame#errorFrame {{ background-color: {t.SURFACE}; border: 2px solid {t.DANGER}; border-radius: 12px; padding: 24px; }}
QLabel#errorTitle {{ color: {t.DANGER}; background: transparent; }}
QLabel#errorMessage {{ color: {t.TEXT_PRIMARY}; background: transparent; }}

/* ═══════════════════════════ FIXED DEPOSITS SCREEN ════════════════════ */
QLabel#fdTitle {{ color: {t.TEXT_PRIMARY}; }}
QLabel#fdSubtitle {{ color: {t.TEXT_SECONDARY}; font-size: 12px; }}
QLabel#fdInfoLabel {{ color: {t.INFO}; font-size: 11px; padding: 4px; }}
QLabel#fdStatusLabel {{ color: {t.WARNING}; font-weight: 600; }}
QLabel#fdMaturityDateLabel {{ font-weight: 700; color: {t.TEXT_PRIMARY}; }}
QLabel#fdMaturityAmountLabel {{ font-weight: 700; font-size: 15px; color: {t.SUCCESS}; }}
QLabel#fdMaturityFormulaLabel {{ font-weight: 700; color: {t.TEXT_PRIMARY}; }}

/* ═══════════════════════════ STATEMENT IMPORT SCREEN ═════════════════ */
QLabel#importTitle {{ color: {t.TEXT_PRIMARY}; font-size: 15px; }}
QLabel#importStatusLabel {{ color: {t.TEXT_PRIMARY}; font-size: 13px; font-weight: 700; }}
QPlainTextEdit#importDebugOutput {{ background: {t.SURFACE_ALT}; color: {t.TEXT_SECONDARY}; border: 1px solid {t.BORDER}; border-radius: 8px; font-size: 11px; font-family: 'Consolas', 'Courier New', monospace; padding: 8px; }}
QLabel#importStepDot {{ border-radius: 13px; }}
QLabel#importStepLine {{ background: transparent; }}
QFrame#importStepCard {{ background: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 12px; padding: 16px; }}
QLabel#fileLabel {{ background: {t.SURFACE_ALT}; color: {t.TEXT_SECONDARY}; border: 2px dashed {t.BORDER}; border-radius: 10px; padding: 12px 16px; font-size: 13px; }}
QLabel#previewSummaryLabel {{ color: {t.TEXT_PRIMARY}; font-size: 13px; font-weight: 700; }}

/* ═══════════════════════════ AIS/TIS IMPORT SCREEN ═══════════════════ */
QFrame#aisTisHeaderFrame {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 10px; padding: 12px; }}
QLabel#aisTisTitle {{ color: {t.TEXT_PRIMARY}; font-size: 14px; font-weight: 700; }}
QLabel#aisTisPersonLabel {{ color: {t.TEXT_SECONDARY}; font-size: 11px; font-weight: 500; }}
QLabel#aisTisPersonLabel[variant="warning"] {{ color: {t.WARNING}; font-size: 11px; font-weight: 500; }}
QLabel#aisTisPersonLabel[variant="selected"] {{ color: {t.TEXT_PRIMARY}; font-size: 11px; font-weight: 600; }}
QLabel#aisTisCountLabel {{ color: {t.TEXT_MUTED}; font-size: 11px; }}
QFrame#aisTisDebugFrame {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 8px; padding: 8px; }}
QLabel#aisTisDebugTitle {{ color: {t.TEXT_SECONDARY}; font-size: 11px; font-weight: 600; }}
QTextEdit#aisTisDebugText {{ background: {t.SURFACE_ALT}; border: 1px solid {t.BORDER}; border-radius: 6px; padding: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: 10px; color: {t.TEXT_PRIMARY}; }}
QPushButton#aisTisCloseDebugBtn {{ background: transparent; border: none; color: {t.TEXT_SECONDARY}; font-weight: bold; }}
QPushButton#aisTisCloseDebugBtn:hover {{ color: {t.DANGER}; }}

/* ═══════════════════════════ SETUP SCREEN ════════════════════════════ */
QWidget#setupWindow {{ background-color: {t.BG}; }}
QFrame#setupCard {{ background-color: {t.SURFACE_TINT_START}; border: 1px solid {t.BORDER}; border-radius: 16px; padding: 0px; }}
QFrame#setupStrip {{ background: {t.gradient(t.PRIMARY_GRADIENT_START, t.PRIMARY_GRADIENT_END)}; border-radius: 2px; }}
QLabel#setupTitle {{ color: {t.TEXT_PRIMARY}; font-size: 22px; font-weight: 700; }}
QLabel#setupSubtitle {{ color: {t.TEXT_SECONDARY}; font-size: 13px; }}
QLabel#setupFieldLabel {{ color: {t.TEXT_PRIMARY}; font-size: 13px; font-weight: 600; }}
QLabel#setupNote {{ color: {t.WARNING}; font-size: 11px; }}
QLabel#setupStrengthLabel {{ color: {t.TEXT_MUTED}; font-size: 11px; }}
QLabel#setupStrengthLabel[strength="weak"] {{ color: {t.DANGER}; font-size: 11px; }}
QLabel#setupStrengthLabel[strength="moderate"] {{ color: {t.WARNING}; font-size: 11px; }}
QLabel#setupStrengthLabel[strength="strong"] {{ color: {t.SUCCESS}; font-size: 11px; }}
QFrame#setupStrengthBar {{ background: {t.BORDER}; border-radius: 2px; }}
QFrame#setupStrengthBar[strength="weak"] {{ background: {t.gradient(t.DANGER_GRADIENT_START, t.DANGER_GRADIENT_END)}; border-radius: 2px; }}
QFrame#setupStrengthBar[strength="moderate"] {{ background: {t.gradient(t.WARNING_GRADIENT_START, t.WARNING_GRADIENT_END)}; border-radius: 2px; }}
QFrame#setupStrengthBar[strength="strong"] {{ background: {t.gradient(t.SUCCESS_GRADIENT_START, t.SUCCESS_GRADIENT_END)}; border-radius: 2px; }}
QCheckBox#setupTotpCheck {{ color: {t.TEXT_SECONDARY}; font-size: 12px; }}

/* ═══════════════════════════ TEXT ROLES ════════════════════════════ */
/* Title variants */
QLabel[textrole="title-sm"] {{ color: {t.TEXT_HEADING}; font-size: 14px; font-weight: 700; }}
QLabel[textrole="title-md"] {{ color: {t.TEXT_HEADING}; font-size: 15px; font-weight: 700; }}
QLabel[textrole="title-lg"] {{ color: {t.TEXT_HEADING}; font-size: 16px; font-weight: 700; }}
QLabel[textrole="title-xl"] {{ color: {t.TEXT_HEADING}; font-size: 18px; font-weight: 700; }}

/* Section/label roles */
QLabel[textrole="section-label"] {{ color: {t.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; }}

/* Muted text roles */
QLabel[textrole="muted-sm"] {{ color: {t.TEXT_MUTED}; font-size: 11px; font-weight: 400; }}
QLabel[textrole="muted-md"] {{ color: {t.TEXT_MUTED}; font-size: 12px; font-weight: 400; }}
QLabel[textrole="muted-lg"] {{ color: {t.TEXT_MUTED}; font-size: 14px; font-weight: 400; }}

/* Secondary text roles */
QLabel[textrole="secondary-sm"] {{ color: {t.TEXT_SECONDARY}; font-size: 12px; font-weight: 400; }}
QLabel[textrole="secondary-md"] {{ color: {t.TEXT_SECONDARY}; font-size: 13px; font-weight: 400; }}
QLabel[textrole="secondary-lg"] {{ color: {t.TEXT_SECONDARY}; font-size: 14px; font-weight: 400; }}

/* Body/primary text roles */
QLabel[textrole="body-sm"] {{ color: {t.TEXT_PRIMARY}; font-size: 11px; font-weight: 400; }}
QLabel[textrole="body-md"] {{ color: {t.TEXT_PRIMARY}; font-size: 13px; font-weight: 400; }}
QLabel[textrole="body-lg"] {{ color: {t.TEXT_PRIMARY}; font-size: 14px; font-weight: 400; }}

/* Emphasis text roles */
QLabel[textrole="emphasis-sm"] {{ color: {t.TEXT_PRIMARY}; font-size: 11px; font-weight: 600; }}
QLabel[textrole="emphasis-md"] {{ color: {t.TEXT_PRIMARY}; font-size: 13px; font-weight: 700; }}
QLabel[textrole="emphasis-lg"] {{ color: {t.TEXT_PRIMARY}; font-size: 14px; font-weight: 700; }}
QLabel[textrole="emphasis-xl"] {{ color: {t.TEXT_PRIMARY}; font-size: 16px; font-weight: 700; }}

/* Metric value roles - base and semantic variants */
QLabel[textrole="metric"] {{ color: {t.TEXT_SECONDARY}; font-size: 15px; font-weight: 700; }}
QLabel[textrole="metric"][color="success"] {{ color: {t.SUCCESS}; }}
QLabel[textrole="metric"][color="danger"] {{ color: {t.DANGER}; }}
QLabel[textrole="metric"][color="warning"] {{ color: {t.WARNING}; }}
QLabel[textrole="metric"][color="info"] {{ color: {t.INFO}; }}
QLabel[textrole="metric"][color="teal"] {{ color: {t.TEAL}; }}
QLabel[textrole="metric"][color="primary"] {{ color: {t.PRIMARY}; }}

/* Semantic text colors (for dynamic labels) */
QLabel[textrole="label"][color="danger"] {{ color: {t.DANGER}; }}
QLabel[textrole="label"][color="success"] {{ color: {t.SUCCESS}; }}
QLabel[textrole="label"][color="warning"] {{ color: {t.WARNING}; }}
QLabel[textrole="label"][color="primary"] {{ color: {t.PRIMARY}; }}
"""
