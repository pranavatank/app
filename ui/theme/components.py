"""
Reusable style builders consumed by Theme.
"""


def gradient(start, end, diagonal=False):
    if diagonal:
        return f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {start},stop:1 {end})"
    return f"qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {start},stop:1 {end})"


def text_style(theme, color=None, size=14, weight=400, background="transparent"):
    return (
        f"color: {color or theme.TEXT_PRIMARY}; "
        f"font-size: {size}px; "
        f"font-weight: {weight}; "
        f"background: {background};"
    )


def title_style(theme, size=15):
    return text_style(theme, color=theme.TEXT_PRIMARY, size=size, weight=700)


def muted_style(theme, size=12):
    return text_style(theme, color=theme.TEXT_SECONDARY, size=size, weight=400)


def section_label_style(theme, size=12):
    return text_style(theme, color=theme.TEXT_SECONDARY, size=size, weight=600)


def badge_style(theme, bg, fg, radius=12, padding="5px 14px", size=12, weight=600):
    return (
        f"background-color: {bg}; "
        f"color: {fg}; "
        f"border-radius: {radius}px; "
        f"padding: {padding}; "
        f"font-size: {size}px; "
        f"font-weight: {weight};"
    )


def card_style(
    theme,
    bg=None,
    border_color=None,
    radius=12,
    padding=14,
    left_accent=None,
    selector="QFrame",
):
    base_bg = bg or theme.SURFACE
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
            font-weight: 700;
            font-size: 14px;
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
    bg = theme.SURFACE_ALT
    border = border_color or theme.BORDER
    return f"""
        {selector} {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {radius}px;
        }}
    """
