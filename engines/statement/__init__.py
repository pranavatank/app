"""
engines/statement/ — Coordinate-based PDF statement parsing

Entry point for parsing bank statements using word coordinates and column geometry.
"""

from engines.statement.extract import extract_words_from_pdf
from engines.statement.rows import cluster_into_rows
from engines.statement.columns import find_header, build_columns
from engines.statement.assemble import assemble_transactions, deposit_account_matches
from engines.statement.validate import (
    normalise_order,
    confidence,
    balance_walk,
    LowConfidenceParse,
)


def parse_statement_pdf(
    file_path: str,
    password: str | None = None,
    debug: dict | None = None,
    min_confidence: float = 0.9,
) -> list[dict]:
    """
    Parse bank statement PDF using coordinate-based word extraction.

    Returns transactions in the same shape as the existing parser:
    [{
        "transaction_date": "YYYY-MM-DD",
        "description": str,
        "amount": float,
        "transaction_type": "Income" or "Expense",
        "category": str,
        "mode": str,
        "reference_no": str or None,
        "balance_after": float or None,
    }, ...]

    Args:
        file_path: Path to PDF statement
        password: Optional password for encrypted PDFs
        debug: Optional dict to collect debug info
        min_confidence: Minimum confidence score required (0.0-1.0). Default 0.9.
                       Raises LowConfidenceParse if below threshold.

    Returns:
        List of transaction dicts (always in chronological ascending order)

    Raises:
        LowConfidenceParse: If balance reconciliation confidence is below min_confidence
    """
    try:
        # Extract words from all pages
        all_pages_words = extract_words_from_pdf(file_path, password)
        if not all_pages_words:
            return []

        # Find header from any page (some statements have cover pages)
        header_words = None
        header_page_index = 0
        for page_idx, page_words in enumerate(all_pages_words):
            page_rows = cluster_into_rows(page_words)
            header_words = find_header(page_rows)
            if header_words:
                header_page_index = page_idx
                break

        if not header_words:
            return []

        columns = build_columns(header_words)
        if not columns:
            return []

        # Parse all pages - assemble_transactions will filter out non-transaction rows
        all_transactions = []
        for page_words in all_pages_words:
            rows = cluster_into_rows(page_words)
            txns = assemble_transactions(rows, columns)
            all_transactions.extend(txns)

        # Normalise row order BEFORE any balance reasoning
        all_transactions = normalise_order(all_transactions)

        # Check confidence and raise if below threshold
        conf = confidence(all_transactions)
        failing_rows = balance_walk(all_transactions)

        if debug:
            debug["confidence"] = conf
            debug["failing_row_count"] = len(failing_rows)

        if conf < min_confidence:
            raise LowConfidenceParse(conf, failing_rows)

        return all_transactions

    except LowConfidenceParse:
        raise
    except Exception as e:
        if debug:
            debug["error"] = str(e)
        raise


__all__ = ["parse_statement_pdf", "deposit_account_matches"]
