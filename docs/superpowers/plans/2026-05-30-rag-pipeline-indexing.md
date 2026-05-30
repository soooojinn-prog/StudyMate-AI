# RAG Pipeline & Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working RAG pipeline that ingests Korean PDF source material (정보처리기사 기출문제) into a persistent ChromaDB index, tagging chunks by topic via Anthropic Haiku and embedding them with BGE-M3. Exposes a single public function `retrieve(query, k=5) -> list[Chunk]` callable by the future LangGraph agents (Plan 3). Verified by `make seed` indexing a sample PDF and `retriever.retrieve("정규화의 목적")` returning topically relevant chunks.

**Architecture:** Module `app.rag` is the only entry/exit point — anyone outside (`app.agents`, `app.api`) calls `retrieve()`; no one outside touches ChromaDB or sentence-transformers. Inside `app.rag`, ingestion is a one-way pipeline (PDF → loader → cleaner → chunker → tagger → embedder → store), with intermediate jsonl artifacts so any stage can be re-run without re-doing earlier ones. Embeddings are pluggable behind an `Embedder` Protocol (BGE-M3 default, Fake for tests).

**Tech Stack:** Python 3.12 / pdfplumber / sentence-transformers (BGE-M3, multilingual) / ChromaDB (persistent, embedded) / Anthropic SDK (claude-haiku-4-5) / PyYAML / typer (CLI) / pytest + pytest-mock

**This plan is plan 2 of 7 in the StudyMate AI V1 series.** See `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` §5 (Data Model & RAG) and §13 마일스톤.

**Deferred from spec:**
- Reranker (BGE-reranker-v2) — only if Retrieval Recall@5 misses the 75% target during Plan 6's eval phase.
- Voyage AI / OpenAI embeddings — `Embedder` Protocol leaves this swappable; not implemented in V1.
- Per-document permissions, multi-user isolation — V1 is single-user (per spec §1.3).

---

## File Structure

```
studymate-ai/
├─ backend/
│  ├─ pyproject.toml                    # MODIFY: add 6 runtime + 1 dev dep
│  ├─ app/
│  │  ├─ rag/
│  │  │  ├─ __init__.py                 # re-export: retrieve, IngestPipeline
│  │  │  ├─ models.py                   # Chunk, ChunkMetadata, ExtractedPage
│  │  │  ├─ embedder.py                 # Embedder protocol + BGE-M3 + Fake
│  │  │  ├─ store.py                    # ChunkStore (ChromaDB wrapper)
│  │  │  ├─ retriever.py                # public retrieve(query, k)
│  │  │  └─ ingest/
│  │  │     ├─ __init__.py
│  │  │     ├─ pdf_loader.py            # load_pdf(path) -> list[ExtractedPage]
│  │  │     ├─ cleaner.py               # clean_pages(...) -> list[ExtractedPage]
│  │  │     ├─ chunker.py               # chunk_pages(...) -> list[Chunk]
│  │  │     ├─ topic_tagger.py          # tag_chunks(chunks, topics) -> chunks
│  │  │     ├─ topics.py                # load_topics() -> list[str]
│  │  │     └─ pipeline.py              # IngestPipeline.run(pdf_dir)
│  │  └─ core/
│  │     └─ settings.py                 # MODIFY: add anthropic_api_key + paths
│  ├─ scripts/
│  │  ├─ __init__.py
│  │  └─ seed.py                        # typer CLI: `python -m scripts.seed`
│  └─ tests/
│     └─ rag/
│        ├─ __init__.py
│        ├─ conftest.py                 # tmp_store, fake_embedder, sample_chunks
│        ├─ test_models.py
│        ├─ test_chunker.py
│        ├─ test_cleaner.py
│        ├─ test_pdf_loader.py
│        ├─ test_topic_tagger.py
│        ├─ test_store.py
│        ├─ test_retriever.py
│        ├─ test_pipeline.py
│        └─ fixtures/
│           └─ tiny.pdf                 # 2-page Korean PDF for loader tests
├─ data/
│  ├─ topics.yaml                       # 20 core topics
│  └─ raw/                              # gitignored — user drops PDFs here
└─ Makefile                             # MODIFY: add `seed` target
```

### File-by-file responsibility

- **`app/rag/__init__.py`** — Single public surface. Re-exports `retrieve` and `IngestPipeline`. Importing anything deeper from outside `app.rag` is forbidden by import-linter.
- **`app/rag/models.py`** — Pure Pydantic types shared across the pipeline. No I/O.
- **`app/rag/embedder.py`** — `Embedder` Protocol + `BGEM3Embedder` (loads sentence-transformers, lazy init) + `FakeEmbedder` (deterministic hash → vector, for tests).
- **`app/rag/store.py`** — `ChunkStore` wraps ChromaDB persistent client. Owns the collection lifecycle; no other module talks to chromadb directly.
- **`app/rag/retriever.py`** — Builds default store + embedder, exposes `retrieve(query, k=5)`. The only function `app.agents` will call.
- **`app/rag/ingest/pdf_loader.py`** — pdfplumber wrapper, returns one `ExtractedPage` per page. Preserves page numbers.
- **`app/rag/ingest/cleaner.py`** — Strips headers/footers/page-number lines based on repetition across pages.
- **`app/rag/ingest/chunker.py`** — Paragraph-aware splitting, target ~400 tokens, overlap ~50, hard ceiling on character count for safety.
- **`app/rag/ingest/topic_tagger.py`** — Calls Anthropic Haiku once per chunk with the topic list, expects strict JSON, falls back to "기타" on parse failure.
- **`app/rag/ingest/topics.py`** — Loads `data/topics.yaml` into `list[str]`. Validates uniqueness.
- **`app/rag/ingest/pipeline.py`** — `IngestPipeline.run(pdf_dir)` orchestrates: every stage's output is written as jsonl under `data/extracted/`, `data/chunks/` so any stage can be resumed independently.
- **`scripts/seed.py`** — typer CLI: `seed all` (full pipeline), `seed embed-only` (re-embed without re-tagging), `seed status` (collection counts).
- **`tests/rag/conftest.py`** — Shared fixtures: temporary `ChunkStore` rooted at `tmp_path`, deterministic `FakeEmbedder`, a few hand-built `Chunk`s.

