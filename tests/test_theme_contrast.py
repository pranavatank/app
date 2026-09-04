"""
tests/test_theme_contrast.py — WCAG AA contrast gate over theme palettes.

Validates that text-on-background and other critical color pairs in each theme
meet WCAG 2.1 AA contrast requirements (4.5:1 for text, 3:1 for UI components).

56 of 140 contrast checks currently fail across the 14 pairs with existing tokens;
8 additional pairs reference tokens that do not yet exist (TOOLTIP_FG, TOOLTIP_BG,
FOCUS_RING, DANGER_TEXT, SUCCESS_TEXT, WARNING_TEXT, INFO_TEXT, ICON_DEFAULT).

T037 will add the missing tokens. T039 will consolidate themes. This gate proves
both changes landed correctly by requiring all pairs to pass once they exist.
"""

import importlib
import pytest
from ui.theme.theme_manager import _THEME_MODULES


# ─────────────────────────────────────────────────────────────────────────────
# WCAG 2.1 Contrast Ratio Calculation
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


class TestContrastMath:
    """Verify the WCAG 2.1 math is correct.

    This test must ALWAYS pass (no xfail). A contrast checker that is itself
    wrong would silently bless a broken palette.
    """

    def test_black_on_white(self):
        """#000000 on #FFFFFF must be exactly 21.0 ±0.01."""
        ratio = contrast_ratio("#000000", "#FFFFFF")
        assert abs(ratio - 21.0) < 0.01, f"Expected 21.0, got {ratio}"

    def test_white_on_white(self):
        """#FFFFFF on #FFFFFF must be exactly 1.0."""
        ratio = contrast_ratio("#FFFFFF", "#FFFFFF")
        assert abs(ratio - 1.0) < 0.01, f"Expected 1.0, got {ratio}"

    def test_gray_on_white(self):
        """#767676 on #FFFFFF should be ~4.54."""
        ratio = contrast_ratio("#767676", "#FFFFFF")
        assert 4.5 < ratio < 4.6, f"Expected ~4.54, got {ratio}"


# ─────────────────────────────────────────────────────────────────────────────
# Required Contrast Pairs
# ─────────────────────────────────────────────────────────────────────────────


REQUIRED_PAIRS = [
    ("TEXT_PRIMARY",   "BG",            4.5),
    ("TEXT_PRIMARY",   "SURFACE",       4.5),
    ("TEXT_SECONDARY", "SURFACE",       4.5),
    ("TEXT_MUTED",     "SURFACE",       4.5),
    ("TEXT_ON_PRIMARY","PRIMARY",       4.5),
    ("PRIMARY_DARK",   "PRIMARY_LIGHT", 4.5),
    ("TOOLTIP_FG",     "TOOLTIP_BG",    4.5),
    ("SIDEBAR_TEXT",   "SIDEBAR_BG",    4.5),
    ("TEXT_SECONDARY", "SURFACE_ALT",   4.5),
    ("BORDER",         "SURFACE",       3.0),
    ("FOCUS_RING",     "SURFACE",       3.0),
    ("FOCUS_RING",     "PRIMARY",       3.0),
    ("DANGER_TEXT",    "SURFACE",       4.5),
    ("SUCCESS_TEXT",   "SURFACE",       4.5),
    ("WARNING_TEXT",   "SURFACE",       4.5),
    ("INFO_TEXT",      "SURFACE",       4.5),
    ("ICON_DEFAULT",   "SIDEBAR_BG",    3.0),
]


# ─────────────────────────────────────────────────────────────────────────────
# Baseline: Themes Currently Failing
# ─────────────────────────────────────────────────────────────────────────────


_BASELINE_FAILING: set[str] = set()
# All 4 surviving themes now pass all 17 pairs (verified: 0 violations of 68).
# This set exists so a future regression can be recorded deliberately rather than
# by weakening the gate. T037 and T039 validated the palettes at 0 violations.


