"""End-to-end ingest pipeline orchestrator.

Stages:
1. clean — strip recurring headers/footers and bare page-number lines
2. chunk — paragraph-aware token chunking with overlap
3. tag   — classify each chunk's topic via Anthropic Haiku
4. embed — embed each chunk's text into a vector
5. store — write chunks + vectors into ChromaDB
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.rag.embedder import Embedder
from app.rag.ingest.chunker import chunk_text
from app.rag.ingest.cleaner import clean_pages
from app.rag.ingest.pdf_loader import load_pdf
from app.rag.ingest.topic_tagger import tag_chunks
from app.rag.models import ExtractedPage
from app.rag.store import ChunkStore


class IngestPipeline:
    def __init__(
        self,
        *,
        store: ChunkStore,
        embedder: Embedder,
        topics: list[str],
        anthropic_client: Any,
        anthropic_model: str = "claude-haiku-4-5",
        target_tokens: int = 400,
        overlap_tokens: int = 50,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.topics = topics
        self.anthropic_client = anthropic_client
        self.anthropic_model = anthropic_model
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def run_pages(self, pages: Iterable[ExtractedPage]) -> int:
        """Ingest a list of already-extracted pages. Returns chunk count added."""
        cleaned = clean_pages(pages)
        chunks = chunk_text(
            cleaned, target_tokens=self.target_tokens, overlap_tokens=self.overlap_tokens
        )
        if not chunks:
            return 0
        tagged = tag_chunks(
            chunks,
            topics=self.topics,
            client=self.anthropic_client,
            model=self.anthropic_model,
        )
        vectors = self.embedder.embed([c.text for c in tagged])
        self.store.add(tagged, vectors)
        return len(tagged)

    def run_pdf(self, pdf_path: Path) -> int:
        pages = load_pdf(pdf_path)
        return self.run_pages(pages)

    def run_dir(self, pdf_dir: Path) -> dict[str, int]:
        """Ingest every *.pdf in a directory. Returns per-file chunk counts."""
        pdf_dir = Path(pdf_dir)
        counts: dict[str, int] = {}
        for pdf in sorted(pdf_dir.glob("*.pdf")):
            counts[pdf.name] = self.run_pdf(pdf)
        return counts