---

## Task 1: Backend dependencies + RAG module skeleton

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/rag/models.py`
- Create: `backend/app/rag/ingest/__init__.py`
- Create: `backend/tests/rag/__init__.py`
- Create: `backend/tests/rag/test_models.py`
- Modify: `backend/app/core/settings.py` (add anthropic key, paths)

- [ ] **Step 1: Modify `backend/pyproject.toml` runtime dependencies**

Replace the `[project] dependencies` block with:

```toml
dependencies = [
  "fastapi>=0.115",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "uvicorn[standard]>=0.32",
  "structlog>=24.4",
  "pdfplumber>=0.11",
  "sentence-transformers>=3.2",
  "chromadb>=0.5.20",
  "anthropic>=0.39",
  "pyyaml>=6.0",
  "typer>=0.13",
]
```

And add to `[dependency-groups] dev`:
```toml
  "pytest-mock>=3.14",
```

(Keep all existing dev deps unchanged.)

- [ ] **Step 2: Run `uv sync` to pull the new dependencies**

```bash
cd backend && uv sync
```

Expected: `Resolved N packages` (now larger than Task 4's 17). Will take noticeably longer because `sentence-transformers` pulls torch + tokenizers + transformers (~1-2GB of wheels, no model download yet — model loads lazily on first use).

- [ ] **Step 3: Modify `backend/app/core/settings.py`** to add RAG-related settings

Replace the file with:

```python
"""Application settings loaded from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level settings. Only environment access lives here."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "StudyMate AI"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # ── RAG ────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    chroma_dir: Path = Field(default=Path("./chroma"))
    chroma_collection: str = Field(default="jeongcheo_v1")
    topics_file: Path = Field(default=Path("./data/topics.yaml"))
    raw_pdf_dir: Path = Field(default=Path("./data/raw"))
    extracted_dir: Path = Field(default=Path("./data/extracted"))
    chunks_dir: Path = Field(default=Path("./data/chunks"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 4: Create `backend/app/rag/__init__.py`**

```python
"""RAG (Retrieval-Augmented Generation) module.

