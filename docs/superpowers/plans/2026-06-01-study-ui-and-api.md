# Study UI & API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Plan 3 agent graph into a FastAPI HTTP surface and a Next.js Study page so a user can click "다음 문제 →" in the browser, type a learner answer, and see the Grader's score + rubric + feedback rendered live. The frontend implements the Architectural-Dark design from `docs/design-explorations/2026-05-30-study-session-architectural-dark.html`. End-to-end demo: open browser → /study → session starts → question rendered → user types → submit → score displayed.

**Architecture:** Three API endpoints (`POST /sessions`, `POST /sessions/{id}/answer`, `GET /sessions/{id}`) wrap `app.agents.run_session` / `resume_session`. FastAPI Depends() injects a singleton graph built at app startup from real Anthropic + real RAG retriever. Next.js 14 server components fetch from the API; client components handle answer submission. shadcn/ui provides accessible primitives (Button, Input, Card, Badge) themed with the Architectural-Dark tokens from `docs/design-explorations/DECISION.md`.

**Tech Stack:** FastAPI / Pydantic v2 / structlog / pytest + httpx | Next.js 14 / Tailwind 3.4 / shadcn/ui / Pretendard + Fraunces + JetBrains Mono | LangGraph (consumed from app.agents) | Anthropic SDK (real, gated on ANTHROPIC_API_KEY at runtime; mocked in pytest)

**This plan is plan 4 of 7 in the StudyMate AI V1 series.** See `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` §3 + §4 and `docs/design-explorations/DECISION.md`.

**Deferred from spec:**
- **DB persistence of sessions** — Plan 5 wires `PersistAdapter` to SQLAlchemy. In Plan 4, the adapter is `None` (state lives only in the LangGraph checkpointer SQLite).
- **`/dashboard` and `/history` pages** — Plan 5.
- **Real-time SSE streaming of token-by-token output** — Plan 4 uses request/response (browser waits for the Grader to finish). SSE comes in Plan 7 polish.
- **Auth** — single local user; no login.

---

## File Structure

```
studymate-ai/
├─ backend/
│  └─ app/
│     ├─ api/
│     │  ├─ schemas/
│     │  │  ├─ __init__.py
│     │  │  └─ sessions.py                 # Pydantic DTOs
│     │  ├─ dependencies.py                # Depends() factories: graph, retriever, anthropic client
│     │  ├─ session_store.py               # in-process map session_id → SessionRecord (Plan 5 replaces)
│     │  └─ routes/
│     │     ├─ __init__.py
│     │     ├─ health.py                   # (Plan 1)
│     │     └─ sessions.py                 # /sessions endpoints
│     └─ main.py                            # MODIFY: include sessions router + lifespan graph init
├─ frontend/
│  ├─ package.json                          # MODIFY: add shadcn-ui deps (class-variance-authority, clsx, etc.)
│  ├─ tailwind.config.ts                    # MODIFY: extend with Architectural-Dark tokens
│  ├─ components.json                       # shadcn/ui config
│  └─ src/
│     ├─ app/
│     │  ├─ globals.css                     # MODIFY: shadcn CSS variables for the dark palette
│     │  ├─ layout.tsx                      # MODIFY: bg-bg color
│     │  └─ study/
│     │     ├─ page.tsx                     # server: starts session, hands payload to client
│     │     └─ session-view.tsx             # "use client": question → answer input → score render
│     ├─ components/
│     │  └─ ui/                             # shadcn primitives (button, input, badge, card)
│     └─ lib/
│        ├─ api.ts                          # MODIFY: add createSession, submitAnswer, getSession
│        └─ utils.ts                        # shadcn cn() helper
└─ backend/tests/api/
   ├─ __init__.py
   ├─ conftest.py                           # FastAPI TestClient with mocked graph
   ├─ test_sessions_create.py
   ├─ test_sessions_answer.py
   ├─ test_sessions_get.py
   └─ test_sessions_e2e.py                  # full POST→POST→GET cycle, mocked graph
```

### File-by-file responsibility

- **`app/api/schemas/sessions.py`** — Request/response Pydantic shapes. Distinct from `app.agents.state.SessionState` (TypedDict) because HTTP needs strict validation and OpenAPI generation.
- **`app/api/dependencies.py`** — `Depends()` factories for the singleton `CompiledGraph`, `Retriever`, `Anthropic` client. Built once at app startup (`lifespan`).
- **`app/api/session_store.py`** — Minimal map `session_id → {created_at, user_id, target_count, status}`. The actual graph state is in the LangGraph checkpointer. Plan 5 replaces this with a SQLAlchemy table.
- **`app/api/routes/sessions.py`** — 3 endpoints: `POST /sessions`, `POST /sessions/{id}/answer`, `GET /sessions/{id}`.
- **`app/main.py`** — `lifespan` builds the graph; router included.
- **`frontend/components.json`** — shadcn/ui scaffold config (one-time).
- **`frontend/tailwind.config.ts`** — Architectural-Dark color tokens + Fraunces / JetBrains Mono font registration.
- **`frontend/src/app/study/page.tsx`** — Server component, calls `createSession` once on render.
- **`frontend/src/app/study/session-view.tsx`** — Client component, owns the answer-input + submit state.
- **`frontend/src/lib/api.ts`** — Adds typed wrappers `createSession`, `submitAnswer`, `getSession`.

---

## Task 1: Backend DTOs + session store

**Files:**
- Create: `backend/app/api/schemas/__init__.py`
- Create: `backend/app/api/schemas/sessions.py`
- Create: `backend/app/api/session_store.py`
- Create: `backend/tests/api/__init__.py`
- Create: `backend/tests/api/test_schemas.py`

