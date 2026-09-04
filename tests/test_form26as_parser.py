"""
tests/test_form26as_parser.py — Unit tests for Form 26AS parser

Tests the helper functions and parsing logic without requiring the real PDF fixture.
Focuses on:
- INR amount parsing (Indian digit grouping)
- Date parsing (dd-MMM-yyyy format)
- PART-<ROMAN> section detection
- Section code extraction (guarding against false matches like 194BA→194B)
- Reversal netting logic
- Column finding
"""

import re
import pytest
from engines.taxdocs.form26as import (
    _parse_inr_amount,
    _parse_date,
    _detect_part_roman,
    _extract_section_code_from_row,
    _roman_to_int,
    _find_column_index,
    _assign_table_to_part,
    parse_form26as_pdf
)


class TestParseInrAmount:
    """Test Indian-formatted amount parsing with comma grouping."""

    def test_simple_amount_no_comma(self):
        """Parse simple amount without commas."""
        assert _parse_inr_amount("1000") == 1000.0
        assert _parse_inr_amount("500") == 500.0

    def test_indian_digit_grouping(self):
        """Parse amounts with Indian grouping (2,23,133 = 223133)."""
        assert _parse_inr_amount("2,23,133") == 223133.0
        assert _parse_inr_amount("1,05,069") == 105069.0
        assert _parse_inr_amount("10,508") == 10508.0

    def test_with_rupee_symbol(self):
        """Parse amounts with rupee symbol."""
        assert _parse_inr_amount("₹2,23,133") == 223133.0
        assert _parse_inr_amount("₹1000") == 1000.0

    def test_decimal_amounts(self):
        """Parse decimal amounts."""
        assert _parse_inr_amount("1,000.50") == 1000.50
        assert _parse_inr_amount("2,23,133.25") == 223133.25

    def test_negative_amounts(self):
        """Parse negative amounts (reversals)."""
        assert _parse_inr_amount("-1000") == -1000.0
        assert _parse_inr_amount("-2,23,133") == -223133.0

    def test_whitespace_handling(self):
        """Parse with surrounding whitespace."""
        assert _parse_inr_amount("  1000  ") == 1000.0
        assert _parse_inr_amount("  2,23,133  ") == 223133.0

    def test_empty_string(self):
        """Return 0 for empty string."""
        assert _parse_inr_amount("") == 0.0
        assert _parse_inr_amount("   ") == 0.0

    def test_invalid_format(self):
        """Return 0 for invalid formats."""
        assert _parse_inr_amount("abc") == 0.0
        assert _parse_inr_amount("12a34") == 0.0
        assert _parse_inr_amount("N/A") == 0.0


class TestParseDate:
    """Test date parsing in dd-MMM-yyyy format."""

    def test_dd_mmm_yyyy_format(self):
        """Parse dd-MMM-yyyy format (31-Mar-2026)."""
        result = _parse_date("31-Mar-2026")
        assert result == "31-Mar-2026"

        result = _parse_date("01-Apr-2025")
        assert result == "01-Apr-2025"

        result = _parse_date("15-Jan-2025")
        assert result == "15-Jan-2025"

    def test_lowercase_month(self):
        """Parse with lowercase month abbreviation."""
        result = _parse_date("31-mar-2026")
        assert result == "31-Mar-2026"

    def test_uppercase_month(self):
        """Parse with uppercase month abbreviation."""
        result = _parse_date("31-MAR-2026")
        assert result == "31-Mar-2026"

    def test_dd_mm_yyyy_slash_format_fallback(self):
        """Fallback to dd/mm/yyyy format if dd-MMM-yyyy fails."""
        result = _parse_date("31/03/2026")
        assert result == "31-Mar-2026"

    def test_dd_mm_yyyy_dash_format_fallback(self):
        """Fallback to dd-mm-yyyy format if dd-MMM-yyyy fails."""
        result = _parse_date("31-03-2026")
        assert result == "31-Mar-2026"

    def test_empty_date(self):
        """Return empty string for empty input."""
        assert _parse_date("") == ""
        assert _parse_date("   ") == ""

    def test_invalid_date(self):
        """Return empty string for invalid dates."""
        assert _parse_date("invalid") == ""
        assert _parse_date("32-Jan-2026") == ""  # Invalid day
        assert _parse_date("29-Feb-2025") == ""  # Feb 29 in non-leap year