This is the single public surface for retrieval. Outside callers should
import only what is re-exported here. The internal subpackages
(`ingest`, `store`, `embedder`) are implementation details.
"""
```

- [ ] **Step 5: Create `backend/app/rag/ingest/__init__.py`** (empty namespace package)

```python
```

- [ ] **Step 6: Create `backend/app/rag/models.py`**

```python
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
```

- [ ] **Step 7: Create `backend/tests/rag/__init__.py`** (empty)

```python
```

- [ ] **Step 8: Write `backend/tests/rag/test_models.py`**

```python
"""Tests for app.rag.models."""
import pytest
from pydantic import ValidationError

from app.rag.models import Chunk, ChunkMetadata, ExtractedPage


def test_chunk_metadata_defaults_to_concept_type():
    meta = ChunkMetadata(source="2024.pdf", page=1, topic="정규화")
    assert meta.chunk_type == "concept"
    assert meta.difficulty is None


def test_chunk_metadata_rejects_out_of_range_difficulty():
    with pytest.raises(ValidationError):
        ChunkMetadata(source="x.pdf", page=1, topic="x", difficulty=4)


def test_chunk_round_trips_through_dict():
    chunk = Chunk(
        id="abc",
        text="hello",
        metadata=ChunkMetadata(source="x.pdf", page=1, topic="정규화"),
    )
    payload = chunk.model_dump()
    restored = Chunk.model_validate(payload)
    assert restored == chunk


def test_extracted_page_minimal():
    page = ExtractedPage(source="2024.pdf", page=12, text="some text")
    assert page.page == 12
```

- [ ] **Step 9: Run the tests**

```bash
cd backend && uv run pytest tests/rag/test_models.py -v
```

Expected: 4 passed.

- [ ] **Step 10: Run full suite to make sure nothing regressed**

```bash
cd backend && uv run pytest -v
```

Expected: all tests pass (8 previously + 4 new = 12).

- [ ] **Step 11: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/rag/ backend/app/core/settings.py backend/tests/rag/
git commit -m "feat(rag): add module skeleton, models, and dependencies"
```

---

## Task 2: Chunker (deterministic, TDD)

**Files:**
- Create: `backend/app/rag/ingest/chunker.py`
- Create: `backend/tests/rag/test_chunker.py`

- [ ] **Step 1: Write the failing test in `backend/tests/rag/test_chunker.py`**

```python
"""Tests for app.rag.ingest.chunker."""
from app.rag.ingest.chunker import chunk_text
from app.rag.models import ExtractedPage


def test_short_page_yields_single_chunk():
    page = ExtractedPage(source="x.pdf", page=1, text="짧은 단락 하나입니다.")
    chunks = chunk_text([page], target_tokens=400, overlap_tokens=50)
    assert len(chunks) == 1
    assert chunks[0].text.strip() == "짧은 단락 하나입니다."
    assert chunks[0].metadata.source == "x.pdf"
    assert chunks[0].metadata.page == 1


def test_long_page_splits_into_multiple_chunks():
    # ~ 1600 chars => >> 400 tokens
    long_text = ("정규화는 데이터 중복을 줄이기 위한 작업이다. " * 80).strip()
    page = ExtractedPage(source="x.pdf", page=1, text=long_text)
    chunks = chunk_text([page], target_tokens=120, overlap_tokens=20)
    assert len(chunks) > 1
    # every chunk has the page provenance
    assert all(c.metadata.source == "x.pdf" and c.metadata.page == 1 for c in chunks)


def test_overlap_creates_shared_text_between_consecutive_chunks():
    text = ("문장 A. " + "문장 B. " * 50).strip()
    page = ExtractedPage(source="x.pdf", page=1, text=text)
    chunks = chunk_text([page], target_tokens=60, overlap_tokens=20)
    assert len(chunks) >= 2
    # second chunk should start with content that also appears at the
    # tail of the first
    tail = chunks[0].text[-40:]
    head = chunks[1].text[:80]
    shared_words = set(tail.split()) & set(head.split())
    assert shared_words, "expected overlap to share at least one word"


def test_pages_yield_chunk_ids_that_are_unique():
    pages = [
        ExtractedPage(source="x.pdf", page=1, text="첫 페이지 문장."),
        ExtractedPage(source="x.pdf", page=2, text="둘째 페이지 문장."),
    ]
    chunks = chunk_text(pages, target_tokens=400, overlap_tokens=50)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"


def test_chunk_default_metadata_topic_is_placeholder_until_tagged():
    page = ExtractedPage(source="x.pdf", page=1, text="짧은 문장.")
    chunks = chunk_text([page], target_tokens=400, overlap_tokens=50)
    # tagger fills this in later — chunker leaves it as a marker
    assert chunks[0].metadata.topic == "untagged"
```

- [ ] **Step 2: Run the failing test**

```bash
cd backend && uv run pytest tests/rag/test_chunker.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.rag.ingest.chunker'`.

- [ ] **Step 3: Implement `backend/app/rag/ingest/chunker.py`**

```python
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


def _accumulate(
    paragraphs: list[str], target_tokens: int, overlap_tokens: int
) -> list[str]:
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
                    metadata=ChunkMetadata(
                        source=page.source, page=page.page, topic="untagged"
                    ),
                )
            )
    return out
```

- [ ] **Step 4: Run the test, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_chunker.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run mypy + ruff to make sure the new code is clean**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

Expected: all clean. If ruff format wants edits, run `uv run ruff format app/rag tests/rag` and re-check.

- [ ] **Step 6: Commit**

```bash
git add backend/app/rag/ingest/chunker.py backend/tests/rag/test_chunker.py
git commit -m "feat(rag): add paragraph-aware token chunker"
```

---

## Task 3: Cleaner (header/footer/page-number removal)

**Files:**
- Create: `backend/app/rag/ingest/cleaner.py`
- Create: `backend/tests/rag/test_cleaner.py`

- [ ] **Step 1: Write the failing test in `backend/tests/rag/test_cleaner.py`**

```python
"""Tests for app.rag.ingest.cleaner."""
from app.rag.ingest.cleaner import clean_pages
from app.rag.models import ExtractedPage


def _pages(texts: list[str]) -> list[ExtractedPage]:
    return [ExtractedPage(source="x.pdf", page=i + 1, text=t) for i, t in enumerate(texts)]


def test_repeated_header_line_removed():
    pages = _pages([
        "정보처리기사 실기 2024년 1회\n\n본문 내용 페이지 1.",
        "정보처리기사 실기 2024년 1회\n\n본문 내용 페이지 2.",
        "정보처리기사 실기 2024년 1회\n\n본문 내용 페이지 3.",
    ])
    cleaned = clean_pages(pages)
    for c in cleaned:
        assert "정보처리기사 실기 2024년 1회" not in c.text
        assert "본문 내용 페이지" in c.text


def test_repeated_footer_line_removed():
    pages = _pages([
        "본문 1.\n\n— 1 —",
        "본문 2.\n\n— 2 —",
        "본문 3.\n\n— 3 —",
    ])
    cleaned = clean_pages(pages)
    for c in cleaned:
        assert "본문" in c.text
        # the per-page number footer pattern should be gone
        assert c.text.strip().split("\n")[-1].startswith("본문")


def test_unique_line_preserved():
    pages = _pages([
        "공통 헤더\n\n특수한 첫 페이지 메시지",
        "공통 헤더\n\n둘째 페이지 본문",
        "공통 헤더\n\n셋째 페이지 본문",
    ])
    cleaned = clean_pages(pages)
    assert "특수한 첫 페이지 메시지" in cleaned[0].text
    for c in cleaned:
        assert "공통 헤더" not in c.text


def test_single_page_input_is_unchanged():
    pages = _pages(["한 페이지짜리 본문.\n\n페이지 1"])
    cleaned = clean_pages(pages)
    assert cleaned[0].text == pages[0].text


def test_page_number_only_line_removed_even_if_not_repeated():
    pages = _pages([
        "본문 A\n\n1",
        "본문 B\n\n2",
        "본문 C\n\n3",
    ])
    cleaned = clean_pages(pages)
    for c in cleaned:
        # the bare page-number line should be gone
        assert c.text.strip().split("\n")[-1].startswith("본문")
```

- [ ] **Step 2: Run the test (must FAIL)**

```bash
cd backend && uv run pytest tests/rag/test_cleaner.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `backend/app/rag/ingest/cleaner.py`**

```python
"""Header/footer/page-number removal from extracted PDF pages.

Heuristics:
1. Any line that appears verbatim on ≥ ceil(n_pages * 0.6) pages is
   treated as a recurring header/footer and removed.
2. Lines that are *only* a number (with optional surrounding punctuation
   like dashes) are removed regardless — these are page-number footers.
3. Single-page input is returned unchanged (no signal for recurrence).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

from app.rag.models import ExtractedPage


_PAGE_NUMBER_LINE = re.compile(r"^\s*[\-—–\.\(\[]*\s*\d{1,4}\s*[\-—–\.\)\]]*\s*$")


def _split_lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.splitlines()]


def _is_page_number(line: str) -> bool:
    return bool(line.strip()) and bool(_PAGE_NUMBER_LINE.match(line))


