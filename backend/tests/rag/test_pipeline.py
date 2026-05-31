"""Tests for IngestPipeline — uses fakes for embedder & anthropic client."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.rag.embedder import FakeEmbedder
from app.rag.ingest.pipeline import IngestPipeline
from app.rag.models import ExtractedPage
from app.rag.store import ChunkStore


@pytest.fixture
def fake_anthropic_client() -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"topic": "정규화"}')]
    client.messages.create.return_value = response
    return client


def test_run_with_in_memory_pages_persists_chunks(
    store_dir: Path,
    fake_embedder: FakeEmbedder,
    fake_anthropic_client: MagicMock,
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    pipeline = IngestPipeline(
        store=store,
        embedder=fake_embedder,
        topics=["정규화"],
        anthropic_client=fake_anthropic_client,
        anthropic_model="claude-haiku-4-5",
    )
    pages = [
        ExtractedPage(source="t.pdf", page=1, text="1NF는 원자값을 가져야 한다."),
        ExtractedPage(source="t.pdf", page=2, text="2NF는 부분 함수 종속을 제거한다."),
    ]
    pipeline.run_pages(pages)
    expected_chunk_count = 2
    assert store.count() == expected_chunk_count


def test_run_pages_tags_topics_via_client(
    store_dir: Path,
    fake_embedder: FakeEmbedder,
    fake_anthropic_client: MagicMock,
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    pipeline = IngestPipeline(
        store=store,
        embedder=fake_embedder,
        topics=["정규화"],
        anthropic_client=fake_anthropic_client,
        anthropic_model="claude-haiku-4-5",
    )
    pages = [ExtractedPage(source="t.pdf", page=1, text="짧은 문장.")]
    pipeline.run_pages(pages)
    assert fake_anthropic_client.messages.create.called


def test_run_pages_with_no_text_skips_silently(
    store_dir: Path,
    fake_embedder: FakeEmbedder,
    fake_anthropic_client: MagicMock,
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    pipeline = IngestPipeline(
        store=store,
        embedder=fake_embedder,
        topics=["정규화"],
        anthropic_client=fake_anthropic_client,
        anthropic_model="claude-haiku-4-5",
    )
    pipeline.run_pages([ExtractedPage(source="t.pdf", page=1, text="")])
    assert store.count() == 0
    fake_anthropic_client.messages.create.assert_not_called()
