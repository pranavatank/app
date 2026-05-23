"""
ui/theme/constants.py — Re-exports from the active theme module.

This file is the single import point for all color/shadow constants
throughout the app. At startup, ThemeManager patches the values here
by updating the Theme class directly. This file now simply mirrors
the default (Ocean Blue) values so static imports still work before
the manager runs.

All new code should use Theme.ATTRIBUTE not import from constants directly.
"""

# Re-export everything from default theme so existing
# `from . import constants as c` and `c.PRIMARY` calls keep working.
from .theme_ocean_blue import (
    NAME, DESCRIPTION, IS_DARK,
    PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, PRIMARY_TEXT,
    PRIMARY_GRADIENT_START, PRIMARY_GRADIENT_END,
    PRIMARY_GRADIENT_HOVER_START, PRIMARY_GRADIENT_HOVER_END,
    SUCCESS, SUCCESS_DARK, SUCCESS_LIGHT,
    SUCCESS_GRADIENT_START, SUCCESS_GRADIENT_END,
    DANGER, DANGER_DARK, DANGER_LIGHT,
    DANGER_GRADIENT_START, DANGER_GRADIENT_END,
    WARNING, WARNING_DARK, WARNING_LIGHT,
    WARNING_GRADIENT_START, WARNING_GRADIENT_END,
    INFO, INFO_DARK, INFO_LIGHT,
    INFO_GRADIENT_START, INFO_GRADIENT_END,
    EDIT, EDIT_DARK, EDIT_LIGHT,
    EDIT_GRADIENT_START, EDIT_GRADIENT_END,
    HERO_GRADIENT_START, HERO_GRADIENT_END,
    HERO_GRADIENT_HOVER_START, HERO_GRADIENT_HOVER_END,
    PURPLE, PURPLE_LIGHT, TEAL, TEAL_LIGHT, ORANGE, ORANGE_LIGHT, PINK, PINK_LIGHT,
    BG, SURFACE, SURFACE_ALT, SURFACE_TINT_START, SURFACE_TINT_END,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_ACTIVE, SIDEBAR_ACTIVE_TEXT, SIDEBAR_HOVER,
    TOPBAR_BG, TOPBAR_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_ON_PRIMARY, TEXT_HEADING,
    BORDER, BORDER_FOCUS, DIVIDER,
    SHADOW_BLUR_CARD, SHADOW_BLUR_ELEVATED,
    SHADOW_OFFSET_Y, SHADOW_OFFSET_Y_ELEVATED,
    SHADOW_RGBA_CARD, SHADOW_RGBA_ELEVATED, SHADOW_RGBA_PRIMARY,
    CHART_COLORS, CHART_COLORS_LIGHT,
)

# Legacy aliases kept for any old code that referenced these names
SHADOW_COLOR_LIGHT   = "rgba(15,23,42,0.07)"
SHADOW_COLOR_MEDIUM  = "rgba(15,23,42,0.12)"
SHADOW_COLOR_STRONG  = "rgba(37,99,235,0.18)"
