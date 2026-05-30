"""Header/footer/page-number removal from extracted PDF pages.

Heuristics:
1. Any line that appears verbatim on >= ceil(n_pages * 0.6) pages is
   treated as a recurring header/footer and removed.
2. Lines that are *only* a number (with optional surrounding punctuation
   like dashes) are removed regardless - these are page-number footers.
3. Single-page input is returned unchanged (no signal for recurrence).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

from app.rag.models import ExtractedPage

_PAGE_NUMBER_LINE = re.compile(r"^\s*[\-—–\.\(\[]*\s*\d{1,4}\s*[\-—–\.\)\]]*\s*$")

_MIN_PAGES_FOR_RECURRENCE = 2


def _split_lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.splitlines()]


def _is_page_number(line: str) -> bool:
    return bool(line.strip()) and bool(_PAGE_NUMBER_LINE.match(line))


def clean_pages(pages: Iterable[ExtractedPage]) -> list[ExtractedPage]:
    pages_list = list(pages)
    if len(pages_list) < _MIN_PAGES_FOR_RECURRENCE:
        return pages_list

    # Count line frequency across pages (only for non-empty, non-page-number lines)
    counter: Counter[str] = Counter()
    for p in pages_list:
        for ln in _split_lines(p.text):
            stripped = ln.strip()
            if not stripped or _is_page_number(stripped):
                continue
            counter[stripped] += 1

    threshold = max(2, math.ceil(len(pages_list) * 0.6))
    recurring = {ln for ln, count in counter.items() if count >= threshold}

    cleaned: list[ExtractedPage] = []
    for p in pages_list:
        kept: list[str] = []
        for ln in _split_lines(p.text):
            stripped = ln.strip()
            if not stripped:
                kept.append(ln)
                continue
            if stripped in recurring:
                continue
            if _is_page_number(stripped):
                continue
            kept.append(ln)
        new_text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept).strip())
        cleaned.append(ExtractedPage(source=p.source, page=p.page, text=new_text))

    return cleaned
