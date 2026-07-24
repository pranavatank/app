"""
ui/theme/theme_ocean_blue.py — THEME 1: Ocean Blue (Default)
Modern professional light theme. Crisp blue primary, vivid emerald success,
warm card surfaces. Inspired by Linear, Vercel dashboard, and Stripe.
"""

NAME         = "Ocean Blue"
DESCRIPTION  = "Modern professional light theme — blue primary, clean white cards"
IS_DARK      = False
EMOJI        = "🌊"

# ── Primary — vivid electric blue ─────────────────────────────────────────────
PRIMARY                   = "#2563EB"
PRIMARY_DARK              = "#1D4ED8"
PRIMARY_LIGHT             = "#EFF6FF"
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#3B82F6"
PRIMARY_GRADIENT_END      = "#1D4ED8"
PRIMARY_GRADIENT_HOVER_START = "#2563EB"
PRIMARY_GRADIENT_HOVER_END   = "#1E40AF"

# ── Success — vivid emerald green ─────────────────────────────────────────────
SUCCESS                   = "#059669"
SUCCESS_DARK              = "#047857"
SUCCESS_LIGHT             = "#ECFDF5"
SUCCESS_GRADIENT_START    = "#10B981"
SUCCESS_GRADIENT_END      = "#047857"

# ── Danger — bright red ───────────────────────────────────────────────────────
DANGER                    = "#DC2626"
DANGER_DARK               = "#B91C1C"
DANGER_LIGHT              = "#FEF2F2"
DANGER_GRADIENT_START     = "#EF4444"
DANGER_GRADIENT_END       = "#B91C1C"

# ── Warning — vivid amber ─────────────────────────────────────────────────────
WARNING                   = "#D97706"
WARNING_DARK              = "#B45309"
WARNING_LIGHT             = "#FFFBEB"
WARNING_GRADIENT_START    = "#F59E0B"
WARNING_GRADIENT_END      = "#B45309"

# ── Info — sky blue ───────────────────────────────────────────────────────────
INFO                      = "#0284C7"
INFO_DARK                 = "#0369A1"
INFO_LIGHT                = "#F0F9FF"
INFO_GRADIENT_START       = "#38BDF8"
INFO_GRADIENT_END         = "#0369A1"

# ── Edit — violet ─────────────────────────────────────────────────────────────
EDIT                      = "#7C3AED"
EDIT_DARK                 = "#6D28D9"
EDIT_LIGHT                = "#F5F3FF"
EDIT_GRADIENT_START       = "#8B5CF6"
EDIT_GRADIENT_END         = "#6D28D9"

# ── Hero banner gradient ──────────────────────────────────────────────────────
HERO_GRADIENT_START       = "#2563EB"
HERO_GRADIENT_END         = "#0EA5E9"
HERO_GRADIENT_HOVER_START = "#1D4ED8"
HERO_GRADIENT_HOVER_END   = "#0284C7"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#7C3AED";  PURPLE_LIGHT  = "#F5F3FF"
TEAL         = "#0D9488";  TEAL_LIGHT    = "#F0FDFA"
ORANGE       = "#EA580C";  ORANGE_LIGHT  = "#FFF7ED"
PINK         = "#DB2777";  PINK_LIGHT    = "#FDF2F8"

# ── Surfaces — cool-white with blue tint ──────────────────────────────────────
BG                        = "#F5F8FF"
SURFACE                   = "#FFFFFF"
SURFACE_ALT               = "#F1F5FD"
SURFACE_TINT_START        = "#FFFFFF"
SURFACE_TINT_END          = "#F1F5FD"

# ── Sidebar — light, matches the page background ─────────────────────────────
SIDEBAR_BG                = "#F5F8FF"
SIDEBAR_TEXT              = "#475569"
SIDEBAR_ACTIVE            = "#2563EB"
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#F1F5FD"

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#FFFFFF"
TOPBAR_BORDER             = "#E2E8F0"

# ── Text ──────────────────────────────────────────────────────────────────────
TEXT_PRIMARY              = "#0F172A"
TEXT_SECONDARY            = "#475569"
TEXT_MUTED                = "#94A3B8"
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#020617"

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER                    = "#E2E8F0"
BORDER_FOCUS              = "#93C5FD"
DIVIDER                   = "#F1F5F9"

# ── Shadows ───────────────────────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 20
SHADOW_BLUR_ELEVATED      = 36
SHADOW_OFFSET_Y           = 4
SHADOW_OFFSET_Y_ELEVATED  = 9
SHADOW_RGBA_CARD          = (15, 23, 42, 14)
SHADOW_RGBA_ELEVATED      = (15, 23, 42, 24)
SHADOW_RGBA_PRIMARY       = (37, 99, 235, 32)

# ── Chart palette ─────────────────────────────────────────────────────────────
CHART_COLORS = [
    "#2563EB",  # blue
    "#059669",  # emerald
    "#F59E0B",  # amber
    "#DC2626",  # red
    "#7C3AED",  # violet
    "#0D9488",  # teal
    "#DB2777",  # pink
    "#EA580C",  # orange
]
CHART_COLORS_LIGHT = [
    "#EFF6FF",  # blue light
    "#ECFDF5",  # green light
    "#FFFBEB",  # amber light
    "#FEF2F2",  # red light
    "#F5F3FF",  # violet light
    "#F0FDFA",  # teal light
    "#FDF2F8",  # pink light
    "#FFF7ED",  # orange light
]
