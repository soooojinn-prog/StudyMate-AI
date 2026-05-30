"""Tests for app.rag.ingest.chunker."""

from app.rag.ingest.chunker import chunk_text
from app.rag.models import ExtractedPage


def test_short_page_yields_single_chunk():
    page = ExtractedPage(source="x.pdf", page=1, text="짧은 단락 하나입니다.")
    chunks = chunk_text([page], target_tokens=400, overlap_tokens=50)
    assert len(chunks) == 1
    assert chunks[0].text.strip() == "짧은 단락 하나입니다."
    assert chunks[0].metadata.source == "x.pdf"
    assert chunks[0].metadata.page == 1


def test_long_page_splits_into_multiple_chunks():
    # ~ 1600 chars => >> 400 tokens
    long_text = ("정규화는 데이터 중복을 줄이기 위한 작업이다. " * 80).strip()
    page = ExtractedPage(source="x.pdf", page=1, text=long_text)
    chunks = chunk_text([page], target_tokens=120, overlap_tokens=20)
    assert len(chunks) > 1
    # every chunk has the page provenance
    assert all(c.metadata.source == "x.pdf" and c.metadata.page == 1 for c in chunks)


def test_overlap_creates_shared_text_between_consecutive_chunks():
    text = ("문장 A. " + "문장 B. " * 50).strip()
    page = ExtractedPage(source="x.pdf", page=1, text=text)
    chunks = chunk_text([page], target_tokens=60, overlap_tokens=20)
    min_expected_chunks = 2
    assert len(chunks) >= min_expected_chunks
    # second chunk should start with content that also appears at the
    # tail of the first
    tail = chunks[0].text[-40:]
    head = chunks[1].text[:80]
    shared_words = set(tail.split()) & set(head.split())
    assert shared_words, "expected overlap to share at least one word"


def test_pages_yield_chunk_ids_that_are_unique():
    pages = [
        ExtractedPage(source="x.pdf", page=1, text="첫 페이지 문장."),
        ExtractedPage(source="x.pdf", page=2, text="둘째 페이지 문장."),
    ]
    chunks = chunk_text(pages, target_tokens=400, overlap_tokens=50)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"


def test_chunk_default_metadata_topic_is_placeholder_until_tagged():
    page = ExtractedPage(source="x.pdf", page=1, text="짧은 문장.")
    chunks = chunk_text([page], target_tokens=400, overlap_tokens=50)
    # tagger fills this in later — chunker leaves it as a marker
    assert chunks[0].metadata.topic == "untagged"
