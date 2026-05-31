# LangGraph Workflow & 3 Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working LangGraph state machine with 3 agents (`Coordinator`, `QuestionGenerator`, `Grader`) plus a deterministic `Persist` node, plus an `AWAIT_ANSWER` interrupt for human-in-the-loop. The whole graph is reachable through `app.agents.run_session(user_id, ...)` and resumable via `app.agents.resume_session(thread_id, user_answer)`. Verified by integration test: full Coordinator → QuestionGenerator → AWAIT (interrupt) → resume(answer) → Grader → Persist with mocked Anthropic + mocked Retriever, plus an end-to-end smoke with real Anthropic (gated on `ANTHROPIC_API_KEY`).

**Architecture:** `app.agents` is the only module that imports `langgraph` or `langchain-core`. Each node is a pure function taking `SessionState` (TypedDict) and returning a dict update — no node imports another node. The graph topology and checkpointer wiring live in `app.agents.graph`; node implementations under `app.agents.nodes/`. `interrupt_before=["await_answer"]` pauses the graph after `QuestionGenerator` so the API layer (Plan 4) can collect the learner's answer and call `resume_session()`. The `SqliteSaver` checkpointer reuses the same SQLite file the `learning` domain will use in Plan 5 (separate table — no schema collision).

**Tech Stack:** Python 3.12 / LangGraph 0.2 / langchain-core / Anthropic SDK (Sonnet 4.6 + Haiku 4.5) / Pydantic v2 / pytest + pytest-mock / SqliteSaver

**This plan is plan 3 of 7 in the StudyMate AI V1 series.** See `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` §4 (LangGraph Workflow) and §13 마일스톤.

**Deferred from spec:**
- **Real DB persistence of session records** — `Persist` node updates `SessionState` only. Real SQLAlchemy writes to `StudySession`/`QuestionInstance`/`Answer` tables are Plan 5. This plan leaves a `PersistAdapter` callback hook so Plan 5 can wire it without changing the graph.
- **Real約점 분석** — Plan 5's `learning.analytics.compute_weakness()` is what Coordinator will eventually call. In this plan Coordinator gets a `WeaknessProvider` callback (default no-op returning empty list) so Plan 5 can drop the real implementation in.
- **LangSmith tracing** — wiring is `os.environ["LANGSMITH_API_KEY"]` away; not exercised in V1.

---

## File Structure

```
studymate-ai/
├─ backend/
│  ├─ pyproject.toml                       # MODIFY: add langgraph + langchain-core
│  └─ app/
│     ├─ agents/
│     │  ├─ __init__.py                    # re-export: run_session, resume_session, SessionState
│     │  ├─ state.py                       # TypedDict SessionState + RubricItem, QuestionPayload, GradingResult
│     │  ├─ models.py                      # Pydantic request/response shapes for LLM calls
│     │  ├─ prompts.py                     # All system + user prompt templates (single source)
│     │  ├─ graph.py                       # build_graph(), run_session, resume_session
│     │  ├─ checkpointer.py                # SqliteSaver factory (uses settings.studymate_db)
│     │  └─ nodes/
│     │     ├─ __init__.py
│     │     ├─ coordinator.py              # decides (topic, difficulty, target_weakness)
│     │     ├─ question_generator.py       # rag.retrieve + Sonnet → question/model_answer/rubric
│     │     ├─ grader.py                   # Sonnet → score/rationale/feedback/missing_points
│     │     └─ persist.py                  # deterministic update of SessionState; calls PersistAdapter
│     ├─ core/
│     │  └─ settings.py                    # MODIFY: add studymate_db path
│     └─ rag/  (unchanged — read-only consumer of app.rag.Retriever)
└─ backend/tests/agents/
   ├─ __init__.py
   ├─ conftest.py                          # fake_anthropic, fake_retriever, frozen_clock
   ├─ test_state.py
   ├─ test_coordinator.py
   ├─ test_question_generator.py
   ├─ test_grader.py
   ├─ test_persist.py
   ├─ test_graph_topology.py               # structural — verifies edges/interrupts
   ├─ test_run_session_with_mocks.py       # integration with mocked clients
   └─ fixtures/
      └─ rubrics_sample.json               # 3 hand-built rubric items for tests
```

### File-by-file responsibility

- **`app/agents/__init__.py`** — Single public surface. Re-exports `run_session`, `resume_session`, `SessionState`. `Plan 4` (API) and Plan 5 (Learning Records) call only these.
- **`app/agents/state.py`** — `SessionState` TypedDict (the graph's shared state) + Pydantic models for nested structures (`RubricItem`, `QuestionPayload`, `GradingResult`).
- **`app/agents/models.py`** — Pydantic shapes for LLM structured output. Distinct from `state.py` because LLM outputs are validated at the boundary, then unpacked into `SessionState`.
- **`app/agents/prompts.py`** — All prompt strings. Decoupled from code so prompts can be tuned without touching node logic; also enables future prompt-versioning.
- **`app/agents/graph.py`** — `build_graph(checkpointer, retriever, anthropic_client, weakness_provider, persist_adapter)` factory. Returns a compiled LangGraph. `run_session`/`resume_session` wrap invoke/resume.
- **`app/agents/checkpointer.py`** — `make_checkpointer(db_path)` → SqliteSaver. Single import point so Plan 5 can share the same DB file.
- **`app/agents/nodes/*.py`** — Pure node functions. Each takes `SessionState` and returns `dict[str, Any]` (partial state update). Side effects (LLM calls, retrieval) flow through injected dependencies, never imported globally.
- **`tests/agents/conftest.py`** — Common fakes: `fake_anthropic` returning canned JSON, `fake_retriever` returning fixed chunks, `frozen_clock` for deterministic timestamps.

---

## Task 1: Dependencies + agents module skeleton + state models

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/settings.py`
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/agents/state.py`
- Create: `backend/app/agents/models.py`
- Create: `backend/app/agents/nodes/__init__.py`
- Create: `backend/tests/agents/__init__.py`
- Create: `backend/tests/agents/test_state.py`

- [ ] **Step 1: Add LangGraph deps to `backend/pyproject.toml`**

Replace the `[project] dependencies` block with (adds 2 new entries):

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
  "langgraph>=0.2.50",
  "langchain-core>=0.3.20",
]
```

Add a new mypy override under existing `[[tool.mypy.overrides]]` blocks:

```toml
[[tool.mypy.overrides]]
module = "langgraph.*"
ignore_missing_imports = true
follow_imports = "skip"

[[tool.mypy.overrides]]
module = "langchain_core.*"
ignore_missing_imports = true
follow_imports = "skip"
```

- [ ] **Step 2: Run `uv sync`**

```bash
cd backend && uv sync
```

Expected: ~10-20 new packages resolved (langgraph + langchain-core + transitive). Few hundred MB.

- [ ] **Step 3: Modify `backend/app/core/settings.py` — add `studymate_db` path**

Find the `# ── RAG ─` block and add after the existing RAG settings (before the `@lru_cache` decorator):

