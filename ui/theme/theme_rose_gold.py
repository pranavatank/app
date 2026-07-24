"""
ui/theme/theme_rose_gold.py — THEME 4: Rose Gold Luxe
Luxurious warm theme. Rose gold primary, champagne surfaces, platinum borders.
Inspired by high-end fintech apps, Bloomberg Terminal light, and luxury banking UIs.
"""

NAME         = "Rose Gold Luxe"
DESCRIPTION  = "Luxurious rose gold & champagne — elegant warm premium feel"
IS_DARK      = False
EMOJI        = "🌹"

# ── Primary — rose gold ────────────────────────────────────────────────────────
PRIMARY                   = "#C2185B"   # deep rose
PRIMARY_DARK              = "#AD1457"   # darker rose
PRIMARY_LIGHT             = "#FCE4EC"   # blush
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#E91E8C"   # vivid rose-pink
PRIMARY_GRADIENT_END      = "#AD1457"   # deep rose
PRIMARY_GRADIENT_HOVER_START = "#C2185B"
PRIMARY_GRADIENT_HOVER_END   = "#880E4F"   # darkest rose

# ── Success — warm sage gold ──────────────────────────────────────────────────
SUCCESS                   = "#B7791F"   # warm gold
SUCCESS_DARK              = "#92400E"
SUCCESS_LIGHT             = "#FEF9EE"   # champagne tint
SUCCESS_GRADIENT_START    = "#D4A017"   # bright gold
SUCCESS_GRADIENT_END      = "#92400E"

# ── Danger — deep crimson ─────────────────────────────────────────────────────
DANGER                    = "#C62828"
DANGER_DARK               = "#B71C1C"
DANGER_LIGHT              = "#FFEBEE"
DANGER_GRADIENT_START     = "#EF5350"
DANGER_GRADIENT_END       = "#B71C1C"

# ── Warning — amber gold ──────────────────────────────────────────────────────
WARNING                   = "#E65100"   # deep amber
WARNING_DARK              = "#BF360C"
WARNING_LIGHT             = "#FBE9E7"
WARNING_GRADIENT_START    = "#FF7043"
WARNING_GRADIENT_END      = "#BF360C"

# ── Info — platinum blue ──────────────────────────────────────────────────────
INFO                      = "#546E7A"   # blue-grey (platinum)
INFO_DARK                 = "#37474F"
INFO_LIGHT                = "#ECEFF1"
INFO_GRADIENT_START       = "#78909C"
INFO_GRADIENT_END         = "#37474F"

# ── Edit — mauve violet ───────────────────────────────────────────────────────
EDIT                      = "#7B1FA2"
EDIT_DARK                 = "#6A1B9A"
EDIT_LIGHT                = "#F3E5F5"
EDIT_GRADIENT_START       = "#AB47BC"
EDIT_GRADIENT_END         = "#6A1B9A"

# ── Hero — true rose → gold gradient (honors the theme's name) ──────────────
HERO_GRADIENT_START       = "#E91E8C"
HERO_GRADIENT_END         = "#D4A017"   # bright gold
HERO_GRADIENT_HOVER_START = "#C2185B"
HERO_GRADIENT_HOVER_END   = "#B7791F"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#7B1FA2";  PURPLE_LIGHT  = "#F3E5F5"
TEAL         = "#00897B";  TEAL_LIGHT    = "#E0F2F1"
ORANGE       = "#E64A19";  ORANGE_LIGHT  = "#FBE9E7"
PINK         = "#E91E63";  PINK_LIGHT    = "#FCE4EC"

# ── Surfaces — champagne & ivory ─────────────────────────────────────────────
BG                        = "#FDF6F0"   # warm ivory page
SURFACE                   = "#FFFDF9"   # champagne card
SURFACE_ALT               = "#F9F0EA"   # hover — warm blush tint
SURFACE_TINT_START        = "#FFFDF9"
SURFACE_TINT_END          = "#F5ECE4"

# ── Sidebar — light, matches the warm ivory page background ─────────────────
SIDEBAR_BG                = "#FDF6F0"   # warm ivory page
SIDEBAR_TEXT              = "#7D5A5A"   # warm brown-grey
SIDEBAR_ACTIVE            = "#E91E8C"   # vivid rose
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#F9F0EA"   # warm blush hover

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#FFFDF9"
TOPBAR_BORDER             = "#F0DDD5"

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY              = "#2D1515"   # deep warm brown-black
TEXT_SECONDARY            = "#7D5A5A"   # warm brown-grey
TEXT_MUTED                = "#C4A0A0"   # muted blush
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#1A0808"   # richest dark heading

# ── Borders — gold-tinted ─────────────────────────────────────────────────────
BORDER                    = "#EDD5CC"   # warm rose border
BORDER_FOCUS              = "#F48FB1"   # blush focus
DIVIDER                   = "#F5E8E4"

# ── Shadows — warm rose-tinted ────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 18
SHADOW_BLUR_ELEVATED      = 32
SHADOW_OFFSET_Y           = 4
SHADOW_OFFSET_Y_ELEVATED  = 8
SHADOW_RGBA_CARD          = (45, 21, 21, 14)
SHADOW_RGBA_ELEVATED      = (45, 21, 21, 22)
SHADOW_RGBA_PRIMARY       = (194, 24, 91, 30)

# ── Charts — warm jewel tones ─────────────────────────────────────────────────
CHART_COLORS = [
    "#E91E8C",  # rose
    "#B7791F",  # gold
    "#7B1FA2",  # mauve
    "#C62828",  # crimson
    "#00897B",  # teal
    "#546E7A",  # platinum
    "#E64A19",  # coral
    "#E91E63",  # pink
]
CHART_COLORS_LIGHT = [
    "#FCE4EC",  # blush
    "#FEF9EE",  # champagne
    "#F3E5F5",  # lavender
    "#FFEBEE",  # pale red
    "#E0F2F1",  # pale teal
    "#ECEFF1",  # pale grey
    "#FBE9E7",  # pale coral
    "#FCE4EC",  # pale pink
]
