"""
tests/test_terminology.py — Validate that retired terminology is not used in UI strings.

This test ensures consistency with TERMINOLOGY.md by checking that user-facing
strings in ui/ use the correct unified terms.

Retired terms (and their replacements):
  - "Credit" / "Debit" → "Income" / "Expense" (exception: bank statement column headers)
  - "Family Member" / "Family Members" → "Person" / "People"
  - "Balance After" → "Balance"
  - Variable/function names, database column names, and code comments are not checked.

Exceptions:
  - "Taxpayer" is allowed in ui/tax_screen.py (legal term of art)
  - Raw bank statement column headers during import display are allowed
"""

import os
import re
from pathlib import Path


def find_ui_files():
    """Recursively find all .py files under ui/."""
    ui_path = Path(__file__).parent.parent / "ui"
    return sorted(ui_path.rglob("*.py"))


def extract_string_literals(file_path):
    """
    Extract string literals from a Python file.

    Returns a list of tuples: (line_number, string_value, quote_type)
    Only extracts user-facing strings (in quotes), not variable names or comments.
    """
    strings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return strings

    for line_num, line in enumerate(lines, start=1):
        # Skip pure comment lines
        stripped = line.strip()
        if stripped.startswith('#'):
            continue

        # Find all quoted strings (both single and double quotes, including f-strings)
        # Pattern matches: "..." or '...' or f"..." or f'...' or r"..." etc.
        pattern = r'''(?:f|r|b|fr|rb)?["'](?:[^"'\\]|\\.)*["']'''
        for match in re.finditer(pattern, line):
            quote_str = match.group(0)
            # Extract the actual string content (removing quotes and prefix)
            if quote_str.startswith(('f"', "f'", 'r"', "r'", 'b"', "b'")):
                content = quote_str[2:-1]
            elif quote_str.startswith(('"', "'")):
                content = quote_str[1:-1]
            else:
                continue

            strings.append((line_num, content, quote_str))

    return strings


def has_exception(file_path, content, line_num):
    """Check if this line is an acceptable exception."""
    file_name = file_path.name

    # Exception 1: "Taxpayer" in tax_screen.py is a legal term and is allowed
    if file_name == "tax_screen.py" and "Taxpayer" in content:
        return True

    # Exception 2: "Debit Card" / "Debit card" (account type/product) - not transaction type
    # Keep "Debit Card" because it refers to a specific banking product type, not transaction direction
    if "debit card" in content.lower():
        return True

    # Exception 3: "Debit Column" / "Credit Column" in column mapping (raw bank statement columns)
    if file_name == "column_mapping_dialog.py" and ("Debit Column" in content or "Credit Column" in content):
        return True

    # Exception 4: Bank statement column headers during import are allowed
    # Look for context like "Debit" or "Credit" appearing in import-related comments or context
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Check surrounding lines for import/statement/column mapping context
        if line_num > 1:
            context_before = ''.join(lines[max(0, line_num - 5):line_num - 1]).lower()
            context_after = ''.join(lines[line_num:min(len(lines), line_num + 5)]).lower()
            context = context_before + context_after

            # If this is clearly about statement import, column mapping, or display of raw headers
            if any(keyword in context for keyword in [
                'import', 'statement', 'column', 'header', 'debit', 'credit',
                'parsed', 'raw', 'source', 'display', 'preview', 'map'
            ]):
                # Only allow if it's specifically about showing raw column data
                if any(phrase in context for phrase in [
                    'column header', 'raw', 'parsed', 'display', 'preview'
                ]):
                    return True
    except Exception:
        pass

    return False


def test_no_retired_credit_debit_in_ui():
    """Ensure "Credit" and "Debit" are not used in user-facing strings (except exceptions)."""
    retired_terms = {
        "Credit": "Income",
        "Debit": "Expense"
    }

    failures = []

    for file_path in find_ui_files():
        strings = extract_string_literals(file_path)
        for line_num, content, _ in strings:
            for retired, replacement in retired_terms.items():
                if retired in content:
                    if not has_exception(file_path, content, line_num):
                        rel_path = file_path.relative_to(Path(__file__).parent.parent)
                        failures.append(
                            f"{rel_path}:{line_num} — Found retired term '{retired}' "
                            f"(use '{replacement}' instead): {repr(content[:60])}"
                        )

    assert not failures, f"Retired terminology found:\n" + "\n".join(failures)


def test_no_retired_family_member_in_ui():
    """Ensure 'Family Member' and 'Family Members' are not used in user-facing strings."""
    retired_terms = {
        "Family Member": "Person",
        "Family Members": "People"
    }

    failures = []

    for file_path in find_ui_files():
        strings = extract_string_literals(file_path)
        for line_num, content, _ in strings:
            for retired, replacement in retired_terms.items():
                if retired in content:
                    rel_path = file_path.relative_to(Path(__file__).parent.parent)
                    failures.append(
                        f"{rel_path}:{line_num} — Found retired term '{retired}' "
                        f"(use '{replacement}' instead): {repr(content[:60])}"
                    )

    assert not failures, f"Retired terminology found:\n" + "\n".join(failures)


def test_no_balance_after_in_ui():
    """Ensure 'Balance After' is not used in user-facing strings (use 'Balance' instead)."""
    failures = []

    for file_path in find_ui_files():
        strings = extract_string_literals(file_path)
        for line_num, content, _ in strings:
            if "Balance After" in content:
                rel_path = file_path.relative_to(Path(__file__).parent.parent)
                failures.append(
                    f"{rel_path}:{line_num} — Found retired term 'Balance After' "
                    f"(use 'Balance' instead): {repr(content[:60])}"
                )

    assert not failures, f"Retired terminology found:\n" + "\n".join(failures)


def test_no_reprocess_data_in_ui():
    """Ensure 'Reprocess Data' button label is not used (use 'Link Transfers' instead)."""
    failures = []

    for file_path in find_ui_files():
        strings = extract_string_literals(file_path)
        for line_num, content, _ in strings:
            # Look for the specific button label (not in comments or other contexts)
            if "Reprocess Data" in content:
                rel_path = file_path.relative_to(Path(__file__).parent.parent)
                failures.append(
                    f"{rel_path}:{line_num} — Found retired term 'Reprocess Data' "
                    f"(use 'Link Transfers' instead): {repr(content[:60])}"
                )

    assert not failures, f"Retired terminology found:\n" + "\n".join(failures)


if __name__ == "__main__":
    test_no_retired_credit_debit_in_ui()
    test_no_retired_family_member_in_ui()
    test_no_balance_after_in_ui()
    test_no_reprocess_data_in_ui()
    print("✓ All terminology tests passed!")
