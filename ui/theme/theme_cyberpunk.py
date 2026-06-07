"""
ui/theme/theme_cyberpunk.py — THEME 5: Cyberpunk Neon
Dark futuristic theme. Electric cyan primary, neon green accents,
deep charcoal surfaces with subtle grid pattern feel.
Inspired by Raycast, Supabase dark, and cyberpunk game UIs.
"""

NAME         = "Cyberpunk Neon"
DESCRIPTION  = "Futuristic dark theme — electric cyan, neon green, deep void background"
IS_DARK      = True
EMOJI        = "⚡"

# ── Primary — electric cyan / electric blue ────────────────────────────────────
PRIMARY                   = "#00E5FF"   # electric cyan
PRIMARY_DARK              = "#00B2CC"   # deeper cyan
PRIMARY_LIGHT             = "#002B33"   # dark teal — tinted bg
PRIMARY_TEXT              = "#000000"   # black text on neon
PRIMARY_GRADIENT_START    = "#00E5FF"   # electric cyan
PRIMARY_GRADIENT_END      = "#0288D1"   # deeper electric blue
PRIMARY_GRADIENT_HOVER_START = "#29F3FF"
PRIMARY_GRADIENT_HOVER_END   = "#00B2CC"

# ── Success — neon green ──────────────────────────────────────────────────────
SUCCESS                   = "#39FF14"   # neon green
SUCCESS_DARK              = "#00C853"   # vivid green
SUCCESS_LIGHT             = "#001A00"   # deep green void
SUCCESS_GRADIENT_START    = "#69FF47"
SUCCESS_GRADIENT_END      = "#00C853"

# ── Danger — hot magenta ──────────────────────────────────────────────────────
DANGER                    = "#FF1744"   # neon red
DANGER_DARK               = "#D50000"
DANGER_LIGHT              = "#1A0005"   # dark red void
DANGER_GRADIENT_START     = "#FF4569"
DANGER_GRADIENT_END       = "#D50000"

# ── Warning — electric orange ─────────────────────────────────────────────────
WARNING                   = "#FF9100"   # neon orange
WARNING_DARK              = "#E65100"
WARNING_LIGHT             = "#1A0800"
WARNING_GRADIENT_START    = "#FFAB40"
WARNING_GRADIENT_END      = "#E65100"

# ── Info — violet electric ────────────────────────────────────────────────────
INFO                      = "#D500F9"   # neon violet
INFO_DARK                 = "#AA00FF"
INFO_LIGHT                = "#170027"
INFO_GRADIENT_START       = "#EA80FC"
INFO_GRADIENT_END         = "#AA00FF"

# ── Edit — laser yellow ───────────────────────────────────────────────────────
EDIT                      = "#FFE500"   # neon yellow
EDIT_DARK                 = "#FFC400"
EDIT_LIGHT                = "#1A1500"
EDIT_GRADIENT_START       = "#FFF176"
EDIT_GRADIENT_END         = "#FFC400"

# ── Hero — cyan → violet ──────────────────────────────────────────────────────
HERO_GRADIENT_START       = "#00E5FF"
HERO_GRADIENT_END         = "#D500F9"   # cyan to neon violet
HERO_GRADIENT_HOVER_START = "#29F3FF"
HERO_GRADIENT_HOVER_END   = "#AA00FF"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#D500F9";  PURPLE_LIGHT  = "#170027"
TEAL         = "#1DE9B6";  TEAL_LIGHT    = "#00241C"
ORANGE       = "#FF9100";  ORANGE_LIGHT  = "#1A0800"
PINK         = "#FF4081";  PINK_LIGHT    = "#1A0010"

# ── Surfaces — deep void ─────────────────────────────────────────────────────
BG                        = "#030A0F"   # near-black with blue tint — void
SURFACE                   = "#080F18"   # card — dark blue-black
SURFACE_ALT               = "#0D1824"   # hover / alt rows
SURFACE_TINT_START        = "#0A1520"
SURFACE_TINT_END          = "#080F18"

# ── Sidebar — absolute void ───────────────────────────────────────────────────
SIDEBAR_BG                = "#020609"   # deepest
SIDEBAR_TEXT              = "#2E4A5A"   # dim teal-grey
SIDEBAR_ACTIVE            = "#00E5FF"
SIDEBAR_ACTIVE_TEXT       = "#000000"   # black on cyan
SIDEBAR_HOVER             = "#0A1820"

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#080F18"
TOPBAR_BORDER             = "#0D2535"

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY              = "#B0E8F0"   # cool blue-white
TEXT_SECONDARY            = "#4A8A9A"   # dim teal
TEXT_MUTED                = "#1E3A4A"   # very dim teal
TEXT_ON_PRIMARY           = "#000000"   # black on neon
TEXT_HEADING              = "#E0F8FF"   # brightest near-white-cyan

# ── Borders — glowing teal ────────────────────────────────────────────────────
BORDER                    = "#0D2535"   # dark teal border
BORDER_FOCUS              = "#00E5FF"   # glowing cyan focus
DIVIDER                   = "#081520"

# ── Shadows — neon glow effects ───────────────────────────────────────────────
SHADOW_BLUR_CARD          = 30
SHADOW_BLUR_ELEVATED      = 50
SHADOW_OFFSET_Y           = 4
SHADOW_OFFSET_Y_ELEVATED  = 10
SHADOW_RGBA_CARD          = (0, 229, 255, 25)    # cyan glow
SHADOW_RGBA_ELEVATED      = (0, 229, 255, 50)    # stronger cyan glow
SHADOW_RGBA_PRIMARY       = (0, 229, 255, 80)    # intense primary glow

# ── Charts — full neon rainbow ────────────────────────────────────────────────
CHART_COLORS = [
    "#00E5FF",  # electric cyan
    "#39FF14",  # neon green
    "#FF9100",  # neon orange
    "#FF1744",  # neon red
    "#D500F9",  # neon violet
    "#1DE9B6",  # neon teal
    "#FF4081",  # neon pink
    "#FFE500",  # neon yellow
]
CHART_COLORS_LIGHT = [
    "#002B33",  # dark cyan
    "#001A00",  # dark green
    "#1A0800",  # dark orange
    "#1A0005",  # dark red
    "#170027",  # dark violet
    "#00241C",  # dark teal
    "#1A0010",  # dark pink
    "#1A1500",  # dark yellow
]
