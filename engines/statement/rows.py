"""
engines/statement/rows.py — Cluster words into visual rows by coordinate
"""


def cluster_into_rows(words: list[dict], tolerance: int = 3) -> list[list[dict]]:
    """
    Cluster words whose top coordinates are within a visual row's tolerance.

    Args:
        words: List of word dicts with 'top', 'x0', 'x1', 'text', 'bottom'
        tolerance: Pixel tolerance for grouping (default 3)

    Returns:
        List of rows, each row is a list of words sorted by x0 (left to right)
    """
    if not words:
        return []

    if tolerance < 0:
        raise ValueError("row tolerance must be nonnegative")

    # A fixed rounding grid can split words just 0.2 pixels apart when they
    # straddle a bucket boundary. Anchor each group at its topmost word instead.
    # Keeping that anchor fixed also prevents a chain of nearby words from
    # merging distinct lines into one row.
    rows = []
    row_top = None
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if row_top is None or word["top"] - row_top > tolerance:
            rows.append([])
            row_top = word["top"]
        rows[-1].append(word)
    return [sorted(row, key=lambda word: word["x0"]) for row in rows]
