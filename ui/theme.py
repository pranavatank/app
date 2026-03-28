"""
ui/theme.py — Complete modern theme system.

Color palette inspired by the Flutter app reference:
  Primary  : Blue    #2563EB → #1E40AF
  Accent   : Green   #10B981 → #059669
  Error    : Red     #EF4444
  Warning  : Amber   #F59E0B
  Info     : Blue    #3B82F6
  Surface  : White   #FFFFFF
  BG       : Slate   #F8FAFC
"""

from PyQt6.QtGui import QColor


class Theme:
    # ── Color Tokens ─────────────────────────────────────────────────────────
    # Primary brand blue
    PRIMARY        = "#2563EB"
    PRIMARY_DARK   = "#1E40AF"
    PRIMARY_LIGHT  = "#DBEAFE"
    PRIMARY_TEXT   = "#FFFFFF"

    # Accent green
    SUCCESS        = "#10B981"
    SUCCESS_DARK   = "#059669"
    SUCCESS_LIGHT  = "#D1FAE5"

    # Status colours
    DANGER         = "#EF4444"
    DANGER_DARK    = "#DC2626"
    DANGER_LIGHT   = "#FEE2E2"

    WARNING        = "#F59E0B"
    WARNING_DARK   = "#D97706"
    WARNING_LIGHT  = "#FEF3C7"

    INFO           = "#3B82F6"
    INFO_DARK      = "#2563EB"
    INFO_LIGHT     = "#DBEAFE"

    PURPLE         = "#8B5CF6"
    PURPLE_LIGHT   = "#EDE9FE"

    TEAL           = "#06B6D4"
    TEAL_LIGHT     = "#CFFAFE"

    # Neutral surface colours
    BG             = "#F8FAFC"      # page background
    SURFACE        = "#FFFFFF"      # card / panel surface
    SURFACE_ALT    = "#F1F5F9"      # alternate row / hover

    # Sidebar
    SIDEBAR_BG     = "#1E293B"      # deep slate sidebar
    SIDEBAR_TEXT   = "#94A3B8"
    SIDEBAR_ACTIVE = "#2563EB"
    SIDEBAR_ACTIVE_TEXT = "#FFFFFF"
    SIDEBAR_HOVER  = "#334155"

    # Top bar
    TOPBAR_BG      = "#FFFFFF"
    TOPBAR_BORDER  = "#E2E8F0"

    # Text
    TEXT_PRIMARY   = "#0F172A"
    TEXT_SECONDARY = "#64748B"
    TEXT_MUTED     = "#94A3B8"
    TEXT_ON_PRIMARY= "#FFFFFF"

    # Border / divider
    BORDER         = "#E2E8F0"
    DIVIDER        = "#F1F5F9"

    # Chart palette
    CHART_COLORS   = ["#2563EB","#10B981","#F59E0B","#EF4444",
                      "#8B5CF6","#06B6D4","#EC4899","#F97316"]

    @staticmethod
    def get_colors(theme_name: str | None = None) -> dict:
        """Return a color dictionary (future-proofed for multiple themes)."""
        t = Theme

        # Currently a single light theme; theme_name is reserved for future variants.
        return {
            # Base brand colors
            "primary":        t.PRIMARY,
            "primary_dark":   t.PRIMARY_DARK,
            "primary_light":  t.PRIMARY_LIGHT,
            "success":        t.SUCCESS,
            "success_dark":   t.SUCCESS_DARK,
            "success_light":  t.SUCCESS_LIGHT,
            "danger":         t.DANGER,
            "danger_dark":    t.DANGER_DARK,
            "danger_light":   t.DANGER_LIGHT,
            "warning":        t.WARNING,
            "warning_dark":   t.WARNING_DARK,
            "warning_light":  t.WARNING_LIGHT,
            "info":           t.INFO,
            "info_light":     t.INFO_LIGHT,
            "purple":         t.PURPLE,
            "purple_light":   t.PURPLE_LIGHT,
            "teal":           t.TEAL,
            "teal_light":     t.TEAL_LIGHT,

            # Surfaces / text
            "bg":             t.BG,
            "bg_primary":     t.SURFACE,      # used by charts
            "bg_secondary":   t.SURFACE_ALT,  # used by charts
            "surface":        t.SURFACE,
            "surface_alt":    t.SURFACE_ALT,
            "sidebar_bg":     t.SIDEBAR_BG,
            "sidebar_text":   t.SIDEBAR_TEXT,
            "text_primary":   t.TEXT_PRIMARY,
            "text_secondary": t.TEXT_SECONDARY,
            "text_muted":     t.TEXT_MUTED,

            # Borders
            "border":         t.BORDER,
            "divider":        t.DIVIDER,

            # Charts
            "chart_colors":   t.CHART_COLORS,
            "chart_1":        t.CHART_COLORS[0],
            "chart_2":        t.CHART_COLORS[1],
            "chart_3":        t.CHART_COLORS[2],
            "chart_4":        t.CHART_COLORS[3],
            "chart_5":        t.CHART_COLORS[4],
            "chart_6":        t.CHART_COLORS[5],
            "chart_7":        t.CHART_COLORS[6],
            "chart_8":        t.CHART_COLORS[7],
        }

    @staticmethod
    def get_settings_styles() -> dict:
        """Dedicated Settings screen styles to avoid parent stylesheet conflicts."""
        t = Theme
        return {
            "section_group": (
                "border: none;"
                "margin-top: 8px;"
                "background: transparent;"
                "font-size: 14px;"
                "font-weight: 700;"
                f"color: {t.TEXT_PRIMARY};"
            ),
            "card": (
                "background-color: #FFFFFF;"
                "border: 1px solid #d9e2ec;"
                "border-radius: 14px;"
                "padding: 16px;"
            ),
            "card_title": f"color: {t.TEXT_PRIMARY}; font-size: 13px; font-weight: 700;",
            "text": f"color: {t.TEXT_PRIMARY}; font-size: 14px;",
            "muted": f"color: {t.TEXT_SECONDARY}; font-size: 13px;",
            "warning": f"color: {t.WARNING_DARK}; font-size: 13px; font-weight: 600;",
            "line_edit": (
                "background-color: #FFFFFF;"
                f"color: {t.TEXT_PRIMARY};"
                f"border: 1px solid {t.BORDER};"
                "border-radius: 9px;"
                "padding: 8px 10px;"
                "font-size: 14px;"
            ),
            "checkbox": f"color: {t.TEXT_PRIMARY}; font-size: 14px;",
            "button_primary": (
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {t.PRIMARY}, stop:1 {t.PRIMARY_DARK});"
                "color: #FFFFFF;"
                "border: none;"
                "border-radius: 10px;"
                "font-size: 14px;"
                "font-weight: 700;"
                "padding: 8px 14px;"
                "min-height: 34px;"
            ),
            "button_success": (
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {t.SUCCESS}, stop:1 {t.SUCCESS_DARK});"
                "color: #FFFFFF;"
                "border: none;"
                "border-radius: 10px;"
                "font-size: 14px;"
                "font-weight: 700;"
                "padding: 8px 14px;"
                "min-height: 34px;"
            ),
            "button_danger": (
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {t.DANGER}, stop:1 {t.DANGER_DARK});"
                "color: #FFFFFF;"
                "border: none;"
                "border-radius: 10px;"
                "font-size: 14px;"
                "font-weight: 700;"
                "padding: 8px 14px;"
                "min-height: 34px;"
            ),
        }

    @staticmethod
    def get_stylesheet() -> str:
        t = Theme
        return f"""
/* ═══════════════════════════════════════════════════════
   BASE
═══════════════════════════════════════════════════════ */
QMainWindow, QWidget {{
    background-color: {t.BG};
    color: {t.TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
}}
QDialog {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
}}
QLabel {{
    color: {t.TEXT_PRIMARY};
    background: transparent;
    border: none;
}}

/* ═══════════════════════════════════════════════════════
   INPUTS
═══════════════════════════════════════════════════════ */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
    selection-background-color: {t.PRIMARY_LIGHT};
    selection-color: {t.PRIMARY_DARK};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {t.PRIMARY};
    background-color: {t.SURFACE};
    outline: none;
}}
QLineEdit:hover, QTextEdit:hover {{
    border-color: {t.INFO};
}}
QLineEdit[readOnly="true"] {{
    background-color: {t.SURFACE_ALT};
    color: {t.TEXT_SECONDARY};
}}

/* ═══════════════════════════════════════════════════════
   COMBO BOX
═══════════════════════════════════════════════════════ */
QComboBox {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 14px;
    min-height: 18px;
}}
QComboBox:hover {{ border-color: {t.INFO}; }}
QComboBox:focus {{ border-color: {t.PRIMARY}; }}
QComboBox::drop-down {{
    border: none; width: 28px;
    subcontrol-position: right center;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t.TEXT_SECONDARY};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER};
    border-radius: 8px;
    selection-background-color: {t.PRIMARY_LIGHT};
    selection-color: {t.PRIMARY_DARK};
    padding: 4px;
    outline: none;
}}

/* ═══════════════════════════════════════════════════════
   SPIN BOX / DATE EDIT
═══════════════════════════════════════════════════════ */
QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 14px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border-color: {t.PRIMARY};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    border: none; width: 22px;
    background: {t.SURFACE_ALT};
}}
QDateEdit::drop-down {{ border: none; width: 28px; }}

/* ═══════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════ */
QPushButton {{
    background-color: {t.PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 600;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {t.PRIMARY_DARK};
}}
QPushButton:pressed {{
    background-color: {t.PRIMARY_DARK};
}}
QPushButton:disabled {{
    background-color: {t.SURFACE_ALT};
    color: {t.TEXT_MUTED};
}}
QPushButton#primaryBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t.PRIMARY}, stop:1 {t.PRIMARY_DARK});
    color: #FFFFFF;
}}
QPushButton#primaryBtn:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t.PRIMARY_DARK}, stop:1 {t.PRIMARY});
}}
QPushButton#secondaryBtn {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
    border: 1.5px solid {t.BORDER};
}}
QPushButton#secondaryBtn:hover {{
    background-color: {t.PRIMARY_LIGHT};
    border-color: {t.PRIMARY};
    color: {t.PRIMARY_DARK};
}}
QPushButton#successBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t.SUCCESS}, stop:1 {t.SUCCESS_DARK});
    color: #FFFFFF;
}}
QPushButton#successBtn:hover {{ background-color: {t.SUCCESS_DARK}; }}
QPushButton#dangerBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t.DANGER}, stop:1 {t.DANGER_DARK});
    color: #FFFFFF;
}}
QPushButton#dangerBtn:hover {{ background-color: {t.DANGER_DARK}; }}
QPushButton#warningBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t.WARNING}, stop:1 {t.WARNING_DARK});
    color: #FFFFFF;
}}

/* ═══════════════════════════════════════════════════════
   TABLE
═══════════════════════════════════════════════════════ */
QTableWidget {{
    background-color: {t.SURFACE};
    alternate-background-color: {t.SURFACE_ALT};
    color: {t.TEXT_PRIMARY};
    gridline-color: {t.DIVIDER};
    border: 1px solid {t.BORDER};
    border-radius: 10px;
    selection-background-color: {t.PRIMARY_LIGHT};
    selection-color: {t.PRIMARY_DARK};
    font-size: 14px;
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableWidget::item:selected {{
    background-color: {t.PRIMARY_LIGHT};
    color: {t.PRIMARY_DARK};
}}
QTableWidget::item:hover {{
    background-color: {t.SURFACE_ALT};
}}
QHeaderView::section {{
    background-color: {t.SURFACE_ALT};
    color: {t.TEXT_SECONDARY};
    padding: 10px 8px;
    border: none;
    border-bottom: 2px solid {t.BORDER};
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* ═══════════════════════════════════════════════════════
   SCROLL BAR
═══════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent;
    width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t.BORDER};
    border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.PRIMARY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 8px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t.BORDER}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {t.PRIMARY}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ═══════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════ */
QTabWidget::pane {{
    border: 1px solid {t.BORDER};
    border-radius: 10px;
    background-color: {t.SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {t.SURFACE_ALT};
    color: {t.TEXT_SECONDARY};
    padding: 10px 22px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 3px;
    font-weight: 500;
    font-size: 14px;
    border: 1px solid {t.BORDER};
    border-bottom: none;
}}
QTabBar::tab:selected {{
    background-color: {t.PRIMARY};
    color: #FFFFFF;
    font-weight: 700;
    border-color: {t.PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background-color: {t.PRIMARY_LIGHT};
    color: {t.PRIMARY_DARK};
    border-color: {t.PRIMARY};
}}

/* ═══════════════════════════════════════════════════════
   GROUP BOX
═══════════════════════════════════════════════════════ */
QGroupBox {{
    border: 1px solid {t.BORDER};
    border-radius: 10px;
    margin-top: 18px;
    padding: 16px 16px 12px 16px;
    background-color: {t.SURFACE};
    font-weight: 700;
    font-size: 14px;
    color: {t.PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    background-color: {t.SURFACE};
    color: {t.PRIMARY};
}}

/* ═══════════════════════════════════════════════════════
   CHECKBOX / RADIO
═══════════════════════════════════════════════════════ */
QCheckBox, QRadioButton {{
    color: {t.TEXT_PRIMARY};
    spacing: 8px; font-size: 14px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px; height: 18px;
    border: 2px solid {t.BORDER};
    border-radius: 4px;
    background-color: {t.SURFACE};
}}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {t.PRIMARY};
    border-color: {t.PRIMARY};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {t.PRIMARY};
}}

/* ═══════════════════════════════════════════════════════
   PROGRESS BAR
═══════════════════════════════════════════════════════ */
QProgressBar {{
    border: 1.5px solid {t.BORDER};
    border-radius: 8px;
    background-color: {t.SURFACE_ALT};
    text-align: center;
    color: {t.TEXT_PRIMARY};
    font-weight: 600;
    height: 22px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t.PRIMARY}, stop:1 {t.SUCCESS});
    border-radius: 6px;
}}

/* ═══════════════════════════════════════════════════════
   MENU / TOOLTIP
═══════════════════════════════════════════════════════ */
QMenu {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
    border: 1px solid {t.BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}
QMenu::item:selected {{
    background-color: {t.PRIMARY_LIGHT};
    color: {t.PRIMARY_DARK};
}}
QToolTip {{
    background-color: {t.TEXT_PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ═══════════════════════════════════════════════════════
   SCROLL AREA
═══════════════════════════════════════════════════════ */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ═══════════════════════════════════════════════════════
   MESSAGE BOX
═══════════════════════════════════════════════════════ */
QMessageBox {{
    background-color: {t.SURFACE};
    color: {t.TEXT_PRIMARY};
}}
QMessageBox QLabel {{ color: {t.TEXT_PRIMARY}; }}
QMessageBox QPushButton {{
    min-width: 80px; min-height: 32px;
}}

/* ═══════════════════════════════════════════════════════
   NAMED OBJECT STYLES
═══════════════════════════════════════════════════════ */
QWidget#sidebar {{
    background-color: {t.SIDEBAR_BG};
    border-right: 1px solid rgba(255,255,255,0.06);
}}
QWidget#topBar {{
    background-color: {t.TOPBAR_BG};
    border-bottom: 1px solid {t.TOPBAR_BORDER};
}}
QWidget#topBar QComboBox {{
    font-size: 13px;
    padding: 6px 10px;
}}
QWidget#topBar QPushButton {{
    font-size: 13px;
    padding: 6px 12px;
}}
QWidget#contentArea {{
    background-color: {t.BG};
}}
QFrame#card {{
    background-color: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: 12px;
}}
QFrame#actionBar {{
    background-color: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: 12px;
    padding: 10px 12px;
}}
QFrame#cardAccent {{
    background-color: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-left: 4px solid {t.PRIMARY};
    border-radius: 12px;
}}
QFrame#dividerLine {{
    background-color: {t.DIVIDER};
    border: none; max-height: 1px;
}}
/* Settings screen cards now reuse the general card style via objectName "card" */
QFrame#filterBar {{
    background-color: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: 10px;
    padding: 6px 4px;
}}
QFrame#stepCard {{
    background-color: {t.SURFACE};
    border: 1px solid {t.BORDER};
    border-radius: 12px;
}}
QLabel#pageTitle {{
    color: {t.TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 700;
}}
QLabel#sectionTitle {{
    color: {t.TEXT_SECONDARY};
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QLabel#errorLabel  {{ color: {t.DANGER};  font-size: 12px; }}
QLabel#warningLabel{{ color: {t.WARNING}; font-size: 12px; }}
QLabel#successLabel{{ color: {t.SUCCESS}; font-size: 12px; }}
QLabel#mutedLabel  {{ color: {t.TEXT_MUTED}; font-size: 12px; }}
"""