```python
    # ── Agents ─────────────────────────────────────────────
    studymate_db: Path = Field(default=Path("./data/studymate.db"))
    anthropic_model_sonnet: str = Field(default="claude-sonnet-4-6")
    anthropic_model_haiku: str = Field(default="claude-haiku-4-5")
```

(Keep all existing fields.)

- [ ] **Step 4: Create `backend/app/agents/__init__.py`** (placeholder; re-exports added in Task 8)

```python
"""LangGraph workflow + 3 agents.

This is the single public surface for orchestrated learning sessions.
Outside callers should import only what is re-exported from this module.
"""
```

- [ ] **Step 5: Create `backend/app/agents/nodes/__init__.py`** (empty)

```python
```

- [ ] **Step 6: Create `backend/app/agents/state.py`**

```python
"""Shared graph state and nested value objects."""
from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class RubricItem(BaseModel):
    """One scored criterion within a grading rubric."""

    point: str
    weight: float = Field(ge=0.0, le=1.0)
    keywords: list[str] = Field(default_factory=list)


class QuestionPayload(BaseModel):
    """The QuestionGenerator's structured output."""

    question: str
    model_answer: str
    rubric: list[RubricItem]


class GradingResult(BaseModel):
    """The Grader's structured output."""

    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    feedback: str
    missing_points: list[str] = Field(default_factory=list)


class SessionState(TypedDict, total=False):
    """LangGraph shared state.

    session_id is used directly as the LangGraph checkpointer thread_id
    (1:1 mapping; see spec §4.2).
    """

    user_id: str
    session_id: str

    # Coordinator output
    topic: str
    difficulty: int
    target_weakness: bool

    # QuestionGenerator output
    question: str
    model_answer: str
    rubric: list[dict]                 # serialized RubricItem (LangGraph state must be JSON-friendly)
    ref_chunk_ids: list[str]

    # learner input (set by API layer between QGen and Grader)
    user_answer: str

    # Grader output
    score: float
    rationale: str
    feedback: str
    missing_points: list[str]

    # loop control
    questions_done: int
    target_count: int
```

- [ ] **Step 7: Create `backend/app/agents/models.py`**

```python
"""Pydantic shapes used at LLM I/O boundaries.

These are distinct from `state.py` because LLM outputs need strict
schema validation; SessionState (TypedDict) is more permissive to keep
LangGraph happy.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CoordinatorDecision(BaseModel):
    """Haiku's output for the Coordinator node."""

    topic: str
    difficulty: int = Field(ge=1, le=3)
    target_weakness: bool
    reason: str = ""  # short justification, useful for logs


class QuestionGenerationRequest(BaseModel):
    topic: str
    difficulty: int = Field(ge=1, le=3)
    context_chunks: list[str]


class GradingRequest(BaseModel):
    question: str
    model_answer: str
    rubric: list[dict]
    user_answer: str
```

- [ ] **Step 8: Create `backend/tests/agents/__init__.py`** (empty)

```python
```

- [ ] **Step 9: Write `backend/tests/agents/test_state.py`**

```python
"""Tests for app.agents.state."""
import pytest
from pydantic import ValidationError

from app.agents.state import GradingResult, QuestionPayload, RubricItem, SessionState


def test_rubric_item_rejects_out_of_range_weight():
    with pytest.raises(ValidationError):
        RubricItem(point="x", weight=1.5)


def test_rubric_item_defaults_empty_keywords():
    item = RubricItem(point="정규화 정의", weight=0.3)
    assert item.keywords == []


def test_question_payload_round_trips():
    payload = QuestionPayload(
        question="정규화의 목적을 서술하시오.",
        model_answer="이상현상 방지.",
        rubric=[RubricItem(point="목적 명시", weight=0.5, keywords=["이상현상"])],
    )
    restored = QuestionPayload.model_validate(payload.model_dump())
    assert restored == payload


def test_grading_result_rejects_score_above_one():
    with pytest.raises(ValidationError):
        GradingResult(score=1.5, rationale="ok", feedback="")


def test_session_state_is_partial_typed_dict():
    # SessionState uses total=False — empty dict is valid
    state: SessionState = {}
    state["user_id"] = "u1"
    state["topic"] = "정규화"
    assert state["topic"] == "정규화"
```

- [ ] **Step 10: Run pytest, verify pass**

```bash
cd backend && uv run pytest tests/agents/test_state.py -v
```

Expected: 5 passed.

- [ ] **Step 11: Lint + types**

```bash
cd backend && uv run ruff check app/agents tests/agents && uv run ruff format --check app/agents tests/agents && uv run mypy app/agents tests/agents
```

Apply `ruff format` if needed. Apply PLR2004 named locals if any literal-int comparisons fire.

- [ ] **Step 12: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/agents/ backend/app/core/settings.py backend/tests/agents/
git commit -m "feat(agents): add LangGraph deps and state/models skeleton"
```

---

## Task 2: Coordinator node (Haiku, deterministic on top of LLM)

**Files:**
- Create: `backend/app/agents/prompts.py` (start file; later tasks append)
- Create: `backend/app/agents/nodes/coordinator.py`
- Create: `backend/tests/agents/conftest.py`
- Create: `backend/tests/agents/test_coordinator.py`

- [ ] **Step 1: Create `backend/app/agents/prompts.py` (initial)**

```python
"""Single source for all agent prompt templates.

Each template is a callable that returns a fully-formatted user message
string. System prompts are kept separate and short — model-tuning
should change templates here, not node code.
"""
from __future__ import annotations


COORDINATOR_SYSTEM = (
    "당신은 학습 코디네이터입니다. 사용자의 의도와 약점 목록을 보고 "
    "다음으로 풀 문제의 주제와 난이도를 결정합니다. "
    "응답은 반드시 JSON만 출력하세요."
)


