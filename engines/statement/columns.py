"""
engines/statement/columns.py — Header detection and column geometry
"""

from engines.statement.schema import match_field


def find_header(rows: list[list[dict]]) -> list[dict] | None:
    """
    Find the header row by scoring how many canonical fields its text matches.
    A row scoring >= 4 with <= 14 words wins. Returns the row with highest score.
    Also tries concatenating current row with the next (for IDFC's split header).

    Args:
        rows: List of clustered rows

    Returns:
        List of header word dicts, or None if not found
    """
    best_row = None
    best_score = 0

    for i, row in enumerate(rows):
        # Try single row
        score = _score_header_row(row)
        if score >= 4 and len(row) <= 14 and score > best_score:
            best_row = row
            best_score = score

        # Try concatenating with next row (for split headers like IDFC)
        if i + 1 < len(rows):
            combined = row + rows[i + 1]
            score = _score_header_row(combined)
            if score >= 4 and len(combined) <= 14 and score > best_score:
                best_row = combined
                best_score = score

    return best_row


def _score_header_row(row: list[dict]) -> int:
    """Count how many words in row match canonical field names."""
    score = 0
    for word in row:
        if match_field(word["text"]):
            score += 1
    return score


def build_columns(header_words: list[dict]) -> dict:
    """
    Map header words to fields and derive column x-ranges.

    Returns dict: {field_key: {"x_min": float, "x_max": float, "center": float}}
    Each field is recorded only once (first occurrence).

    Args:
        header_words: List of word dicts from header row

    Returns:
        Dictionary mapping field names to x-range info
    """
    # Build field -> centre mapping, keeping first occurrence
    field_centres = {}
    for word in header_words:
        field = match_field(word["text"])
        if field and field not in field_centres:
            centre = (word["x0"] + word["x1"]) / 2
            field_centres[field] = centre

    if not field_centres:
        return {}

    # Sort fields by centre position
    sorted_fields = sorted(field_centres.items(), key=lambda x: x[1])

    # Derive x-ranges as midpoints between adjacent centres
    columns = {}
    for i, (field, centre) in enumerate(sorted_fields):
        if i == 0:
            # First column: unbounded left
            x_min = -float("inf")
        else:
            # Midpoint between previous and current centre
            prev_centre = sorted_fields[i - 1][1]
            x_min = (prev_centre + centre) / 2

        if i == len(sorted_fields) - 1:
            # Last column: unbounded right
            x_max = float("inf")
        else:
            # Midpoint between current and next centre
            next_centre = sorted_fields[i + 1][1]
            x_max = (centre + next_centre) / 2

        columns[field] = {
            "x_min": x_min,
            "x_max": x_max,
            "center": centre,
        }

    return columns


def assign(word: dict, columns: dict) -> str | None:
    """
    Assign a word to a column by its OWN CENTRE (not x0).
    Returns the field name, or None if word doesn't fit any column.

    Args:
        word: Word dict with 'x0', 'x1'
        columns: Dict from build_columns

    Returns:
        Field name (e.g., "date", "desc", "debit") or None
    """
    word_centre = (word["x0"] + word["x1"]) / 2

    for field, bounds in columns.items():
        if bounds["x_min"] <= word_centre <= bounds["x_max"]:
            return field

    return None
