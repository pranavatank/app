"""
ui/theme/theme_slate_light.py — THEME: Slate (Light)
Neutral light theme — calm slate greys with a clear blue primary.
Clean, professional, minimalist design with excellent contrast and readability.
"""

NAME         = "Slate"
DESCRIPTION  = "Neutral light theme — calm slate greys with a clear blue primary"
IS_DARK      = False
EMOJI        = "🪨"

# ── Primary — clear blue ──────────────────────────────────────────────────────
PRIMARY                   = "#2563EB"
PRIMARY_DARK              = "#1D4DD5"
PRIMARY_LIGHT             = "#EFF6FF"
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#1D6EF2"
PRIMARY_GRADIENT_END      = "#1D4ED8"
PRIMARY_GRADIENT_HOVER_START = "#2563EB"
PRIMARY_GRADIENT_HOVER_END   = "#1E40AF"

# ── Success — vivid emerald ───────────────────────────────────────────────────
SUCCESS                   = "#059669"
SUCCESS_DARK              = "#047857"
SUCCESS_LIGHT             = "#ECFDF5"
SUCCESS_GRADIENT_START    = "#34D399"
SUCCESS_GRADIENT_END      = "#059669"

# ── Danger — vivid rose ───────────────────────────────────────────────────────
DANGER                    = "#DC2626"
DANGER_DARK               = "#B91C1C"
DANGER_LIGHT              = "#FEF2F2"
DANGER_GRADIENT_START     = "#E81131"
DANGER_GRADIENT_END       = "#B91C1C"

# ── Warning — vivid amber ─────────────────────────────────────────────────────
WARNING                   = "#D97706"
WARNING_DARK              = "#B45309"
WARNING_LIGHT             = "#FFFBEB"
WARNING_GRADIENT_START    = "#946E0B"
WARNING_GRADIENT_END      = "#9F4A09"

# ── Info — vivid cyan ─────────────────────────────────────────────────────────
INFO                      = "#0891B2"
INFO_DARK                 = "#0E7490"
INFO_LIGHT                = "#ECFEFF"
INFO_GRADIENT_START       = "#128090"
INFO_GRADIENT_END         = "#0D6B84"

# ── Edit — vivid fuchsia ───────────────────────────────────────────────────────
EDIT                      = "#C026D3"
EDIT_DARK                 = "#A21CAF"
EDIT_LIGHT                = "#FDF4FF"
EDIT_GRADIENT_START       = "#C515E0"
EDIT_GRADIENT_END         = "#A21CAF"

# ── Hero banner gradient — blue → cyan ────────────────────────────────────────
HERO_GRADIENT_START       = "#2563EB"
HERO_GRADIENT_END         = "#086B83"
HERO_GRADIENT_HOVER_START = "#1D4ED8"
HERO_GRADIENT_HOVER_END   = "#0D6B84"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#7C3AED";  PURPLE_LIGHT  = "#F5F3FF"
TEAL         = "#0D9488";  TEAL_LIGHT    = "#F0FDFA"
ORANGE       = "#EA580C";  ORANGE_LIGHT  = "#FFF7ED"
PINK         = "#DB2777";  PINK_LIGHT    = "#FDF2F8"

# ── Surfaces — clean slate white ──────────────────────────────────────────────
BG                        = "#F8FAFC"
SURFACE                   = "#FFFFFF"
SURFACE_ALT               = "#F1F5F9"
SURFACE_TINT_START        = "#FFFFFF"
SURFACE_TINT_END          = "#F1F5F9"

# ── Sidebar — light, matches the page background (not a fixed dark panel) ───
SIDEBAR_BG                = "#F8FAFC"
SIDEBAR_TEXT              = "#465467"
SIDEBAR_ACTIVE            = "#2563EB"
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#E2E8F0"

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#FFFFFF"
TOPBAR_BORDER             = "#E2E8F0"

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY              = "#0F172A"
TEXT_SECONDARY            = "#475569"
TEXT_MUTED                = "#637389"
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#020617"

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER                    = "#8793A1"
BORDER_FOCUS              = "#2563EB"
DIVIDER                   = "#E2E8F0"

# ── Shadows ───────────────────────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 22
SHADOW_BLUR_ELEVATED      = 40
SHADOW_OFFSET_Y           = 4
SHADOW_OFFSET_Y_ELEVATED  = 10
SHADOW_RGBA_CARD          = (15, 23, 42, 12)
SHADOW_RGBA_ELEVATED      = (15, 23, 42, 22)
SHADOW_RGBA_PRIMARY       = (37, 99, 235, 32)

# ── Chart palette ─────────────────────────────────────────────────────────────
CHART_COLORS = [
    "#2563EB",  # blue
    "#059669",  # emerald
    "#D97706",  # amber
    "#DC2626",  # red
    "#C026D3",  # fuchsia
    "#0891B2",  # cyan
    "#EC4899",  # pink
    "#EA580C",  # orange
]
CHART_COLORS_LIGHT = [
    "#EFF6FF",  # blue light
    "#ECFDF5",  # emerald light
    "#FFFBEB",  # amber light
    "#FEF2F2",  # red light
    "#FDF4FF",  # fuchsia light
    "#ECFEFF",  # cyan light
    "#FDF2F8",  # pink light
    "#FFF7ED",  # orange light
]

# ── Overlays and focus ────────────────────────────────────────────────────────
TOOLTIP_BG         = "#1F2430"
TOOLTIP_FG         = "#F7F8FA"
FOCUS_RING         = "#071E4F"
SCRIM              = "rgba(0, 0, 0, 0.55)"

# ── Icons ─────────────────────────────────────────────────────────────────────
ICON_DEFAULT       = "#465467"
ICON_MUTED         = "#455365"
ICON_ON_PRIMARY    = "#FFFFFF"

# ── Semantic text colors ──────────────────────────────────────────────────────
DANGER_TEXT        = "#DC2323"
SUCCESS_TEXT       = "#04845D"
WARNING_TEXT       = "#AF6005"
INFO_TEXT          = "#077E9B"
TEXT_ON_SUCCESS    = "#081C15"
TEXT_ON_DANGER     = "#FFFFFF"
TEXT_ON_WARNING    = "#FFFFFF"
TEXT_ON_INFO       = "#FFFFFF"
TEXT_ON_EDIT       = "#FFFFFF"
TEXT_ON_HERO       = "#FFFFFF"
