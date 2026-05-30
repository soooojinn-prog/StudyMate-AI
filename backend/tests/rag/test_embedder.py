"""Tests for app.rag.embedder — uses FakeEmbedder only (BGE-M3 is integration)."""
from app.rag.embedder import Embedder, FakeEmbedder


def test_fake_embedder_returns_fixed_dim_vectors():
    expected_count = 2
    expected_dim = 8
    emb = FakeEmbedder(dim=expected_dim)
    out = emb.embed(["문장 하나", "다른 문장"])
    assert len(out) == expected_count
    assert all(len(v) == expected_dim for v in out)


def test_fake_embedder_is_deterministic_for_same_text():
    emb = FakeEmbedder(dim=8)
    a = emb.embed(["같은 문장"])[0]
    b = emb.embed(["같은 문장"])[0]
    assert a == b


def test_fake_embedder_differs_for_different_text():
    emb = FakeEmbedder(dim=8)
    a = emb.embed(["문장 A"])[0]
    b = emb.embed(["문장 B"])[0]
    assert a != b


def test_fake_embedder_implements_protocol():
    expected_dim = 8
    emb: Embedder = FakeEmbedder(dim=expected_dim)
    out = emb.embed_query("질의")
    assert isinstance(out, list)
    assert len(out) == expected_dim
