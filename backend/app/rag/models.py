"""Pydantic models shared across the RAG pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChunkType = Literal["concept", "problem", "explanation"]


class ChunkMetadata(BaseModel):
    """Provenance and classification of a chunk."""

    source: str
    page: int
    topic: str
    chunk_type: ChunkType = "concept"
    difficulty: int | None = Field(default=None, ge=1, le=3)


class Chunk(BaseModel):
    """A retrievable unit: text + metadata + (optionally) its embedding."""

    id: str
    text: str
    metadata: ChunkMetadata
    embedding: list[float] | None = None
    score: float | None = None  # populated by retriever when returned


class ExtractedPage(BaseModel):
    """One page extracted from a PDF, before any cleaning or chunking."""

    source: str
    page: int
    text: str
