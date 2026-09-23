import os
import sys
import re
import importlib
import pytest
import numpy as np

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QImage

from ui.theme.theme_manager import _THEME_MODULES, _COLOR_ATTRS
from ui.theme.theme import Theme
from ui.theme import components as tc
from ui.dashboard_screen import _NAV_ITEMS


# ─────────────────────────────────────────────────────────────────────────────
# WCAG 2.1 Contrast Ratio Calculation (copied from test_theme_contrast.py)
# ─────────────────────────────────────────────────────────────────────────────


def _relative_luminance(hex_color: str) -> float:
    """
    Calculate relative luminance per WCAG 2.1 definition.

    Input: 6-digit hex color (e.g. "#FFFFFF")
    Output: luminance value in [0.0, 1.0]
    """
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

    def _lin(c):
        """Linearize sRGB component per WCAG 2.1."""
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _lin(r), _lin(g), _lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """
    Calculate contrast ratio per WCAG 2.1.

    Args:
        fg: Foreground color as 6-digit hex string
        bg: Background color as 6-digit hex string

    Returns:
        Contrast ratio >= 1.0, typically in [1.0, 21.0]
    """
    l1, l2 = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def composite(fg_hex: str, bg_hex: str, alpha: float) -> str:
    """
    Composite a foreground color over a background using alpha blending.

    Args:
        fg_hex: Foreground color as 6-digit hex string
        bg_hex: Background color as 6-digit hex string
        alpha: Alpha value (0.0-1.0)

    Returns:
        Composited color as 6-digit hex string
    """
    fg = fg_hex.lstrip("#")
    bg = bg_hex.lstrip("#")
    fg_r, fg_g, fg_b = int(fg[0:2], 16), int(fg[2:4], 16), int(fg[4:6], 16)
    bg_r, bg_g, bg_b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)

    r = round(alpha * fg_r + (1 - alpha) * bg_r)
    g = round(alpha * fg_g + (1 - alpha) * bg_g)
    b = round(alpha * fg_b + (1 - alpha) * bg_b)

    return f"#{r:02x}{g:02x}{b:02x}"


# ─────────────────────────────────────────────────────────────────────────────
# Pixel Sampling Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _pixel_at(widget, x, y):
    """Grab a widget and return the (r, g, b) color at local point (x, y)."""
    pm = widget.grab()
    img = pm.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    arr = np.frombuffer(img.constBits(), dtype=np.uint8).reshape(img.height(), img.bytesPerLine())
    arr = arr[:, : img.width() * 4].reshape(img.height(), img.width(), 4)
    r, g, b, a = arr[y, x]
    return int(r), int(g), int(b)


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _colors_close(c1, c2, tol=16):
    return all(abs(a - b) <= tol for a, b in zip(c1, c2))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_every_color_attr_defined():
    """
    For each theme module, confirm every name in _COLOR_ATTRS exists as an
    attribute on that module.
    """
    for theme_name, module_path in _THEME_MODULES.items():
        mod = importlib.import_module(module_path)
        missing = []
        for attr_name in _COLOR_ATTRS:
            if not hasattr(mod, attr_name):
                missing.append(attr_name)
        assert not missing, f"{theme_name}: missing attributes: {missing}"


def test_screen_accent_keys_match_nav():
    """
    For each theme module, verify that SCREEN_ACCENT_FILL and SCREEN_ACCENT_TINT
    keys match the canonical screen keys from _NAV_ITEMS.
    """
    nav_keys = {key for _, key in _NAV_ITEMS}

    for theme_name, module_path in _THEME_MODULES.items():
        mod = importlib.import_module(module_path)

        fill_keys = set(mod.SCREEN_ACCENT_FILL.keys())
        tint_keys = set(mod.SCREEN_ACCENT_TINT.keys())

        assert fill_keys == nav_keys, \
            f"{theme_name}: SCREEN_ACCENT_FILL keys {fill_keys} != nav keys {nav_keys}"
        assert tint_keys == nav_keys, \
            f"{theme_name}: SCREEN_ACCENT_TINT keys {tint_keys} != nav keys {nav_keys}"


