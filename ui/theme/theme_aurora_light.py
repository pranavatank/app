"""
ui/theme/theme_aurora_light.py — THEME: Aurora (Light)
Vibrant modern light theme. Electric indigo primary with a colorful
multi-hue accent set (emerald, amber, rose, fuchsia, cyan). Designed for
a bold, contemporary dashboard look — think Linear x Stripe x Raycast,
but turned up in saturation.
"""

NAME         = "Aurora"
DESCRIPTION  = "Vibrant modern light theme — electric indigo with colorful multi-hue accents"
IS_DARK      = False
EMOJI        = "🌈"

# ── Primary — electric indigo ─────────────────────────────────────────────────
PRIMARY                   = "#4F46E5"
PRIMARY_DARK              = "#4136C9"
PRIMARY_LIGHT             = "#EEF2FF"
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#5F63F0"
PRIMARY_GRADIENT_END      = "#4338CA"
PRIMARY_GRADIENT_HOVER_START = "#4F46E5"
PRIMARY_GRADIENT_HOVER_END   = "#3730A3"

# ── Success — vivid emerald ───────────────────────────────────────────────────
SUCCESS                   = "#10B981"
SUCCESS_DARK              = "#059669"
SUCCESS_LIGHT             = "#ECFDF5"
SUCCESS_GRADIENT_START    = "#34D399"
SUCCESS_GRADIENT_END      = "#059669"

# ── Danger — vivid rose ───────────────────────────────────────────────────────
DANGER                    = "#E11D48"
DANGER_DARK               = "#BE123C"
DANGER_LIGHT              = "#FFF1F2"
DANGER_GRADIENT_START     = "#E81131"
DANGER_GRADIENT_END       = "#BE123C"

# ── Warning — vivid amber ─────────────────────────────────────────────────────
WARNING                   = "#F59E0B"
WARNING_DARK              = "#D97706"
WARNING_LIGHT             = "#FFFBEB"
WARNING_GRADIENT_START    = "#FBBF24"
WARNING_GRADIENT_END      = "#D97706"

# ── Info — vivid cyan ─────────────────────────────────────────────────────────
INFO                      = "#06B6D4"
INFO_DARK                 = "#0891B2"
INFO_LIGHT                = "#ECFEFF"
INFO_GRADIENT_START       = "#22D3EE"
INFO_GRADIENT_END         = "#0891B2"

# ── Edit — vivid fuchsia ───────────────────────────────────────────────────────
EDIT                      = "#C026D3"
EDIT_DARK                 = "#A21CAF"
EDIT_LIGHT                = "#FDF4FF"
EDIT_GRADIENT_START       = "#C515E0"
EDIT_GRADIENT_END         = "#A21CAF"

# ── Hero banner gradient — indigo → pink (colorful signature look) ───────────
HERO_GRADIENT_START       = "#4F46E5"
HERO_GRADIENT_END         = "#BA1A69"
HERO_GRADIENT_HOVER_START = "#4338CA"
HERO_GRADIENT_HOVER_END   = "#B82264"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#7C3AED";  PURPLE_LIGHT  = "#F5F3FF"
TEAL         = "#0D9488";  TEAL_LIGHT    = "#F0FDFA"
ORANGE       = "#EA580C";  ORANGE_LIGHT  = "#FFF7ED"
PINK         = "#DB2777";  PINK_LIGHT    = "#FDF2F8"

# ── Surfaces — soft violet-white ─────────────────────────────────────────────
BG                        = "#F7F7FD"
SURFACE                   = "#FFFFFF"
SURFACE_ALT               = "#E8E4F7"
SURFACE_TINT_START        = "#FFFFFF"
SURFACE_TINT_END          = "#F1EFFC"

# ── Sidebar — light, matches the page background (not a fixed dark panel) ───
SIDEBAR_BG                = "#F7F7FD"
SIDEBAR_TEXT              = "#56526C"
SIDEBAR_ACTIVE            = "#4F46E5"
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#E8E4F7"

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#FFFFFF"
TOPBAR_BORDER             = "#E7E5F5"

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY              = "#1E1B2E"
TEXT_SECONDARY            = "#57536E"
TEXT_MUTED                = "#75718F"
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#120F22"

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER                    = "#918DB0"
BORDER_FOCUS              = "#A5B4FC"
DIVIDER                   = "#F1EFFA"

# ── Shadows ───────────────────────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 22
SHADOW_BLUR_ELEVATED      = 40
SHADOW_OFFSET_Y           = 4
SHADOW_OFFSET_Y_ELEVATED  = 10
SHADOW_RGBA_CARD          = (30, 20, 70, 14)
SHADOW_RGBA_ELEVATED      = (30, 20, 70, 24)
SHADOW_RGBA_PRIMARY       = (79, 70, 229, 34)

# ── Chart palette ─────────────────────────────────────────────────────────────
CHART_COLORS = [
    "#4F46E5",  # indigo
    "#10B981",  # emerald
    "#F59E0B",  # amber
    "#E11D48",  # rose
    "#C026D3",  # fuchsia
    "#06B6D4",  # cyan
    "#EC4899",  # pink
    "#EA580C",  # orange
]
CHART_COLORS_LIGHT = [
    "#EEF2FF",  # indigo light
    "#ECFDF5",  # emerald light
    "#FFFBEB",  # amber light
    "#FFF1F2",  # rose light
    "#FDF4FF",  # fuchsia light
    "#ECFEFF",  # cyan light
    "#FDF2F8",  # pink light
    "#FFF7ED",  # orange light
]

# ── Overlays and focus ────────────────────────────────────────────────────────
TOOLTIP_BG         = "#1F2430"
TOOLTIP_FG         = "#F7F8FA"
FOCUS_RING         = "#01092C"
SCRIM              = "rgba(0, 0, 0, 0.55)"

# ── Icons ─────────────────────────────────────────────────────────────────────
ICON_DEFAULT       = "#56526C"
ICON_MUTED         = "#55516A"
ICON_ON_PRIMARY    = "#FFFFFF"

# ── Semantic text colors ──────────────────────────────────────────────────────
DANGER_TEXT        = "#DE1D47"
SUCCESS_TEXT       = "#0B835C"
WARNING_TEXT       = "#A16707"
INFO_TEXT          = "#048096"
TEXT_ON_SUCCESS    = "#081C15"
TEXT_ON_DANGER     = "#FFFFFF"
TEXT_ON_WARNING    = "#1C1608"
TEXT_ON_INFO       = "#08191C"
TEXT_ON_EDIT       = "#FFFFFF"
TEXT_ON_HERO       = "#FFFFFF"