# ─────────────────────────────────────────────────────────────────────────────
# Per-Theme Contrast Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "theme_name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason=f"56 of 140 contrast checks fail across themes; T037/T039 will fix",
            )
        ) if name in _BASELINE_FAILING else name
        for name in _THEME_MODULES.keys()
    ],
)
def test_theme_contrast(theme_name: str):
    """
    Test that all required color pairs in a theme meet WCAG AA requirements.

    Each theme is parametrised with an xfail marker if it's currently failing.
    A theme added later (or fixed) is required to pass. Missing tokens are
    reported as "missing" violations, not skipped.
    """
    mod = importlib.import_module(_THEME_MODULES[theme_name])
    violations = []

    for fg_token, bg_token, min_ratio in REQUIRED_PAIRS:
        fg_val = getattr(mod, fg_token, None)
        bg_val = getattr(mod, bg_token, None)

        # Check for missing tokens
        if fg_val is None:
            violations.append(f"{fg_token} on {bg_token}: missing {fg_token} (need >= {min_ratio})")
            continue
        if bg_val is None:
            violations.append(f"{fg_token} on {bg_token}: missing {bg_token} (need >= {min_ratio})")
            continue

        # Check if values are parseable as 6-digit hex
        if not isinstance(fg_val, str) or not fg_val.startswith("#") or len(fg_val) != 7:
            violations.append(f"{fg_token} on {bg_token}: unparseable {fg_token} = {fg_val!r} (need >= {min_ratio})")
            continue
        if not isinstance(bg_val, str) or not bg_val.startswith("#") or len(bg_val) != 7:
            violations.append(f"{fg_token} on {bg_token}: unparseable {bg_token} = {bg_val!r} (need >= {min_ratio})")
            continue

        # Calculate contrast ratio
        try:
            ratio = contrast_ratio(fg_val, bg_val)
            if ratio < min_ratio:
                violations.append(f"{fg_token} on {bg_token}: {ratio:.2f} (need >= {min_ratio})")
        except Exception as e:
            violations.append(f"{fg_token} on {bg_token}: error calculating ratio: {e} (need >= {min_ratio})")

    # Assert all violations are empty
    assert not violations, "\n".join(violations)


# ─────────────────────────────────────────────────────────────────────────────
# Summary Test: Record Today's Baseline
# ─────────────────────────────────────────────────────────────────────────────


def test_gradient_contrast():
    """
    Test that gradient stops for all colored families pass WCAG AA contrast
    with their corresponding TEXT_ON_* tokens.

    For each theme and family (PRIMARY, SUCCESS, DANGER, WARNING, INFO, EDIT, HERO),
    validates that the family's text token clears 4.5:1 against EVERY defined stop:
    _GRADIENT_START, _GRADIENT_END, _GRADIENT_HOVER_START, _GRADIENT_HOVER_END.
    """
    gradient_stops = ["_GRADIENT_START", "_GRADIENT_END", "_GRADIENT_HOVER_START", "_GRADIENT_HOVER_END"]
    families = ["PRIMARY", "SUCCESS", "DANGER", "WARNING", "INFO", "EDIT", "HERO"]
    text_tokens = {
        "PRIMARY": "TEXT_ON_PRIMARY",
        "SUCCESS": "TEXT_ON_SUCCESS",
        "DANGER": "TEXT_ON_DANGER",
        "WARNING": "TEXT_ON_WARNING",
        "INFO": "TEXT_ON_INFO",
        "EDIT": "TEXT_ON_EDIT",
        "HERO": "TEXT_ON_HERO",
    }

    violations = []

    for theme_name in _THEME_MODULES.keys():
        mod = importlib.import_module(_THEME_MODULES[theme_name])

        for family in families:
            text_token = text_tokens[family]
            text_val = getattr(mod, text_token, None)

            if text_val is None:
                violations.append(f"{theme_name}: {text_token} missing")
                continue

            # Check if text token is parseable as 6-digit hex
            if not isinstance(text_val, str) or not text_val.startswith("#") or len(text_val) != 7:
                violations.append(f"{theme_name}: {text_token} unparseable = {text_val!r}")
                continue

            # Check each gradient stop
            for stop in gradient_stops:
                stop_attr = family + stop
                stop_val = getattr(mod, stop_attr, None)

                if stop_val is None:
                    # Some themes may not define all stops (e.g. SUCCESS doesn't have hover stops)
                    continue

                # Check if stop is parseable
                if not isinstance(stop_val, str) or not stop_val.startswith("#") or len(stop_val) != 7:
                    violations.append(f"{theme_name}: {stop_attr} unparseable = {stop_val!r}")
                    continue

                # Calculate contrast ratio
                try:
                    ratio = contrast_ratio(text_val, stop_val)
                    if ratio < 4.5:
                        violations.append(
                            f"{theme_name}: {text_token} on {stop_attr}: {ratio:.2f} (need >= 4.5)"
                        )
                except Exception as e:
                    violations.append(f"{theme_name}: {text_token} on {stop_attr}: error: {e}")

    # Assert all violations are empty
    assert not violations, "\n".join(violations)