- [ ] **Step 1: Create `backend/app/api/schemas/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Create `backend/app/api/schemas/sessions.py`**

```python
"""HTTP request/response shapes for /sessions endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SessionStatus = Literal["awaiting_answer", "graded", "completed"]


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="local-user")
    target_count: int = Field(default=5, ge=1, le=20)
    user_intent: str = Field(default="자유 학습")


class RubricItemDTO(BaseModel):
    point: str
    weight: float
    keywords: list[str]


class SessionStateDTO(BaseModel):
    """The snapshot returned after run_session / resume_session."""

    session_id: str
    user_id: str
    status: SessionStatus
    topic: str | None = None
    difficulty: int | None = None
    target_weakness: bool | None = None
    question: str | None = None
    model_answer: str | None = None
    rubric: list[RubricItemDTO] = Field(default_factory=list)
    ref_chunk_ids: list[str] = Field(default_factory=list)
    user_answer: str | None = None
    score: float | None = None
    rationale: str | None = None
    feedback: str | None = None
    missing_points: list[str] = Field(default_factory=list)
    questions_done: int = 0
    target_count: int = 5
    created_at: datetime


class SubmitAnswerRequest(BaseModel):
    user_answer: str = Field(min_length=1, max_length=4000)
```

- [ ] **Step 3: Create `backend/app/api/session_store.py`**

```python
"""In-process registry of session metadata.

The LangGraph checkpointer owns the actual graph state. This module only
tracks who created which session and when. Plan 5 replaces with SQLAlchemy.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SessionRecord:
    session_id: str
    user_id: str
    target_count: int
    user_intent: str
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class SessionStore:
    """Thread-safe in-memory registry."""

    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = threading.Lock()

    def add(self, record: SessionRecord) -> None:
        with self._lock:
            self._records[record.session_id] = record

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._records.get(session_id)

    def all(self) -> list[SessionRecord]:
        with self._lock:
            return list(self._records.values())
```

- [ ] **Step 4: Create `backend/tests/api/__init__.py`** (empty)

```python
```

- [ ] **Step 5: Write `backend/tests/api/test_schemas.py`**

```python
"""Tests for app.api.schemas.sessions."""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.schemas.sessions import (
    CreateSessionRequest,
    RubricItemDTO,
    SessionStateDTO,
    SubmitAnswerRequest,
)


def test_create_session_defaults():
    req = CreateSessionRequest()
    expected_target = 5
    assert req.user_id == "local-user"
    assert req.target_count == expected_target
    assert req.user_intent == "자유 학습"


def test_create_session_rejects_zero_target_count():
    with pytest.raises(ValidationError):
        CreateSessionRequest(target_count=0)


def test_create_session_rejects_huge_target_count():
    huge_target = 100
    with pytest.raises(ValidationError):
        CreateSessionRequest(target_count=huge_target)


def test_submit_answer_rejects_empty():
    with pytest.raises(ValidationError):
        SubmitAnswerRequest(user_answer="")


def test_submit_answer_caps_at_4000_chars():
    too_long = "x" * 4001
    with pytest.raises(ValidationError):
        SubmitAnswerRequest(user_answer=too_long)


def test_session_state_dto_round_trips():
    state = SessionStateDTO(
        session_id="s1",
        user_id="u1",
        status="awaiting_answer",
        topic="정규화",
        difficulty=2,
        target_weakness=True,
        question="q?",
        rubric=[RubricItemDTO(point="p", weight=1.0, keywords=["k"])],
        created_at=datetime.now(tz=UTC),
    )
    restored = SessionStateDTO.model_validate(state.model_dump())
    assert restored == state
```

- [ ] **Step 6: Run pytest**

```bash
cd backend && uv run pytest tests/api/test_schemas.py -v
```

Expected: 6 passed.

- [ ] **Step 7: Lint + types**

```bash
cd backend && uv run ruff check app/api tests/api && uv run ruff format --check app/api tests/api && uv run mypy app/api tests/api
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/ backend/tests/api/
git commit -m "feat(api): add session DTOs and in-memory session store"
git push
```

---

## Task 2: Dependencies wiring (graph + retriever + anthropic singletons)

**Files:**
- Create: `backend/app/api/dependencies.py`
- Modify: `backend/app/main.py` (lifespan builds graph; expose deps)

- [ ] **Step 1: Create `backend/app/api/dependencies.py`**

```python
"""FastAPI Depends() factories.

The graph and its expensive components (BGE-M3 embedder, Anthropic client,
ChromaDB store) are built once at app startup and reused across requests.
"""
from __future__ import annotations

from typing import Annotated, Any

from anthropic import Anthropic
from fastapi import Depends, Request

from app.agents import build_graph, make_checkpointer
from app.api.session_store import SessionStore
from app.core.settings import settings
from app.rag.ingest.topics import load_topics
from app.rag.retriever import default_retriever


