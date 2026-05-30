"""Embedder protocol with BGE-M3 default and a deterministic Fake.

BGE-M3 is loaded lazily on first call to keep import cost low for the
unit-test process. The Fake is hash-based and seeds numpy for repeatable
fixed-dim float vectors — usable everywhere a real embedder would go
without downloading the 2.3GB BGE-M3 weights.
"""
from __future__ import annotations

import hashlib
from typing import Protocol


class Embedder(Protocol):
    """Anything that can turn text into fixed-dimensional vectors."""

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class FakeEmbedder:
    """Deterministic hash-based embedder for tests."""

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # repeat the digest until we have at least `dim` bytes
        needed = self.dim
        buf = bytearray()
        while len(buf) < needed:
            buf.extend(digest)
        return [(b / 255.0) - 0.5 for b in buf[:needed]]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class BGEM3Embedder:
    """Real embedder using sentence-transformers BAAI/bge-m3 (1024-dim)."""

    def __init__(self, model_name: str = "BAAI/bge-m3", dim: int = 1024) -> None:
        self.model_name = model_name
        self.dim = dim
        self._model = None  # lazy

    def _load(self) -> None:
        if self._model is not None:
            return
        # Lazy import: SentenceTransformer pulls in torch + transformers (~2GB
        # of weights + heavy C extensions). Importing at module top would slow
        # every unit-test process even when only FakeEmbedder is used.
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        assert self._model is not None
        vectors = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]
