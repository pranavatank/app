"""
ui/theme/theme_midnight_pro.py — THEME 2: Midnight Pro
Premium dark theme. Deep charcoal background, bright indigo-violet primary,
gold accents. Inspired by Linear, VS Code Dark+, Raycast.
"""

NAME         = "Midnight Pro"
DESCRIPTION  = "Premium dark theme — deep charcoal with indigo & gold accents"
IS_DARK      = True
EMOJI        = "🌙"

# ── Primary — bright indigo that pops on dark ─────────────────────────────────
PRIMARY                   = "#5563F6"   # was #818CF8 — same reason as Nova
PRIMARY_DARK              = "#7C7FF3"   # was #6366F1
PRIMARY_LIGHT             = "#1E1B4B"   # indigo-950 — used as tinted bg
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#5664F2"
PRIMARY_GRADIENT_END      = "#474BEC"
PRIMARY_GRADIENT_HOVER_START = "#4B68F2"
PRIMARY_GRADIENT_HOVER_END   = "#3C4CEE"

# ── Success — bright emerald ──────────────────────────────────────────────────
SUCCESS                   = "#34D399"   # emerald-400
SUCCESS_DARK              = "#10B981"   # emerald-500
SUCCESS_LIGHT             = "#022C22"   # emerald-950
SUCCESS_GRADIENT_START    = "#6EE7B7"
SUCCESS_GRADIENT_END      = "#059669"

# ── Danger — soft red (readable on dark) ──────────────────────────────────────
DANGER                    = "#F87171"   # red-400
DANGER_DARK               = "#EF4444"   # red-500
DANGER_LIGHT              = "#450A0A"   # red-950
DANGER_GRADIENT_START     = "#E61717"
DANGER_GRADIENT_END       = "#C02121"

# ── Warning — warm gold ───────────────────────────────────────────────────────
WARNING                   = "#FCD34D"   # amber-300
WARNING_DARK              = "#F59E0B"   # amber-500
WARNING_LIGHT             = "#2D1F00"   # amber-950
WARNING_GRADIENT_START    = "#FDE68A"
WARNING_GRADIENT_END      = "#D97706"

# ── Info — vivid sky ──────────────────────────────────────────────────────────
INFO                      = "#38BDF8"   # sky-400
INFO_DARK                 = "#0EA5E9"   # sky-500
INFO_LIGHT                = "#082F49"   # sky-950
INFO_GRADIENT_START       = "#7DD3FC"
INFO_GRADIENT_END         = "#0284C7"

# ── Edit — fuchsia / magenta ──────────────────────────────────────────────────
EDIT                      = "#E879F9"   # fuchsia-400
EDIT_DARK                 = "#D946EF"   # fuchsia-500
EDIT_LIGHT                = "#2E0A3C"   # fuchsia-950
EDIT_GRADIENT_START       = "#C318E1"
EDIT_GRADIENT_END         = "#A423B4"

# ── Hero — indigo → purple gradient ──────────────────────────────────────────
HERO_GRADIENT_START       = "#5664F2"
HERO_GRADIENT_END         = "#8820EF"   # purple-400
HERO_GRADIENT_HOVER_START = "#5F63F0"
HERO_GRADIENT_HOVER_END   = "#891EEF"   # purple-500

# ── Extra accents (vivid on dark) ─────────────────────────────────────────────
PURPLE       = "#C084FC";  PURPLE_LIGHT  = "#1A0533"
TEAL         = "#2DD4BF";  TEAL_LIGHT    = "#021A19"
ORANGE       = "#FB923C";  ORANGE_LIGHT  = "#2C0A00"
PINK         = "#F472B6";  PINK_LIGHT    = "#2D0020"

# ── Surfaces — true layered dark ─────────────────────────────────────────────
BG                        = "#0B0D14"
SURFACE                   = "#13161F"
SURFACE_ALT               = "#1C2030"
SURFACE_TINT_START        = "#181C29"
SURFACE_TINT_END          = "#13161F"

# ── Sidebar — deepest layer ───────────────────────────────────────────────────
SIDEBAR_BG                = "#080A10"
SIDEBAR_TEXT              = "#6D7C90"
SIDEBAR_ACTIVE            = "#818CF8"
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#181C29"

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#13161F"
TOPBAR_BORDER             = "#1F2436"

# ── Text — light on dark ─────────────────────────────────────────────────────
TEXT_PRIMARY              = "#E2E8F0"   # slate-200
TEXT_SECONDARY            = "#94A3B8"   # slate-400
TEXT_MUTED                = "#70829E"   # was #374151
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#F8FAFC"   # slate-50

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER                    = "#5F6579"
BORDER_FOCUS              = "#818CF8"
DIVIDER                   = "#151929"

# ── Shadows — dark theme glows ────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 28
SHADOW_BLUR_ELEVATED      = 48
SHADOW_OFFSET_Y           = 5
SHADOW_OFFSET_Y_ELEVATED  = 12
SHADOW_RGBA_CARD          = (0, 0, 0, 60)
SHADOW_RGBA_ELEVATED      = (0, 0, 0, 100)
SHADOW_RGBA_PRIMARY       = (129, 140, 248, 55)

# ── Charts — vivid on dark bg ─────────────────────────────────────────────────
CHART_COLORS = [
    "#818CF8",  # indigo
    "#34D399",  # emerald
    "#FCD34D",  # gold
    "#F87171",  # red
    "#C084FC",  # purple
    "#38BDF8",  # sky
    "#F472B6",  # pink
    "#FB923C",  # orange
]
CHART_COLORS_LIGHT = [
    "#1E1B4B",  # indigo dark
    "#022C22",  # emerald dark
    "#2D1F00",  # amber dark
    "#450A0A",  # red dark
    "#1A0533",  # purple dark
    "#082F49",  # sky dark
    "#2D0020",  # pink dark
    "#2C0A00",  # orange dark
]

# ── Overlays and focus ────────────────────────────────────────────────────────
TOOLTIP_BG         = "#F5F5F7"
TOOLTIP_FG         = "#14181F"
FOCUS_RING         = "#CFD3FC"
SCRIM              = "rgba(0, 0, 0, 0.55)"

# ── Icons ─────────────────────────────────────────────────────────────────────
ICON_DEFAULT       = "#566171"
ICON_MUTED         = "#576273"
ICON_ON_PRIMARY    = "#FFFFFF"

# ── Semantic text colors ──────────────────────────────────────────────────────
DANGER_TEXT        = "#F86E6E"
SUCCESS_TEXT       = "#31D298"
WARNING_TEXT       = "#FCD24A"
INFO_TEXT          = "#35BCF8"
TEXT_ON_SUCCESS    = "#081C14"
TEXT_ON_DANGER     = "#FFFFFF"
TEXT_ON_WARNING    = "#1C1808"
TEXT_ON_INFO       = "#08151C"
TEXT_ON_EDIT       = "#FFFFFF"
TEXT_ON_HERO       = "#FFFFFF"
