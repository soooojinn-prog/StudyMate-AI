"""Token-aware paragraph chunker.

Approximates token count as `len(text) / 2.2` for Korean+English text
(empirically close to the BGE-M3 tokenizer's behavior). This avoids
loading a tokenizer at chunking time — the same approximation is used
everywhere the pipeline needs a rough token estimate.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from app.rag.models import Chunk, ChunkMetadata, ExtractedPage

_CHAR_PER_TOKEN = 2.2


def _approx_tokens(text: str) -> int:
    return int(len(text) / _CHAR_PER_TOKEN)


def _split_into_paragraphs(text: str) -> list[str]:
    # split on two-or-more newlines; collapse single newlines into spaces
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [re.sub(r"\s+", " ", p).strip() for p in paragraphs if p.strip()]


def _accumulate(paragraphs: list[str], target_tokens: int, overlap_tokens: int) -> list[str]:
    """Greedy accumulator: pack paragraphs into chunks under the token budget.

    When a single paragraph exceeds the budget, it is split on sentence
    boundaries. The tail of each chunk (sized to overlap_tokens) is
    prepended to the next chunk to preserve context across the seam.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            chunks.append(" ".join(current))
            current = []
            current_tokens = 0

    for para in paragraphs:
        para_tokens = _approx_tokens(para)
        if para_tokens > target_tokens:
            # split this oversized paragraph on sentence boundaries
            flush()
            sentences = re.split(r"(?<=[.?!。·])\s+", para)
            buf: list[str] = []
            buf_tokens = 0
            for s in sentences:
                s_tokens = _approx_tokens(s)
                if buf_tokens + s_tokens > target_tokens and buf:
                    chunks.append(" ".join(buf))
                    buf = []
                    buf_tokens = 0
                buf.append(s)
                buf_tokens += s_tokens
            if buf:
                chunks.append(" ".join(buf))
            continue

        if current_tokens + para_tokens > target_tokens and current:
            flush()
        current.append(para)
        current_tokens += para_tokens

    flush()

    if overlap_tokens > 0 and len(chunks) > 1:
        overlap_chars = int(overlap_tokens * _CHAR_PER_TOKEN)
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap_chars:]
            # walk back to a word boundary so we don't slice mid-word
            space = tail.find(" ")
            if space != -1:
                tail = tail[space + 1 :]
            chunks[i] = tail + " " + chunks[i]

    return chunks


def _chunk_id(source: str, page: int, seq: int, text: str) -> str:
    h = hashlib.sha1(f"{source}:{page}:{seq}:{text[:64]}".encode()).hexdigest()[:16]
    return f"{source}_p{page:04d}_c{seq:03d}_{h}"


def chunk_text(
    pages: Iterable[ExtractedPage],
    *,
    target_tokens: int = 400,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Chunk a list of extracted pages into retrievable units."""
    out: list[Chunk] = []
    for page in pages:
        paras = _split_into_paragraphs(page.text)
        if not paras:
            continue
        pieces = _accumulate(paras, target_tokens, overlap_tokens)
        for seq, piece in enumerate(pieces):
            out.append(
                Chunk(
                    id=_chunk_id(page.source, page.page, seq, piece),
                    text=piece,
                    metadata=ChunkMetadata(source=page.source, page=page.page, topic="untagged"),
                )
            )
    return out
