"""
ui/theme/theme_finance_pro.py — THEME 6: Finance Pro
Purpose-built for a financial application. Authoritative dark-navy background,
confident teal-green primary, gold accents. Feels like Bloomberg Terminal,
Zerodha Kite dark, or a premium trading dashboard.
Never boring — every panel has depth and meaning.
"""

NAME         = "Finance Pro"
DESCRIPTION  = "Financial-grade dark — authoritative navy, confident teal, gold accents"
IS_DARK      = True
EMOJI        = "📊"

# ── Primary — confident teal-blue (finance authority colour) ─────────────────
PRIMARY                   = "#00BCD4"   # strong cyan-teal
PRIMARY_DARK              = "#0097A7"   # deeper teal
PRIMARY_LIGHT             = "#002B33"   # dark teal tint
PRIMARY_TEXT              = "#000000"   # black on teal (high contrast)
PRIMARY_GRADIENT_START    = "#26C6DA"   # lighter teal
PRIMARY_GRADIENT_END      = "#0097A7"   # darker teal
PRIMARY_GRADIENT_HOVER_START = "#00BCD4"
PRIMARY_GRADIENT_HOVER_END   = "#00838F"

# ── Success — ticker green (profit colour) ────────────────────────────────────
SUCCESS                   = "#00E676"   # vivid market green
SUCCESS_DARK              = "#00C853"   # deeper green
SUCCESS_LIGHT             = "#00200F"   # dark green void
SUCCESS_GRADIENT_START    = "#69F0AE"   # bright green
SUCCESS_GRADIENT_END      = "#00C853"

# ── Danger — ticker red (loss colour) ────────────────────────────────────────
DANGER                    = "#FF5252"   # vivid market red
DANGER_DARK               = "#D50000"
DANGER_LIGHT              = "#200005"
DANGER_GRADIENT_START     = "#FF8A80"
DANGER_GRADIENT_END       = "#D50000"

# ── Warning — gold (premium signal colour) ───────────────────────────────────
WARNING                   = "#FFD740"   # gold / amber
WARNING_DARK              = "#FFC400"   # deeper gold
WARNING_LIGHT             = "#1E1500"
WARNING_GRADIENT_START    = "#FFE57F"   # pale gold
WARNING_GRADIENT_END      = "#FFA000"   # warm amber

# ── Info — soft blue (informational, data) ───────────────────────────────────
INFO                      = "#82B1FF"   # blue-accent
INFO_DARK                 = "#448AFF"
INFO_LIGHT                = "#0A0F2E"
INFO_GRADIENT_START       = "#B3CFFF"
INFO_GRADIENT_END         = "#2979FF"

# ── Edit — purple-violet (analytical / edit actions) ─────────────────────────
EDIT                      = "#CE93D8"   # soft purple
EDIT_DARK                 = "#AB47BC"
EDIT_LIGHT                = "#1A0521"
EDIT_GRADIENT_START       = "#E1BEE7"
EDIT_GRADIENT_END         = "#8E24AA"

# ── Hero — teal → blue (authority gradient) ───────────────────────────────────
HERO_GRADIENT_START       = "#00BCD4"
HERO_GRADIENT_END         = "#1565C0"   # deep blue
HERO_GRADIENT_HOVER_START = "#0097A7"
HERO_GRADIENT_HOVER_END   = "#0D47A1"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#CE93D8";  PURPLE_LIGHT  = "#1A0521"
TEAL         = "#00BCD4";  TEAL_LIGHT    = "#002B33"
ORANGE       = "#FFAB40";  ORANGE_LIGHT  = "#1E0D00"
PINK         = "#F48FB1";  PINK_LIGHT    = "#1E0010"

# ── Surfaces — deep navy layers (Bloomberg-style) ─────────────────────────────
BG                        = "#060B12"   # absolute dark navy — window
SURFACE                   = "#0C1825"   # card — deep blue-black
SURFACE_ALT               = "#132035"   # hover / alt rows — navy
SURFACE_TINT_START        = "#0F1E30"
SURFACE_TINT_END          = "#0C1825"

# ── Sidebar — deeper navy panel ───────────────────────────────────────────────
SIDEBAR_BG                = "#040810"   # deepest navy
SIDEBAR_TEXT              = "#37596E"   # muted steel blue
SIDEBAR_ACTIVE            = "#00BCD4"   # teal
SIDEBAR_ACTIVE_TEXT       = "#000000"   # black on teal
SIDEBAR_HOVER             = "#0C1825"

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#0C1825"
TOPBAR_BORDER             = "#132035"

# ── Text — cool blue-white (financial data style) ─────────────────────────────
TEXT_PRIMARY              = "#C8D8E8"   # cool blue-white
TEXT_SECONDARY            = "#4E7A90"   # steel blue-grey
TEXT_MUTED                = "#1C3A50"   # dim navy
TEXT_ON_PRIMARY           = "#000000"   # black on teal
TEXT_HEADING              = "#E0EEF8"   # bright cool white

# ── Borders — dark steel ──────────────────────────────────────────────────────
BORDER                    = "#132035"   # dark navy border
BORDER_FOCUS              = "#00BCD4"   # teal focus
DIVIDER                   = "#0C1825"

# ── Shadows — dark navy glow ──────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 26
SHADOW_BLUR_ELEVATED      = 45
SHADOW_OFFSET_Y           = 5
SHADOW_OFFSET_Y_ELEVATED  = 12
SHADOW_RGBA_CARD          = (0, 188, 212, 18)    # teal glow (subtle)
SHADOW_RGBA_ELEVATED      = (0, 188, 212, 40)    # stronger teal glow
SHADOW_RGBA_PRIMARY       = (0, 188, 212, 65)    # intense teal glow

# ── Charts — financial data palette ───────────────────────────────────────────
CHART_COLORS = [
    "#00BCD4",  # teal — primary data
    "#00E676",  # green — profit / positive
    "#FF5252",  # red — loss / negative
    "#FFD740",  # gold — significant
    "#82B1FF",  # blue — informational
    "#CE93D8",  # purple — analytical
    "#FFAB40",  # orange — alert
    "#F48FB1",  # pink — secondary
]
CHART_COLORS_LIGHT = [
    "#002B33",  # teal void
    "#00200F",  # green void
    "#200005",  # red void
    "#1E1500",  # gold void
    "#0A0F2E",  # blue void
    "#1A0521",  # purple void
    "#1E0D00",  # orange void
    "#1E0010",  # pink void
]
