"""
CV PDF -> plain text extraction.

Kept isolated from routes so the parsing strategy (pypdf today, maybe
pdfplumber or an OCR fallback tomorrow) can change without touching
API code.
"""
from __future__ import annotations

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)


class CVParsingError(Exception):
    """Raised when a CV PDF cannot be parsed into usable text."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract raw text from an in-memory PDF.

    Args:
        file_bytes: Raw bytes of the uploaded PDF file.

    Returns:
        Concatenated text from all pages, whitespace-normalized.

    Raises:
        CVParsingError: if the file isn't a valid PDF or yields no text
            (e.g. a scanned image PDF with no embedded text layer).
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError as exc:
        raise CVParsingError("The uploaded file is not a valid, readable PDF.") from exc

    if reader.is_encrypted:
        # Try an empty-password decrypt (common for "protected" but not
        # truly locked exports); if that fails, surface a clear error.
        try:
            reader.decrypt("")
        except Exception as exc:  # pypdf raises varied exception types here
            raise CVParsingError(
                "This PDF is password-protected. Please upload an unprotected copy."
            ) from exc

    pages_text = []
    for page_num, page in enumerate(reader.pages):
        try:
            pages_text.append(page.extract_text() or "")
        except Exception as exc:  # a single malformed page shouldn't kill the whole parse
            logger.warning("Failed to extract text from page %d: %s", page_num, exc)

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        raise CVParsingError(
            "No extractable text found in this PDF. It may be a scanned "
            "image without an OCR text layer — try exporting your CV as "
            "a text-based PDF instead."
        )

    return full_text


def validate_pdf_size(file_bytes: bytes, max_size_mb: int) -> None:
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise CVParsingError(f"File is {size_mb:.1f}MB; the limit is {max_size_mb}MB.")