def _build_graph_singleton() -> Any:
    """Construct the agent graph with real Anthropic + real retriever."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    retriever = default_retriever()
    topics = load_topics(settings.topics_file)
    saver = make_checkpointer(settings.studymate_db)
    return build_graph(
        checkpointer=saver,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: [],
        persist_adapter=None,
        topics=topics,
        sonnet_model=settings.anthropic_model_sonnet,
        haiku_model=settings.anthropic_model_haiku,
    )


def get_graph(request: Request) -> Any:
    """Return the graph singleton attached to app.state by the lifespan."""
    return request.app.state.graph


def get_session_store(request: Request) -> SessionStore:
    """Return the session-store singleton attached to app.state by the lifespan."""
    return request.app.state.session_store


GraphDep = Annotated[Any, Depends(get_graph)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
```

- [ ] **Step 2: Modify `backend/app/main.py` lifespan to build graph + session store**

Replace the file content with:

```python
"""FastAPI application entry point."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import _build_graph_singleton
from app.api.routes import health
from app.api.session_store import SessionStore
from app.core.logging import configure_logging
from app.core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    app.state.session_store = SessionStore()
    # Defer expensive graph build until a real ANTHROPIC_API_KEY is configured.
    # Tests inject their own graph via dependency overrides.
    if settings.anthropic_api_key:
        app.state.graph = _build_graph_singleton()
    else:
        app.state.graph = None
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
```

(Sessions router will be included in Task 5.)

- [ ] **Step 3: Run full pytest to confirm no regressions**

```bash
cd backend && uv run pytest -v
```

Expected: all tests pass (no new tests yet; existing 76 + 6 from Task 1 = 82 should be similar).

- [ ] **Step 4: Lint + types**

```bash
cd backend && uv run ruff check app/api tests/api app/main.py && uv run ruff format --check app/api tests/api app/main.py && uv run mypy app/api tests/api app/main.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/dependencies.py backend/app/main.py
git commit -m "feat(api): wire graph + session store as FastAPI singletons via lifespan"
git push
```

---

## Task 3: `POST /sessions` endpoint (TDD with mocked graph)

**Files:**
- Create: `backend/tests/api/conftest.py`
- Create: `backend/tests/api/test_sessions_create.py`
- Create: `backend/app/api/routes/sessions.py`
- Modify: `backend/app/main.py` (include sessions router)

- [ ] **Step 1: Write the conftest**

`backend/tests/api/conftest.py`:

```python
"""Shared fixtures for app.api tests."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_graph, get_session_store
from app.api.session_store import SessionStore
from app.main import create_app


@pytest.fixture
def fake_graph() -> MagicMock:
    """A mock graph that records invoke / update_state calls."""
    return MagicMock()


@pytest.fixture
def session_store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def client(fake_graph: MagicMock, session_store: SessionStore) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_graph] = lambda: fake_graph
    app.dependency_overrides[get_session_store] = lambda: session_store
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 2: Write the failing test**

`backend/tests/api/test_sessions_create.py`:

```python
"""POST /sessions — start a new learning session."""
from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_create_session_returns_question(client: TestClient, fake_graph: MagicMock):
    # Graph's invoke returns the post-QGen, pre-Grader snapshot
    fake_graph.invoke.return_value = {
        "user_id": "local-user",
        "session_id": "ignored-by-route",
        "topic": "정규화",
        "difficulty": 2,
        "target_weakness": False,
        "question": "정규화의 목적을 서술하시오.",
        "model_answer": "이상현상 방지.",
        "rubric": [{"point": "목적", "weight": 1.0, "keywords": ["이상현상"]}],
        "ref_chunk_ids": ["c1"],
        "questions_done": 0,
        "target_count": 5,
    }
    response = client.post("/sessions", json={"user_id": "u1", "target_count": 5})
    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body["status"] == "awaiting_answer"
    assert body["question"] == "정규화의 목적을 서술하시오."
    assert body["topic"] == "정규화"
    assert body["user_id"] == "u1"
    assert body["session_id"]  # generated server-side


def test_create_session_uses_defaults(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {
        "topic": "x",
        "question": "q",
        "rubric": [],
        "ref_chunk_ids": [],
    }
    response = client.post("/sessions", json={})
    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    expected_target = 5
    assert body["user_id"] == "local-user"
    assert body["target_count"] == expected_target


def test_create_session_rejects_invalid_target(client: TestClient):
    response = client.post("/sessions", json={"target_count": 0})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_session_returns_503_when_graph_disabled(
    client: TestClient, fake_graph: MagicMock, monkeypatch
):
    """If lifespan didn't build a graph (no ANTHROPIC_API_KEY), POST should fail cleanly."""
    # Override the dependency to return None (simulating no key)
    from app.api.dependencies import get_graph

    client.app.dependency_overrides[get_graph] = lambda: None
    response = client.post("/sessions", json={})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
