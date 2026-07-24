"""
ui/theme/theme.py — Live Theme class. Color attributes are patched at runtime
by ThemeManager.apply(). All UI code imports Theme from here and calls
Theme.ATTRIBUTE or Theme.method() — never imports from theme_*.py directly.
"""

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect

from . import components as tc
from . import constants as c   # default (Ocean Blue) values at import time


class Theme:
    # ── Color tokens (defaults = Ocean Blue, overwritten by ThemeManager) ─────
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
                    color: #FFFFFF; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.gradient(t.PRIMARY_GRADIENT_HOVER_START, t.PRIMARY_GRADIENT_HOVER_END)}; }}
                QPushButton:pressed{{ background: {t.PRIMARY_DARK}; padding-top: 3px; }}
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
                    color: #FFFFFF; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.SUCCESS_DARK}; }}
                QPushButton:pressed{{ background: {t.SUCCESS_DARK}; padding-top: 3px; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "danger": f"""
                QPushButton {{
                    background: {t.gradient(t.DANGER_GRADIENT_START, t.DANGER_GRADIENT_END)};
                    color: #FFFFFF; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.DANGER_DARK}; }}
                QPushButton:pressed{{ background: {t.DANGER_DARK}; padding-top: 3px; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "warning": f"""
                QPushButton {{
                    background: {t.gradient(t.WARNING_GRADIENT_START, t.WARNING_GRADIENT_END)};
                    color: #FFFFFF; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.WARNING_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "info": f"""
                QPushButton {{
                    background: {t.gradient(t.INFO_GRADIENT_START, t.INFO_GRADIENT_END)};
                    color: #FFFFFF; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.INFO_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "edit": f"""
                QPushButton {{
                    background: {t.gradient(t.EDIT_GRADIENT_START, t.EDIT_GRADIENT_END)};
                    color: #FFFFFF; border: none; border-radius: 10px;
                    padding: 4px 20px; font-size: 13px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.EDIT_DARK}; }}
                QPushButton:disabled{{ background: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; }}
            """,
            "hero": f"""
                QPushButton {{
                    background: {t.gradient(t.HERO_GRADIENT_START, t.HERO_GRADIENT_END)};
                    color: #FFFFFF; border: none; border-radius: 12px;
                    padding: 4px 26px; font-size: 14px; font-weight: 700;
                }}
                QPushButton:hover  {{ background: {t.gradient(t.HERO_GRADIENT_HOVER_START, t.HERO_GRADIENT_HOVER_END)}; }}
                QPushButton:pressed{{ background: {t.PRIMARY_DARK}; padding-top: 3px; }}
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
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 1.5px solid {t.PRIMARY}; }}
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
QComboBox:focus {{ border-color: {t.PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t.TEXT_SECONDARY}; margin-right: 8px;
}}
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
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{ border-color: {t.PRIMARY}; }}
QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover {{ border-color: {t.BORDER_FOCUS}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    border: none; width: 20px; background: {t.SURFACE_ALT};
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
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid {t.TEXT_SECONDARY};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {t.TEXT_SECONDARY};
}}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{ border-bottom-color: {t.PRIMARY}; }}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{ border-top-color: {t.PRIMARY}; }}
QDateEdit::drop-down {{ border: none; width: 28px; subcontrol-origin: border; subcontrol-position: right; }}
QDateEdit::down-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {t.TEXT_SECONDARY}; margin-right: 8px;
}}
QCalendarWidget QToolButton {{ color: {t.TEXT_PRIMARY}; background: transparent; font-weight: 600; }}
QCalendarWidget QMenu {{ background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY}; }}
QCalendarWidget QAbstractItemView:enabled {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    selection-background-color: {t.PRIMARY}; selection-color: #FFFFFF;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background-color: {t.SURFACE_ALT}; }}

/* ═══════════════════════════ BUTTONS ════════════════════════ */
QPushButton {{
    background: {t.gradient(t.PRIMARY_GRADIENT_START, t.PRIMARY_GRADIENT_END)};
    color: #FFFFFF; border: none; border-radius: 10px;
    padding: 8px 18px; font-size: 14px; font-weight: 600; min-height: 22px;
}}
QPushButton:hover   {{ background: {t.gradient(t.PRIMARY_GRADIENT_HOVER_START, t.PRIMARY_GRADIENT_HOVER_END)}; }}
QPushButton:pressed {{ background-color: {t.PRIMARY_DARK}; padding-top: 10px; }}
QPushButton:disabled {{ background-color: {t.SURFACE_ALT}; color: {t.TEXT_MUTED}; border: 1px solid {t.DIVIDER}; }}
QPushButton#primaryBtn   {{ background: {t.gradient(t.PRIMARY_GRADIENT_START,  t.PRIMARY_GRADIENT_END)};  color: #FFFFFF; }}
QPushButton#primaryBtn:hover {{ background: {t.gradient(t.PRIMARY_GRADIENT_HOVER_START, t.PRIMARY_GRADIENT_HOVER_END)}; }}
QPushButton#secondaryBtn {{ background: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1.5px solid {t.BORDER}; }}
QPushButton#secondaryBtn:hover {{ background: {t.PRIMARY_LIGHT}; border-color: {t.PRIMARY}; color: {t.PRIMARY_DARK}; }}
QPushButton#successBtn {{ background: {t.gradient(t.SUCCESS_GRADIENT_START, t.SUCCESS_GRADIENT_END)}; color: #FFFFFF; }}
QPushButton#dangerBtn  {{ background: {t.gradient(t.DANGER_GRADIENT_START,  t.DANGER_GRADIENT_END)};  color: #FFFFFF; }}
QPushButton#warningBtn {{ background: {t.gradient(t.WARNING_GRADIENT_START, t.WARNING_GRADIENT_END)}; color: #FFFFFF; }}
QPushButton#infoBtn    {{ background: {t.gradient(t.INFO_GRADIENT_START,    t.INFO_GRADIENT_END)};    color: #FFFFFF; }}
QPushButton#editBtn    {{ background: {t.gradient(t.EDIT_GRADIENT_START,    t.EDIT_GRADIENT_END)};    color: #FFFFFF; }}

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
    border: none; outline: none;
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
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t.BORDER}; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {t.PRIMARY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 7px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t.BORDER}; border-radius: 3px; min-width: 28px; }}
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
QTabBar::tab:selected {{ background-color: {t.PRIMARY}; color: #FFFFFF; font-weight: 700; border-color: {t.PRIMARY}; }}
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
    color: #FFFFFF; background: transparent; border: none;
    border-radius: 8px; font-size: 13px; font-weight: 700;
    icon-size: 16px, 16px; padding: 4px 8px; margin: 4px 2px;
}}
QCalendarWidget QToolButton:hover {{ background: rgba(255,255,255,0.18); }}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QSpinBox {{
    color: #FFFFFF; background: rgba(255,255,255,0.12);
    border: none; border-radius: 6px; padding: 2px 6px; font-weight: 700;
}}
QCalendarWidget QMenu {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER}; border-radius: 10px; padding: 4px;
}}
QCalendarWidget QAbstractItemView {{
    background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY};
    selection-background-color: {t.PRIMARY}; selection-color: #FFFFFF;
    outline: none; border: none; font-size: 13px;
    gridline-color: transparent;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {t.TEXT_MUTED}; }}
QCalendarWidget QTableView {{ border: none; }}

/* ═══════════════════════════ MENU / TOOLTIP ═════════════════ */
QMenu {{ background-color: {t.SURFACE}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: {t.PRIMARY_LIGHT}; color: {t.PRIMARY_DARK}; }}
QToolTip {{ background-color: {t.TEXT_PRIMARY}; color: #FFFFFF; border: none; border-radius: 6px; padding: 6px 10px; font-size: 12px; }}

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
QFrame#filterBar {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 10px; padding: 6px 4px; }}
QFrame#stepCard {{ background-color: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 12px; }}
QFrame#dividerLine {{ background-color: {t.DIVIDER}; border: none; max-height: 1px; }}
QLabel#pageTitle    {{ color: {t.TEXT_HEADING}; font-size: 20px; font-weight: 700; }}
QLabel#sectionTitle {{ color: {t.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; }}
QLabel#errorLabel   {{ color: {t.DANGER};         font-size: 12px; }}
QLabel#warningLabel {{ color: {t.WARNING};        font-size: 12px; }}
QLabel#successLabel {{ color: {t.SUCCESS};        font-size: 12px; }}
QLabel#mutedLabel   {{ color: {t.TEXT_MUTED};     font-size: 12px; }}
"""
