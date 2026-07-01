"""
ui/theme/components.py — Reusable style-string builders consumed by Theme.
Shadows use Theme.SHADOW_RGBA_* so they adapt per theme (dark themes glow).
"""

from __future__ import annotations


# ── Gradient ──────────────────────────────────────────────────────────────────
def gradient(start: str, end: str, diagonal: bool = False) -> str:
    if diagonal:
        return f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {start},stop:1 {end})"
    return f"qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {start},stop:1 {end})"


def gradient_v(start: str, end: str) -> str:
    return f"qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {start},stop:1 {end})"


# ── Shadow ────────────────────────────────────────────────────────────────────
def make_shadow(blur=18, offset_x=0, offset_y=4, color_rgba=(15, 23, 42, 18)):
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect
    from PyQt6.QtGui import QColor
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setOffset(offset_x, offset_y)
    r, g, b, a = color_rgba
    effect.setColor(QColor(r, g, b, a))
    return effect


def card_shadow(theme=None):
    rgba = getattr(theme, "SHADOW_RGBA_CARD", (15, 23, 42, 16)) if theme else (15, 23, 42, 16)
    blur = getattr(theme, "SHADOW_BLUR_CARD", 16) if theme else 16
    return make_shadow(blur=blur, offset_y=3, color_rgba=rgba)


def elevated_shadow(theme=None):
    rgba = getattr(theme, "SHADOW_RGBA_ELEVATED", (15, 23, 42, 26)) if theme else (15, 23, 42, 26)
    blur = getattr(theme, "SHADOW_BLUR_ELEVATED", 28) if theme else 28
    return make_shadow(blur=blur, offset_y=7, color_rgba=rgba)


def primary_shadow(theme=None):
    rgba = getattr(theme, "SHADOW_RGBA_PRIMARY", (37, 99, 235, 36)) if theme else (37, 99, 235, 36)
    return make_shadow(blur=20, offset_y=5, color_rgba=rgba)


def success_shadow():
    return make_shadow(blur=20, offset_y=5, color_rgba=(22, 163, 74, 32))


def danger_shadow():
    return make_shadow(blur=20, offset_y=5, color_rgba=(220, 38, 38, 30))


# ── Text helpers ──────────────────────────────────────────────────────────────
def text_style(theme, color=None, size=14, weight=400, background="transparent"):
    return (
        f"color: {color or theme.TEXT_PRIMARY}; "
        f"font-size: {size}px; font-weight: {weight}; "
        f"background: {background};"
    )


def title_style(theme, size=15):
    return text_style(theme, color=getattr(theme, "TEXT_HEADING", theme.TEXT_PRIMARY),
                      size=size, weight=700)


def muted_style(theme, size=12):
    return text_style(theme, color=theme.TEXT_SECONDARY, size=size, weight=400)


def section_label_style(theme, size=12):
    return text_style(theme, color=theme.TEXT_SECONDARY, size=size, weight=600)


# ── Badge / pill ──────────────────────────────────────────────────────────────
def badge_style(theme, bg, fg, radius=12, padding="5px 14px", size=12, weight=600):
    return (
        f"background-color: {bg}; color: {fg}; "
        f"border-radius: {radius}px; padding: {padding}; "
        f"font-size: {size}px; font-weight: {weight}; border: none;"
    )


# ── Cards ─────────────────────────────────────────────────────────────────────
def card_style(theme, bg=None, border_color=None, radius=12, padding=14,
               left_accent=None, selector="QFrame"):
    base_bg     = bg or theme.SURFACE
    base_border = border_color or theme.BORDER
    left_border = f"border-left: 4px solid {left_accent};" if left_accent else ""
    return f"""
        {selector} {{
            background-color: {base_bg};
            border: 1px solid {base_border};
            {left_border}
            border-radius: {radius}px;
            padding: {padding}px;
        }}
    """


def metric_card_style(theme, accent, bg, radius=14):
    return f"""
        QFrame {{
            background: {gradient_v(theme.SURFACE, bg)};
            border: 1px solid {accent}2E;
            border-top: 3px solid {accent};
            border-radius: {radius}px;
        }}
    """


