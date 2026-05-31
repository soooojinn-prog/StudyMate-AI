"""Tests for app.rag.store.ChunkStore."""
from pathlib import Path

from app.rag.embedder import FakeEmbedder
from app.rag.models import Chunk
from app.rag.store import ChunkStore


def test_empty_store_count_is_zero(store_dir: Path):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    assert store.count() == 0


def test_add_then_count(store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    vectors = fake_embedder.embed([c.text for c in sample_chunks])
    store.add(sample_chunks, vectors)
    expected_count = 3
    assert store.count() == expected_count


def test_query_returns_most_similar_first(
    store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    vectors = fake_embedder.embed([c.text for c in sample_chunks])
    store.add(sample_chunks, vectors)
    query_vec = fake_embedder.embed_query("정규화는 데이터 중복을 줄이기 위한 작업이다.")
    expected_results = 2
    results = store.query(query_vec, k=2)
    assert len(results) == expected_results
    # the exact-text match must come first
    assert results[0].id == "a1"
    assert results[0].score is not None


def test_query_on_empty_store_returns_empty(store_dir: Path, fake_embedder: FakeEmbedder):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    results = store.query(fake_embedder.embed_query("아무거나"), k=5)
    assert results == []


def test_reset_clears_all(store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    vectors = fake_embedder.embed([c.text for c in sample_chunks])
    store.add(sample_chunks, vectors)
    expected_count = 3
    assert store.count() == expected_count
    store.reset()
    assert store.count() == 0


def test_persists_across_instances(
    store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder
):
    store1 = ChunkStore(persist_dir=store_dir, collection="test_v1")
    vectors = fake_embedder.embed([c.text for c in sample_chunks])
    store1.add(sample_chunks, vectors)
    del store1
    store2 = ChunkStore(persist_dir=store_dir, collection="test_v1")
    expected_count = 3
    assert store2.count() == expected_count