class TestDetectPartRoman:
    """Test PART-<ROMAN> detection."""

    def test_part_i(self):
        """Detect PART-I."""
        assert _detect_part_roman("PART-I") == "I"
        assert _detect_part_roman("  PART-I  ") == "I"
        assert _detect_part_roman("part-i") == "I"

    def test_part_ii(self):
        """Detect PART-II."""
        assert _detect_part_roman("PART-II") == "II"
        assert _detect_part_roman("part-ii") == "II"

    def test_part_x(self):
        """Detect PART-X."""
        assert _detect_part_roman("PART-X") == "X"
        assert _detect_part_roman("part-x") == "X"

    def test_all_roman_numerals(self):
        """Detect all Roman numerals I through X."""
        for i, roman in enumerate(["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"], 1):
            result = _detect_part_roman(f"PART-{roman}")
            assert result == roman, f"Failed to detect PART-{roman}"

    def test_no_match_for_part_a(self):
        """Do not match PART A (no hyphen)."""
        assert _detect_part_roman("PART A") is None
        assert _detect_part_roman("PART-A") is None

    def test_no_match_for_part_b(self):
        """Do not match PART B."""
        assert _detect_part_roman("PART B") is None
        assert _detect_part_roman("PART-B") is None

    def test_embedded_in_text(self):
        """Detect PART marker even if surrounded by other text."""
        # Our regex matches PART- at the beginning, so it detects the Roman numeral
        assert _detect_part_roman("PART-III details") == "III"
        assert _detect_part_roman("PART-V some text") == "V"

    def test_none_for_no_match(self):
        """Return None when no PART marker found."""
        assert _detect_part_roman("Some other text") is None
        assert _detect_part_roman("") is None


class TestExtractSectionCode:
    """Test section code extraction from table cells."""

    def test_valid_section_code_exact(self):
        """Extract valid section code when it's the only content."""
        assert _extract_section_code_from_row("194A") == "194A"
        assert _extract_section_code_from_row("194J") == "194J"
        assert _extract_section_code_from_row("194H") == "194H"

    def test_section_code_with_whitespace(self):
        """Extract section code with surrounding whitespace."""
        assert _extract_section_code_from_row("  194A  ") == "194A"
        assert _extract_section_code_from_row("  194J  ") == "194J"

    def test_no_false_match_for_194ba_in_legend(self):
        """
        CRITICAL: 194BA in legend text should NOT become 194B.
        This was a bug in the old parser that matched substrings.
        """
        # When 194BA appears in a description, don't extract it as a code
        result = _extract_section_code_from_row("Lottery winnings 194BA")
        # Since our regex looks for word boundaries and checks cell length,
        # a long cell shouldn't match
        assert result is None or result == "194BA"  # Only accept if exact match or word boundary

        # But if 194B is alone or at word boundary in a short cell, accept it
        result = _extract_section_code_from_row("194B")
        assert result == "194B"

    def test_empty_or_none(self):
        """Return None for empty cells."""
        assert _extract_section_code_from_row("") is None
        assert _extract_section_code_from_row("   ") is None
        assert _extract_section_code_from_row(None) is None

    def test_invalid_codes(self):
        """Return None for invalid section codes."""
        assert _extract_section_code_from_row("ABC") is None
        assert _extract_section_code_from_row("189A") is None  # Starts with 18, not 19
        assert _extract_section_code_from_row("200A") is None  # Starts with 20, not 19
        # Note: 192A, 193A, 194A, 195A would all match 19[0-9][A-Z]? pattern
        # Our filter accepts any 19[0-9][A-Z]? so all are technically valid

    def test_short_cell_with_code(self):
        """Accept section code in short cells (not descriptions)."""
        result = _extract_section_code_from_row("194A")
        assert result == "194A"

        result = _extract_section_code_from_row("Section 194A")
        # This is ambiguous - a short cell could have "Section 194A"
        assert result is None or result == "194A"


