"""Tests for app.rag.retriever — uses fake embedder + tmp store."""
from pathlib import Path

from app.rag import IngestPipeline as TopPipeline
from app.rag import Retriever as TopRetriever
from app.rag.embedder import FakeEmbedder
from app.rag.models import Chunk
from app.rag.retriever import Retriever
from app.rag.store import ChunkStore


def test_retrieve_returns_top_k(
    store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder
):
    expected_results = 2
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    store.add(sample_chunks, fake_embedder.embed([c.text for c in sample_chunks]))
    retriever = Retriever(store=store, embedder=fake_embedder)
    results = retriever.retrieve("정규화는 데이터 중복을 줄이기 위한 작업이다.", k=expected_results)
    assert len(results) == expected_results
    assert results[0].score is not None


def test_retrieve_with_k_larger_than_store_returns_all(
    store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder
):
    expected_total = 3
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    store.add(sample_chunks, fake_embedder.embed([c.text for c in sample_chunks]))
    retriever = Retriever(store=store, embedder=fake_embedder)
    results = retriever.retrieve("query", k=99)
    assert len(results) == expected_total


def test_retrieve_on_empty_store_returns_empty(
    store_dir: Path, fake_embedder: FakeEmbedder
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    retriever = Retriever(store=store, embedder=fake_embedder)
    assert retriever.retrieve("아무거나", k=5) == []


def test_module_reexports_public_surface():
    # the top-level package should re-export the retriever helpers
    assert TopRetriever is Retriever
    assert TopPipeline.__name__ == "IngestPipeline"
