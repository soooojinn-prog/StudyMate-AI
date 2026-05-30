"""Tests for app.rag.ingest.pdf_loader."""

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from app.rag.ingest.pdf_loader import load_pdf


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    """Build a 2-page PDF in memory with reportlab."""
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))

    path = tmp_path / "tiny.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("HYSMyeongJo-Medium", 14)
    c.drawString(72, 720, "첫째 페이지 본문입니다.")
    c.drawString(72, 700, "정규화는 데이터 중복을 줄인다.")
    c.showPage()
    c.setFont("HYSMyeongJo-Medium", 14)
    c.drawString(72, 720, "둘째 페이지 본문입니다.")
    c.drawString(72, 700, "1NF는 원자값만 허용한다.")
    c.showPage()
    c.save()
    return path


def test_load_pdf_returns_one_page_per_pdf_page(tiny_pdf: Path) -> None:
    expected_page_count = 2
    first_page_number = 1
    second_page_number = 2
    pages = load_pdf(tiny_pdf)
    assert len(pages) == expected_page_count
    assert pages[0].page == first_page_number
    assert pages[1].page == second_page_number


def test_load_pdf_preserves_source_filename(tiny_pdf: Path) -> None:
    pages = load_pdf(tiny_pdf)
    assert all(p.source == "tiny.pdf" for p in pages)


def test_load_pdf_extracts_korean_text(tiny_pdf: Path) -> None:
    pages = load_pdf(tiny_pdf)
    assert "정규화" in pages[0].text
    assert "1NF" in pages[1].text


def test_load_pdf_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_pdf(tmp_path / "nope.pdf")
