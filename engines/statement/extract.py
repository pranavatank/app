"""
engines/statement/extract.py — PDF word extraction
"""

import pdfplumber
from engines.statement_passwords import ensure_pdf_password


def extract_words_from_pdf(file_path: str, password: str | None = None) -> list[list[dict]]:
    """
    Open PDF and extract words per page.
    Each page returns a list of word dicts with keys: text, x0, x1, top, bottom.

    Args:
        file_path: Path to PDF file
        password: Optional password for encrypted PDFs

    Returns:
        List of page word lists, e.g., [[word1, word2, ...], [word3, ...], ...]
    """
    ensure_pdf_password(file_path, password)

    all_pages_words = []

    if password:
        pdf_ctx = pdfplumber.open(file_path, password=password)
    else:
        pdf_ctx = pdfplumber.open(file_path)

    with pdf_ctx as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            all_pages_words.append(words or [])

    return all_pages_words
