"""Public retrieval API.

Outside callers should construct a `Retriever` with their preferred
embedder and store, then call `retrieve(query, k)`. For the default
project-wide retriever wired against settings, use `default_retriever()`.
"""
from __future__ import annotations

from app.rag.embedder import BGEM3Embedder, Embedder
from app.rag.models import Chunk
from app.rag.store import ChunkStore


class Retriever:
    def __init__(self, *, store: ChunkStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    def retrieve(self, query: str, k: int = 5) -> list[Chunk]:
        vec = self.embedder.embed_query(query)
        return self.store.query(vec, k=k)


def default_retriever() -> Retriever:
    """Build a Retriever from app settings (BGE-M3 + persistent ChromaDB)."""
    # Lazy import to avoid pulling settings (and its env-file load) at module
    # import time. Callers that build retrievers manually shouldn't have to
    # have env vars configured just to import `app.rag`.
    from app.core.settings import settings  # noqa: PLC0415

    store = ChunkStore(
        persist_dir=settings.chroma_dir, collection=settings.chroma_collection
    )
    embedder = BGEM3Embedder(
        model_name=settings.embedding_model, dim=settings.embedding_dim
    )
    return Retriever(store=store, embedder=embedder)
