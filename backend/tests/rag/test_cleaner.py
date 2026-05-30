"""Tests for app.rag.ingest.cleaner."""

from app.rag.ingest.cleaner import clean_pages
from app.rag.models import ExtractedPage


def _pages(texts: list[str]) -> list[ExtractedPage]:
    return [ExtractedPage(source="x.pdf", page=i + 1, text=t) for i, t in enumerate(texts)]


def test_repeated_header_line_removed():
    pages = _pages(
        [
            "정보처리기사 실기 2024년 1회\n\n본문 내용 페이지 1.",
            "정보처리기사 실기 2024년 1회\n\n본문 내용 페이지 2.",
            "정보처리기사 실기 2024년 1회\n\n본문 내용 페이지 3.",
        ]
    )
    cleaned = clean_pages(pages)
    for c in cleaned:
        assert "정보처리기사 실기 2024년 1회" not in c.text
        assert "본문 내용 페이지" in c.text


def test_repeated_footer_line_removed():
    pages = _pages(
        [
            "본문 1.\n\n— 1 —",
            "본문 2.\n\n— 2 —",
            "본문 3.\n\n— 3 —",
        ]
    )
    cleaned = clean_pages(pages)
    for c in cleaned:
        assert "본문" in c.text
        # the per-page number footer pattern should be gone
        assert c.text.strip().split("\n")[-1].startswith("본문")


def test_unique_line_preserved():
    pages = _pages(
        [
            "공통 헤더\n\n특수한 첫 페이지 메시지",
            "공통 헤더\n\n둘째 페이지 본문",
            "공통 헤더\n\n셋째 페이지 본문",
        ]
    )
    cleaned = clean_pages(pages)
    assert "특수한 첫 페이지 메시지" in cleaned[0].text
    for c in cleaned:
        assert "공통 헤더" not in c.text


def test_single_page_input_is_unchanged():
    pages = _pages(["한 페이지짜리 본문.\n\n페이지 1"])
    cleaned = clean_pages(pages)
    assert cleaned[0].text == pages[0].text


def test_page_number_only_line_removed_even_if_not_repeated():
    pages = _pages(
        [
            "본문 A\n\n1",
            "본문 B\n\n2",
            "본문 C\n\n3",
        ]
    )
    cleaned = clean_pages(pages)
    for c in cleaned:
        # the bare page-number line should be gone
        assert c.text.strip().split("\n")[-1].startswith("본문")