def filter_bar_style(theme, radius=10):
    return f"""
        QFrame#filterBar {{
            background-color: {theme.SURFACE};
            border: 1px solid {theme.BORDER};
            border-radius: {radius}px;
        }}
    """


def group_box_style(theme):
    return f"""
        QGroupBox {{
            border: 1px solid {theme.BORDER};
            border-radius: 12px;
            margin-top: 18px;
            padding: 16px 16px 12px 16px;
            background-color: {theme.SURFACE};
            font-weight: 700; font-size: 14px;
            color: {theme.PRIMARY};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px; padding: 0 6px;
            background-color: {theme.SURFACE};
            color: {theme.PRIMARY};
        }}
    """


def panel_strip_style(theme, start=None, end=None, radius=2):
    g = gradient(start or theme.PRIMARY, end or theme.SUCCESS)
    return f"background: {g}; border-radius: {radius}px;"


def tinted_surface_style(theme, radius=12, border_color=None, selector="QFrame"):
    bg     = theme.SURFACE_ALT
    border = border_color or theme.BORDER
    return f"""
        {selector} {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {radius}px;
        }}
    """


def info_banner_style(theme, accent=None, radius=10):
    a = accent or theme.PRIMARY
    return f"""
        QFrame {{
            background: {gradient_v(theme.PRIMARY_LIGHT, theme.SURFACE)};
            border: 1px solid {a}50;
            border-left: 4px solid {a};
            border-radius: {radius}px;
        }}
    """


def regime_card_style(theme, accent, radius=12):
    return f"""
        QFrame {{
            background-color: {theme.SURFACE};
            border: 1px solid {theme.BORDER};
            border-top: 3px solid {accent};
            border-radius: {radius}px;
        }}
    """


def banner_style(theme, level="info", radius=10):
    colors = {
        "info":    (theme.INFO_LIGHT,    theme.INFO,    theme.INFO_DARK),
        "success": (theme.SUCCESS_LIGHT, theme.SUCCESS, theme.SUCCESS_DARK),
        "warning": (theme.WARNING_LIGHT, theme.WARNING, theme.WARNING_DARK),
        "danger":  (theme.DANGER_LIGHT,  theme.DANGER,  theme.DANGER_DARK),
    }
    bg, border, text = colors.get(level, colors["info"])
    return f"""
        QFrame {{
            background: {gradient_v(bg, theme.SURFACE)};
            border: 1px solid {border}50;
            border-left: 4px solid {border};
            border-radius: {radius}px;
        }}
    """


def sidebar_nav_normal():
    from .theme import Theme
    return f"""
        QPushButton {{
            background: transparent; color: {Theme.SIDEBAR_TEXT};
            border: none; border-radius: 0;
            text-align: left; padding-left: 8px; font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {Theme.SIDEBAR_HOVER}; color: white; }}
    """


def sidebar_nav_active():
    from .theme import Theme
    return f"""
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {Theme.SIDEBAR_ACTIVE}, stop:1 {Theme.SIDEBAR_HOVER});
            color: white; border: none;
            border-left: 3px solid {Theme.PRIMARY_LIGHT};
            border-radius: 0; text-align: left;
            padding-left: 8px; font-size: 13px; font-weight: 700;
        }}
    """


def chat_bubble_user(theme):
    return f"""
        QFrame {{
            background: {gradient(theme.PRIMARY_GRADIENT_START, theme.PRIMARY_GRADIENT_END)};
            border: none; border-radius: 16px;
            padding: 12px 16px;
        }}
    """


def chat_bubble_assistant(theme):
    return f"""
        QFrame {{
            background-color: {theme.SURFACE};
            border: 1px solid {theme.BORDER};
            border-radius: 16px;
            padding: 12px 16px;
        }}
    """


def chat_input_box(theme):
    return f"""
        QPlainTextEdit {{
            background-color: {theme.SURFACE};
            color: {theme.TEXT_PRIMARY};
            border: 2px solid {theme.BORDER};
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 14px;
        }}
        QPlainTextEdit:focus {{
            border: 2px solid {theme.PRIMARY};
        }}
    """


def attachment_chip(theme):
    return f"""
        QFrame {{
            background-color: {theme.SURFACE_ALT};
            border: 1px solid {theme.BORDER};
            border-radius: 8px;
            padding: 6px 10px;
        }}
    """