def clean_pages(pages: Iterable[ExtractedPage]) -> list[ExtractedPage]:
    pages_list = list(pages)
    if len(pages_list) < 2:
        return pages_list

    # Count line frequency across pages (only for non-empty, non-page-number lines)
    counter: Counter[str] = Counter()
    for p in pages_list:
        for ln in _split_lines(p.text):
            stripped = ln.strip()
            if not stripped or _is_page_number(stripped):
                continue
            counter[stripped] += 1

    threshold = max(2, math.ceil(len(pages_list) * 0.6))
    recurring = {ln for ln, count in counter.items() if count >= threshold}

    cleaned: list[ExtractedPage] = []
    for p in pages_list:
        kept: list[str] = []
        for ln in _split_lines(p.text):
            stripped = ln.strip()
            if not stripped:
                kept.append(ln)
                continue
            if stripped in recurring:
                continue
            if _is_page_number(stripped):
                continue
            kept.append(ln)
        new_text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept).strip())
        cleaned.append(ExtractedPage(source=p.source, page=p.page, text=new_text))

    return cleaned
```

- [ ] **Step 4: Run test, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_cleaner.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add backend/app/rag/ingest/cleaner.py backend/tests/rag/test_cleaner.py
git commit -m "feat(rag): add header/footer/page-number cleaner"
```

---

## Task 4: PDF loader with pdfplumber

**Files:**
- Create: `backend/app/rag/ingest/pdf_loader.py`
- Create: `backend/tests/rag/test_pdf_loader.py`
- Create: `backend/tests/rag/fixtures/tiny.pdf` (generated in-test from text)

- [ ] **Step 1: Write the failing test**

`backend/tests/rag/test_pdf_loader.py`:

```python
"""Tests for app.rag.ingest.pdf_loader."""
from pathlib import Path

import pytest

from app.rag.ingest.pdf_loader import load_pdf


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    """Build a 2-page PDF in memory with reportlab."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))

    path = tmp_path / "tiny.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("HYSMyeongJo-Medium", 14)
    c.drawString(72, 720, "첫째 페이지 본문입니다.")
    c.drawString(72, 700, "정규화는 데이터 중복을 줄인다.")
    c.showPage()
    c.setFont("HYSMyeongJo-Medium", 14)
    c.drawString(72, 720, "둘째 페이지 본문입니다.")
    c.drawString(72, 700, "1NF는 원자값만 허용한다.")
    c.showPage()
    c.save()
    return path


def test_load_pdf_returns_one_page_per_pdf_page(tiny_pdf: Path):
    pages = load_pdf(tiny_pdf)
    assert len(pages) == 2
    assert pages[0].page == 1
    assert pages[1].page == 2


def test_load_pdf_preserves_source_filename(tiny_pdf: Path):
    pages = load_pdf(tiny_pdf)
    assert all(p.source == "tiny.pdf" for p in pages)


def test_load_pdf_extracts_korean_text(tiny_pdf: Path):
    pages = load_pdf(tiny_pdf)
    assert "정규화" in pages[0].text
    assert "1NF" in pages[1].text


def test_load_pdf_raises_for_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_pdf(tmp_path / "nope.pdf")
```

- [ ] **Step 2: Add `reportlab` to dev deps for test fixture generation**

Modify `backend/pyproject.toml` `[dependency-groups] dev`:
```toml
  "reportlab>=4.2",
```

Run:
```bash
cd backend && uv sync
```

- [ ] **Step 3: Run the test (must FAIL on the import)**

```bash
cd backend && uv run pytest tests/rag/test_pdf_loader.py -v
```

Expected: ModuleNotFoundError on `app.rag.ingest.pdf_loader`.

- [ ] **Step 4: Implement `backend/app/rag/ingest/pdf_loader.py`**

```python
"""PDF text extraction using pdfplumber."""
from __future__ import annotations

from pathlib import Path

import pdfplumber

from app.rag.models import ExtractedPage


def load_pdf(path: Path) -> list[ExtractedPage]:
    """Extract one ExtractedPage per page of the given PDF.

    Raises:
        FileNotFoundError: if `path` does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages: list[ExtractedPage] = []
    source = path.name
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(ExtractedPage(source=source, page=i, text=text))
    return pages
```

- [ ] **Step 5: Run the test, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_pdf_loader.py -v
```

Expected: 4 passed (reportlab + pdfplumber both wired up).

- [ ] **Step 6: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/rag/ingest/pdf_loader.py backend/tests/rag/test_pdf_loader.py
git commit -m "feat(rag): add pdfplumber-based PDF loader"
```

---

## Task 5: Embedder protocol + BGE-M3 implementation + Fake

**Files:**
- Create: `backend/app/rag/embedder.py`
- Create: `backend/tests/rag/test_embedder.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/rag/test_embedder.py`:

```python
"""Tests for app.rag.embedder — uses FakeEmbedder only (BGE-M3 is integration)."""
from app.rag.embedder import Embedder, FakeEmbedder


def test_fake_embedder_returns_fixed_dim_vectors():
    emb = FakeEmbedder(dim=8)
    out = emb.embed(["문장 하나", "다른 문장"])
    assert len(out) == 2
    assert all(len(v) == 8 for v in out)


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
    emb: Embedder = FakeEmbedder(dim=8)
    out = emb.embed_query("질의")
    assert isinstance(out, list)
    assert len(out) == 8
```

- [ ] **Step 2: Run, must fail**

```bash
cd backend && uv run pytest tests/rag/test_embedder.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `backend/app/rag/embedder.py`**

```python
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
        from sentence_transformers import SentenceTransformer

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
```

- [ ] **Step 4: Run, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_embedder.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/rag/embedder.py backend/tests/rag/test_embedder.py
git commit -m "feat(rag): add Embedder protocol with BGE-M3 and Fake"
```

---

## Task 6: ChunkStore (ChromaDB wrapper)

**Files:**
- Create: `backend/app/rag/store.py`
- Create: `backend/tests/rag/conftest.py`
- Create: `backend/tests/rag/test_store.py`

- [ ] **Step 1: Write shared fixtures in `backend/tests/rag/conftest.py`**