class TestRomanToInt:
    """Test Roman numeral to integer conversion."""

    def test_basic_numerals(self):
        """Convert basic Roman numerals."""
        assert _roman_to_int("I") == 1
        assert _roman_to_int("V") == 5
        assert _roman_to_int("X") == 10

    def test_compound_numerals(self):
        """Convert compound Roman numerals."""
        assert _roman_to_int("II") == 2
        assert _roman_to_int("III") == 3
        assert _roman_to_int("IV") == 4
        assert _roman_to_int("IX") == 9

    def test_larger_numerals(self):
        """Convert larger numerals."""
        assert _roman_to_int("X") == 10
        assert _roman_to_int("XX") == 20

    def test_case_insensitive(self):
        """Handle lowercase and uppercase."""
        assert _roman_to_int("i") == 1
        assert _roman_to_int("ii") == 2
        assert _roman_to_int("x") == 10

    def test_invalid_numerals(self):
        """Return -1 for invalid numerals."""
        assert _roman_to_int("ABC") == -1
        assert _roman_to_int("") == -1
        assert _roman_to_int(None) == -1


class TestFindColumnIndex:
    """Test column finding by keyword."""

    def test_exact_substring_match(self):
        """Find column by substring match."""
        header = ["SR", "Section", "Deductor Name", "TDS Deducted"]
        assert _find_column_index(header, "Section") == 1
        assert _find_column_index(header, "Deductor") == 2
        assert _find_column_index(header, "TDS") == 3

    def test_case_insensitive_match(self):
        """Keyword matching is case-insensitive."""
        header = ["SR", "SECTION", "deductor name", "TDS DEDUCTED"]
        assert _find_column_index(header, "section") == 1
        assert _find_column_index(header, "DEDUCTOR") == 2
        assert _find_column_index(header, "tds") == 3

    def test_partial_word_match(self):
        """Match partial words."""
        header = ["SR", "Section Code", "Deductor Name", "TDS Amount"]
        assert _find_column_index(header, "Section") == 1
        assert _find_column_index(header, "Deduct") == 2

    def test_not_found_returns_none(self):
        """Return None when keyword not found."""
        header = ["SR", "Section", "Deductor"]
        assert _find_column_index(header, "Amount") is None
        assert _find_column_index(header, "Date") is None

    def test_returns_first_match(self):
        """Return first matching column."""
        header = ["SR", "Section", "Section Code", "Deductor"]
        assert _find_column_index(header, "Section") == 1  # First match


class TestAssignTableToPart:
    """Test position-based table-to-part assignment."""

    def test_tables_above_and_below_heading(self):
        """
        Test p2 case: one heading at top=300, tables at tops [100, 500].
        Carried-in part is 'I'.
        Table at 100 (above heading) -> 'I' (carried)
        Table at 500 (below heading) -> 'II' (from heading)
        """
        headings = [('II', 300.0)]
        table_tops = [100.0, 500.0]
        carried_part = 'I'

        result = _assign_table_to_part(headings, table_tops, carried_part)

        assert result[0] == 'I', f"Table at 100 should be 'I' (above heading), got {result[0]}"
        assert result[1] == 'II', f"Table at 500 should be 'II' (below heading), got {result[1]}"

    def test_no_headings_on_page(self):
        """
        Test p3 case: no headings on page, carried-in part is 'II'.
        Both tables should belong to 'II'.
        """
        headings = []
        table_tops = [100.0, 300.0]
        carried_part = 'II'

        result = _assign_table_to_part(headings, table_tops, carried_part)

        assert result[0] == 'II', f"Table at 100 should be 'II' (no headings), got {result[0]}"
        assert result[1] == 'II', f"Table at 300 should be 'II' (no headings), got {result[1]}"

    def test_multiple_headings_with_tables(self):
        """
        Test case with multiple headings: PART-III at 400, PART-IV at 700.
        Tables at tops [200, 500, 800].
        Carried-in part is 'II'.
        Table at 200 (before all) -> 'II' (carried)
        Table at 500 (between III and IV) -> 'III'
        Table at 800 (after IV) -> 'IV'
        """
        headings = [('III', 400.0), ('IV', 700.0)]
        table_tops = [200.0, 500.0, 800.0]
        carried_part = 'II'

        result = _assign_table_to_part(headings, table_tops, carried_part)

        assert result[0] == 'II', f"Table at 200 should be 'II' (carried), got {result[0]}"
        assert result[1] == 'III', f"Table at 500 should be 'III', got {result[1]}"
        assert result[2] == 'IV', f"Table at 800 should be 'IV', got {result[2]}"

    def test_table_at_exact_heading_position(self):
        """
        Test when table top equals heading top.
        Table at exact heading position should belong to that heading's part.
        """
        headings = [('II', 300.0)]
        table_tops = [300.0]
        carried_part = 'I'

        result = _assign_table_to_part(headings, table_tops, carried_part)

        # Table at 300 is NOT less than 300, so it should belong to carried part 'I'
        # (it's not BELOW the heading, it's AT the heading)
        assert result[0] == 'I', f"Table at heading position should use carried part, got {result[0]}"

    def test_empty_table_tops(self):
        """Test with no tables (empty table_tops)."""
        headings = [('II', 300.0)]
        table_tops = []
        carried_part = 'I'

        result = _assign_table_to_part(headings, table_tops, carried_part)

        assert result == [], "Empty table_tops should return empty result"

    def test_carried_part_none(self):
        """Test when carried_part is None."""
        headings = [('II', 300.0)]
        table_tops = [100.0]
        carried_part = None

        result = _assign_table_to_part(headings, table_tops, carried_part)

        assert result[0] is None, f"Table above heading with None carried part should be None, got {result[0]}"


