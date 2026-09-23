"""
tools/real_ui_tests/test_dark_theme_sweep.py — Dark theme rendering test

Measures screen brightness across all 10 nav screens in different themes.
Renders each screen and samples pixel brightness to catch theme bugs that
grep cannot find.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_dark_theme_sweep.py
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

# UTF-8 for rupee sign
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
from PySide6.QtWidgets import QApplication, QWidget, QDialog, QPushButton
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt

from tools.real_ui_test_harness import RealUIHarness
from ui.dashboard_screen import DashboardScreen
from ui.theme.theme_manager import ThemeManager

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

checks = []
SCREEN_NAMES = [
    "Overview", "Accounts", "Transactions", "Income & Expectations",
    "Fixed Deposits", "Statement Import", "Tax Documents", "Tax",
    "Income Prediction", "Settings"
]

PAGE_ATTRS = [
    None,  # Overview doesn't have a separate page attribute
    "accounts_page",
    "transactions_page",
    "income_page",
    "fd_page",
    "import_page",
    "tax_documents_page",
    "tax_page",
    "prediction_page",
    "settings_page",
]


def check(label, ok):
    checks.append((label, ok))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}", flush=True)
    return ok


def dismiss_blocking_dialogs():
    app = QApplication.instance()
    for w in list(app.topLevelWidgets()):
        if isinstance(w, QDialog) and w.isVisible():
            try:
                w.reject()
            except Exception:
                pass


def measure_brightness(widget):
    """Measure the average luminance (0-255) of a widget's rendered pixels.

    Luminance = 0.2126*R + 0.7152*G + 0.0722*B (ITU BT.709)
    Returns: tuple (mean_luminance, ratio_above_216)
    """
    pm = widget.grab()
    img = pm.toImage().convertToFormat(QImage.Format.Format_RGB32)

    if img.isNull() or img.width() == 0 or img.height() == 0:
        return 0.0, 0.0

    # Extract pixel data as numpy array (constBits() returns a memoryview in PySide6)
    ptr = img.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(img.height(), img.bytesPerLine())
    arr = arr[:, : img.width() * 4].reshape(img.height(), img.width(), 4)

    # Pixel format is BGRA, extract BGR
    b = arr[:, :, 0].astype(float)
    g = arr[:, :, 1].astype(float)
    r = arr[:, :, 2].astype(float)

    # Calculate luminance
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

    # Proportion of bright pixels (>= 216 is "bright")
    bright_ratio = (lum >= 216).mean()
    mean_lum = lum.mean()

    return mean_lum, bright_ratio


def check_screen_brightness(dashboard, screen_idx):
    """Navigate to a screen and check for overly-bright elements in a dark theme."""
    screen_name = SCREEN_NAMES[screen_idx]
    settle_time = 3.0 if screen_idx == 8 else 2.0  # Prediction screen loads async

    dashboard._navigate(screen_idx)
    print(f"\n[{screen_name}] navigating...", flush=True)

    from tools.real_ui_test_harness import RealUIHarness
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)

    harness.settle(settle_time)

    # Measure whole screen
    mean_lum, bright_ratio = measure_brightness(dashboard)
    print(f"[{screen_name}] screen bright_ratio: {bright_ratio:.1%}", flush=True)

    # Check all visible child widgets with area >= 1% of dashboard
    screen = dashboard.stack.currentWidget()
    if not screen:
        print(f"[{screen_name}] screen widget is None", flush=True)
        return

    dashboard_area = dashboard.width() * dashboard.height()
    min_area = max(1, int(0.01 * dashboard_area))

    overly_bright = []
    for w in screen.findChildren(QWidget):
        if not w.isVisible():
            continue

        # ThemeCard intentionally paints a fixed preview of its own theme's
        # colours regardless of the active theme - a bright card is correct.
        if type(w).__name__ == "ThemeCard":
            continue

        w_area = w.width() * w.height()
        if w_area < min_area:
            continue

        w_lum, w_ratio = measure_brightness(w)
        if w_ratio > 0.5:
            cls_name = type(w).__name__
            obj_name = w.objectName()
            acc_name = w.accessibleName()
            geom = f"{w.x()},{w.y()} {w.width()}x{w.height()}"
            overly_bright.append({
                "class": cls_name,
                "object": obj_name,
                "accessible": acc_name,
                "geom": geom,
                "ratio": w_ratio,
                "area": w_area,
            })

    # Check QPushButton variant property
    for btn in screen.findChildren(QPushButton):
        if not btn.isVisible():
            continue
        variant = btn.property("variant")
        if variant is None:
            continue
        btn_lum, btn_ratio = measure_brightness(btn)
        if btn_ratio > 0.5:
            overly_bright.append({
                "class": "QPushButton",
                "object": btn.objectName(),
                "accessible": btn.accessibleName(),
                "geom": f"{btn.x()},{btn.y()} {btn.width()}x{btn.height()}",
                "ratio": btn_ratio,
                "variant": variant,
                "area": btn.width() * btn.height(),
            })

    if overly_bright:
        # Sort by area descending, show top 10
        overly_bright.sort(key=lambda x: x["area"], reverse=True)
        print(f"[{screen_name}] {len(overly_bright)} elements with bright_ratio > 0.5:", flush=True)
        for i, item in enumerate(overly_bright[:10]):
            print(f"  {i+1}. {item['class']} '{item['object']}' "
                  f"ratio={item['ratio']:.1%} area={item['area']}", flush=True)

    ok = len(overly_bright) == 0
    check(f"{screen_name}: no overly-bright elements", ok)

    return ok


def check_refresh_theme_methods(dashboard):
    """Check whether each page has a refresh_theme method."""
    print("\n[theme] checking refresh_theme methods...", flush=True)
    for idx, attr_name in enumerate(PAGE_ATTRS):
        screen_name = SCREEN_NAMES[idx]
        if attr_name is None:
            print(f"[{screen_name}] Overview (no page attr)", flush=True)
            continue
        page = getattr(dashboard, attr_name, None)
        has_method = page is not None and hasattr(page, "refresh_theme")
        print(f"[{screen_name}] {attr_name}: has_refresh_theme={has_method}", flush=True)


def main():
    ThemeManager.apply("Midnight Pro", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("00_dashboard_midnight")

    print(f"\n===== PASS A: Midnight Pro (dark) =====", flush=True)
    all_ok_a = True
    for i in range(10):
        ok = check_screen_brightness(dashboard, i)
        if not ok:
            all_ok_a = False
        harness.shot(f"darkA_{i:02d}_{SCREEN_NAMES[i]}")

    harness.close()
    harness.settle(0.5)

    # Pass B: Light theme
    print(f"\n===== PASS B: Aurora (light) =====", flush=True)
    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("01_dashboard_aurora")

    # Build all screens
    for i in range(10):
        dashboard._navigate(i)
        harness.settle(0.5 if i != 8 else 1.0)

    check_refresh_theme_methods(dashboard)

    # Apply Nova (dark)
    print(f"\n===== PASS B continued: Nova (dark) =====", flush=True)
    ThemeManager.apply("Nova", save=False, notify=False)
    harness.settle(2.0)

    all_ok_b = True
    for i in range(10):
        ok = check_screen_brightness(dashboard, i)
        if not ok:
            all_ok_b = False
        harness.shot(f"darkB_{i:02d}_{SCREEN_NAMES[i]}")

    return report(harness)


def report(harness):
    dismiss_blocking_dialogs()
    try:
        if harness:
            harness.close()
    except Exception:
        pass

    print("\n===== SUMMARY =====", flush=True)
    failed = [label for label, ok in checks if not ok]
    if failed:
        print(f"{len(failed)} check(s) FAILED:", flush=True)
        for label in failed:
            print(f"  - {label}", flush=True)
        return 1
    print("All checks PASSED.", flush=True)
    print(f"Screenshots saved to: {SHOT_DIR}", flush=True)
    return 0


def _close_all_windows():
    try:
        app = QApplication.instance()
        if app:
            for w in list(app.topLevelWidgets()):
                try:
                    w.close()
                except Exception:
                    pass
            app.processEvents()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        rc = main()
    except BaseException:
        import traceback
        traceback.print_exc()
        rc = 1
    finally:
        _close_all_windows()
    sys.exit(rc)
