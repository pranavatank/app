"""
ui/theme/theme_sunrise_warm.py — THEME 7: Sunrise Warm

A vibrant, energetic light theme designed specifically for financial apps.
Warm coral-orange primary, golden accents, sky-blue info, crisp white surfaces.
Feels modern, alive, and professional — never boring.

Inspired by: Robinhood, Groww, and Monzo's warm design language.
"""

NAME         = "Sunrise Warm"
DESCRIPTION  = "Warm energetic light — coral orange primary, golden accents, sky blue info"
IS_DARK      = False
EMOJI        = "🌅"

# ── Primary — vivid coral-orange (energetic, modern) ─────────────────────────
PRIMARY                   = "#F05A28"   # warm coral-orange
PRIMARY_DARK              = "#D94B1A"   # deeper burn
PRIMARY_LIGHT             = "#FFF1EC"   # pale apricot
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#FF7043"   # bright coral
PRIMARY_GRADIENT_END      = "#D84315"   # deep ember
PRIMARY_GRADIENT_HOVER_START = "#F05A28"
PRIMARY_GRADIENT_HOVER_END   = "#BF360C"   # darkest ember

# ── Success — fresh lime-green (growth, gains) ────────────────────────────────
SUCCESS                   = "#2E7D32"   # deep forest green
SUCCESS_DARK              = "#1B5E20"
SUCCESS_LIGHT             = "#F1F8E9"   # pale mint
SUCCESS_GRADIENT_START    = "#66BB6A"   # bright green
SUCCESS_GRADIENT_END      = "#1B5E20"   # deep green

# ── Danger — vivid crimson ────────────────────────────────────────────────────
DANGER                    = "#C62828"   # deep crimson
DANGER_DARK               = "#B71C1C"
DANGER_LIGHT              = "#FFEBEE"   # pale blush
DANGER_GRADIENT_START     = "#EF5350"
DANGER_GRADIENT_END       = "#B71C1C"

# ── Warning — rich golden amber ───────────────────────────────────────────────
WARNING                   = "#F57F17"   # deep amber
WARNING_DARK              = "#E65100"   # burnt orange
WARNING_LIGHT             = "#FFFDE7"   # pale yellow
WARNING_GRADIENT_START    = "#FFCA28"   # bright gold
WARNING_GRADIENT_END      = "#F57F17"   # deep amber

# ── Info — clear sky blue ─────────────────────────────────────────────────────
INFO                      = "#0277BD"   # sky blue
INFO_DARK                 = "#01579B"
INFO_LIGHT                = "#E1F5FE"   # pale sky
INFO_GRADIENT_START       = "#29B6F6"   # light sky
INFO_GRADIENT_END         = "#01579B"   # deep sky

# ── Edit — rich indigo ────────────────────────────────────────────────────────
EDIT                      = "#4527A0"   # deep indigo
EDIT_DARK                 = "#311B92"
EDIT_LIGHT                = "#EDE7F6"   # pale lavender
EDIT_GRADIENT_START       = "#7E57C2"
EDIT_GRADIENT_END         = "#311B92"

# ── Hero — sunrise gradient (coral → golden sky) ──────────────────────────────
HERO_GRADIENT_START       = "#FF7043"   # warm coral
HERO_GRADIENT_END         = "#FFA000"   # warm amber-gold
HERO_GRADIENT_HOVER_START = "#F05A28"
HERO_GRADIENT_HOVER_END   = "#F57F17"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#6A1B9A";  PURPLE_LIGHT  = "#F3E5F5"
TEAL         = "#00796B";  TEAL_LIGHT    = "#E0F2F1"
ORANGE       = "#EF6C00";  ORANGE_LIGHT  = "#FFF3E0"
PINK         = "#AD1457";  PINK_LIGHT    = "#FCE4EC"

# ── Surfaces — warm white (clean, bright, inviting) ───────────────────────────
BG                        = "#FFFAF7"   # warm cream white — page bg
SURFACE                   = "#FFFFFF"   # pure white — cards
SURFACE_ALT               = "#FFF4EE"   # warm apricot tint — hover rows
SURFACE_TINT_START        = "#FFFFFF"
SURFACE_TINT_END          = "#FFF4EE"

# ── Sidebar — light, matches the warm cream page background ─────────────────
SIDEBAR_BG                = "#FFFAF7"   # warm cream white — page bg
SIDEBAR_TEXT              = "#6D4C41"   # warm brown-grey
SIDEBAR_ACTIVE            = "#F05A28"   # coral active nav
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#FFF4EE"   # warm apricot tint hover

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#FFFFFF"
TOPBAR_BORDER             = "#F0D8CC"   # warm peach border

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY              = "#1A0D05"   # near-black with warm tone
TEXT_SECONDARY            = "#6D4C41"   # warm brown-grey
TEXT_MUTED                = "#C09E91"   # muted warm taupe
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#0D0500"   # richest warm-black

# ── Borders — warm peach tones ────────────────────────────────────────────────
BORDER                    = "#F0D0BC"   # warm peach border
BORDER_FOCUS              = "#FF7043"   # coral focus ring
DIVIDER                   = "#FBE9E0"

# ── Shadows — warm tinted ─────────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 18
SHADOW_BLUR_ELEVATED      = 32
SHADOW_OFFSET_Y           = 4
SHADOW_OFFSET_Y_ELEVATED  = 8
SHADOW_RGBA_CARD          = (26, 13, 5, 13)       # warm dark shadow
SHADOW_RGBA_ELEVATED      = (26, 13, 5, 22)
SHADOW_RGBA_PRIMARY       = (240, 90, 40, 28)     # coral glow

# ── Charts — vivid warm financial palette ────────────────────────────────────
CHART_COLORS = [
    "#F05A28",  # coral — primary
    "#2E7D32",  # green — success/profit
    "#0277BD",  # sky — information
    "#C62828",  # crimson — danger/loss
    "#F57F17",  # amber — warning
    "#4527A0",  # indigo — edit/analytical
    "#00796B",  # teal — secondary
    "#AD1457",  # rose — accent
]
CHART_COLORS_LIGHT = [
    "#FFF1EC",  # coral light
    "#F1F8E9",  # green light
    "#E1F5FE",  # sky light
    "#FFEBEE",  # crimson light
    "#FFFDE7",  # amber light
    "#EDE7F6",  # indigo light
    "#E0F2F1",  # teal light
    "#FCE4EC",  # rose light
]