def test_screen_accent_contrast():
    """
    For each theme module and each screen key, validate contrast ratios:
    - SIDEBAR_ACTIVE_TEXT vs SCREEN_ACCENT_FILL >= 4.5
    - SIDEBAR_ACTIVE_TEXT vs darkened fill >= 4.5
    - SCREEN_ACCENT_FILL vs SIDEBAR_BG >= 3.0
    - SCREEN_ACCENT_TINT vs SIDEBAR_BG >= 4.5
    - SCREEN_ACCENT_TINT vs SURFACE >= 4.5
    - SCREEN_ACCENT_TINT vs SIDEBAR_HOVER >= 3.0
    - SCREEN_ACCENT_TINT vs TOPBAR_BG >= 3.0
    """
    violations = []

    for theme_name, module_path in _THEME_MODULES.items():
        mod = importlib.import_module(module_path)

        for key in mod.SCREEN_ACCENT_FILL.keys():
            fill = mod.SCREEN_ACCENT_FILL[key]
            tint = mod.SCREEN_ACCENT_TINT[key]

            # Get referenced attributes
            sidebar_active_text = mod.SIDEBAR_ACTIVE_TEXT
            darkened_fill = tc.darken_hex(fill, 0.85)
            sidebar_bg = mod.SIDEBAR_BG
            surface = mod.SURFACE
            sidebar_hover = mod.SIDEBAR_HOVER
            topbar_bg = mod.TOPBAR_BG

            # Check each contrast requirement
            tests = [
                (sidebar_active_text, fill, 4.5, f"{theme_name}/{key}: SIDEBAR_ACTIVE_TEXT vs SCREEN_ACCENT_FILL"),
                (sidebar_active_text, darkened_fill, 4.5, f"{theme_name}/{key}: SIDEBAR_ACTIVE_TEXT vs darkened FILL"),
                (fill, sidebar_bg, 3.0, f"{theme_name}/{key}: SCREEN_ACCENT_FILL vs SIDEBAR_BG"),
                (tint, sidebar_bg, 4.5, f"{theme_name}/{key}: SCREEN_ACCENT_TINT vs SIDEBAR_BG"),
                (tint, surface, 4.5, f"{theme_name}/{key}: SCREEN_ACCENT_TINT vs SURFACE"),
                (tint, sidebar_hover, 3.0, f"{theme_name}/{key}: SCREEN_ACCENT_TINT vs SIDEBAR_HOVER"),
                (tint, topbar_bg, 3.0, f"{theme_name}/{key}: SCREEN_ACCENT_TINT vs TOPBAR_BG"),
            ]

            for fg, bg, min_ratio, desc in tests:
                ratio = contrast_ratio(fg, bg)
                if ratio < min_ratio:
                    violations.append(f"{desc}: {ratio:.2f} (need >= {min_ratio})")

    assert not violations, "\n".join(violations)


def test_card_gradient_contrast():
    """
    For each theme module and each card gradient stop (START and END), validate
    that all text colors meet minimum contrast:
    - TEXT_PRIMARY >= 4.5
    - TEXT_SECONDARY >= 4.5
    - TEXT_MUTED >= 4.5
    - SUCCESS_TEXT >= 4.5
    - DANGER_TEXT >= 4.5
    - WARNING_TEXT >= 4.5
    - INFO_TEXT >= 4.5
    - BORDER >= 3.0
    """
    violations = []

    for theme_name, module_path in _THEME_MODULES.items():
        mod = importlib.import_module(module_path)

        for stop_name in ["CARD_GRADIENT_START", "CARD_GRADIENT_END"]:
            stop = getattr(mod, stop_name)

            tests = [
                (mod.TEXT_PRIMARY, 4.5, f"TEXT_PRIMARY on {stop_name}"),
                (mod.TEXT_SECONDARY, 4.5, f"TEXT_SECONDARY on {stop_name}"),
                (mod.TEXT_MUTED, 4.5, f"TEXT_MUTED on {stop_name}"),
                (mod.SUCCESS_TEXT, 4.5, f"SUCCESS_TEXT on {stop_name}"),
                (mod.DANGER_TEXT, 4.5, f"DANGER_TEXT on {stop_name}"),
                (mod.WARNING_TEXT, 4.5, f"WARNING_TEXT on {stop_name}"),
                (mod.INFO_TEXT, 4.5, f"INFO_TEXT on {stop_name}"),
                (mod.BORDER, 3.0, f"BORDER on {stop_name}"),
            ]

            for fg, min_ratio, desc in tests:
                ratio = contrast_ratio(fg, stop)
                if ratio < min_ratio:
                    violations.append(f"{theme_name}/{desc}: {ratio:.2f} (need >= {min_ratio})")

    assert not violations, "\n".join(violations)