```

- [ ] **Step 3: Run, must fail**

```bash
cd backend && uv run pytest tests/api/test_sessions_create.py -v
```

Expected: ModuleNotFoundError on `app.api.routes.sessions`.

- [ ] **Step 4: Implement `backend/app/api/routes/sessions.py`**

```python
"""Session lifecycle endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import GraphDep, SessionStoreDep
from app.api.schemas.sessions import (
    CreateSessionRequest,
    RubricItemDTO,
    SessionStateDTO,
)
from app.api.session_store import SessionRecord


router = APIRouter(prefix="/sessions", tags=["sessions"])


def _state_to_dto(
    *,
    raw: dict[str, Any],
    record: SessionRecord,
    status_label: str,
) -> SessionStateDTO:
    rubric_dtos = [
        RubricItemDTO(
            point=str(r.get("point", "")),
            weight=float(r.get("weight", 0.0)),
            keywords=list(r.get("keywords", [])),
        )
        for r in raw.get("rubric", [])
    ]
    return SessionStateDTO(
        session_id=record.session_id,
        user_id=record.user_id,
        status=status_label,  # type: ignore[arg-type]
        topic=raw.get("topic"),
        difficulty=raw.get("difficulty"),
        target_weakness=raw.get("target_weakness"),
        question=raw.get("question"),
        model_answer=raw.get("model_answer"),
        rubric=rubric_dtos,
        ref_chunk_ids=list(raw.get("ref_chunk_ids", [])),
        user_answer=raw.get("user_answer"),
        score=raw.get("score"),
        rationale=raw.get("rationale"),
        feedback=raw.get("feedback"),
        missing_points=list(raw.get("missing_points", [])),
        questions_done=int(raw.get("questions_done", 0)),
        target_count=record.target_count,
        created_at=record.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionStateDTO)
def create_session(
    req: CreateSessionRequest, graph: GraphDep, store: SessionStoreDep
) -> SessionStateDTO:
    if graph is None:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="agent_graph_unavailable — set ANTHROPIC_API_KEY and restart",
        )
    session_id = str(uuid.uuid4())
    record = SessionRecord(
        session_id=session_id,
        user_id=req.user_id,
        target_count=req.target_count,
        user_intent=req.user_intent,
        created_at=datetime.now(tz=UTC),
    )
    store.add(record)

    config = {"configurable": {"thread_id": session_id}}
    initial = {
        "user_id": req.user_id,
        "session_id": session_id,
        "questions_done": 0,
        "target_count": req.target_count,
    }
    raw_state = graph.invoke(initial, config=config) or {}
    return _state_to_dto(raw=raw_state, record=record, status_label="awaiting_answer")
```

- [ ] **Step 5: Modify `backend/app/main.py` to include the sessions router**

In `create_app()` after `app.include_router(health.router)` add:

```python
    from app.api.routes import sessions

    app.include_router(sessions.router)
```

(The local import avoids a circular dep with `dependencies.py` at module load.)

- [ ] **Step 6: Run, confirm pass**

```bash
cd backend && uv run pytest tests/api/test_sessions_create.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Lint + types**

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/routes/sessions.py backend/app/main.py backend/tests/api/conftest.py backend/tests/api/test_sessions_create.py
git commit -m "feat(api): add POST /sessions endpoint with mocked-graph TDD"
git push
```

---

## Task 4: `POST /sessions/{id}/answer` endpoint

**Files:**
- Create: `backend/tests/api/test_sessions_answer.py`
- Modify: `backend/app/api/routes/sessions.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_sessions_answer.py`:

```python
"""POST /sessions/{id}/answer — submit learner answer + resume graph."""
from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_submit_answer_returns_grading(client: TestClient, fake_graph: MagicMock):
    # Step 1: create session
    fake_graph.invoke.return_value = {
        "topic": "정규화",
        "question": "q",
        "rubric": [],
        "ref_chunk_ids": [],
    }
    create_resp = client.post("/sessions", json={"user_id": "u1"})
    session_id = create_resp.json()["session_id"]

    # Step 2: resume — graph.update_state + graph.invoke(None) returns Grader output
    fake_graph.invoke.side_effect = None
    fake_graph.invoke.return_value = {
        "topic": "정규화",
        "question": "q",
        "rubric": [],
        "user_answer": "answer text",
        "score": 0.83,
        "rationale": "ok",
        "feedback": "보강 가이드",
        "missing_points": ["이상현상"],
        "questions_done": 1,
    }
    response = client.post(
        f"/sessions/{session_id}/answer",
        json={"user_answer": "answer text"},
    )
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["status"] == "graded"
    assert body["score"] == 0.83
    assert body["missing_points"] == ["이상현상"]
    fake_graph.update_state.assert_called_once()


def test_submit_answer_rejects_unknown_session(client: TestClient):
    response = client.post(
        "/sessions/00000000-0000-0000-0000-000000000000/answer",
        json={"user_answer": "x"},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_submit_answer_rejects_empty(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {"question": "q", "rubric": [], "ref_chunk_ids": []}
    create_resp = client.post("/sessions", json={})
    sid = create_resp.json()["session_id"]
    response = client.post(f"/sessions/{sid}/answer", json={"user_answer": ""})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_submit_answer_503_when_graph_disabled(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {"question": "q", "rubric": [], "ref_chunk_ids": []}
    create_resp = client.post("/sessions", json={})
    sid = create_resp.json()["session_id"]

    from app.api.dependencies import get_graph

    client.app.dependency_overrides[get_graph] = lambda: None
    response = client.post(f"/sessions/{sid}/answer", json={"user_answer": "a"})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
```

- [ ] **Step 2: Run, must fail.**

- [ ] **Step 3: Add the `submit_answer` route to `backend/app/api/routes/sessions.py`**

Append to the existing file:

```python
@router.post(
    "/{session_id}/answer",
    response_model=SessionStateDTO,
    status_code=status.HTTP_200_OK,
)
def submit_answer(
    session_id: str,
    body: "SubmitAnswerRequest",
    graph: GraphDep,
    store: SessionStoreDep,
) -> SessionStateDTO:
    if graph is None:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="agent_graph_unavailable — set ANTHROPIC_API_KEY and restart",
        )
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="session_not_found")

    config = {"configurable": {"thread_id": session_id}}
    graph.update_state(config, {"user_answer": body.user_answer})
    raw_state = graph.invoke(None, config=config) or {}
    return _state_to_dto(raw=raw_state, record=record, status_label="graded")
```

Also add the import at the top of the file:

```python
from app.api.schemas.sessions import (
    CreateSessionRequest,
    RubricItemDTO,
    SessionStateDTO,
    SubmitAnswerRequest,
)
```

- [ ] **Step 4: Run, confirm 4 passed.**

- [ ] **Step 5: Lint + types**

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/sessions.py backend/tests/api/test_sessions_answer.py
git commit -m "feat(api): add POST /sessions/{id}/answer endpoint"
git push
```

---

## Task 5: `GET /sessions/{id}` snapshot endpoint

**Files:**
- Create: `backend/tests/api/test_sessions_get.py`
- Modify: `backend/app/api/routes/sessions.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_sessions_get.py`:

```python
"""GET /sessions/{id} — snapshot the latest graph state."""
from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_get_session_returns_current_state(client: TestClient, fake_graph: MagicMock):
    # Seed a session
    fake_graph.invoke.return_value = {
        "topic": "정규화",
        "question": "q",
        "rubric": [],
        "ref_chunk_ids": [],
    }
    create_resp = client.post("/sessions", json={"user_id": "u1"})
    sid = create_resp.json()["session_id"]

    # graph.get_state returns a StateSnapshot-like object with .values dict
    fake_graph.get_state.return_value = MagicMock(
        values={
            "topic": "정규화",
            "question": "q",
            "score": 0.7,
            "rubric": [],
        }
    )
    response = client.get(f"/sessions/{sid}")
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["session_id"] == sid
    assert body["score"] == 0.7
    assert body["topic"] == "정규화"


def test_get_session_404_for_unknown(client: TestClient):
    response = client.get("/sessions/nonexistent")
    assert response.status_code == HTTPStatus.NOT_FOUND
```

- [ ] **Step 2: Run, must fail.**

- [ ] **Step 3: Add the `get_session` route to `backend/app/api/routes/sessions.py`**

Append:

```python
@router.get("/{session_id}", response_model=SessionStateDTO)
def get_session(
    session_id: str, graph: GraphDep, store: SessionStoreDep
) -> SessionStateDTO:
    record = store.get(session_id)
    if record is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="session_not_found")
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config) if graph is not None else None
    raw_state = dict(snapshot.values) if snapshot is not None else {}
    has_score = raw_state.get("score") is not None
    label = "graded" if has_score else "awaiting_answer"
    return _state_to_dto(raw=raw_state, record=record, status_label=label)
```

- [ ] **Step 4: Run, confirm 2 passed.**

- [ ] **Step 5: Lint + types**

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/sessions.py backend/tests/api/test_sessions_get.py
git commit -m "feat(api): add GET /sessions/{id} snapshot endpoint"
git push
```

---

## Task 6: Full-flow integration test

**Files:**
- Create: `backend/tests/api/test_sessions_e2e.py`

- [ ] **Step 1: Write the integration test**

```python
"""End-to-end /sessions flow with mocked graph that mimics LangGraph semantics."""
import json
from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def _payload(text: str):
    return type("M", (), {"content": [type("C", (), {"text": text})()]})()


def test_full_session_lifecycle(client: TestClient, fake_graph: MagicMock):
    # Phase 1: POST /sessions returns awaiting_answer
    create_state = {
        "topic": "정규화",
        "question": "정규화의 목적을 서술하시오.",
        "model_answer": "이상현상 방지.",
        "rubric": [{"point": "목적", "weight": 1.0, "keywords": ["이상현상"]}],
        "ref_chunk_ids": ["c1"],
    }
    fake_graph.invoke.return_value = create_state
    create_resp = client.post("/sessions", json={"user_id": "u1", "target_count": 3})
    assert create_resp.status_code == HTTPStatus.CREATED
    sid = create_resp.json()["session_id"]
    assert create_resp.json()["status"] == "awaiting_answer"

    # Phase 2: POST /sessions/{id}/answer returns graded
    fake_graph.invoke.return_value = {
        **create_state,
        "user_answer": "데이터 중복을 줄이기 위함.",
        "score": 0.5,
        "rationale": "목적 절반만",
        "feedback": "이상현상을 명시하세요.",
        "missing_points": ["이상현상"],
        "questions_done": 1,
    }
    answer_resp = client.post(
        f"/sessions/{sid}/answer",
        json={"user_answer": "데이터 중복을 줄이기 위함."},
    )
    assert answer_resp.status_code == HTTPStatus.OK
    assert answer_resp.json()["score"] == 0.5
    assert answer_resp.json()["status"] == "graded"

    # Phase 3: GET /sessions/{id} returns the same graded snapshot
    fake_graph.get_state.return_value = MagicMock(values=fake_graph.invoke.return_value)
    get_resp = client.get(f"/sessions/{sid}")
    assert get_resp.status_code == HTTPStatus.OK
    assert get_resp.json()["score"] == 0.5
    assert get_resp.json()["session_id"] == sid
```

- [ ] **Step 2: Run, confirm 1 passed.**

- [ ] **Step 3: Lint + types**

- [ ] **Step 4: Commit**

```bash
git add backend/tests/api/test_sessions_e2e.py
git commit -m "test(api): full /sessions create→answer→get flow with mocked graph"
git push
```

---

## Task 7: Frontend — Tailwind tokens + shadcn/ui init

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/app/layout.tsx`
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/badge.tsx`
- Create: `frontend/src/components/ui/card.tsx`

- [ ] **Step 1: Add shadcn-related deps to `frontend/package.json`**

Add to `dependencies`:
```json
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "tailwind-merge": "2.5.4",
    "@radix-ui/react-slot": "1.1.0",
    "lucide-react": "0.460.0"
```

Add to `devDependencies`:
```json
    "tailwindcss-animate": "1.0.7"
```

Then:
```bash
cd frontend && pnpm install
```

- [ ] **Step 2: Modify `frontend/tailwind.config.ts`** to add Architectural-Dark tokens

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-deep": "var(--bg-deep)",
        panel: "var(--panel)",
        "panel-line": "var(--panel-line)",
        ink: "var(--ink)",
        "ink-mid": "var(--ink-mid)",
        "ink-soft": "var(--ink-soft)",
        cyan: "var(--cyan)",
        "cyan-deep": "var(--cyan-deep)",
        amber: "var(--amber)",
        magenta: "var(--magenta)",
        danger: "var(--danger)",
      },
      fontFamily: {
        display: ["Fraunces", "Times New Roman", "serif"],
        body: ['"Pretendard Variable"', "Pretendard", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "blueprint-grid":
          "linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

- [ ] **Step 3: Modify `frontend/src/app/globals.css`** to define the dark palette CSS variables

```css
@import url("https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400&family=JetBrains+Mono:wght@400;500;700&display=swap");
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable-dynamic-subset.min.css");

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #0b0e15;
  --bg-deep: #070912;
  --panel: #141826;
  --panel-line: #262d3e;
  --ink: #f1f3f8;
  --ink-mid: #b4bbcb;
  --ink-soft: #828a9d;
  --cyan: #7fe2ec;
  --cyan-deep: #2a8a93;
  --amber: #f3bd6f;
  --magenta: #e684a8;
  --danger: #f47878;
  --grid: rgba(127, 226, 236, 0.055);
  color-scheme: dark;
}

html, body { background: var(--bg); color: var(--ink); }
body {
  font-family: var(--font-body, "Pretendard Variable", system-ui, sans-serif);
  background-image: var(--blueprint, none);
}
::selection { background: var(--cyan); color: var(--bg-deep); }
```

- [ ] **Step 4: Modify `frontend/src/app/layout.tsx`** body className → `font-body bg-bg text-ink`

Replace the `<body>{children}</body>` line with:
```tsx
      <body className="font-body bg-bg text-ink antialiased">{children}</body>
```

- [ ] **Step 5: Create `frontend/components.json`**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "hooks": "@/hooks",
    "lib": "@/lib"
  }
}
```

- [ ] **Step 6: Create `frontend/src/lib/utils.ts`**

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 7: Create `frontend/src/components/ui/button.tsx`**

```tsx
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 font-mono text-xs uppercase tracking-[0.18em] " +
    "transition-all duration-200 focus-visible:outline-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-cyan text-bg-deep hover:bg-ink hover:shadow-[0_0_22px_rgba(127,226,236,0.4)]",
        ghost:
          "border border-panel-line text-ink hover:border-cyan hover:text-cyan " +
          "hover:shadow-[0_0_18px_rgba(127,226,236,0.18)]",
        danger: "border border-danger text-danger hover:bg-danger hover:text-bg-deep",
      },
      size: {
        default: "h-11 px-5",
        sm: "h-9 px-4 text-[10px]",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
```

- [ ] **Step 8: Create `frontend/src/components/ui/input.tsx`** (multi-line textarea variant — answers can be long)

```tsx
import * as React from "react";

import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full min-h-[140px] resize-y bg-panel/60 border border-panel-line",
      "px-4 py-3 text-[16.5px] leading-relaxed text-ink placeholder:text-ink-soft",
      "focus:outline-none focus:border-cyan focus:shadow-[0_0_0_1px_rgba(127,226,236,0.6)]",
      "transition-all duration-200",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
```

- [ ] **Step 9: Create `frontend/src/components/ui/badge.tsx`**

```tsx
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center font-mono text-[10px] uppercase tracking-[0.22em] " +
    "px-2 py-1 border",
  {
    variants: {
      tone: {
        cyan: "border-cyan text-cyan",
        amber: "border-amber text-amber",
        magenta: "border-magenta text-magenta",
        muted: "border-panel-line text-ink-soft",
      },
    },
    defaultVariants: { tone: "muted" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
```

- [ ] **Step 10: Create `frontend/src/components/ui/card.tsx`**

```tsx
import * as React from "react";

import { cn } from "@/lib/utils";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "border border-panel-line bg-gradient-to-b from-panel to-panel/40",
        "p-6 relative",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";
```

- [ ] **Step 11: Verify typecheck + lint + build**

```bash
cd frontend && pnpm typecheck && pnpm lint && pnpm build
```

Expected: all clean. `pnpm build` shows `/` and `/health` routes; `/study` will exist after Task 8.

- [ ] **Step 12: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/tailwind.config.ts frontend/components.json frontend/src/lib/utils.ts frontend/src/components/ frontend/src/app/globals.css frontend/src/app/layout.tsx
git commit -m "feat(frontend): add shadcn primitives + Architectural-Dark tokens"
git push
```

---

## Task 8: Frontend — API client extensions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Modify `frontend/src/lib/api.ts`** — add session typed wrappers

```typescript
/**
 * Backend API client. All HTTP calls to the backend go through this module
 * so that page components never hardcode URLs.
 */
const DEFAULT_BACKEND_URL = "http://localhost:8000";

function backendUrl(): string {
  return process.env.BACKEND_URL ?? DEFAULT_BACKEND_URL;
}

export type HealthPayload = {
  status: string;
  app: string;
  version: string;
};

export type RubricItem = {
  point: string;
  weight: number;
  keywords: string[];
};

export type SessionState = {
  session_id: string;
  user_id: string;
  status: "awaiting_answer" | "graded" | "completed";
  topic: string | null;
  difficulty: number | null;
  target_weakness: boolean | null;
  question: string | null;
  model_answer: string | null;
  rubric: RubricItem[];
  ref_chunk_ids: string[];
  user_answer: string | null;
  score: number | null;
  rationale: string | null;
  feedback: string | null;
  missing_points: string[];
  questions_done: number;
  target_count: number;
  created_at: string;
};

async function _json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return (await res.json()) as T;
}

export async function fetchHealth(): Promise<HealthPayload> {
  return _json<HealthPayload>(`${backendUrl()}/health`);
}

export async function createSession(opts?: {
  user_id?: string;
  target_count?: number;
  user_intent?: string;
}): Promise<SessionState> {
  return _json<SessionState>(`${backendUrl()}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts ?? {}),
  });
}

export async function submitAnswer(
  sessionId: string,
  user_answer: string,
): Promise<SessionState> {
  return _json<SessionState>(`${backendUrl()}/sessions/${sessionId}/answer`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user_answer }),
  });
}

export async function getSession(sessionId: string): Promise<SessionState> {
  return _json<SessionState>(`${backendUrl()}/sessions/${sessionId}`);
}
```

- [ ] **Step 2: Typecheck + lint**

```bash
cd frontend && pnpm typecheck && pnpm lint
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(frontend): add session API client wrappers (createSession, submitAnswer, getSession)"
git push
```

---

## Task 9: Frontend — Study page (server component + client view)

**Files:**
- Create: `frontend/src/app/study/page.tsx`
- Create: `frontend/src/app/study/session-view.tsx`
- Modify: `frontend/src/app/page.tsx` (link to /study)

- [ ] **Step 1: Create `frontend/src/app/study/page.tsx`** (server component — creates session)

```tsx
import { SessionView } from "./session-view";
import { createSession } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function StudyPage() {
  let initial = null;
  let error: string | null = null;
  try {
    initial = await createSession({ user_id: "local-user", target_count: 5 });
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  if (error) {
    return (
      <main className="mx-auto max-w-3xl p-10">
        <div className="border border-danger/40 bg-danger/5 p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-danger">
            session_start_failed
          </p>
          <pre className="mt-3 whitespace-pre-wrap text-sm text-ink-mid">{error}</pre>
        </div>
      </main>
    );
  }

  return <SessionView initial={initial!} />;
}
```

- [ ] **Step 2: Create `frontend/src/app/study/session-view.tsx`** (client component — answer + result)

```tsx
"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { submitAnswer, type SessionState } from "@/lib/api";

export function SessionView({ initial }: { initial: SessionState }) {
  const [state, setState] = useState<SessionState>(initial);
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isGraded = state.status === "graded" && state.score !== null;

  async function onSubmit() {
    if (!answer.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const next = await submitAnswer(state.session_id, answer);
      setState(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-10 py-12 bg-blueprint-grid bg-[length:36px_36px]">
      {/* masthead */}
      <header className="flex items-baseline justify-between border-y border-panel-line py-3 mb-10 font-mono text-[11px] uppercase tracking-[0.22em] text-ink-soft">
        <span>
          <span className="text-cyan">●</span> Live · StudyMate
        </span>
        <span>Session {state.session_id.slice(0, 8)} · {state.target_count} 문제</span>
      </header>

      {/* question */}
      <section className="mb-10">
        <Badge tone="cyan" className="mb-4">
          ● Question Generated · k=5 retrieval
        </Badge>
        <h1 className="font-display italic font-medium text-[clamp(72px,10vw,116px)] leading-[0.92] tracking-tight">
          {String(state.questions_done + 1).padStart(2, "0")}
          <span className="text-ink-soft mx-2">/</span>
          <span className="text-ink-soft">{String(state.target_count).padStart(2, "0")}</span>
        </h1>
        <p className="mt-4 text-[24px] leading-snug font-medium max-w-[36ch]">
          {state.question}
        </p>
        {state.topic && (
          <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-mid">
            Topic · {state.topic} · 난이도 {state.difficulty ?? "?"}
          </p>
        )}
      </section>

      {/* answer form (visible until graded) */}
      {!isGraded && (
        <section className="mb-10">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan mb-3">
            // answer.input
          </p>
          <Textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="여기에 답안을 작성하세요…"
            disabled={submitting}
          />
          <div className="mt-4 flex items-center gap-4">
            <Button onClick={onSubmit} disabled={submitting || !answer.trim()}>
              {submitting ? "채점 중…" : "채점 받기 →"}
            </Button>
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {answer.length} chars
            </span>
          </div>
          {error && (
            <p className="mt-4 font-mono text-[11px] text-danger tracking-[0.18em] uppercase">
              error · {error}
            </p>
          )}
        </section>
      )}

      {/* grading result */}
      {isGraded && (
        <>
          <section className="mb-10">
            <Badge tone="amber" className="mb-4">
              · Grading · Sonnet 4.6
            </Badge>
            <Card>
              <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-amber mb-3">
                Score · partial
              </p>
              <div className="flex items-baseline gap-3">
                <span className="font-display text-[100px] leading-[0.85] font-medium tracking-tight">
                  {state.score?.toFixed(2)}
                </span>
                <span className="font-display italic text-[22px] text-ink-soft">/1.00</span>
              </div>
              <ol className="mt-6 border-t border-panel-line">
                {state.rubric.map((r, i) => {
                  const matched = !state.missing_points.includes(r.keywords[0] ?? "");
                  return (
                    <li
                      key={i}
                      className="grid grid-cols-[40px_1fr_auto] items-center gap-4 py-3.5 border-b border-panel-line text-[16.5px]"
                    >
                      <span className="font-mono text-[11px] text-ink-soft tracking-[0.18em]">
                        R{String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="text-ink">{r.point}</span>
                      <Badge tone={matched ? "cyan" : "amber"}>
                        {matched ? "✓ match" : "✕ missing"}
                      </Badge>
                    </li>
                  );
                })}
              </ol>
            </Card>
          </section>

          {state.feedback && (
            <section className="mb-10">
              <Badge tone="magenta" className="mb-4">
                · Reinforcement note
              </Badge>
              <div className="border border-dashed border-magenta bg-magenta/5 p-6">
                <p className="text-[18px] leading-relaxed text-ink">{state.feedback}</p>
                {state.missing_points.length > 0 && (
                  <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.18em] text-amber">
                    Missing → {state.missing_points.join(" · ")}
                  </p>
                )}
            </div>
            </section>
          )}

          <div className="mt-12 flex gap-3 border-t border-panel-line pt-6">
            <Button onClick={() => location.reload()}>다음 문제 →</Button>
            <Button variant="ghost" onClick={() => location.reload()}>
              재시도
            </Button>
          </div>
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Modify `frontend/src/app/page.tsx`** to link to /study

Replace its content with:

```tsx
import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-10 py-20">
      <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan mb-6">
        StudyMate — vol.01 iss.04
      </p>
      <h1 className="font-display italic text-[clamp(64px,9vw,108px)] leading-[0.95] tracking-tight">
        Multi-agent<br />learning, fenced
      </h1>
      <p className="mt-6 text-[19px] text-ink-mid max-w-[42ch] leading-relaxed">
        멀티 에이전트 기반 학습 시스템. 정보처리기사 실기 도메인. LangGraph
        + RAG로 학습자 답안을 의미 기반으로 채점하고 근거 청크와 함께
        보강 가이드를 제공합니다.
      </p>
      <div className="mt-10 flex gap-3">
        <Button asChild>
          <Link href="/study">학습 시작 →</Link>
        </Button>
        <Button variant="ghost" asChild>
          <Link href="/health">시스템 상태</Link>
        </Button>
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Typecheck + lint + build**

```bash
cd frontend && pnpm typecheck && pnpm lint && pnpm build
```

Expected: `/`, `/health`, `/study` routes all in the build output.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/study/ frontend/src/app/page.tsx
git commit -m "feat(frontend): add /study page with Architectural-Dark session view"
git push
```

---

## Task 10: End-to-end manual verification

This task confirms the full demo works: open browser, see question, submit answer, see graded result. Requires real `ANTHROPIC_API_KEY` and seeded RAG (Plan 2 Task 12).

- [ ] **Step 1: Confirm prerequisites**

```bash
# .env has ANTHROPIC_API_KEY set
grep ANTHROPIC_API_KEY .env | grep -v "^#"

# ChromaDB has chunks
cd backend && uv run python -m scripts.seed status
```

Expected: API key line present (not blank), seed-status shows ≥ 1 chunk.

- [ ] **Step 2: Start backend (terminal A)**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Wait for `Uvicorn running on http://0.0.0.0:8000`.

- [ ] **Step 3: Start frontend (terminal B)**

```bash
cd frontend
pnpm dev
```

Wait for `✓ Ready in N ms`.

- [ ] **Step 4: Open browser at http://localhost:3000/study**

Expected sequence:
1. Page loads with masthead + question number + Korean question text.
2. Textarea is enabled, "채점 받기 →" button visible.
3. Type a partial answer (e.g., "정규화는 데이터 중복을 줄입니다.") and click submit.
4. After 5-15 seconds, page updates with score card (Fraunces italic large number), rubric list with match/missing badges, magenta reinforcement note.

- [ ] **Step 5: Programmatic smoke checks**

```bash
# In a third terminal
curl --fail http://localhost:8000/health
curl --fail -X POST -H "content-type: application/json" -d '{}' http://localhost:8000/sessions | python -m json.tool
```

- [ ] **Step 6: Tear down**

`Ctrl-C` in both terminals.

- [ ] **Step 7: dev-log + commit any lockfile changes**

```bash
git status
git add backend/uv.lock frontend/pnpm-lock.yaml 2>/dev/null || true
git diff --cached --quiet || git commit -m "chore: lock files after Plan 4 verification"
git push
```

---

## Acceptance Criteria

Plan 4 is complete when **all** of the following hold:

1. `cd backend && uv run pytest -v` passes 100% — Plans 1-3 tests + ~13 new api tests = ~90 total.
2. `cd backend && uv run lint-imports --config .importlinter` reports `5 kept, 0 broken`.
3. `cd backend && uv run mypy app tests` passes.
4. `cd frontend && pnpm typecheck && pnpm lint && pnpm build` all clean. Build output shows `/`, `/health`, `/study` routes.
5. `POST /sessions` returns a question payload with `status=awaiting_answer`.
6. `POST /sessions/{id}/answer` returns a graded snapshot with `status=graded` and a numeric `score`.
7. Browser at <http://localhost:3000/study> renders the Architectural-Dark themed session view, submits an answer, and shows the score + rubric + feedback.

---

## What's Next

Plan 5: **Learning Records & Dashboard**. SQLAlchemy 2.0 models (User, StudySession, QuestionInstance, Answer), Alembic migration, `learning.analytics.compute_weakness()` for Top-3 약점 주제, `PersistAdapter` wired to write through every Persist node call, `/dashboard` page showing topic-level stats. The agent graph's `weakness_provider` callback (currently `lambda _uid: []`) will be wired to the real analytics function so the Coordinator starts steering toward weak topics.