```python
"""Shared fixtures for app.rag tests."""
from pathlib import Path

import pytest

from app.rag.embedder import FakeEmbedder
from app.rag.models import Chunk, ChunkMetadata


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder(dim=16)


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            id="a1",
            text="정규화는 데이터 중복을 줄이기 위한 작업이다.",
            metadata=ChunkMetadata(source="x.pdf", page=1, topic="정규화"),
        ),
        Chunk(
            id="a2",
            text="1NF는 원자값만 허용한다.",
            metadata=ChunkMetadata(source="x.pdf", page=1, topic="정규화"),
        ),
        Chunk(
            id="b1",
            text="HTTP는 상태 비저장 프로토콜이다.",
            metadata=ChunkMetadata(source="y.pdf", page=2, topic="네트워크"),
        ),
    ]


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    d = tmp_path / "chroma"
    d.mkdir()
    return d
```

- [ ] **Step 2: Write the failing test in `backend/tests/rag/test_store.py`**

```python
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
    assert store.count() == 3


def test_query_returns_most_similar_first(
    store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    vectors = fake_embedder.embed([c.text for c in sample_chunks])
    store.add(sample_chunks, vectors)
    query_vec = fake_embedder.embed_query("정규화는 데이터 중복을 줄이기 위한 작업이다.")
    results = store.query(query_vec, k=2)
    assert len(results) == 2
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
    assert store.count() == 3
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
    assert store2.count() == 3
```

- [ ] **Step 3: Run, must fail**

```bash
cd backend && uv run pytest tests/rag/test_store.py -v
```

Expected: ModuleNotFoundError on `app.rag.store`.

- [ ] **Step 4: Implement `backend/app/rag/store.py`**

```python
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
                    "difficulty": c.metadata.difficulty if c.metadata.difficulty is not None else -1,
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
```

- [ ] **Step 5: Run, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_store.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/rag/store.py backend/tests/rag/conftest.py backend/tests/rag/test_store.py
git commit -m "feat(rag): add ChromaDB-backed ChunkStore wrapper"
```

---

## Task 7: Topic catalog + loader

**Files:**
- Create: `data/topics.yaml`
- Create: `backend/app/rag/ingest/topics.py`
- Create: `backend/tests/rag/test_topics.py`

- [ ] **Step 1: Create `data/topics.yaml`**

```yaml
# 정보처리기사 실기 V1 — 20 core topics.
# Used by topic_tagger.py when classifying chunks during ingestion.
topics:
  - 소프트웨어 설계
  - 요구사항 분석
  - 디자인 패턴
  - 데이터 입출력 구현
  - 정규화
  - SQL 응용
  - 트랜잭션
  - 통합 구현
  - 서버 프로그램 구현
  - 인터페이스 구현
  - 화면 설계
  - 애플리케이션 테스트 관리
  - 소프트웨어 개발 보안
  - 암호화
  - 프로그래밍 언어 활용
  - 자료구조와 알고리즘
  - 운영체제와 메모리
  - 네트워크
  - 응용 SW 기초 기술 활용
  - 제품 소프트웨어 패키징
```

- [ ] **Step 2: Write the failing test in `backend/tests/rag/test_topics.py`**

```python
"""Tests for app.rag.ingest.topics."""
from pathlib import Path

import pytest

from app.rag.ingest.topics import TopicLoadError, load_topics


def test_loads_topic_list(tmp_path: Path):
    file = tmp_path / "topics.yaml"
    file.write_text("topics:\n  - 정규화\n  - 네트워크\n", encoding="utf-8")
    assert load_topics(file) == ["정규화", "네트워크"]


def test_rejects_duplicate_topics(tmp_path: Path):
    file = tmp_path / "topics.yaml"
    file.write_text("topics:\n  - 정규화\n  - 정규화\n", encoding="utf-8")
    with pytest.raises(TopicLoadError, match="duplicate"):
        load_topics(file)


def test_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_topics(tmp_path / "nope.yaml")


def test_rejects_missing_topics_key(tmp_path: Path):
    file = tmp_path / "topics.yaml"
    file.write_text("things: [a, b]\n", encoding="utf-8")
    with pytest.raises(TopicLoadError, match="topics"):
        load_topics(file)


def test_project_topics_file_loads():
    """Smoke-load the real project topics.yaml."""
    root = Path(__file__).resolve().parents[3]  # backend → repo root
    topics = load_topics(root / "data" / "topics.yaml")
    assert "정규화" in topics
    assert len(topics) == 20
```

- [ ] **Step 3: Run, must fail**

```bash
cd backend && uv run pytest tests/rag/test_topics.py -v
```

- [ ] **Step 4: Implement `backend/app/rag/ingest/topics.py`**

```python
"""Topic catalog loader."""
from __future__ import annotations

from pathlib import Path

import yaml


class TopicLoadError(ValueError):
    """Raised when the topics yaml is malformed."""