def test_accent_glyph_contrast(qapp):
    """
    For each theme, apply it globally, then for every accent name returned by
    Theme.accent_names(), validate contrast against card gradient stops:
    - color vs stop >= 3.0
    - color vs composite(color, stop, ACCENT_CHIP_ALPHA) >= 3.0
    """
    from ui.theme.theme_manager import ThemeManager

    violations = []

    for theme_name, module_path in _THEME_MODULES.items():
        ThemeManager.apply(theme_name, save=False, notify=False)

        for accent_name in Theme.accent_names():
            color = Theme.accent(accent_name)

            for stop_name in ["CARD_GRADIENT_START", "CARD_GRADIENT_END"]:
                stop = getattr(Theme, stop_name)

                # Test direct contrast
                ratio1 = contrast_ratio(color, stop)
                if ratio1 < 3.0:
                    violations.append(
                        f"{theme_name}/{accent_name} on {stop_name}: {ratio1:.2f} (need >= 3.0)"
                    )

                # Test contrast with composited chip
                chip_color = composite(color, stop, tc.ACCENT_CHIP_ALPHA)
                ratio2 = contrast_ratio(color, chip_color)
                if ratio2 < 3.0:
                    violations.append(
                        f"{theme_name}/{accent_name} chip on {stop_name}: {ratio2:.2f} (need >= 3.0)"
                    )

    assert not violations, "\n".join(violations)


def test_no_argb_hex_in_qss(qapp):
    """
    For each theme, apply it globally and build a combined QSS string from all
    style functions. Assert that no 8-digit hex colors (#RRGGBBAA) appear in
    the QSS (they should be rgba() format instead for cross-platform compatibility).
    """
    from ui.theme.theme_manager import ThemeManager

    for theme_name in _THEME_MODULES.keys():
        ThemeManager.apply(theme_name, save=False, notify=False)

        # Build combined QSS
        qss_parts = [
            Theme.get_stylesheet(),
            tc.metric_card_style(Theme, Theme.PRIMARY, Theme.SURFACE),
            tc.info_banner_style(Theme),
            tc.banner_style(Theme, level="info"),
            tc.banner_style(Theme, level="success"),
            tc.banner_style(Theme, level="warning"),
            tc.banner_style(Theme, level="danger"),
            tc.stat_tile_style(Theme, Theme.PRIMARY),
            tc.icon_chip_style(Theme, Theme.PRIMARY),
        ]
        combined = "\n".join(qss_parts)

        # Search for 8-digit hex patterns
        argb_matches = re.findall(r"#[0-9A-Fa-f]{8}\b", combined)
        assert not argb_matches, \
            f"{theme_name}: found 8-digit hex colors (should use rgba()): {argb_matches}"


def test_rgba_helper():
    """
    Verify the rgba() helper function produces correct rgba() strings.
    """
    result = tc.rgba("#4F46E5", 0.12)
    assert result == "rgba(79, 70, 229, 31)", f"Expected 'rgba(79, 70, 229, 31)', got {result!r}"


def test_kpi_tile_pixel_accent(qapp):
    """Verify KpiTile renders accent color at expected pixel location."""
    from ui.theme.theme_manager import ThemeManager
    ThemeManager.apply("Aurora", save=False, notify=False)
    from ui.widgets.kpi_tile import KpiTile
    tile = KpiTile("X", 1.0, accent="success", icon="trend")
    tile.resize(240, 105)
    tile.show()
    qapp.processEvents()
    color = _pixel_at(tile, 2, 52)
    expected = _hex_to_rgb(Theme.accent("success"))
    assert _colors_close(color, expected), f"expected {expected}, got {color}"


def test_summary_panel_pixel_accent(qapp):
    """Verify SummaryPanel renders accent color at expected pixel location."""
    from ui.theme.theme_manager import ThemeManager
    ThemeManager.apply("Aurora", save=False, notify=False)
    from ui.widgets.summary_panel import SummaryPanel
    panel = SummaryPanel("P", "trend", accent="warning")
    panel.resize(300, 200)
    panel.show()
    qapp.processEvents()
    color = _pixel_at(panel, 2, 100)
    expected = _hex_to_rgb(Theme.accent("warning"))
    assert _colors_close(color, expected), f"expected {expected}, got {color}"


