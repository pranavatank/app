"""
ui/theme/theme_arctic_breeze.py — THEME: Arctic Breeze

A breathtaking, eye-soothing light theme in soft periwinkle-blue tones.
Designed for long sessions — cool, calm, never fatiguing.
Primary is a gentle periwinkle-indigo, surfaces are pale ice-blue,
text is warm charcoal for comfortable contrast.

Inspired by: macOS Monterey, Notion Light, Linear's cool palette.
Perfect for: long work sessions where eyes need rest.
"""

NAME         = "Arctic Breeze"
DESCRIPTION  = "Peaceful ice-blue light — periwinkle primary, soft frost surfaces"
IS_DARK      = False
EMOJI        = "🧊"

# ── Primary — gentle periwinkle-indigo (calm, trustworthy) ────────────────────
PRIMARY                   = "#4F6EF7"   # soft periwinkle-blue
PRIMARY_DARK              = "#3A56D4"   # deeper cool blue
PRIMARY_LIGHT             = "#EEF2FF"   # pale periwinkle tint
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#6B8AFF"   # bright periwinkle
PRIMARY_GRADIENT_END      = "#3A56D4"   # deep cool blue
PRIMARY_GRADIENT_HOVER_START = "#4F6EF7"
PRIMARY_GRADIENT_HOVER_END   = "#2D44B8"

# ── Success — soft sage-teal green (natural, calming) ─────────────────────────
SUCCESS                   = "#0E9F6E"   # calm sage green
SUCCESS_DARK              = "#057A55"
SUCCESS_LIGHT             = "#E8F8F2"   # pale mint frost
SUCCESS_GRADIENT_START    = "#31C48D"
SUCCESS_GRADIENT_END      = "#057A55"

# ── Danger — muted rose red (readable but not jarring) ────────────────────────
DANGER                    = "#E02424"   # clear red, not harsh
DANGER_DARK               = "#C81E1E"
DANGER_LIGHT              = "#FDF2F2"   # pale blush
DANGER_GRADIENT_START     = "#F05252"
DANGER_GRADIENT_END       = "#C81E1E"

# ── Warning — soft honey amber (warm accent on cool theme) ────────────────────
WARNING                   = "#C27803"   # deep honey
WARNING_DARK              = "#A56600"
WARNING_LIGHT             = "#FFF8EC"   # pale butter
WARNING_GRADIENT_START    = "#E3A008"   # warm gold
WARNING_GRADIENT_END      = "#A56600"

# ── Info — clear sky cyan-blue ────────────────────────────────────────────────
INFO                      = "#0694A2"   # clear teal-cyan
INFO_DARK                 = "#047481"
INFO_LIGHT                = "#E5F7FA"   # pale ice-cyan
INFO_GRADIENT_START       = "#16BDCA"
INFO_GRADIENT_END         = "#047481"

# ── Edit — soft lavender-violet (distinct from primary) ───────────────────────
EDIT                      = "#6B3FA0"   # cool lavender violet
EDIT_DARK                 = "#5521B5"
EDIT_LIGHT                = "#F0EBF8"   # pale lavender
EDIT_GRADIENT_START       = "#9061F9"
EDIT_GRADIENT_END         = "#5521B5"

# ── Hero — periwinkle → ice-teal gradient (peaceful, scenic) ─────────────────
HERO_GRADIENT_START       = "#4F6EF7"   # periwinkle
HERO_GRADIENT_END         = "#06AED4"   # ice teal
HERO_GRADIENT_HOVER_START = "#3A56D4"
HERO_GRADIENT_HOVER_END   = "#0694A2"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#6B3FA0";  PURPLE_LIGHT  = "#F0EBF8"
TEAL         = "#0694A2";  TEAL_LIGHT    = "#E5F7FA"
ORANGE       = "#D03801";  ORANGE_LIGHT  = "#FFF0EA"
PINK         = "#B3125D";  PINK_LIGHT    = "#FBE8F3"

# ── Surfaces — frost white with the faintest ice-blue tint ────────────────────
BG                        = "#F4F7FF"   # frost page background — very pale blue
SURFACE                   = "#FAFCFF"   # card surface — near-white with blue hint
SURFACE_ALT               = "#EDF1FB"   # alt rows / hover — soft blue-grey
SURFACE_TINT_START        = "#FAFCFF"
SURFACE_TINT_END          = "#EDF1FB"

# ── Sidebar — light, matches the frost page background ───────────────────────
SIDEBAR_BG                = "#F4F7FF"   # frost page background
SIDEBAR_TEXT              = "#4B5563"   # cool grey
SIDEBAR_ACTIVE            = "#4F6EF7"   # periwinkle active
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#EDF1FB"   # soft blue-grey hover

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#FAFCFF"
TOPBAR_BORDER             = "#D9E2FF"   # pale periwinkle border

# ── Text — warm charcoal (comfortable on cool surfaces) ──────────────────────
TEXT_PRIMARY              = "#111827"   # near-black with cool undertone
TEXT_SECONDARY            = "#4B5563"   # cool grey
TEXT_MUTED                = "#9CA3AF"   # light cool grey
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#030712"   # deepest cool-black

# ── Borders — gentle periwinkle tints ─────────────────────────────────────────
BORDER                    = "#D9E2FF"   # soft periwinkle border
BORDER_FOCUS              = "#6B8AFF"   # bright periwinkle focus
DIVIDER                   = "#EEF2FF"

# ── Shadows — cool blue-tinted (gentle depth) ─────────────────────────────────
SHADOW_BLUR_CARD          = 22
SHADOW_BLUR_ELEVATED      = 38
SHADOW_OFFSET_Y           = 4
SHADOW_OFFSET_Y_ELEVATED  = 9
SHADOW_RGBA_CARD          = (17, 24, 92, 12)     # cool navy shadow (very subtle)
SHADOW_RGBA_ELEVATED      = (17, 24, 92, 20)
SHADOW_RGBA_PRIMARY       = (79, 110, 247, 25)   # periwinkle glow

# ── Charts — cool, clear, easy to read ────────────────────────────────────────
CHART_COLORS = [
    "#4F6EF7",  # periwinkle — primary data
    "#0E9F6E",  # sage green — positive
    "#E3A008",  # honey amber — caution
    "#E02424",  # rose red — negative
    "#0694A2",  # ice teal — info
    "#6B3FA0",  # lavender — analytical
    "#D03801",  # burnt orange — secondary
    "#B3125D",  # rose — accent
]
CHART_COLORS_LIGHT = [
    "#EEF2FF",  # periwinkle light
    "#E8F8F2",  # green light
    "#FFF8EC",  # amber light
    "#FDF2F2",  # red light
    "#E5F7FA",  # teal light
    "#F0EBF8",  # lavender light
    "#FFF0EA",  # orange light
    "#FBE8F3",  # pink light
]
