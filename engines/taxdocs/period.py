"""Source-period extraction for tax documents."""

import re


_YEAR_RANGE = r"(\d{4})\s*[-/\u2012-\u2015]\s*(\d{4}|\d{2})(?!\d)"
_FY_RE = re.compile(r"\b(?:financial\s+year|f\s*\.\s*y\s*\.?|fy)\s*[:\-]?\s*" + _YEAR_RANGE, re.I)
_AY_RE = re.compile(r"\b(?:assessment\s+year|a\s*\.\s*y\s*\.?|ay)\s*[:\-]?\s*" + _YEAR_RANGE, re.I)


def _normalize_year_range(match):
    first, second = match
    first_year = int(first)
    second_year = int(second) if len(second) == 4 else (first_year // 100) * 100 + int(second)
    if second_year != first_year + 1:
        return None
    return f"{first_year}-{str(second_year)[-2:]}"


def _years_from_matches(matches):
    years = {year for year in (_normalize_year_range(match) for match in matches) if year}
    if len(years) > 1:
        raise ValueError(f"conflicting tax document years: {sorted(years)}")
    return next(iter(years), None)


def extract_tax_period(text: str) -> dict:
    """Return labeled financial/assessment years found in extracted PDF text."""
    text = text or ""
    financial_year = _years_from_matches(_FY_RE.findall(text))
    assessment_year = _years_from_matches(_AY_RE.findall(text))
    if financial_year and assessment_year:
        ay_start = int(assessment_year.split("-")[0])
        expected_fy = f"{ay_start - 1}-{str(ay_start)[-2:]}"
        if financial_year != expected_fy:
            raise ValueError(
                f"financial year {financial_year} conflicts with assessment year {assessment_year}"
            )
    if not financial_year and assessment_year:
        ay_start = int(assessment_year.split("-")[0])
        financial_year = f"{ay_start - 1}-{str(ay_start)[-2:]}"
    return {"financial_year": financial_year, "assessment_year": assessment_year}