def coordinator_prompt(
    user_intent: str, weak_topics: list[str], all_topics: list[str]
) -> str:
    weak = ", ".join(weak_topics) if weak_topics else "(없음)"
    topics = ", ".join(all_topics)
    return f"""사용자 의도: "{user_intent}"
사용 가능한 주제: {topics}
사용자의 최근 약점 Top3: {weak}

다음을 JSON으로만 응답하시오 (다른 텍스트 금지):
{{
  "topic": "<주제명>",
  "difficulty": <1|2|3>,
  "target_weakness": <true if 약점 보강 목적이면, else false>,
  "reason": "<한 문장 근거>"
}}"""
```

- [ ] **Step 2: Create `backend/tests/agents/conftest.py`**

```python
"""Shared agent test fixtures."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def make_anthropic_client():
    """Returns a factory that builds a fake Anthropic client with canned JSON."""

    def factory(payload: dict[str, Any]) -> MagicMock:
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps(payload, ensure_ascii=False))]
        client.messages.create.return_value = response
        return client

    return factory


@pytest.fixture
def topics_default() -> list[str]:
    return ["정규화", "SQL 응용", "네트워크"]
```

- [ ] **Step 3: Write the failing test in `backend/tests/agents/test_coordinator.py`**

```python
"""Tests for app.agents.nodes.coordinator."""
from app.agents.nodes.coordinator import coordinator_node


def test_coordinator_returns_topic_difficulty_target(make_anthropic_client, topics_default):
    client = make_anthropic_client(
        {"topic": "정규화", "difficulty": 2, "target_weakness": True, "reason": "ok"}
    )
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=["정규화"],
        user_intent="약점 보강 학습",
    )
    assert result["topic"] == "정규화"
    assert result["difficulty"] == 2
    assert result["target_weakness"] is True


def test_coordinator_falls_back_when_topic_not_in_allowlist(
    make_anthropic_client, topics_default
):
    client = make_anthropic_client(
        {"topic": "존재하지않는주제", "difficulty": 2, "target_weakness": False, "reason": "?"}
    )
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=[],
        user_intent="자유 학습",
    )
    # falls back to first available topic when LLM returns an unknown one
    assert result["topic"] in topics_default


def test_coordinator_uses_weak_topic_when_target_weakness_true_and_no_topic_hint(
    make_anthropic_client, topics_default
):
    # LLM somehow returns target_weakness=true but a non-weak topic
    client = make_anthropic_client(
        {"topic": "네트워크", "difficulty": 1, "target_weakness": True, "reason": ""}
    )
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=["정규화", "SQL 응용"],
        user_intent="약점 보강",
    )
    # when target_weakness, prefer the LLM's choice if it's in weak_topics,
    # otherwise replace with the first weak topic
    assert result["topic"] == "정규화"
    assert result["target_weakness"] is True


def test_coordinator_handles_malformed_json(make_anthropic_client, topics_default):
    client = make_anthropic_client({})  # we'll override the text below
    client.messages.create.return_value.content = [type("R", (), {"text": "not json"})()]
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=[],
        user_intent="자유 학습",
    )
    # fallback to the first topic, difficulty=1, target_weakness=False
    assert result["topic"] == topics_default[0]
    assert result["difficulty"] == 1
    assert result["target_weakness"] is False
```

- [ ] **Step 4: Run, must fail with ModuleNotFoundError on coordinator_node.**

- [ ] **Step 5: Implement `backend/app/agents/nodes/coordinator.py`**

```python
"""Coordinator node — decides (topic, difficulty, target_weakness)."""
from __future__ import annotations

import json
from typing import Any

from app.agents.models import CoordinatorDecision
from app.agents.prompts import COORDINATOR_SYSTEM, coordinator_prompt
from app.agents.state import SessionState


def _call_haiku(
    client: Any, model: str, system: str, user_message: str
) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=200,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return str(resp.content[0].text).strip()


def _parse_decision(
    raw: str, topics: list[str], weak_topics: list[str]
) -> CoordinatorDecision:
    try:
        data = json.loads(raw)
        decision = CoordinatorDecision.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return CoordinatorDecision(
            topic=topics[0], difficulty=1, target_weakness=False, reason="fallback: parse"
        )

    # enforce topic allowlist
    if decision.topic not in topics:
        replacement = weak_topics[0] if weak_topics else topics[0]
        decision = decision.model_copy(update={"topic": replacement, "reason": "fallback: allowlist"})

    # if target_weakness=True but topic isn't in weak_topics, replace with a weak topic
    if decision.target_weakness and weak_topics and decision.topic not in weak_topics:
        decision = decision.model_copy(update={"topic": weak_topics[0], "reason": "fallback: prefer weak"})

    return decision


def coordinator_node(
    state: SessionState,
    *,
    client: Any,
    model: str,
    topics: list[str],
    weak_topics: list[str],
    user_intent: str,
) -> dict[str, Any]:
    """LangGraph node: decide next (topic, difficulty, target_weakness)."""
    prompt = coordinator_prompt(user_intent, weak_topics, topics)
    raw = _call_haiku(client, model, COORDINATOR_SYSTEM, prompt)
    decision = _parse_decision(raw, topics, weak_topics)
    return {
        "topic": decision.topic,
        "difficulty": decision.difficulty,
        "target_weakness": decision.target_weakness,
    }
```

- [ ] **Step 6: Run, confirm pass**

```bash
cd backend && uv run pytest tests/agents/test_coordinator.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Lint + types**

Same gates as Task 1. Apply PLR2004 named locals if needed (e.g., `assert result["difficulty"] == 2` → `expected_difficulty = 2`).

- [ ] **Step 8: Commit**

```bash
git add backend/app/agents/prompts.py backend/app/agents/nodes/coordinator.py backend/tests/agents/conftest.py backend/tests/agents/test_coordinator.py
git commit -m "feat(agents): add Coordinator node with topic-allowlist fallback"
```

---

## Task 3: QuestionGenerator node (Sonnet, rubric co-generated)

**Files:**
- Modify: `backend/app/agents/prompts.py` (append QGen prompt)
- Create: `backend/app/agents/nodes/question_generator.py`
- Create: `backend/tests/agents/test_question_generator.py`

- [ ] **Step 1: Append QGen prompt to `backend/app/agents/prompts.py`**

Add at the bottom of the file:

```python
QGEN_SYSTEM = (
    "당신은 한국 정보처리기사 실기 시험 출제자입니다. 주어진 학습 자료를 바탕으로 "
    "서술형 문제 한 개와 모범답안, 그리고 채점 루브릭(3~5개 항목)을 동시에 생성합니다. "
    "응답은 반드시 JSON만 출력하세요."
)


def qgen_prompt(topic: str, difficulty: int, context_chunks: list[str]) -> str:
    context = "\n\n".join(f"[자료 {i + 1}]\n{c}" for i, c in enumerate(context_chunks))
    return f"""주제: {topic}
난이도: {difficulty} (1=쉬움, 2=보통, 3=어려움)

참고 자료:
{context}

다음 JSON 형식으로만 응답하시오:
{{
  "question": "<서술형 문제 한 문장>",
  "model_answer": "<모범답안 3~5문장>",
  "rubric": [
    {{"point": "<채점 기준>", "weight": <0~1>, "keywords": ["<키워드>", ...]}}
  ]
}}