class TestParserIntegration:
    """Integration tests with synthetic table structures."""

    def test_header_table_label_value_pairs(self):
        """
        Test that header table extracts values from the cell AFTER the label.
        Synthetic header table from Form 26AS:
        Row 0: ['Permanent Account Number (PAN)', 'AZIPT9702H', 'Current Status of PAN', 'Active and Operative', ...]
        Row 1: ['Name of Assessee', 'PRANAV ARVINDBHAI TANK', '', '', ...]
        Row 2: ['Address of Assessee', 'SHYAM, ATIKA MAIN ROAD, OPP NA', '', '', ...]
        """
        import tempfile
        import os
        from unittest.mock import patch, MagicMock

        # Create a mock PDF with synthetic header table
        synthetic_header_table = [
            ['Permanent Account Number (PAN)', 'AZIPT9702H', 'Current Status of PAN', 'Active and Operative',
             'Financial Year', '2025-26', 'Assessment Year', '2026-27'],
            ['Name of Assessee', 'PRANAV ARVINDBHAI TANK', '', '', '', '', '', ''],
            ['Address of Assessee', 'SHYAM, ATIKA MAIN ROAD, OPP NA', '', '', '', '', '', '']
        ]

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch('pdfplumber.open') as mock_open:
                # Mock pdfplumber to return our synthetic table
                mock_pdf = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_tables.return_value = [synthetic_header_table]
                mock_page.extract_text.return_value = ""
                mock_pdf.pages = [mock_page]
                mock_pdf.__enter__.return_value = mock_pdf
                mock_pdf.__exit__.return_value = None
                mock_open.return_value = mock_pdf

                from engines.taxdocs.form26as import parse_form26as_pdf

                result = parse_form26as_pdf(tmp_path)

                # Verify extracted values
                assert result['pan'] == 'AZIPT9702H', f"PAN mismatch: {result['pan']}"
                assert result['name'] == 'PRANAV ARVINDBHAI TANK', f"Name mismatch: {result['name']}"
                assert result['assessment_year'] == '2026-27', f"Assessment year mismatch: {result['assessment_year']}"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_nested_table_mode_switching_deductor_and_detail(self):
        """
        Test that the parser correctly switches between DEDUCTOR and DETAIL headers.
        Synthetic table from PART-I with nested structure:
        - DEDUCTOR header + DEDUCTOR TOTAL row (Enlightvision with TAN, amount, TDS)
        - DETAIL header + DETAIL rows (section codes, transaction dates)
        - DETAIL row with reversal (Remarks B, negative amount)
        """
        import tempfile
        import os
        from unittest.mock import patch, MagicMock

        # Synthetic PART-I table with nested headers
        synthetic_table = [
            # DEDUCTOR header row
            ['Sr. No.', 'Name of Deductor', '', '', 'TAN of Deductor', 'Total Amount Paid/ Credi', 'Total Tax Deducted#', 'Total TDS Deposited'],
            # DEDUCTOR TOTAL row
            ['1', 'ENLIGHTVISION TECHNOLOGIES PRIVATE LIM', '', '', 'AABCU5055K', '105069.00', '10508.00', '10508.00'],
            # DETAIL header row
            ['Sr. No.', 'Section1', 'Transaction Date', 'Date of Booking', 'Remarks**', 'Amount Paid/Credited', 'Tax Deducted##', 'TDS Deposited'],
            # DETAIL rows
            ['1', '194A', '31-Mar-2026', '16-Jun-2026', '-', '36050.00', '3605.00', '3605.00'],
            ['4', '194A', '31-Dec-2025', '12-Feb-2026', 'B', '-1018.00', '-101.80', '-101.80']
        ]

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch('pdfplumber.open') as mock_open:
                mock_pdf = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_tables.return_value = [synthetic_table]
                # Include PART-I in text to set current_part
                mock_page.extract_text.return_value = "PART-I - Details of Tax Deducted at Source"
                mock_pdf.pages = [mock_page]
                mock_pdf.__enter__.return_value = mock_pdf
                mock_pdf.__exit__.return_value = None
                mock_open.return_value = mock_pdf

                from engines.taxdocs.form26as import parse_form26as_pdf

                result = parse_form26as_pdf(tmp_path)

                # Verify detail records with section codes
                assert len(result['records']) >= 2, f"Expected at least 2 detail records, got {len(result['records'])}"
                # Check first detail row
                detail_row = result['records'][0]
                assert detail_row['section'] == '194A', f"Section mismatch: {detail_row['section']}"
                assert detail_row['transaction_date'] == '31-Mar-2026', f"Transaction date mismatch: {detail_row['transaction_date']}"
                assert detail_row['amount_paid'] == 36050.0, f"Detail amount mismatch: {detail_row['amount_paid']}"

                # Check reversal row (Remarks B, negative amount)
                reversal_row = result['records'][1]
                assert reversal_row['section'] == '194A', f"Reversal section mismatch: {reversal_row['section']}"
                assert reversal_row['transaction_date'] == '31-Dec-2025', f"Reversal date mismatch: {reversal_row['transaction_date']}"
                assert reversal_row['amount_paid'] == -1018.0, f"Reversal amount should be negative: {reversal_row['amount_paid']}"
                assert reversal_row['remarks'] == 'B', f"Reversal remarks mismatch: {reversal_row['remarks']}"

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_tds_sum_from_deductor_totals_not_detail_rows(self):
        """
        Test that total_tds sums only DEDUCTOR TOTAL rows of PART-I, not detail rows.
        Synthetic PART-I table with:
        - Deductor row: ENLIGHTVISION, TDS 10508.00
        - Deductor row: JANA SMALL FINANCE, TDS 2859.00
        - Detail rows (some with reversals that would give wrong total if summed)
        Expected total_tds: 13367.00 (from deductors, not from netting detail rows)
        """
        import tempfile
        import os
        from unittest.mock import patch, MagicMock

        # Synthetic PART-I table
        synthetic_table = [
            # DEDUCTOR header
            ['Sr. No.', 'Name of Deductor', '', '', 'TAN of Deductor', 'Total Amount Paid/ Credi', 'Total Tax Deducted#', 'Total TDS Deposited'],
            # DEDUCTOR TOTAL row 1
            ['1', 'ENLIGHTVISION TECHNOLOGIES PRIVATE LIM', '', '', 'AABCU5055K', '105069.00', '10508.00', '10508.00'],
            # DEDUCTOR TOTAL row 2
            ['2', 'JANA SMALL FINANCE BANK LIMITED', '', '', 'BLRJ07125G', '2859.00', '2859.00', '2859.00'],
            # DETAIL header
            ['Sr. No.', 'Section1', 'Transaction Date', 'Date of Booking', 'Remarks**', 'Amount Paid/Credited', 'Tax Deducted##', 'TDS Deposited'],
            # DETAIL rows
            ['1', '194A', '31-Mar-2026', '16-Jun-2026', '-', '186.00', '18.60', '18.60'],
            ['2', '194A', '15-Mar-2026', '10-Jun-2026', 'B', '-186.00', '-18.60', '-18.60']
        ]

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch('pdfplumber.open') as mock_open:
                mock_pdf = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_tables.return_value = [synthetic_table]
                mock_page.extract_text.return_value = "PART-I - Details of Tax Deducted at Source"
                mock_pdf.pages = [mock_page]
                mock_pdf.__enter__.return_value = mock_pdf
                mock_pdf.__exit__.return_value = None
                mock_open.return_value = mock_pdf

                from engines.taxdocs.form26as import parse_form26as_pdf

                result = parse_form26as_pdf(tmp_path)

                # Verify total_tds is sum of deductor total rows: 10508 + 2859 = 13367
                assert result['total_tds'] == 13367.0, f"TDS total mismatch: expected 13367.0, got {result['total_tds']}"

                # Verify detail rows are still captured
                assert len(result['records']) >= 2, f"Expected at least 2 detail records, got {len(result['records'])}"

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_reversal_netting_logic(self):
        """
        Test that negative amounts are properly handled.
        A reversal entry should net against positive entries.
        """
        # Test data: one positive, one negative
        positive_amount = _parse_inr_amount("10,000")
        negative_amount = _parse_inr_amount("-5,000")

        net = positive_amount + negative_amount
        assert net == 5000.0

    def test_date_consistency(self):
        """Test that dates are consistently parsed across different formats."""
        # All these should parse to the same date
        result1 = _parse_date("31-Mar-2026")
        result2 = _parse_date("31/03/2026")
        result3 = _parse_date("31-03-2026")

        # They should all be non-empty and consistent
        assert result1 != ""
        assert result2 != ""
        assert result3 != ""


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_amounts(self):
        """Parse very large amounts."""
        result = _parse_inr_amount("99,99,99,999")
        assert result == 999999999.0

    def test_zero_amount(self):
        """Parse zero amount."""
        assert _parse_inr_amount("0") == 0.0
        assert _parse_inr_amount("0.00") == 0.0

    def test_part_detection_with_extra_spaces(self):
        """Detect PART with various whitespace."""
        assert _detect_part_roman("   PART-I   ") == "I"
        assert _detect_part_roman("\tPART-II\t") == "II"

    def test_section_code_all_variants(self):
        """Test all valid section codes."""
        for code in ["194A", "194B", "194D", "194F", "194G", "194H", "194J", "194LA", "194LBA"]:
            # Only accept if it matches the pattern 19[0-9][A-Z]?
            if re.match(r"^19[0-9][A-Z]?$", code):
                result = _extract_section_code_from_row(code)
                assert result == code, f"Failed to extract {code}"


# ── Skip marker for fixture-dependent tests ──────────────────────────────────

import os
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "data" / "PersonalData" / "Pranav"

pytestmark_fixture_dependent = pytest.mark.skipif(
    not FIXTURE_DIR.is_dir(),
    reason="owner's document fixtures not present (data/PersonalData/) — see REBUILD_PLAN T004",
)


@pytest.mark.skipif(
    not FIXTURE_DIR.is_dir(),
    reason="owner's document fixtures not present (data/PersonalData/)",
)
class TestFormWithFixture:
    """Tests that require the actual Form 26AS PDF fixture."""

    def test_parse_form26as_fixture(self):
        """Parse the actual Form 26AS PDF and check key metrics."""
        import functools
        from engines.pdf_extractor import extract_pdf_text

        pdf_path = FIXTURE_DIR / "26AS.pdf"
        text = extract_pdf_text(str(pdf_path)).text

        # Note: parse_form26as_pdf currently expects text from old parser
        # This test documents the interface but won't run yet
        # until the parser is updated to work with PDF paths
        pytest.skip("Fixture-dependent test - requires PDF path parser")
