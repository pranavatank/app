"""
engines/statement/rows.py — Cluster words into visual rows by coordinate
"""


def cluster_into_rows(words: list[dict], tolerance: int = 3) -> list[list[dict]]:
    """
    Cluster words into visual rows by rounding their top coordinate.

    Args:
        words: List of word dicts with 'top', 'x0', 'x1', 'text', 'bottom'
        tolerance: Pixel tolerance for grouping (default 3)

    Returns:
        List of rows, each row is a list of words sorted by x0 (left to right)
    """
    if not words:
        return []

    # Group by rounded top coordinate
    row_dict = {}
    for word in words:
        row_key = round(word["top"] / tolerance)
        if row_key not in row_dict:
            row_dict[row_key] = []
        row_dict[row_key].append(word)

    # Sort each row by x0 (left to right) and return as list of rows
    rows = [sorted(row_words, key=lambda w: w["x0"]) for row_words in row_dict.values()]

    # Sort rows by their row_key (top to bottom)
    sorted_row_keys = sorted(row_dict.keys())
    return [row_dict[key] for key in sorted_row_keys]
