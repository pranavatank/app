"""
ui/theme/theme_nova_dark.py — THEME: Nova (Dark)
Vibrant modern dark theme. Deep space-violet background with neon
violet + cyan accents and a colorful multi-hue accent set. Companion
dark theme to Aurora — same hue family, tuned for a dark canvas.
"""

NAME         = "Nova"
DESCRIPTION  = "Vibrant modern dark theme — neon violet & cyan on a deep space background"
IS_DARK      = True
EMOJI        = "🌌"

# ── Primary — neon violet that pops on dark ───────────────────────────────────
PRIMARY                   = "#A78BFA"   # violet-400
PRIMARY_DARK              = "#8B5CF6"   # violet-500
PRIMARY_LIGHT             = "#241B47"   # tinted bg
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#C4B5FD"
PRIMARY_GRADIENT_END      = "#8B5CF6"
PRIMARY_GRADIENT_HOVER_START = "#A78BFA"
PRIMARY_GRADIENT_HOVER_END   = "#7C3AED"

# ── Success — bright emerald ──────────────────────────────────────────────────
SUCCESS                   = "#34D399"   # emerald-400
SUCCESS_DARK              = "#10B981"   # emerald-500
SUCCESS_LIGHT             = "#052E25"
SUCCESS_GRADIENT_START    = "#6EE7B7"
SUCCESS_GRADIENT_END      = "#059669"

# ── Danger — soft rose (readable on dark) ─────────────────────────────────────
DANGER                    = "#FB7185"   # rose-400
DANGER_DARK               = "#F43F5E"   # rose-500
DANGER_LIGHT              = "#3F0817"
DANGER_GRADIENT_START     = "#FDA4AF"
DANGER_GRADIENT_END       = "#E11D48"

# ── Warning — warm gold ───────────────────────────────────────────────────────
WARNING                   = "#FBBF24"   # amber-400
WARNING_DARK              = "#F59E0B"   # amber-500
WARNING_LIGHT             = "#2E2205"
WARNING_GRADIENT_START    = "#FDE68A"
WARNING_GRADIENT_END      = "#D97706"

# ── Info — vivid neon cyan ────────────────────────────────────────────────────
INFO                      = "#22D3EE"   # cyan-400
INFO_DARK                 = "#06B6D4"   # cyan-500
INFO_LIGHT                = "#062B30"
INFO_GRADIENT_START       = "#67E8F9"
INFO_GRADIENT_END         = "#0891B2"

# ── Edit — neon pink/fuchsia ───────────────────────────────────────────────────
EDIT                      = "#F472B6"   # pink-400
EDIT_DARK                 = "#EC4899"   # pink-500
EDIT_LIGHT                = "#3B0A24"
EDIT_GRADIENT_START       = "#F9A8D4"
EDIT_GRADIENT_END         = "#DB2777"

# ── Hero — violet → cyan gradient (colorful signature look) ──────────────────
HERO_GRADIENT_START       = "#A78BFA"
HERO_GRADIENT_END         = "#22D3EE"
HERO_GRADIENT_HOVER_START = "#8B5CF6"
HERO_GRADIENT_HOVER_END   = "#06B6D4"

# ── Extra accents (vivid on dark) ─────────────────────────────────────────────
PURPLE       = "#C4B5FD";  PURPLE_LIGHT  = "#241B47"
TEAL         = "#2DD4BF";  TEAL_LIGHT    = "#042F2B"
ORANGE       = "#FB923C";  ORANGE_LIGHT  = "#341403"
PINK         = "#F9A8D4";  PINK_LIGHT    = "#3B0A24"

# ── Surfaces — deep space-violet, layered ────────────────────────────────────
BG                        = "#0A0714"
SURFACE                   = "#14101F"
SURFACE_ALT               = "#1E1830"
SURFACE_TINT_START        = "#1A1528"
SURFACE_TINT_END          = "#14101F"

# ── Sidebar — deepest layer ───────────────────────────────────────────────────
SIDEBAR_BG                = "#060410"
SIDEBAR_TEXT              = "#5B5678"
SIDEBAR_ACTIVE            = "#A78BFA"
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#1A1528"

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#14101F"
TOPBAR_BORDER             = "#241D38"

# ── Text — light on dark ─────────────────────────────────────────────────────
TEXT_PRIMARY              = "#E4E1F0"
TEXT_SECONDARY            = "#9C97B8"
TEXT_MUTED                = "#4B4568"
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#F8F7FC"

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER                    = "#241D38"
BORDER_FOCUS              = "#A78BFA"
DIVIDER                   = "#1A1528"

# ── Shadows — dark theme glows ────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 30
SHADOW_BLUR_ELEVATED      = 50
SHADOW_OFFSET_Y           = 6
SHADOW_OFFSET_Y_ELEVATED  = 14
SHADOW_RGBA_CARD          = (0, 0, 0, 65)
SHADOW_RGBA_ELEVATED      = (0, 0, 0, 105)
SHADOW_RGBA_PRIMARY       = (167, 139, 250, 60)

# ── Charts — vivid on dark bg ─────────────────────────────────────────────────
CHART_COLORS = [
    "#A78BFA",  # violet
    "#34D399",  # emerald
    "#FBBF24",  # gold
    "#FB7185",  # rose
    "#F472B6",  # pink
    "#22D3EE",  # cyan
    "#F9A8D4",  # light pink
    "#FB923C",  # orange
]
CHART_COLORS_LIGHT = [
    "#241B47",  # violet dark
    "#052E25",  # emerald dark
    "#2E2205",  # amber dark
    "#3F0817",  # rose dark
    "#3B0A24",  # pink dark
    "#062B30",  # cyan dark
    "#3B0A24",  # light pink dark
    "#341403",  # orange dark
]