def load_topics(path: Path) -> list[str]:
    """Load and validate the topic list from a yaml file.

    Raises:
        FileNotFoundError: file does not exist.
        TopicLoadError: yaml is missing `topics:` key, or has duplicates.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"topics file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "topics" not in data or not isinstance(data["topics"], list):
        raise TopicLoadError(
            f"{path}: expected top-level 'topics:' list, got {type(data.get('topics')).__name__}"
        )
    topics = [str(t).strip() for t in data["topics"]]
    seen: set[str] = set()
    dupes: list[str] = []
    for t in topics:
        if t in seen:
            dupes.append(t)
        seen.add(t)
    if dupes:
        raise TopicLoadError(f"{path}: duplicate topics: {dupes}")
    return topics
```

- [ ] **Step 5: Run, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_topics.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/rag/ingest/topics.py backend/tests/rag/test_topics.py data/topics.yaml
git commit -m "feat(rag): add topic catalog and loader"
```

---

## Task 8: Topic tagger (Anthropic Haiku, mocked in tests)

**Files:**
- Create: `backend/app/rag/ingest/topic_tagger.py`
- Create: `backend/tests/rag/test_topic_tagger.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/rag/test_topic_tagger.py`:

```python
"""Tests for app.rag.ingest.topic_tagger — Anthropic client is mocked."""
from unittest.mock import MagicMock

from app.rag.ingest.topic_tagger import tag_chunks
from app.rag.models import Chunk, ChunkMetadata


def _chunk(id: str, text: str) -> Chunk:
    return Chunk(
        id=id, text=text, metadata=ChunkMetadata(source="x.pdf", page=1, topic="untagged")
    )


def test_assigns_topic_from_anthropic_response():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "정규화"}')]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "1NF는 원자값만 허용한다.")]
    tagged = tag_chunks(
        chunks, topics=["정규화", "네트워크"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].metadata.topic == "정규화"
    fake_client.messages.create.assert_called_once()


def test_falls_back_to_기타_on_unknown_topic():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "외계어"}')]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "이상한 문장")]
    tagged = tag_chunks(
        chunks, topics=["정규화", "네트워크"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].metadata.topic == "기타"


def test_falls_back_to_기타_on_malformed_json():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="not json at all")]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "x")]
    tagged = tag_chunks(
        chunks, topics=["정규화"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].metadata.topic == "기타"


def test_makes_one_call_per_chunk():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "정규화"}')]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk(f"c{i}", f"chunk {i}") for i in range(3)]
    tag_chunks(chunks, topics=["정규화"], client=fake_client, model="claude-haiku-4-5")
    assert fake_client.messages.create.call_count == 3


def test_preserves_other_chunk_fields():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "정규화"}')]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "원본 텍스트")]
    tagged = tag_chunks(
        chunks, topics=["정규화"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].id == "c1"
    assert tagged[0].text == "원본 텍스트"
    assert tagged[0].metadata.source == "x.pdf"
    assert tagged[0].metadata.page == 1
```

- [ ] **Step 2: Run, must fail**

```bash
cd backend && uv run pytest tests/rag/test_topic_tagger.py -v
```

- [ ] **Step 3: Implement `backend/app/rag/ingest/topic_tagger.py`**

```python
"""Topic classification via Anthropic Haiku."""
from __future__ import annotations

import json
from typing import Any

from app.rag.models import Chunk, ChunkMetadata


FALLBACK_TOPIC = "기타"


_PROMPT = """다음 텍스트를 가장 잘 설명하는 주제 하나를 아래 목록에서 골라 JSON으로 답하시오.

목록:
{topics}

텍스트:
\"\"\"
{text}
\"\"\"

응답 형식 (다른 말 금지):
{{"topic": "<목록 중 하나>"}}
"""


def _classify_one(
    client: Any, model: str, text: str, allowed: list[str]
) -> str:
    topic_list = "\n".join(f"- {t}" for t in allowed)
    prompt = _PROMPT.format(topics=topic_list, text=text[:1200])
    resp = client.messages.create(
        model=model,
        max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )
    body = resp.content[0].text.strip()
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, AttributeError):
        return FALLBACK_TOPIC
    topic = str(parsed.get("topic", "")).strip()
    if topic not in allowed:
        return FALLBACK_TOPIC
    return topic


def tag_chunks(
    chunks: list[Chunk],
    *,
    topics: list[str],
    client: Any,
    model: str = "claude-haiku-4-5",
) -> list[Chunk]:
    """Classify each chunk's topic using Anthropic Haiku.

    Returns a NEW list of Chunks with `metadata.topic` filled in.
    Original chunks are not mutated.
    """
    allowed = [*topics, FALLBACK_TOPIC]
    out: list[Chunk] = []
    for c in chunks:
        topic = _classify_one(client, model, c.text, allowed)
        new_meta = ChunkMetadata(
            source=c.metadata.source,
            page=c.metadata.page,
            topic=topic,
            chunk_type=c.metadata.chunk_type,
            difficulty=c.metadata.difficulty,
        )
        out.append(
            Chunk(id=c.id, text=c.text, metadata=new_meta, embedding=c.embedding)
        )
    return out
```

- [ ] **Step 4: Run, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_topic_tagger.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/rag/ingest/topic_tagger.py backend/tests/rag/test_topic_tagger.py
git commit -m "feat(rag): add Anthropic-Haiku topic tagger"
```

---

## Task 9: Ingest pipeline (orchestrator)

**Files:**
- Create: `backend/app/rag/ingest/pipeline.py`
- Create: `backend/tests/rag/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/rag/test_pipeline.py`:

```python
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
    assert store.count() == 2


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
```

- [ ] **Step 2: Run, must fail**

```bash
cd backend && uv run pytest tests/rag/test_pipeline.py -v
```

- [ ] **Step 3: Implement `backend/app/rag/ingest/pipeline.py`**

```python
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
```

- [ ] **Step 4: Run, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_pipeline.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/rag/ingest/pipeline.py backend/tests/rag/test_pipeline.py
git commit -m "feat(rag): add IngestPipeline orchestrator"
```

---

## Task 10: Retriever public API

**Files:**
- Modify: `backend/app/rag/__init__.py` (re-export retrieve, IngestPipeline)
- Create: `backend/app/rag/retriever.py`
- Create: `backend/tests/rag/test_retriever.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/rag/test_retriever.py`:

```python
"""Tests for app.rag.retriever — uses fake embedder + tmp store."""
from pathlib import Path

from app.rag.embedder import FakeEmbedder
from app.rag.models import Chunk
from app.rag.retriever import Retriever
from app.rag.store import ChunkStore


def test_retrieve_returns_top_k(
    store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    store.add(sample_chunks, fake_embedder.embed([c.text for c in sample_chunks]))
    retriever = Retriever(store=store, embedder=fake_embedder)
    results = retriever.retrieve("정규화는 데이터 중복을 줄이기 위한 작업이다.", k=2)
    assert len(results) == 2
    assert results[0].score is not None


def test_retrieve_with_k_larger_than_store_returns_all(
    store_dir: Path, sample_chunks: list[Chunk], fake_embedder: FakeEmbedder
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    store.add(sample_chunks, fake_embedder.embed([c.text for c in sample_chunks]))
    retriever = Retriever(store=store, embedder=fake_embedder)
    results = retriever.retrieve("query", k=99)
    assert len(results) == 3


def test_retrieve_on_empty_store_returns_empty(
    store_dir: Path, fake_embedder: FakeEmbedder
):
    store = ChunkStore(persist_dir=store_dir, collection="test_v1")
    retriever = Retriever(store=store, embedder=fake_embedder)
    assert retriever.retrieve("아무거나", k=5) == []


def test_module_reexports_public_surface():
    # the top-level package should re-export the retriever helpers
    from app.rag import Retriever as TopRetriever
    from app.rag import IngestPipeline as TopPipeline
    assert TopRetriever is Retriever
    assert TopPipeline.__name__ == "IngestPipeline"
```

- [ ] **Step 2: Run, must fail**

```bash
cd backend && uv run pytest tests/rag/test_retriever.py -v
```

- [ ] **Step 3: Implement `backend/app/rag/retriever.py`**

```python
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
    from app.core.settings import settings

    store = ChunkStore(
        persist_dir=settings.chroma_dir, collection=settings.chroma_collection
    )
    embedder = BGEM3Embedder(
        model_name=settings.embedding_model, dim=settings.embedding_dim
    )
    return Retriever(store=store, embedder=embedder)
```

- [ ] **Step 4: Modify `backend/app/rag/__init__.py`** to re-export

```python
"""RAG (Retrieval-Augmented Generation) module.

