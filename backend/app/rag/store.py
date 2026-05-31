"""ChromaDB persistent-client wrapper.

This is the only module in the project that talks to chromadb. Other
modules see only the `ChunkStore` API: add / query / count / reset.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings as ChromaSettings

from app.rag.models import Chunk, ChunkMetadata


class ChunkStore:
    def __init__(self, persist_dir: Path, collection: str) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection
        self._client: ClientAPI = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )

    def count(self) -> int:
        return int(self._collection.count())

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) length mismatch"
            )
        if not chunks:
            return
        self._collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=vectors,
            metadatas=[
                {
                    "source": c.metadata.source,
                    "page": c.metadata.page,
                    "topic": c.metadata.topic,
                    "chunk_type": c.metadata.chunk_type,
                    "difficulty": (
                        c.metadata.difficulty if c.metadata.difficulty is not None else -1
                    ),
                }
                for c in chunks
            ],
        )

    def query(self, query_vector: list[float], k: int = 5) -> list[Chunk]:
        if self.count() == 0:
            return []
        res = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(k, self.count()),
            include=["documents", "metadatas", "distances"],
        )
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        out: list[Chunk] = []
        for cid, text, meta, dist in zip(ids, docs, metas, dists, strict=False):
            diff = meta.get("difficulty", -1)
            metadata = ChunkMetadata(
                source=str(meta.get("source", "")),
                page=int(meta.get("page", 0)),
                topic=str(meta.get("topic", "untagged")),
                chunk_type=str(meta.get("chunk_type", "concept")),  # type: ignore[arg-type]
                difficulty=int(diff) if diff is not None and int(diff) >= 1 else None,
            )
            out.append(
                Chunk(
                    id=cid,
                    text=text,
                    metadata=metadata,
                    score=1.0 - float(dist),  # cosine distance → similarity
                )
            )
        return out

    def reset(self) -> None:
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )
