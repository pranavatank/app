"""
ui/theme/theme_forest_light.py — THEME 3: Forest Light
Warm organic light theme. Sage green primary, terracotta danger,
parchment surfaces. Inspired by Notion, Bear, and Obsidian light.
"""

NAME         = "Forest Light"
DESCRIPTION  = "Warm earthy light theme — sage green primary, parchment surfaces"
IS_DARK      = False

# ── Primary — deep sage green ─────────────────────────────────────────────────
PRIMARY                   = "#16A34A"   # green-600
PRIMARY_DARK              = "#15803D"   # green-700
PRIMARY_LIGHT             = "#F0FDF4"   # green-50
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#22C55E"   # green-500
PRIMARY_GRADIENT_END      = "#15803D"   # green-700
PRIMARY_GRADIENT_HOVER_START = "#16A34A"
PRIMARY_GRADIENT_HOVER_END   = "#166534"   # green-800

# ── Success — leaf green ──────────────────────────────────────────────────────
SUCCESS                   = "#16A34A"
SUCCESS_DARK              = "#15803D"
SUCCESS_LIGHT             = "#F0FDF4"
SUCCESS_GRADIENT_START    = "#4ADE80"
SUCCESS_GRADIENT_END      = "#15803D"

# ── Danger — terracotta / warm red ───────────────────────────────────────────
DANGER                    = "#C2410C"   # orange-700 (terracotta)
DANGER_DARK               = "#9A3412"   # orange-800
DANGER_LIGHT              = "#FFF7ED"   # orange-50
DANGER_GRADIENT_START     = "#F97316"   # orange-500
DANGER_GRADIENT_END       = "#9A3412"   # orange-800

# ── Warning — honey amber ─────────────────────────────────────────────────────
WARNING                   = "#92400E"   # amber-800 — deep honey
WARNING_DARK              = "#78350F"   # amber-900
WARNING_LIGHT             = "#FFFBEB"   # amber-50
WARNING_GRADIENT_START    = "#FCD34D"   # amber-300
WARNING_GRADIENT_END      = "#78350F"   # amber-900

# ── Info — slate teal ────────────────────────────────────────────────────────
INFO                      = "#0D9488"   # teal-600
INFO_DARK                 = "#0F766E"   # teal-700
INFO_LIGHT                = "#F0FDFA"   # teal-50
INFO_GRADIENT_START       = "#2DD4BF"   # teal-400
INFO_GRADIENT_END         = "#0F766E"   # teal-700

# ── Edit — warm purple ────────────────────────────────────────────────────────
EDIT                      = "#6D28D9"   # violet-700
EDIT_DARK                 = "#5B21B6"   # violet-800
EDIT_LIGHT                = "#F5F3FF"   # violet-50
EDIT_GRADIENT_START       = "#8B5CF6"
EDIT_GRADIENT_END         = "#5B21B6"

# ── Hero — forest green → teal ────────────────────────────────────────────────
HERO_GRADIENT_START       = "#16A34A"
HERO_GRADIENT_END         = "#0D9488"
HERO_GRADIENT_HOVER_START = "#15803D"
HERO_GRADIENT_HOVER_END   = "#0F766E"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#6D28D9";  PURPLE_LIGHT  = "#F5F3FF"
TEAL         = "#0D9488";  TEAL_LIGHT    = "#F0FDFA"
ORANGE       = "#EA580C";  ORANGE_LIGHT  = "#FFF7ED"
PINK         = "#BE185D";  PINK_LIGHT    = "#FDF2F8"

# ── Surfaces — warm parchment / cream ─────────────────────────────────────────
BG                        = "#FAFAF7"   # warm near-white parchment
SURFACE                   = "#FFFFF8"   # card — slightly warm white
SURFACE_ALT               = "#F3F2EC"   # alternate / hover — warm tint
SURFACE_TINT_START        = "#FFFFF8"
SURFACE_TINT_END          = "#F5F4EE"

# ── Sidebar — dark espresso ───────────────────────────────────────────────────
SIDEBAR_BG                = "#1C1917"   # stone-900
SIDEBAR_TEXT              = "#78716C"   # stone-500
SIDEBAR_ACTIVE            = "#16A34A"
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#292524"   # stone-800

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#FFFFF8"
TOPBAR_BORDER             = "#E5E3DB"

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY              = "#1C1917"   # stone-900
TEXT_SECONDARY            = "#57534E"   # stone-600
TEXT_MUTED                = "#A8A29E"   # stone-400
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#0C0A09"   # stone-950

# ── Borders — warm gray ───────────────────────────────────────────────────────
BORDER                    = "#E5E3DB"
BORDER_FOCUS              = "#86EFAC"   # green-300
DIVIDER                   = "#EFEDE6"

# ── Shadows — warm tinted ─────────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 16
SHADOW_BLUR_ELEVATED      = 28
SHADOW_OFFSET_Y           = 3
SHADOW_OFFSET_Y_ELEVATED  = 7
SHADOW_RGBA_CARD          = (28, 25, 23, 13)
SHADOW_RGBA_ELEVATED      = (28, 25, 23, 22)
SHADOW_RGBA_PRIMARY       = (22, 163, 74, 28)

# ── Charts — earthy, organic palette ─────────────────────────────────────────
CHART_COLORS = [
    "#16A34A",  # green
    "#D97706",  # amber
    "#0D9488",  # teal
    "#C2410C",  # terracotta
    "#6D28D9",  # violet
    "#0284C7",  # sky
    "#BE185D",  # rose
    "#EA580C",  # orange
]
CHART_COLORS_LIGHT = [
    "#F0FDF4",  # green light
    "#FFFBEB",  # amber light
    "#F0FDFA",  # teal light
    "#FFF7ED",  # orange light
    "#F5F3FF",  # violet light
    "#F0F9FF",  # sky light
    "#FDF2F8",  # rose light
    "#FFF7ED",  # orange light
]