This is the single public surface for retrieval. Outside callers should
import only what is re-exported here. The internal subpackages
(`ingest`, `store`, `embedder`) are implementation details.
"""
from app.rag.ingest.pipeline import IngestPipeline
from app.rag.retriever import Retriever, default_retriever

__all__ = ["IngestPipeline", "Retriever", "default_retriever"]
```

- [ ] **Step 5: Run, confirm pass**

```bash
cd backend && uv run pytest tests/rag/test_retriever.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Lint + types**

```bash
cd backend && uv run ruff check app/rag tests/rag && uv run ruff format --check app/rag tests/rag && uv run mypy app/rag tests/rag
```

- [ ] **Step 7: Verify import-linter contracts still pass**

```bash
cd backend && uv run lint-imports --config .importlinter
```

Expected: `5 kept, 0 broken`. `app.rag` only imports from `app.core` (via `default_retriever`), which is allowed.

- [ ] **Step 8: Commit**

```bash
git add backend/app/rag/__init__.py backend/app/rag/retriever.py backend/tests/rag/test_retriever.py
git commit -m "feat(rag): add Retriever public API and module re-exports"
```

---

## Task 11: Seed CLI

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/seed.py`
- Modify: `Makefile` at the project root

- [ ] **Step 1: Create `backend/scripts/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Create `backend/scripts/seed.py`**

```python
"""CLI to ingest PDFs into the RAG store.

Usage (from `backend/`):
    uv run python -m scripts.seed all
    uv run python -m scripts.seed status
    uv run python -m scripts.seed reset