루브릭 가중치 합은 1.0이 되어야 합니다."""
```

- [ ] **Step 2: Write the failing test in `backend/tests/agents/test_question_generator.py`**

```python
"""Tests for app.agents.nodes.question_generator."""
from unittest.mock import MagicMock

from app.agents.nodes.question_generator import question_generator_node


def _mock_retriever(chunk_ids: list[str], texts: list[str]):
    retriever = MagicMock()

    class _C:
        def __init__(self, cid: str, text: str):
            self.id = cid
            self.text = text

    retriever.retrieve.return_value = [_C(i, t) for i, t in zip(chunk_ids, texts, strict=True)]
    return retriever


def test_qgen_produces_question_and_rubric(make_anthropic_client):
    client = make_anthropic_client(
        {
            "question": "정규화의 목적을 서술하시오.",
            "model_answer": "데이터 중복 감소와 이상현상 방지.",
            "rubric": [
                {"point": "목적 명시", "weight": 0.6, "keywords": ["이상현상"]},
                {"point": "예시 제시", "weight": 0.4, "keywords": []},
            ],
        }
    )
    retriever = _mock_retriever(["c1", "c2"], ["1NF는 원자값", "2NF는 부분 함수 종속 제거"])
    state = {"user_id": "u1", "session_id": "s1", "topic": "정규화", "difficulty": 2}
    result = question_generator_node(
        state, client=client, model="claude-sonnet-4-6", retriever=retriever
    )
    assert result["question"] == "정규화의 목적을 서술하시오."
    assert result["model_answer"].startswith("데이터")
    assert len(result["rubric"]) == 2
    assert result["ref_chunk_ids"] == ["c1", "c2"]


def test_qgen_calls_retriever_with_topic(make_anthropic_client):
    client = make_anthropic_client(
        {
            "question": "q",
            "model_answer": "a",
            "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
        }
    )
    retriever = _mock_retriever(["c1"], ["chunk text"])
    state = {"user_id": "u1", "session_id": "s1", "topic": "SQL 응용", "difficulty": 1}
    question_generator_node(
        state, client=client, model="claude-sonnet-4-6", retriever=retriever
    )
    retriever.retrieve.assert_called_once()
    call_args = retriever.retrieve.call_args
    # the query must mention the topic
    assert "SQL 응용" in str(call_args)


def test_qgen_raises_on_invalid_llm_output(make_anthropic_client):
    client = make_anthropic_client({"question": "q"})  # missing model_answer and rubric
    retriever = _mock_retriever(["c1"], ["x"])
    state = {"user_id": "u1", "session_id": "s1", "topic": "정규화", "difficulty": 1}
    # tasks downstream (Grader) need a valid rubric — fail loudly
    import pytest
    with pytest.raises(ValueError, match="invalid"):
        question_generator_node(
            state, client=client, model="claude-sonnet-4-6", retriever=retriever
        )


def test_qgen_works_with_no_retriever_results(make_anthropic_client):
    """Retriever returning empty list should still work — Sonnet handles bare-topic generation."""
    client = make_anthropic_client(
        {
            "question": "정규화는 무엇인가?",
            "model_answer": "데이터 모델링 기법.",
            "rubric": [{"point": "정의", "weight": 1.0, "keywords": []}],
        }
    )
    retriever = MagicMock()
    retriever.retrieve.return_value = []
    state = {"user_id": "u1", "session_id": "s1", "topic": "정규화", "difficulty": 1}
    result = question_generator_node(
        state, client=client, model="claude-sonnet-4-6", retriever=retriever
    )
    assert result["question"]
    assert result["ref_chunk_ids"] == []
```

- [ ] **Step 3: Run, must fail.**

- [ ] **Step 4: Implement `backend/app/agents/nodes/question_generator.py`**

```python
"""QuestionGenerator node — RAG context + Sonnet → question + model_answer + rubric."""
from __future__ import annotations

import json
from typing import Any

from app.agents.models import QuestionGenerationRequest
from app.agents.prompts import QGEN_SYSTEM, qgen_prompt
from app.agents.state import QuestionPayload, SessionState


_RETRIEVAL_K = 5


def _call_sonnet(
    client: Any, model: str, system: str, user_message: str
) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return str(resp.content[0].text).strip()


def _parse_question(raw: str) -> QuestionPayload:
    try:
        data = json.loads(raw)
        return QuestionPayload.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        msg = f"QuestionGenerator returned invalid payload: {e}"
        raise ValueError(msg) from e


def question_generator_node(
    state: SessionState,
    *,
    client: Any,
    model: str,
    retriever: Any,
) -> dict[str, Any]:
    """LangGraph node: produce a question + model answer + rubric for the topic."""
    topic = state.get("topic", "")
    difficulty = state.get("difficulty", 1)

    # Build retrieval query from topic and difficulty
    query = f"{topic} 난이도 {difficulty}"
    chunks = retriever.retrieve(query, k=_RETRIEVAL_K)
    chunk_texts = [c.text for c in chunks]
    chunk_ids = [c.id for c in chunks]

    # Validate the request shape (catches bad state early in dev)
    QuestionGenerationRequest(topic=topic, difficulty=difficulty, context_chunks=chunk_texts)

    raw = _call_sonnet(client, model, QGEN_SYSTEM, qgen_prompt(topic, difficulty, chunk_texts))
    payload = _parse_question(raw)

    return {
        "question": payload.question,
        "model_answer": payload.model_answer,
        "rubric": [item.model_dump() for item in payload.rubric],
        "ref_chunk_ids": chunk_ids,
    }
```

- [ ] **Step 5: Run, confirm pass (4 tests)**

- [ ] **Step 6: Lint + types**

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/prompts.py backend/app/agents/nodes/question_generator.py backend/tests/agents/test_question_generator.py
git commit -m "feat(agents): add QuestionGenerator node with co-generated rubric"
```

---

## Task 4: Grader node (Sonnet, strict JSON)

**Files:**
- Modify: `backend/app/agents/prompts.py` (append Grader prompt)
- Create: `backend/app/agents/nodes/grader.py`
- Create: `backend/tests/agents/test_grader.py`

- [ ] **Step 1: Append Grader prompt to `backend/app/agents/prompts.py`**

```python
GRADER_SYSTEM = (
    "당신은 한국 정보처리기사 실기 시험 채점자입니다. "
    "주어진 루브릭에 따라 학습자 답안을 항목별로 채점하고, "
    "각 항목의 일치 여부와 부분점수를 합산해 최종 점수(0~1)를 산정합니다. "
    "응답은 반드시 JSON만 출력하세요."
)


def grader_prompt(
    question: str, model_answer: str, rubric: list[dict], user_answer: str
) -> str:
    rubric_str = "\n".join(
        f"{i + 1}. {r['point']} (가중치 {r['weight']}, 키워드 {r.get('keywords', [])})"
        for i, r in enumerate(rubric)
    )
    return f"""문제: {question}

모범답안: {model_answer}

루브릭:
{rubric_str}

학습자 답안:
\"\"\"
{user_answer}
\"\"\"