def test_collapsible_section_pixel_accent(qapp):
    """Verify CollapsibleSection header renders accent color at expected pixel location."""
    from ui.theme.theme_manager import ThemeManager
    ThemeManager.apply("Aurora", save=False, notify=False)
    from ui.widgets.section import CollapsibleSection
    section = CollapsibleSection("S", accent="tax")
    header = section._header
    header.resize(300, 44)
    header.show()
    qapp.processEvents()
    color = _pixel_at(header, 2, 22)
    expected = _hex_to_rgb(Theme.screen_accent("tax"))
    assert _colors_close(color, expected), f"expected {expected}, got {color}"


def test_nav_button_pixel_accent(qapp):
    """Verify nav button renders screen accent color when checked."""
    from ui.theme.theme_manager import ThemeManager
    from PySide6.QtWidgets import QToolButton
    ThemeManager.apply("Aurora", save=False, notify=False)
    btn = QToolButton()
    btn.setCheckable(True)
    btn.setChecked(True)
    btn.setProperty("nav_item", "true")
    btn.setProperty("screen", "accounts")
    btn.setStyleSheet(Theme.get_stylesheet())
    btn.resize(200, 44)
    btn.show()
    qapp.processEvents()
    color = _pixel_at(btn, 16, 22)
    expected = _hex_to_rgb(Theme.screen_accent_fill("accounts"))
    assert _colors_close(color, expected), f"expected {expected}, got {color}"


def test_live_theme_switch_pixel(qapp):
    """Verify accent color updates after theme switch."""
    from ui.theme.theme_manager import ThemeManager
    from ui.widgets.kpi_tile import KpiTile
    ThemeManager.apply("Aurora", save=False, notify=False)
    tile = KpiTile("X", 1, accent="success", icon="trend")
    tile.resize(240, 105)
    tile.show()
    qapp.processEvents()
    color_aurora = _pixel_at(tile, 2, 52)
    expected_aurora = _hex_to_rgb(Theme.accent("success"))
    assert _colors_close(color_aurora, expected_aurora), f"Aurora: expected {expected_aurora}, got {color_aurora}"

    ThemeManager.apply("Nova", save=False, notify=False)
    tile.refresh_theme()
    qapp.processEvents()
    color_nova = _pixel_at(tile, 2, 52)
    expected_nova = _hex_to_rgb(Theme.accent("success"))
    assert _colors_close(color_nova, expected_nova), f"Nova: expected {expected_nova}, got {color_nova}"


def test_accent_widgets_not_overbright_dark(qapp):
    """Verify accent widgets in dark theme do not have excessive bright pixels."""
    from ui.theme.theme_manager import ThemeManager
    from ui.widgets.kpi_tile import KpiTile
    from ui.widgets.summary_panel import SummaryPanel
    ThemeManager.apply("Midnight Pro", save=False, notify=False)
    widgets = [
        KpiTile("X", 1.0, accent="success", icon="trend"),
        SummaryPanel("P", "trend", accent="warning"),
    ]
    for w in widgets:
        w.resize(240, 105)
        w.show()
    qapp.processEvents()
    for w in widgets:
        pm = w.grab()
        img = pm.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        arr = np.frombuffer(img.constBits(), dtype=np.uint8).reshape(img.height(), img.bytesPerLine())
        arr = arr[:, : img.width() * 4].reshape(img.height(), img.width(), 4)
        lum = 0.2126 * arr[:,:,0].astype(float) + 0.7152 * arr[:,:,1].astype(float) + 0.0722 * arr[:,:,2].astype(float)
        bright_ratio = (lum >= 216).mean()
        assert bright_ratio < 0.5, f"{type(w).__name__} is {bright_ratio:.1%} bright under Midnight Pro"


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup: Reset theme to Aurora before other tests run
# ─────────────────────────────────────────────────────────────────────────────


def test_cleanup_reset_theme(qapp):
    """
    Reset global theme state back to Aurora for subsequent tests.
    """
    from ui.theme.theme_manager import ThemeManager
    ThemeManager.apply("Aurora", save=False, notify=False)