"""
from __future__ import annotations

import sys
from pathlib import Path

import typer
from anthropic import Anthropic

from app.core.settings import settings
from app.rag.embedder import BGEM3Embedder
from app.rag.ingest.pipeline import IngestPipeline
from app.rag.ingest.topics import load_topics
from app.rag.store import ChunkStore


app = typer.Typer(add_completion=False, help="Seed the RAG store from data/raw/*.pdf")


def _build_pipeline() -> IngestPipeline:
    if not settings.anthropic_api_key:
        typer.echo(
            "ERROR: ANTHROPIC_API_KEY is not set. Add it to .env at the project root.",
            err=True,
        )
        raise typer.Exit(code=2)
    topics = load_topics(settings.topics_file)
    store = ChunkStore(
        persist_dir=settings.chroma_dir, collection=settings.chroma_collection
    )
    embedder = BGEM3Embedder(
        model_name=settings.embedding_model, dim=settings.embedding_dim
    )
    client = Anthropic(api_key=settings.anthropic_api_key)
    return IngestPipeline(
        store=store,
        embedder=embedder,
        topics=topics,
        anthropic_client=client,
        anthropic_model="claude-haiku-4-5",
    )


@app.command()
def all() -> None:  # noqa: A001  (typer expects this name)
    """Ingest every *.pdf under settings.raw_pdf_dir."""
    if not settings.raw_pdf_dir.exists():
        typer.echo(f"ERROR: {settings.raw_pdf_dir} does not exist.", err=True)
        raise typer.Exit(code=2)
    pdfs = sorted(settings.raw_pdf_dir.glob("*.pdf"))
    if not pdfs:
        typer.echo(f"No PDFs found in {settings.raw_pdf_dir}. Drop files there first.")
        raise typer.Exit(code=0)

    typer.echo(f"Ingesting {len(pdfs)} PDF(s) from {settings.raw_pdf_dir} …")
    pipeline = _build_pipeline()
    counts = pipeline.run_dir(settings.raw_pdf_dir)
    total = sum(counts.values())
    for name, n in counts.items():
        typer.echo(f"  · {name}  →  {n} chunk(s)")
    typer.echo(f"Done. Total chunks added: {total}")


@app.command()
def status() -> None:
    """Print collection size."""
    store = ChunkStore(
        persist_dir=settings.chroma_dir, collection=settings.chroma_collection
    )
    typer.echo(f"Collection '{settings.chroma_collection}': {store.count()} chunks")


@app.command()
def reset() -> None:
    """Drop and recreate the collection (data on disk is purged)."""
    store = ChunkStore(
        persist_dir=settings.chroma_dir, collection=settings.chroma_collection
    )
    before = store.count()
    store.reset()
    typer.echo(f"Reset collection '{settings.chroma_collection}' (was {before} chunks).")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app() or 0)
```

- [ ] **Step 3: Modify `Makefile`** — add a `seed` target after the existing `dev` block

Insert these lines into `Makefile` directly under the `dev-frontend:` target's recipe (i.e., before the `# Run both concurrently` comment):

```makefile
seed:
	cd backend && uv run python -m scripts.seed all

seed-status:
	cd backend && uv run python -m scripts.seed status

seed-reset:
	cd backend && uv run python -m scripts.seed reset
```

Also add `seed seed-status seed-reset` to the `.PHONY` line at the top so they look like:

```makefile
.PHONY: help install dev dev-backend dev-frontend test lint typecheck ci-local seed seed-status seed-reset
```

And add to the `help` recipe's `@echo` block, after the existing lines:

```makefile
	@echo "  seed          ingest data/raw/*.pdf into the RAG store"
	@echo "  seed-status   show chunk count in the RAG collection"
	@echo "  seed-reset    drop and recreate the RAG collection"
```

- [ ] **Step 4: Verify the typer CLI imports cleanly**

```bash
cd backend && uv run python -m scripts.seed --help
```

Expected: typer's help banner showing `all`, `status`, `reset` commands.

- [ ] **Step 5: Lint + types on scripts**

```bash
cd backend && uv run ruff check scripts && uv run ruff format --check scripts && uv run mypy scripts
```

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/ Makefile
git commit -m "feat(rag): add typer seed CLI and Makefile targets"
```

---

## Task 12: End-to-end smoke verification with real BGE-M3

This task uses a real (small) PDF and a real BGE-M3 download. On first run, sentence-transformers will download ~2.3GB of weights into the user's HuggingFace cache (`~/.cache/huggingface/hub/`). The user must have set `ANTHROPIC_API_KEY` in `.env` to exercise the tagger.

- [ ] **Step 1: Confirm ANTHROPIC_API_KEY is set**

```bash
cd ..  # project root
python -c "from dotenv import dotenv_values; vals = dotenv_values('.env'); k = vals.get('ANTHROPIC_API_KEY'); print('SET' if k else 'MISSING')"
```

If MISSING, add a line to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

(Block this task and ask the user for the key if not set — do not invent one.)

- [ ] **Step 2: Generate a small Korean PDF for smoke testing**

From `backend/`:

```bash
uv run python - <<'PY'
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
out = Path("../data/raw")
out.mkdir(parents=True, exist_ok=True)
target = out / "smoke_normalization.pdf"

c = canvas.Canvas(str(target), pagesize=letter)
c.setFont("HYSMyeongJo-Medium", 14)

lines = [
    "정규화는 데이터의 중복을 줄이기 위한 작업이다.",
    "제1정규형(1NF)은 모든 속성이 원자값을 가져야 한다.",
    "제2정규형(2NF)은 부분 함수 종속을 제거한 형태이다.",
    "제3정규형(3NF)은 이행적 함수 종속을 제거한 형태이다.",
    "정규화의 일차적 목적은 이상현상(anomaly) 방지에 있다.",
]
y = 720
for ln in lines:
    c.drawString(72, y, ln)
    y -= 20
c.showPage()
c.save()
print(f"wrote {target}")
PY
```

Expected: prints `wrote ../data/raw/smoke_normalization.pdf`.

- [ ] **Step 3: Run `make seed`**

From the project root:

```bash
make seed
```

Expected output:
- A first-run download log from sentence-transformers (~2.3GB pulled into HuggingFace cache).
- `Ingesting 1 PDF(s) from data/raw …`
- `· smoke_normalization.pdf  →  N chunk(s)` where N ≥ 1
- `Done. Total chunks added: N`

If it fails with `ANTHROPIC_API_KEY missing`, fix `.env` and re-run.

- [ ] **Step 4: Run `make seed-status`**

```bash
make seed-status
```

Expected: `Collection 'jeongcheo_v1': N chunks` (matching Step 3).

- [ ] **Step 5: Run a retrieval smoke check**

From `backend/`:

```bash
uv run python - <<'PY'
from app.rag.retriever import default_retriever

r = default_retriever()
results = r.retrieve("정규화의 목적이 무엇인가?", k=3)
for c in results:
    print(f"[{c.score:.3f}] {c.metadata.topic} p{c.metadata.page} :: {c.text[:80]}")
PY
```

Expected:
- 3 results print.
- The top result's text contains "정규화" or "이상현상" (the most semantically relevant content).
- Scores are between roughly 0.4 and 0.9 (cosine similarity).

If the top result is unrelated, that's a signal the embedder pipeline is mis-wired (BGE-M3 not loading, vectors not normalized, etc.) — debug before declaring done.

- [ ] **Step 6: Run the entire test suite to confirm no regressions**

```bash
cd backend && uv run pytest -v
```

Expected: all tests pass (Tasks 1-10 tests, plus pre-existing tests = 30+ passing).

- [ ] **Step 7: Commit any lockfile / chroma data updates**

```bash
git status
git add backend/uv.lock 2>/dev/null || true
git diff --cached --quiet || git commit -m "chore: lock files after RAG smoke verification"
```

Note: `chroma/` and `data/raw/` are gitignored — they will not be committed. The smoke PDF lives only in your local working tree.

---

## Acceptance Criteria

Plan 2 is complete when **all** of the following hold:

1. `cd backend && uv run pytest -v` passes 100% (all RAG tests + pre-existing tests).
2. `cd backend && uv run lint-imports --config .importlinter` reports `5 kept, 0 broken`.
3. `cd backend && uv run mypy app tests` passes.
4. `make seed` with at least one PDF in `data/raw/` produces a non-zero chunk count and persists ChromaDB into `./chroma/`.
5. `make seed-status` shows the same chunk count after a fresh shell.
6. The retrieval smoke check (Task 12 Step 5) returns topically relevant results for a Korean query.
7. `make ci-local` still passes (no regressions in Plan 1 quality gates).

---

## What's Next

Plan 3: **LangGraph Workflow & 3 Agents**. SessionState (TypedDict), `Coordinator` / `QuestionGenerator` / `Grader` nodes, `SqliteSaver` checkpointer, `interrupt_before` HITL for awaiting learner answers. Verification: `run_session(user_id, topic="정규화")` from the CLI runs `Coordinator → QuestionGenerator → AWAIT_ANSWER → Grader → Persist` with `retriever.retrieve()` from Plan 2 supplying the context.