JSON으로만 응답하시오:
{{
  "score": <0.0~1.0>,
  "rationale": "<루브릭 항목별 채점 근거 한 문단>",
  "feedback": "<학습자에게 줄 보강 가이드 한 문단>",
  "missing_points": ["<빠진 키워드 또는 핵심 개념>", ...]
}}"""
```

- [ ] **Step 2: Write the failing test in `backend/tests/agents/test_grader.py`**

```python
"""Tests for app.agents.nodes.grader."""
from app.agents.nodes.grader import grader_node


def test_grader_produces_score_rationale_feedback(make_anthropic_client):
    client = make_anthropic_client(
        {
            "score": 0.83,
            "rationale": "1NF, 2NF, 3NF 조건 모두 정확하나 목적 누락.",
            "feedback": "정규화의 목적을 '이상현상 방지'로 보강하세요.",
            "missing_points": ["이상현상"],
        }
    )
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "question": "정규화의 목적을 서술하시오.",
        "model_answer": "이상현상 방지.",
        "rubric": [{"point": "목적", "weight": 0.5, "keywords": ["이상현상"]}],
        "user_answer": "정규화는 데이터 중복을 줄이는 것입니다.",
    }
    result = grader_node(state, client=client, model="claude-sonnet-4-6")
    assert result["score"] == 0.83
    assert "정규화" in result["rationale"]
    assert result["missing_points"] == ["이상현상"]


def test_grader_retries_once_on_malformed_then_falls_back(make_anthropic_client):
    client = make_anthropic_client({})
    # first call returns garbage, second call returns valid JSON
    bad = type("R", (), {"text": "not json"})()
    good_payload = {
        "score": 0.7,
        "rationale": "ok",
        "feedback": "ok",
        "missing_points": [],
    }
    good = type("R", (), {"text": '{"score": 0.7, "rationale": "ok", "feedback": "ok", "missing_points": []}'})()
    client.messages.create.side_effect = [
        type("M", (), {"content": [bad]})(),
        type("M", (), {"content": [good]})(),
    ]
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "question": "q",
        "model_answer": "a",
        "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
        "user_answer": "x",
    }
    result = grader_node(state, client=client, model="claude-sonnet-4-6")
    assert result["score"] == 0.7
    assert client.messages.create.call_count == 2  # original + 1 retry


def test_grader_falls_back_to_half_score_on_double_failure(make_anthropic_client):
    client = make_anthropic_client({})
    bad1 = type("R", (), {"text": "not json"})()
    bad2 = type("R", (), {"text": "still not json"})()
    client.messages.create.side_effect = [
        type("M", (), {"content": [bad1]})(),
        type("M", (), {"content": [bad2]})(),
    ]
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "question": "q",
        "model_answer": "a",
        "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
        "user_answer": "x",
    }
    result = grader_node(state, client=client, model="claude-sonnet-4-6")
    # spec §8 fallback: 0.5 + error flag
    assert result["score"] == 0.5
    assert "parse_failed" in result.get("feedback", "")
```

- [ ] **Step 3: Run, must fail.**

- [ ] **Step 4: Implement `backend/app/agents/nodes/grader.py`**

```python
"""Grader node — strict JSON, 1 retry, half-score fallback."""
from __future__ import annotations

import json
from typing import Any

from app.agents.models import GradingRequest
from app.agents.prompts import GRADER_SYSTEM, grader_prompt
from app.agents.state import GradingResult, SessionState


_RETRY_LIMIT = 1
_FALLBACK_SCORE = 0.5


def _call_sonnet(
    client: Any, model: str, system: str, user_message: str
) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return str(resp.content[0].text).strip()


def _try_parse(raw: str) -> GradingResult | None:
    try:
        data = json.loads(raw)
        return GradingResult.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None


def grader_node(
    state: SessionState,
    *,
    client: Any,
    model: str,
) -> dict[str, Any]:
    """LangGraph node: grade the user's answer per the rubric."""
    request = GradingRequest(
        question=state.get("question", ""),
        model_answer=state.get("model_answer", ""),
        rubric=list(state.get("rubric", [])),
        user_answer=state.get("user_answer", ""),
    )
    prompt = grader_prompt(
        request.question, request.model_answer, request.rubric, request.user_answer
    )

    for attempt in range(_RETRY_LIMIT + 1):
        raw = _call_sonnet(client, model, GRADER_SYSTEM, prompt)
        parsed = _try_parse(raw)
        if parsed is not None:
            return {
                "score": parsed.score,
                "rationale": parsed.rationale,
                "feedback": parsed.feedback,
                "missing_points": parsed.missing_points,
            }

    # Both attempts failed — record a fallback so the session doesn't crash.
    return {
        "score": _FALLBACK_SCORE,
        "rationale": "grader_parse_failed",
        "feedback": "parse_failed — 채점 결과를 정상적으로 파싱하지 못했습니다. 재시도해 주세요.",
        "missing_points": [],
    }
```

- [ ] **Step 5: Run, confirm pass (3 tests)**

- [ ] **Step 6: Lint + types**

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/prompts.py backend/app/agents/nodes/grader.py backend/tests/agents/test_grader.py
git commit -m "feat(agents): add Grader node with 1-retry strict-JSON parsing"
```

---

## Task 5: Persist node (deterministic, no LLM, adapter hook for Plan 5)

**Files:**
- Create: `backend/app/agents/nodes/persist.py`
- Create: `backend/tests/agents/test_persist.py`

- [ ] **Step 1: Write the failing test in `backend/tests/agents/test_persist.py`**

```python
"""Tests for app.agents.nodes.persist — deterministic, no LLM."""
from unittest.mock import MagicMock

from app.agents.nodes.persist import persist_node


def test_persist_increments_questions_done():
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "questions_done": 0,
        "target_count": 5,
        "score": 0.8,
        "topic": "정규화",
    }
    result = persist_node(state, adapter=None)
    assert result["questions_done"] == 1


def test_persist_calls_adapter_when_provided():
    adapter = MagicMock()
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "questions_done": 2,
        "target_count": 5,
        "score": 0.4,
        "topic": "네트워크",
        "question": "q",
        "user_answer": "a",
        "rationale": "r",
        "feedback": "fb",
    }
    persist_node(state, adapter=adapter)
    adapter.assert_called_once()
    payload = adapter.call_args.args[0]
    assert payload["session_id"] == "s1"
    assert payload["score"] == 0.4
    assert payload["topic"] == "네트워크"


def test_persist_works_when_starting_at_zero():
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "score": 0.5,
        "topic": "x",
    }
    result = persist_node(state, adapter=None)
    assert result["questions_done"] == 1  # defaults questions_done to 0 → +1


def test_persist_does_not_explode_on_missing_optional_fields():
    state = {"user_id": "u1", "session_id": "s1"}
    # no score, no topic — adapter still gets called with whatever's there
    adapter = MagicMock()
    persist_node(state, adapter=adapter)
    adapter.assert_called_once()
```

- [ ] **Step 2: Run, must fail.**

- [ ] **Step 3: Implement `backend/app/agents/nodes/persist.py`**

