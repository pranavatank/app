#!/usr/bin/env python3
"""Verify all refactoring requirements from T047."""

import subprocess
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def count_message_boxes():
    """Count remaining QMessageBox calls."""
    counts = {}
    for msg_type in ["information", "warning", "critical", "question"]:
        result = subprocess.run(
            f'grep -rc "QMessageBox.{msg_type}" ui/ --include="*.py"',
            shell=True,
            capture_output=True,
            text=True,
            cwd="D:\\Pranav\\app"
        )
        total = sum(int(line.split(":")[-1]) for line in result.stdout.strip().split("\n") if line and ":" in line)
        counts[msg_type] = total
    return counts

def check_toast_stylesheet():
    """Verify toast.py has no setStyleSheet calls."""
    result = subprocess.run(
        'grep "setStyleSheet" ui/widgets/toast.py',
        shell=True,
        capture_output=True,
        text=True,
        cwd="D:\\Pranav\\app"
    )
    return len(result.stdout.strip()) == 0

def test_toast_variants():
    """Test that all Toast variants work."""
    from PyQt6.QtWidgets import QApplication
    from ui.theme import Theme, ThemeManager
    from ui.widgets.toast import Toast

    app = QApplication([])
    ThemeManager.load_and_apply()
    app.setStyleSheet(Theme.get_stylesheet())

    variants = ["success", "info", "warning", "danger"]
    for variant in variants:
        toast = Toast(f"Test {variant} message", variant=variant, duration_ms=0)
        assert toast.variant == variant, f"Toast variant {variant} not set correctly"
        toast.show()
        app.processEvents()
        toast.hide()
    return True

def print_results():
    """Print verification results."""
    print("\n" + "="*70)
    print("VERIFICATION REPORT - T047: Replace Acknowledgement Modals with Inline Feedback")
    print("="*70)

    # 1. Count QMessageBox calls
    print("\n1. QMessageBox Call Counts:")
    print("-" * 70)
    counts = count_message_boxes()
    targets = {
        "information": (0, 51),
        "warning": (10, 85),
        "critical": (19, 19),
        "question": (19, 19),
    }
    all_targets_met = True
    for msg_type, (target, original) in targets.items():
        count = counts[msg_type]
        status = "PASS" if count <= target else "FAIL"
        if count > target:
            all_targets_met = False
        print(f"  QMessageBox.{msg_type:12} : {count:3} (target: {target}, original: {original}) [{status}]")

    # 2. Check setStyleSheet
    print("\n2. Toast Widget Styling:")
    print("-" * 70)
    has_no_stylesheet = check_toast_stylesheet()
    print(f"  No setStyleSheet in toast.py: {has_no_stylesheet} [{'PASS' if has_no_stylesheet else 'FAIL'}]")

    # 3. Test toast variants
    print("\n3. Toast Variants:")
    print("-" * 70)
    try:
        variants_ok = test_toast_variants()
        print(f"  All 4 variants work: {variants_ok} [PASS]")
    except Exception as e:
        print(f"  All 4 variants work: False [FAIL - {e}]")
        variants_ok = False

    # 4. Summary
    print("\n4. Summary:")
    print("-" * 70)
    print(f"  Information modals converted: {51 - counts['information']} of 51 -> {counts['information']} remaining (target: 0)")
    print(f"  Validation warnings converted: {85 - counts['warning']} of 85 -> {counts['warning']} remaining (target: <10)")
    print(f"  Critical modals kept: {counts['critical']} (target: 19) [PASS]")
    print(f"  Question modals kept: {counts['question']} (target: 19) [PASS]")

    print("\n" + "="*70)
    if all_targets_met and has_no_stylesheet and variants_ok:
        print("OVERALL RESULT: PASS")
    else:
        print("OVERALL RESULT: FAIL")
    print("="*70 + "\n")

    return all_targets_met and has_no_stylesheet and variants_ok

if __name__ == "__main__":
    try:
        success = print_results()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nVerification failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
