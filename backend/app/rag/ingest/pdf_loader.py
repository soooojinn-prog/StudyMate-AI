"""PDF text extraction using pdfplumber."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from app.rag.models import ExtractedPage


def load_pdf(path: Path) -> list[ExtractedPage]:
    """Extract one ExtractedPage per page of the given PDF.

    Raises:
        FileNotFoundError: if `path` does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages: list[ExtractedPage] = []
    source = path.name
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(ExtractedPage(source=source, page=i, text=text))
    return pages