```python
"""Persist node — deterministic SessionState update + optional adapter callback.

The real database write (StudySession / QuestionInstance / Answer tables)
happens in Plan 5 by wiring a `PersistAdapter` callable that receives the
payload built here. In Plan 3, the adapter is None — the graph still
runs end-to-end, the session state just doesn't outlive the process.
"""
from __future__ import annotations

from typing import Any, Protocol


class PersistAdapter(Protocol):
    """Plan 5 will implement this against SQLAlchemy. Plan 3 uses None or a Mock."""

    def __call__(self, payload: dict[str, Any]) -> None:
        ...


def persist_node(
    state: dict[str, Any],
    *,
    adapter: PersistAdapter | None,
) -> dict[str, Any]:
    """LangGraph node: increment counters and optionally hand a payload to the adapter."""
    questions_done = int(state.get("questions_done", 0)) + 1

    if adapter is not None:
        payload = {
            "user_id": state.get("user_id", ""),
            "session_id": state.get("session_id", ""),
            "topic": state.get("topic"),
            "difficulty": state.get("difficulty"),
            "question": state.get("question"),
            "model_answer": state.get("model_answer"),
            "rubric": state.get("rubric"),
            "ref_chunk_ids": state.get("ref_chunk_ids"),
            "user_answer": state.get("user_answer"),
            "score": state.get("score"),
            "rationale": state.get("rationale"),
            "feedback": state.get("feedback"),
            "missing_points": state.get("missing_points"),
        }
        adapter(payload)

    return {"questions_done": questions_done}
```

- [ ] **Step 4: Run, confirm pass (4 tests)**

- [ ] **Step 5: Lint + types**

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/nodes/persist.py backend/tests/agents/test_persist.py
git commit -m "feat(agents): add deterministic Persist node with adapter hook"
```

---

## Task 6: Checkpointer factory

**Files:**
- Create: `backend/app/agents/checkpointer.py`
- Create: `backend/tests/agents/test_checkpointer.py`

- [ ] **Step 1: Write the failing test in `backend/tests/agents/test_checkpointer.py`**

```python
"""Tests for app.agents.checkpointer."""
from pathlib import Path

from app.agents.checkpointer import make_checkpointer


def test_make_checkpointer_creates_parent_dir(tmp_path: Path):
    db_path = tmp_path / "subdir" / "studymate.db"
    saver = make_checkpointer(db_path)
    assert db_path.parent.exists()
    assert saver is not None


def test_make_checkpointer_returns_sqlite_saver_instance(tmp_path: Path):
    saver = make_checkpointer(tmp_path / "studymate.db")
    # SqliteSaver has a `.conn` attribute pointing at the sqlite3.Connection
    assert hasattr(saver, "conn") or hasattr(saver, "_conn") or hasattr(saver, "put")


def test_make_checkpointer_with_existing_db(tmp_path: Path):
    db_path = tmp_path / "studymate.db"
    db_path.write_bytes(b"")  # empty file
    saver = make_checkpointer(db_path)
    assert saver is not None
```

- [ ] **Step 2: Run, must fail.**

- [ ] **Step 3: Implement `backend/app/agents/checkpointer.py`**

```python
"""SqliteSaver factory — single source for the checkpointer DB path.

Plan 5 will create the StudySession/QuestionInstance/Answer tables in
the same SQLite file. LangGraph's checkpointer uses its own tables
(`checkpoints`, `writes`, `versions`) so there's no collision.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def make_checkpointer(db_path: Path) -> SqliteSaver:
    """Build a LangGraph SqliteSaver rooted at the given file.

    Creates the parent directory if it doesn't exist.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)
```

- [ ] **Step 4: Run, confirm pass (3 tests)**

- [ ] **Step 5: Lint + types**

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/checkpointer.py backend/tests/agents/test_checkpointer.py
git commit -m "feat(agents): add SqliteSaver checkpointer factory"
```

---

## Task 7: Graph topology — `build_graph()`

**Files:**
- Create: `backend/app/agents/graph.py`
- Create: `backend/tests/agents/test_graph_topology.py`

- [ ] **Step 1: Write the failing test in `backend/tests/agents/test_graph_topology.py`**

```python
"""Structural tests for the LangGraph topology.

These verify edges and interrupt placement without invoking any LLM.
"""
from unittest.mock import MagicMock

from app.agents.graph import build_graph


def _stub_deps():
    retriever = MagicMock()
    client = MagicMock()
    return {
        "retriever": retriever,
        "anthropic_client": client,
        "weakness_provider": lambda user_id: [],
        "persist_adapter": None,
        "topics": ["정규화", "SQL 응용"],
        "sonnet_model": "claude-sonnet-4-6",
        "haiku_model": "claude-haiku-4-5",
    }


def test_graph_has_required_nodes(tmp_path):
    from app.agents.checkpointer import make_checkpointer

    saver = make_checkpointer(tmp_path / "g.db")
    graph = build_graph(checkpointer=saver, **_stub_deps())
    node_names = set(graph.nodes.keys())
    # graph.nodes is the public attribute on a CompiledGraph
    for required in ["coordinator", "question_generator", "await_answer", "grader", "persist"]:
        assert required in node_names


def test_graph_interrupts_before_await_answer(tmp_path):
    from app.agents.checkpointer import make_checkpointer

    saver = make_checkpointer(tmp_path / "g.db")
    graph = build_graph(checkpointer=saver, **_stub_deps())
    # Compiled graph stores interrupt config; expose it via `.builder.interrupt_before`
    # or via graph.config / introspection. The exact attribute path can vary by langgraph
    # version, so we accept any of these.
    interrupts = (
        getattr(graph, "interrupt_before", None)
        or getattr(graph.builder, "interrupt_before", None)
        if hasattr(graph, "builder")
        else None
    )
    # Best-effort assertion: at minimum the await_answer node must exist.
    # Strong version: check interrupts; if introspection isn't available, skip.
    if interrupts is not None:
        assert "await_answer" in interrupts
```