def test_contrast_summary(capsys):
    """
    Compute and print contrast check totals across all themes.

    This test always passes (no xfail) and serves as a human-readable record
    of today's baseline. Reports are split into contrast failures (token exists
    but pair below min ratio) and missing tokens (token not yet defined), since
    these are fixed by different tasks (T039 and T037 respectively).

    Reconciliation with audit baseline: The audit measured 56 failures over its
    14-pair set. This contract's 17-pair set replaces 5 of those pairs (DANGER,
    SUCCESS, WARNING, INFO on SURFACE, and BORDER_FOCUS on SURFACE) with
    *_TEXT and FOCUS_RING variants that do not exist yet — moving exactly 19
    failures from contrast-failure to missing-token bucket: 56 - 19 = 37.

    The numbers reported should be:
    - Total checks: 170 (17 pairs × 10 themes)
    - Expressible checks: 90 (checks where both tokens exist and parse)
    - Contrast failures: 37
    - Missing tokens: 80
    - Total violations: 117
    """
    all_violations = {}
    total_checks = 0
    total_expressible_checks = 0
    total_contrast_failures = 0
    total_missing_tokens = 0

    for theme_name in _THEME_MODULES.keys():
        mod = importlib.import_module(_THEME_MODULES[theme_name])
        theme_violations = []
        theme_contrast_failures = 0
        theme_missing_tokens = 0

        for fg_token, bg_token, min_ratio in REQUIRED_PAIRS:
            total_checks += 1
            fg_val = getattr(mod, fg_token, None)
            bg_val = getattr(mod, bg_token, None)

            # Check for missing tokens
            if fg_val is None or bg_val is None:
                total_missing_tokens += 1
                theme_missing_tokens += 1
                theme_violations.append({
                    "type": "missing",
                    "pair": (fg_token, bg_token),
                    "reason": f"missing {fg_token if fg_val is None else bg_token}",
                })
                continue

            # Check if values are parseable as 6-digit hex
            if (not isinstance(fg_val, str) or not fg_val.startswith("#") or len(fg_val) != 7 or
                not isinstance(bg_val, str) or not bg_val.startswith("#") or len(bg_val) != 7):
                total_missing_tokens += 1
                theme_missing_tokens += 1
                theme_violations.append({
                    "type": "unparseable",
                    "pair": (fg_token, bg_token),
                    "fg": fg_val,
                    "bg": bg_val,
                })
                continue

            # Both tokens exist and parse; this is an expressible check
            total_expressible_checks += 1

            # Calculate contrast ratio
            try:
                ratio = contrast_ratio(fg_val, bg_val)
                if ratio < min_ratio:
                    total_contrast_failures += 1
                    theme_contrast_failures += 1
                    theme_violations.append({
                        "type": "contrast_fail",
                        "pair": (fg_token, bg_token),
                        "ratio": ratio,
                        "min_ratio": min_ratio,
                    })
            except Exception as e:
                total_contrast_failures += 1
                theme_contrast_failures += 1
                theme_violations.append({
                    "type": "error",
                    "pair": (fg_token, bg_token),
                    "error": str(e),
                })

        all_violations[theme_name] = (theme_violations, theme_contrast_failures, theme_missing_tokens)

    total_violations = total_contrast_failures + total_missing_tokens

    # Print summary table
    print("\n" + "="*80)
    print("WCAG AA CONTRAST GATE BASELINE")
    print("="*80)
    print(f"\nTotal checks:         {total_checks}")
    print(f"Expressible checks:   {total_expressible_checks}")
    print(f"Contrast failures:    {total_contrast_failures}")
    print(f"Missing tokens:       {total_missing_tokens}")
    print(f"Total violations:     {total_violations}")
    print("\nViolations by theme (contrast failures | missing tokens | total):")
    print("-" * 80)
    for theme_name in _THEME_MODULES.keys():
        theme_violations, theme_contrast_failures, theme_missing_tokens = all_violations[theme_name]
        theme_total = len(theme_violations)
        print(f"{theme_name:.<35} {theme_contrast_failures:>3} | {theme_missing_tokens:>3} | {theme_total:>3}")
    print("-" * 80)
    print(f"{'TOTAL':.<35} {total_contrast_failures:>3} | {total_missing_tokens:>3} | {total_violations:>3}")
    print("="*80 + "\n")

    # Compute and print gradient stop coverage
    gradient_stops = ["_GRADIENT_START", "_GRADIENT_END", "_GRADIENT_HOVER_START", "_GRADIENT_HOVER_END"]
    families = ["PRIMARY", "SUCCESS", "DANGER", "WARNING", "INFO", "EDIT", "HERO"]
    text_tokens = {
        "PRIMARY": "TEXT_ON_PRIMARY",
        "SUCCESS": "TEXT_ON_SUCCESS",
        "DANGER": "TEXT_ON_DANGER",
        "WARNING": "TEXT_ON_WARNING",
        "INFO": "TEXT_ON_INFO",
        "EDIT": "TEXT_ON_EDIT",
        "HERO": "TEXT_ON_HERO",
    }

    gradient_checks_count = 0
    gradient_results = {}  # theme -> family -> worst_ratio

    for theme_name in _THEME_MODULES.keys():
        mod = importlib.import_module(_THEME_MODULES[theme_name])
        gradient_results[theme_name] = {}

        for family in families:
            text_token = text_tokens[family]
            text_val = getattr(mod, text_token, None)

            if text_val is None or not isinstance(text_val, str) or not text_val.startswith("#") or len(text_val) != 7:
                gradient_results[theme_name][family] = None
                continue

            worst_ratio = None
            for stop in gradient_stops:
                stop_attr = family + stop
                stop_val = getattr(mod, stop_attr, None)

                if stop_val is None:
                    continue

                if not isinstance(stop_val, str) or not stop_val.startswith("#") or len(stop_val) != 7:
                    continue

                try:
                    ratio = contrast_ratio(text_val, stop_val)
                    gradient_checks_count += 1
                    if worst_ratio is None or ratio < worst_ratio:
                        worst_ratio = ratio
                except Exception:
                    pass

            gradient_results[theme_name][family] = worst_ratio

    # Print gradient coverage table
    print("GRADIENT STOP CONTRAST — WORST RATIO PER FAMILY")
    print("="*80)
    print(f"Family               ", end="")
    for theme_name in _THEME_MODULES.keys():
        print(f" | {theme_name:.<15}", end="")
    print()
    print("-" * 80)

    for family in families:
        print(f"{family:.<20}", end="")
        for theme_name in _THEME_MODULES.keys():
            ratio = gradient_results[theme_name].get(family)
            if ratio is None:
                print(f" | {'N/A':>15}", end="")
            else:
                status = "PASS" if ratio >= 4.5 else "FAIL"
                print(f" | {ratio:>6.2f} {status:>7}", end="")
        print()
    print("="*80)
    print(f"\nTotal gradient checks: {gradient_checks_count}")
    print("="*80 + "\n")

    # This test always passes; it's just a recording mechanism
    assert True
