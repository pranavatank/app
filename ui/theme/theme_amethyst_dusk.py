"""
ui/theme/theme_amethyst_dusk.py — THEME 5: Amethyst Dusk
Sophisticated dark theme. Deep plum background, warm amethyst primary,
soft gold accents, muted rose highlights. Think premium fintech, Figma dark,
or a high-end private banking interface.
"""

NAME         = "Amethyst Dusk"
DESCRIPTION  = "Sophisticated dark — deep plum, warm amethyst, soft gold accents"
IS_DARK      = True
EMOJI        = "🔮"

# ── Primary — warm amethyst / soft violet ─────────────────────────────────────
PRIMARY                   = "#A78BFA"   # violet-400 — warm, readable on dark
PRIMARY_DARK              = "#8B5CF6"   # violet-500
PRIMARY_LIGHT             = "#1E1033"   # deep violet tint — used as bg accent
PRIMARY_TEXT              = "#FFFFFF"
PRIMARY_GRADIENT_START    = "#C4B5FD"   # violet-300 — lighter start
PRIMARY_GRADIENT_END      = "#7C3AED"   # violet-700 — rich end
PRIMARY_GRADIENT_HOVER_START = "#A78BFA"
PRIMARY_GRADIENT_HOVER_END   = "#6D28D9"

# ── Success — warm sage green ─────────────────────────────────────────────────
SUCCESS                   = "#6EE7B7"   # emerald-300 — soft on dark
SUCCESS_DARK              = "#34D399"   # emerald-400
SUCCESS_LIGHT             = "#022C22"   # deep emerald void
SUCCESS_GRADIENT_START    = "#A7F3D0"   # emerald-200
SUCCESS_GRADIENT_END      = "#059669"   # emerald-600

# ── Danger — warm coral (not harsh) ──────────────────────────────────────────
DANGER                    = "#FCA5A5"   # red-300 — soft coral on dark
DANGER_DARK               = "#F87171"   # red-400
DANGER_LIGHT              = "#2D0A0A"   # deep red void
DANGER_GRADIENT_START     = "#FCA5A5"
DANGER_GRADIENT_END       = "#DC2626"   # red-600

# ── Warning — soft gold / champagne ───────────────────────────────────────────
WARNING                   = "#FDE68A"   # amber-200 — champagne on dark
WARNING_DARK              = "#FBBF24"   # amber-400
WARNING_LIGHT             = "#2D1F00"   # deep amber void
WARNING_GRADIENT_START    = "#FEF3C7"   # amber-100
WARNING_GRADIENT_END      = "#F59E0B"   # amber-500

# ── Info — soft periwinkle blue ──────────────────────────────────────────────
INFO                      = "#93C5FD"   # blue-300 — periwinkle on dark
INFO_DARK                 = "#60A5FA"   # blue-400
INFO_LIGHT                = "#0D1F3C"   # deep blue void
INFO_GRADIENT_START       = "#BFDBFE"   # blue-200
INFO_GRADIENT_END         = "#3B82F6"   # blue-500

# ── Edit — rose gold ──────────────────────────────────────────────────────────
EDIT                      = "#FDA4AF"   # rose-300 — warm on dark
EDIT_DARK                 = "#FB7185"   # rose-400
EDIT_LIGHT                = "#2D0A15"   # deep rose void
EDIT_GRADIENT_START       = "#FECDD3"   # rose-200
EDIT_GRADIENT_END         = "#E11D48"   # rose-600

# ── Hero — amethyst → rose gradient ──────────────────────────────────────────
HERO_GRADIENT_START       = "#A78BFA"   # amethyst
HERO_GRADIENT_END         = "#FDA4AF"   # rose gold
HERO_GRADIENT_HOVER_START = "#8B5CF6"
HERO_GRADIENT_HOVER_END   = "#FB7185"

# ── Extra accents ─────────────────────────────────────────────────────────────
PURPLE       = "#A78BFA";  PURPLE_LIGHT  = "#1E1033"
TEAL         = "#5EEAD4";  TEAL_LIGHT    = "#022024"
ORANGE       = "#FDBA74";  ORANGE_LIGHT  = "#2D1000"
PINK         = "#FDA4AF";  PINK_LIGHT    = "#2D0A15"

# ── Surfaces — warm plum layers ──────────────────────────────────────────────
BG                        = "#0F0B1A"   # deep plum — near black
SURFACE                   = "#1A1330"   # card surface — dark grape
SURFACE_ALT               = "#231A40"   # hover / alt — lighter grape
SURFACE_TINT_START        = "#1E1736"
SURFACE_TINT_END          = "#1A1330"

# ── Sidebar — deepest plum ────────────────────────────────────────────────────
SIDEBAR_BG                = "#09061A"   # absolute plum void
SIDEBAR_TEXT              = "#5B4F7A"   # muted violet-grey
SIDEBAR_ACTIVE            = "#A78BFA"   # amethyst
SIDEBAR_ACTIVE_TEXT       = "#FFFFFF"
SIDEBAR_HOVER             = "#16102A"   # dark hover

# ── Topbar ────────────────────────────────────────────────────────────────────
TOPBAR_BG                 = "#1A1330"
TOPBAR_BORDER             = "#2A1F4A"

# ── Text — warm cool-white on plum ───────────────────────────────────────────
TEXT_PRIMARY              = "#E2D9F3"   # warm lavender-white
TEXT_SECONDARY            = "#9D8EC0"   # muted violet
TEXT_MUTED                = "#4A3D6A"   # very dim violet
TEXT_ON_PRIMARY           = "#FFFFFF"
TEXT_HEADING              = "#EDE9FE"   # bright lavender-white

# ── Borders — subtle violet ───────────────────────────────────────────────────
BORDER                    = "#2A1F4A"   # dark violet border
BORDER_FOCUS              = "#A78BFA"   # amethyst focus glow
DIVIDER                   = "#1E1638"

# ── Shadows — warm violet glow ────────────────────────────────────────────────
SHADOW_BLUR_CARD          = 24
SHADOW_BLUR_ELEVATED      = 44
SHADOW_OFFSET_Y           = 5
SHADOW_OFFSET_Y_ELEVATED  = 12
SHADOW_RGBA_CARD          = (10, 5, 30, 60)        # dark plum shadow
SHADOW_RGBA_ELEVATED      = (10, 5, 30, 100)
SHADOW_RGBA_PRIMARY       = (167, 139, 250, 50)    # amethyst glow

# ── Charts — jewel tones on dark ─────────────────────────────────────────────
CHART_COLORS = [
    "#A78BFA",  # amethyst
    "#6EE7B7",  # sage green
    "#FDE68A",  # champagne gold
    "#FCA5A5",  # coral
    "#93C5FD",  # periwinkle
    "#5EEAD4",  # teal
    "#FDA4AF",  # rose gold
    "#FDBA74",  # peach
]
CHART_COLORS_LIGHT = [
    "#1E1033",  # violet void
    "#022C22",  # green void
    "#2D1F00",  # amber void
    "#2D0A0A",  # red void
    "#0D1F3C",  # blue void
    "#022024",  # teal void
    "#2D0A15",  # rose void
    "#2D1000",  # orange void
]