(Note: the interrupt-introspection test is intentionally best-effort because langgraph's public API for this has shifted across versions. The integration test in Task 8 is the authoritative check.)

- [ ] **Step 2: Run, must fail on `build_graph` import.**

- [ ] **Step 3: Implement `backend/app/agents/graph.py`**

```python
"""LangGraph topology + public run/resume API.

Topology (linear with one interrupt):
    START → coordinator → question_generator → await_answer → grader → persist → END

`await_answer` is a no-op node placed where `interrupt_before` triggers,
so the graph pauses after QuestionGenerator and before Grader runs. The
API layer (Plan 4) collects the learner's answer, writes it into state,
then calls `resume_session(thread_id, user_answer)`.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.coordinator import coordinator_node
from app.agents.nodes.grader import grader_node
from app.agents.nodes.persist import persist_node
from app.agents.nodes.question_generator import question_generator_node
from app.agents.state import SessionState


WeaknessProvider = Callable[[str], list[str]]
PersistAdapter = Callable[[dict[str, Any]], None] | None


def _await_answer_node(state: SessionState) -> dict[str, Any]:
    """No-op pause point. The actual answer is injected by resume_session()."""
    return {}


def build_graph(
    *,
    checkpointer: Any,
    retriever: Any,
    anthropic_client: Any,
    weakness_provider: WeaknessProvider,
    persist_adapter: PersistAdapter,
    topics: list[str],
    sonnet_model: str,
    haiku_model: str,
    user_intent: str = "자유 학습",
) -> Any:
    """Compile the StudyMate learning-session graph with the given dependencies."""
    sg: StateGraph = StateGraph(SessionState)

    def _coordinator(state: SessionState) -> dict[str, Any]:
        weak_topics = weakness_provider(state.get("user_id", "")) or []
        return coordinator_node(
            state,
            client=anthropic_client,
            model=haiku_model,
            topics=topics,
            weak_topics=weak_topics,
            user_intent=user_intent,
        )

    def _qgen(state: SessionState) -> dict[str, Any]:
        return question_generator_node(
            state, client=anthropic_client, model=sonnet_model, retriever=retriever
        )

    def _grader(state: SessionState) -> dict[str, Any]:
        return grader_node(state, client=anthropic_client, model=sonnet_model)

    def _persist(state: SessionState) -> dict[str, Any]:
        return persist_node(state, adapter=persist_adapter)

    sg.add_node("coordinator", _coordinator)
    sg.add_node("question_generator", _qgen)
    sg.add_node("await_answer", _await_answer_node)
    sg.add_node("grader", _grader)
    sg.add_node("persist", _persist)

    sg.add_edge(START, "coordinator")
    sg.add_edge("coordinator", "question_generator")
    sg.add_edge("question_generator", "await_answer")
    sg.add_edge("await_answer", "grader")
    sg.add_edge("grader", "persist")
    sg.add_edge("persist", END)

    return sg.compile(checkpointer=checkpointer, interrupt_before=["await_answer"])


def run_session(
    *,
    graph: Any,
    user_id: str,
    session_id: str,
    target_count: int = 5,
) -> dict[str, Any]:
    """Invoke the graph for a new session; returns state at the AWAIT_ANSWER pause."""
    config = {"configurable": {"thread_id": session_id}}
    initial: SessionState = {
        "user_id": user_id,
        "session_id": session_id,
        "questions_done": 0,
        "target_count": target_count,
    }
    return graph.invoke(initial, config=config)


def resume_session(
    *,
    graph: Any,
    session_id: str,
    user_answer: str,
) -> dict[str, Any]:
    """Inject the learner's answer into state and resume the graph through Grader/Persist."""
    config = {"configurable": {"thread_id": session_id}}
    # update_state writes the answer into the snapshot; next invoke() picks it up
    graph.update_state(config, {"user_answer": user_answer})
    return graph.invoke(None, config=config)
```

- [ ] **Step 4: Run pytest test_graph_topology.py — confirm 2 passed (the third may be skipped depending on langgraph version)**

- [ ] **Step 5: Lint + types**

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/graph.py backend/tests/agents/test_graph_topology.py
git commit -m "feat(agents): wire LangGraph topology with await_answer interrupt"
```

---

## Task 8: Integration test — full run_session + resume_session with mocked clients

**Files:**
- Create: `backend/tests/agents/test_run_session_with_mocks.py`

- [ ] **Step 1: Write the integration test**

```python
"""Integration test for run_session + resume_session with mocked LLM/retriever.

This is the most important test in Plan 3 — it verifies the entire
graph flows correctly with the interrupt and resume cycle.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.checkpointer import make_checkpointer
from app.agents.graph import build_graph, resume_session, run_session


def _client_with_sequence(payloads: list[dict]) -> MagicMock:
    """Build a fake client whose .messages.create returns each payload in turn."""
    client = MagicMock()
    responses = []
    for p in payloads:
        text = json.dumps(p, ensure_ascii=False)
        responses.append(type("M", (), {"content": [type("C", (), {"text": text})()]})())
    client.messages.create.side_effect = responses
    return client


def _retriever_returning(chunks: list[tuple[str, str]]) -> MagicMock:
    retriever = MagicMock()

    class _C:
        def __init__(self, cid: str, text: str):
            self.id = cid
            self.text = text

    retriever.retrieve.return_value = [_C(cid, text) for cid, text in chunks]
    return retriever


def test_run_then_resume_completes_full_cycle(tmp_path: Path):
    # Coordinator → QGen (with retrieval) → AWAIT → Grader → Persist
    client = _client_with_sequence(
        [
            # Coordinator
            {
                "topic": "정규화",
                "difficulty": 2,
                "target_weakness": True,
                "reason": "weak",
            },
            # QGen
            {
                "question": "정규화의 목적을 서술하시오.",
                "model_answer": "데이터 중복 감소와 이상현상 방지.",
                "rubric": [
                    {"point": "목적", "weight": 0.6, "keywords": ["이상현상"]},
                    {"point": "예시", "weight": 0.4, "keywords": []},
                ],
            },
            # Grader
            {
                "score": 0.83,
                "rationale": "목적 일부 누락",
                "feedback": "이상현상을 명시하세요",
                "missing_points": ["이상현상"],
            },
        ]
    )
    retriever = _retriever_returning([("c1", "1NF 원자값"), ("c2", "2NF 부분종속")])

    persist_calls: list[dict] = []
    saver = make_checkpointer(tmp_path / "g.db")
    graph = build_graph(
        checkpointer=saver,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: ["정규화"],
        persist_adapter=persist_calls.append,
        topics=["정규화", "SQL 응용"],
        sonnet_model="claude-sonnet-4-6",
        haiku_model="claude-haiku-4-5",
    )

    # Phase 1: run until the AWAIT_ANSWER interrupt
    state_at_pause = run_session(
        graph=graph, user_id="u1", session_id="s1", target_count=5
    )
    assert state_at_pause["topic"] == "정규화"
    assert state_at_pause["question"] == "정규화의 목적을 서술하시오."
    assert state_at_pause["ref_chunk_ids"] == ["c1", "c2"]
    # grader should not have run yet
    assert "score" not in state_at_pause or state_at_pause.get("score") is None

    # Phase 2: resume with the learner's answer
    final = resume_session(
        graph=graph,
        session_id="s1",
        user_answer="정규화는 데이터 중복을 줄이는 작업입니다.",
    )
    assert final["score"] == 0.83
    assert final["missing_points"] == ["이상현상"]
    assert final["questions_done"] == 1
    assert len(persist_calls) == 1
    assert persist_calls[0]["session_id"] == "s1"


def test_resume_after_process_restart(tmp_path: Path):
    """The checkpointer should persist state across graph instances (same DB)."""
    client = _client_with_sequence(
        [
            {"topic": "정규화", "difficulty": 1, "target_weakness": False, "reason": ""},
            {
                "question": "q?",
                "model_answer": "a.",
                "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
            },
            {"score": 0.6, "rationale": "ok", "feedback": "ok", "missing_points": []},
        ]
    )
    retriever = _retriever_returning([("c1", "x")])
    db = tmp_path / "g.db"

    # Run graph #1 to the pause
    saver1 = make_checkpointer(db)
    graph1 = build_graph(
        checkpointer=saver1,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: [],
        persist_adapter=None,
        topics=["정규화"],
        sonnet_model="claude-sonnet-4-6",
        haiku_model="claude-haiku-4-5",
    )
    run_session(graph=graph1, user_id="u1", session_id="s99", target_count=5)
    del graph1, saver1

    # New graph instance, same DB → resume should work
    saver2 = make_checkpointer(db)
    graph2 = build_graph(
        checkpointer=saver2,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: [],
        persist_adapter=None,
        topics=["정규화"],
        sonnet_model="claude-sonnet-4-6",
        haiku_model="claude-haiku-4-5",
    )
    final = resume_session(graph=graph2, session_id="s99", user_answer="my answer")
    assert final["score"] == 0.6
```

- [ ] **Step 2: Run pytest, confirm 2 passed.**

- [ ] **Step 3: Lint + types**

- [ ] **Step 4: Commit**

```bash
git add backend/tests/agents/test_run_session_with_mocks.py
git commit -m "test(agents): full graph run + interrupt + resume + checkpointer persistence"
```

---

## Task 9: Public API + module re-exports + import-linter verification

**Files:**
- Modify: `backend/app/agents/__init__.py`

- [ ] **Step 1: Modify `backend/app/agents/__init__.py`**

```python
"""LangGraph workflow + 3 agents.

This is the single public surface for orchestrated learning sessions.
Outside callers should import only what is re-exported from this module.
"""
from app.agents.checkpointer import make_checkpointer
from app.agents.graph import build_graph, resume_session, run_session
from app.agents.state import GradingResult, QuestionPayload, RubricItem, SessionState

__all__ = [
    "GradingResult",
    "QuestionPayload",
    "RubricItem",
    "SessionState",
    "build_graph",
    "make_checkpointer",
    "resume_session",
    "run_session",
]
```

- [ ] **Step 2: Verify import-linter contracts hold**

```bash
cd backend && uv run lint-imports --config .importlinter
```

Expected: `5 kept, 0 broken`. The agents module imports from `app.rag` (acceptable, no contract forbids `agents → rag`) and from `langgraph`/`langchain-core` (external).

- [ ] **Step 3: Run full pytest suite**

```bash
cd backend && uv run pytest -v
```

Expected: all tests pass (Plan 1+2 tests + Plan 3 agent tests).

- [ ] **Step 4: Lint + types on the whole agents tree**

```bash
cd backend && uv run ruff check app/agents tests/agents && uv run ruff format --check app/agents tests/agents && uv run mypy app/agents tests/agents
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/__init__.py
git commit -m "feat(agents): export public surface (run_session, resume_session, SessionState)"
```

---

## Task 10: CLI smoke harness (optional, opt-in via marker)

**Files:**
- Create: `backend/scripts/agent_smoke.py`

This script is for manual smoke-testing with real Anthropic. It is NOT a pytest test (Plan 3 does NOT run real LLMs in CI). Plan 4 (API) and Plan 5 (Learning Records) will wire the agents into the actual app and observe real behavior end-to-end.

- [ ] **Step 1: Create `backend/scripts/agent_smoke.py`**

```python
"""Manual smoke harness for the agent graph with real Anthropic + RAG.

Usage:
    cd backend
    uv run python -m scripts.agent_smoke "약점 보강 학습"

Requires:
    - ANTHROPIC_API_KEY in .env
    - data/raw/ has at least one PDF (or `make seed` previously ingested chunks)

This is NOT part of pytest. It calls real LLMs and costs real $$.
"""
from __future__ import annotations

import sys

import typer
from anthropic import Anthropic

from app.agents.checkpointer import make_checkpointer
from app.agents.graph import build_graph, resume_session, run_session
from app.agents.nodes.persist import PersistAdapter
from app.core.settings import settings
from app.rag.ingest.topics import load_topics
from app.rag.retriever import default_retriever


app = typer.Typer(add_completion=False, help="Manual smoke for the agent graph")


def _print_adapter(payload: dict) -> None:
    typer.echo(f"[persist] session={payload['session_id']} score={payload.get('score')}")


@app.command()
def run(intent: str = "약점 보강 학습") -> None:
    """Run one session: Coordinator → QGen → AWAIT (you type answer) → Grader → Persist."""
    if not settings.anthropic_api_key:
        typer.echo("ERROR: ANTHROPIC_API_KEY missing in .env", err=True)
        raise typer.Exit(code=2)

    client = Anthropic(api_key=settings.anthropic_api_key)
    retriever = default_retriever()
    topics = load_topics(settings.topics_file)
    saver = make_checkpointer(settings.studymate_db)

    graph = build_graph(
        checkpointer=saver,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: [],  # Plan 5 will wire real one
        persist_adapter=_print_adapter,
        topics=topics,
        sonnet_model=settings.anthropic_model_sonnet,
        haiku_model=settings.anthropic_model_haiku,
        user_intent=intent,
    )

    session_id = "smoke-1"
    state = run_session(graph=graph, user_id="smoke-user", session_id=session_id)
    typer.echo("─" * 60)
    typer.echo(f"문제: {state.get('question')}")
    typer.echo("─" * 60)
    answer = typer.prompt("답안")
    final = resume_session(graph=graph, session_id=session_id, user_answer=answer)
    typer.echo("─" * 60)
    typer.echo(f"점수: {final.get('score')}")
    typer.echo(f"근거: {final.get('rationale')}")
    typer.echo(f"피드백: {final.get('feedback')}")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app() or 0)
```

- [ ] **Step 2: Lint + types**

```bash
cd backend && uv run ruff check scripts && uv run ruff format --check scripts && uv run mypy scripts
```

- [ ] **Step 3: Verify the CLI imports (does NOT invoke real LLM)**

```bash
cd backend && uv run python -m scripts.agent_smoke --help
```

Expected: typer help banner with `run` command.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/agent_smoke.py
git commit -m "feat(agents): add manual smoke harness for real Anthropic + RAG"
```

---

## Acceptance Criteria

Plan 3 is complete when **all** of the following hold:

1. `cd backend && uv run pytest -v` passes 100%, including the new `tests/agents/` (state, coordinator, qgen, grader, persist, checkpointer, graph topology, run_session integration). Plan 1+2 tests also still pass.
2. `cd backend && uv run lint-imports --config .importlinter` reports `5 kept, 0 broken`.
3. `cd backend && uv run mypy app tests` passes.
4. `cd backend && uv run python -m scripts.agent_smoke --help` shows the typer help banner cleanly (no import errors).
5. The integration test `test_run_then_resume_completes_full_cycle` proves the interrupt + resume cycle: Coordinator → QGen → AWAIT → resume(answer) → Grader → Persist all run, with state correctly threaded between nodes via the SqliteSaver checkpointer.
6. `make ci-local` still passes (no regressions in Plan 1+2 quality gates).

---

## What's Next

Plan 4: **Study UI & API**. FastAPI endpoints (`POST /study/sessions`, `POST /study/sessions/{id}/answer`, `GET /study/sessions/{id}`), SSE for streaming agent output, and a Next.js Study page implementing the Architectural-Dark design from `docs/design-explorations/2026-05-30-study-session-architectural-dark.html`. The API layer will call `app.agents.run_session`/`resume_session` from this plan; the Next.js page consumes the API. End-to-end: a user clicks "다음 문제 →" in the browser, the API runs the agents, the page renders the score + rubric + feedback.
