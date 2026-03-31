"""engines/pdf_extractor.py — Extract text from (optionally encrypted) PDFs.

This module is intentionally generic so it can be reused by:
- Bank statement PDF import
- AIS/TIS PDF import (if you choose to add a PDF workflow)

It does not attempt to interpret document-specific semantics; it just extracts text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PDFExtractResult:
    text: str
    pages_extracted: int


class PDFExtractionError(Exception):
    pass


def extract_pdf_text(file_path: str, password: Optional[str] = None, max_pages: Optional[int] = None) -> PDFExtractResult:
    """Extract text from a PDF.

    Args:
        file_path: Path to PDF.
        password: PDF password (user/owner password). If None/"", tries without password.
        max_pages: Optional maximum pages to extract.

    Returns:
        PDFExtractResult(text=..., pages_extracted=n)

    Raises:
        PDFExtractionError: if the file can't be opened/decrypted or no text can be extracted.
    """

    password = (password or "").strip() or None

    # 1) Try pdfplumber first (already used in this repo; good text extraction).
    try:
        import pdfplumber

        pages = []
        with pdfplumber.open(file_path, password=password) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                if max_pages is not None and idx > max_pages:
                    break
                txt = page.extract_text() or ""
                if txt.strip():
                    pages.append(txt)

        joined = "\n\n".join(pages).strip()
        if joined:
            return PDFExtractResult(text=joined, pages_extracted=len(pages))

        # If it opened but produced no text, fall through to pypdf (sometimes differs).
    except TypeError as e:
        # Older pdfplumber versions may not support the password argument.
        raise PDFExtractionError(
            "Your installed pdfplumber does not support opening encrypted PDFs. "
            "Please upgrade pdfplumber, or use the pypdf fallback. "
            f"Root error: {e}"
        )
    except Exception:
        # Fall back to pypdf (often handles more encryption variants).
        pass

    # 2) Fallback: pypdf.
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        if getattr(reader, "is_encrypted", False):
            if not password:
                raise PDFExtractionError("PDF is encrypted; password is required.")
            decrypt_result = reader.decrypt(password)
            if decrypt_result == 0:
                raise PDFExtractionError("Invalid PDF password (decryption failed).")

        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            if max_pages is not None and idx > max_pages:
                break
            txt = page.extract_text() or ""
            if txt.strip():
                pages.append(txt)

        joined = "\n\n".join(pages).strip()
        if not joined:
            raise PDFExtractionError("No extractable text found in PDF (it may be scanned or image-only).")

        return PDFExtractResult(text=joined, pages_extracted=len(pages))

    except PDFExtractionError:
        raise
    except ModuleNotFoundError as e:
        raise PDFExtractionError(
            "PDF extraction fallback requires 'pypdf'. Install it via requirements.txt. "
            f"Root error: {e}"
        )
    except Exception as e:
        raise PDFExtractionError(f"Failed to extract text from PDF. Root error: {e}")
