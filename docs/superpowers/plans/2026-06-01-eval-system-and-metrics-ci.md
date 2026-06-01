# Evaluation System & Metrics CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the evaluation harness that answers the interview question "how do you know it works?" — load a golden set (`golden_v1.jsonl`, 50 questions × 3 learner answers each = 150 grading cases), invoke the real Grader and Retriever to produce 3 system metrics (Grading Accuracy, Retrieval Recall@5, End-to-end Latency p95), render an HTML report, and wire GitHub Actions to fail PRs that regress those metrics. The mock-driven unit tests can run on every commit without API calls; the full eval runs on demand via `make eval` (cost ~$0.50 per full run).

**Architecture:** `app.eval` is a self-contained domain owning the dataset format, the three metric calculators, the runner orchestrator, and the HTML report builder. It depends on `app.rag` (retriever) and `app.agents` (grader) but is imported by NOBODY (it's a top-of-the-stack tool). Pure unit tests use the `FakeEmbedder` + a mock Anthropic client; real eval uses `default_retriever()` + a real Anthropic key. CI runs only the unit tests on every PR; a separate `make eval` target runs the full 150-case loop with a regression gate (fails if any metric drops below the spec §6.2 target).

**Tech Stack:** Python 3.12 / Pydantic v2 / Anthropic SDK (mocked in tests) / pytest / Jinja2 for HTML / typer CLI / GitHub Actions

**This plan is plan 6 of 7 in the StudyMate AI V1 series.** See `docs/superpowers/specs/2026-05-30-studymate-ai-design.md` §6 (Eval) + §11 (interview answers) + §13 마일스톤.

**Deferred from spec:**
- **Full 50-question golden set authoring** — Plan 6 ships 5 seed items + a documented schema so the full 150 cases can be appended by hand later. The runner works on whatever's in the file.
- **LangSmith trace integration** — Plan 7 (V2 hardening).
- **CI cost gate / token budget** — spec §6.3 mentions PR-cost discipline; this plan establishes the eval runner so a future task can wire it to a billing-aware skip.

---

## File Structure

```
studymate-ai/
├─ backend/
│  ├─ pyproject.toml                       # MODIFY: add jinja2
│  └─ app/
│     └─ eval/
│        ├─ __init__.py                    # re-export run_eval, EvalConfig
│        ├─ dataset.py                     # GoldenItem + load_golden(path)
│        ├─ metrics.py                     # GradingAccuracy + RetrievalRecall + LatencyTracker
│        ├─ runner.py                      # run_eval(config) → EvalReport
│        ├─ report.py                      # render_html(EvalReport) → str
│        └─ templates/
│           └─ report.html.j2              # Jinja2 template (Architectural-Dark style)
├─ data/
│  └─ eval/
│     ├─ golden_v1.jsonl                   # 5 seed items (50 full when ready)
│     └─ reports/                          # gitignored except .gitkeep
│        └─ .gitkeep
├─ backend/scripts/
│  └─ eval.py                              # typer CLI for `make eval`
├─ backend/tests/eval/
│  ├─ __init__.py
│  ├─ conftest.py                          # fake retriever + mocked Anthropic
│  ├─ test_dataset.py
│  ├─ test_metrics.py
│  ├─ test_runner.py
│  ├─ test_report.py
│  └─ fixtures/
│     └─ tiny_golden.jsonl                 # 2-item set for fast unit tests
├─ .github/
│  └─ workflows/
│     └─ ci.yml                            # MODIFY: ensure eval unit tests run; document opt-in real-eval workflow
└─ Makefile                                # MODIFY: add `eval`, `eval-mock`, `eval-report`
```

### File-by-file responsibility

- **`app/eval/dataset.py`** — `GoldenItem` Pydantic model (question + model_answer + rubric + 3 sample_answers with human-scored ground truth) + `load_golden(path)`.
- **`app/eval/metrics.py`** — 3 stateless calculators:
  - `grading_accuracy(predictions, ground_truth, tolerance=0.15)` — fraction within ±0.15
  - `retrieval_recall_at_k(query_keywords, retrieved_chunks, k=5)` — fraction of query keywords found in top-k chunks
  - `LatencyTracker` — record per-case durations, compute p50/p95
- **`app/eval/runner.py`** — `run_eval(config) -> EvalReport`. For each golden item × each sample answer: invoke Grader (real or mock), compare to human score; for each item: invoke Retriever, compute recall@5. Aggregate metrics. Build report.
- **`app/eval/report.py`** — `render_html(report)` returns a string. Save to `data/eval/reports/<timestamp>_<sha>.html` + append a row to `data/eval/reports/history.csv`.
- **`app/eval/templates/report.html.j2`** — Architectural-Dark themed HTML page with the same fonts/colors as the frontend.
- **`scripts/eval.py`** — typer CLI: `uv run python -m scripts.eval run` / `... mock` / `... report-latest`.

---

## Task 1: Dataset format + 5 seed items + loader

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/eval/__init__.py`
- Create: `backend/app/eval/dataset.py`
- Create: `data/eval/golden_v1.jsonl`
- Create: `backend/tests/eval/__init__.py`
- Create: `backend/tests/eval/conftest.py`
- Create: `backend/tests/eval/fixtures/tiny_golden.jsonl`
- Create: `backend/tests/eval/test_dataset.py`

- [ ] **Step 1: Add `jinja2>=3.1.4` to `[project] dependencies`** in `backend/pyproject.toml`, then `cd backend && uv sync`.

- [ ] **Step 2: Create `backend/app/eval/__init__.py`** (docstring only; re-exports in Task 7):

```python
"""Evaluation harness.

Owns the golden dataset format, metric calculators, runner, and HTML
report. Imported by nobody — this is a top-of-the-stack tool.
"""
```

- [ ] **Step 3: Create `backend/app/eval/dataset.py`**:

```python
"""Golden eval dataset — schema + loader."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class SampleAnswer(BaseModel):
    """One human-scored learner answer per question."""

    tier: str = Field(pattern=r"^(high|mid|low)$")
    text: str
    human_score: float = Field(ge=0.0, le=1.0)


class GoldenItem(BaseModel):
    """One question + model answer + rubric + 3 sample answers."""

    id: str
    topic: str
    difficulty: int = Field(ge=1, le=3)
    question: str
    model_answer: str
    rubric: list[dict[str, object]]
    rubric_keywords: list[str] = Field(
        default_factory=list,
        description="Flat keyword list used by Retrieval Recall@5",
    )
    sample_answers: list[SampleAnswer]


class DatasetLoadError(ValueError):
    """Raised when the jsonl file is malformed or violates the schema."""


def load_golden(path: Path) -> list[GoldenItem]:
    """Parse every line of the jsonl into a GoldenItem."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"golden dataset not found: {path}")
    items: list[GoldenItem] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
            items.append(GoldenItem.model_validate(data))
        except (json.JSONDecodeError, ValueError) as e:
            raise DatasetLoadError(f"{path}:{lineno}: {e}") from e
    if not items:
        raise DatasetLoadError(f"{path}: empty dataset")
    return items
```

- [ ] **Step 4: Create `data/eval/golden_v1.jsonl`** with 5 seed items (one per line, valid JSON):

```jsonl
{"id":"g001","topic":"정규화","difficulty":2,"question":"정규화의 목적과 1NF, 2NF, 3NF의 충족 조건을 각각 한 문장으로 서술하시오.","model_answer":"정규화의 목적은 함수적 종속에 기반한 이상현상(anomaly) 방지이며 중복은 부수적 효과이다. 1NF는 모든 속성이 원자값을 가져야 한다. 2NF는 부분 함수 종속을 제거한 형태이다. 3NF는 이행적 함수 종속을 제거한 형태이다.","rubric":[{"point":"정규화 목적","weight":0.25,"keywords":["이상현상"]},{"point":"1NF","weight":0.25,"keywords":["원자값"]},{"point":"2NF","weight":0.25,"keywords":["부분 함수 종속"]},{"point":"3NF","weight":0.25,"keywords":["이행적 함수 종속"]}],"rubric_keywords":["이상현상","원자값","부분 함수 종속","이행적 함수 종속"],"sample_answers":[{"tier":"high","text":"정규화는 이상현상을 막기 위함이며 1NF는 원자값, 2NF는 부분 함수 종속 제거, 3NF는 이행적 함수 종속 제거다.","human_score":0.95},{"tier":"mid","text":"정규화는 데이터 중복을 줄이며 1NF는 원자값, 2NF는 부분 종속, 3NF는 이행 종속을 제거한다.","human_score":0.7},{"tier":"low","text":"정규화는 테이블을 나누는 것이다.","human_score":0.15}]}
{"id":"g002","topic":"SQL 응용","difficulty":1,"question":"SQL의 INNER JOIN과 LEFT JOIN의 차이를 한 문장으로 설명하시오.","model_answer":"INNER JOIN은 양쪽 테이블에서 매칭되는 행만 반환하지만, LEFT JOIN은 왼쪽 테이블의 모든 행을 보존하고 오른쪽에 매칭이 없으면 NULL을 채운다.","rubric":[{"point":"INNER JOIN 정의","weight":0.4,"keywords":["매칭"]},{"point":"LEFT JOIN 정의","weight":0.4,"keywords":["NULL"]},{"point":"차이 명시","weight":0.2,"keywords":["왼쪽","보존"]}],"rubric_keywords":["매칭","NULL","왼쪽","보존"],"sample_answers":[{"tier":"high","text":"INNER JOIN은 양쪽 매칭만 가져오고, LEFT JOIN은 왼쪽을 전부 보존하면서 매칭 안 되면 NULL이다.","human_score":0.9},{"tier":"mid","text":"INNER JOIN은 교집합만 반환하고, LEFT JOIN은 왼쪽 전부를 반환한다.","human_score":0.65},{"tier":"low","text":"JOIN은 테이블 합치는 것이다.","human_score":0.1}]}
{"id":"g003","topic":"네트워크","difficulty":2,"question":"TCP의 3-way handshake 절차를 순서대로 서술하시오.","model_answer":"클라이언트가 SYN을 보내고, 서버가 SYN-ACK으로 응답하며, 클라이언트가 ACK으로 마무리해 양방향 연결을 확립한다.","rubric":[{"point":"SYN 단계","weight":0.34,"keywords":["SYN","클라이언트"]},{"point":"SYN-ACK 단계","weight":0.33,"keywords":["SYN-ACK","서버"]},{"point":"ACK 단계","weight":0.33,"keywords":["ACK"]}],"rubric_keywords":["SYN","SYN-ACK","ACK"],"sample_answers":[{"tier":"high","text":"클라이언트가 SYN, 서버가 SYN-ACK, 클라이언트가 ACK으로 응답해 연결을 확립한다.","human_score":0.95},{"tier":"mid","text":"SYN을 보내고 SYN-ACK 받고 ACK 보낸다.","human_score":0.75},{"tier":"low","text":"세 번 패킷을 주고받는다.","human_score":0.15}]}
{"id":"g004","topic":"디자인 패턴","difficulty":2,"question":"싱글톤(Singleton) 패턴의 목적과 단점 한 가지를 서술하시오.","model_answer":"싱글톤은 어떤 클래스의 인스턴스를 단 하나만 생성하도록 보장해 전역 접근점을 제공하기 위한 패턴이며, 단점으로는 전역 상태가 되어 테스트가 어렵고 결합도가 높아진다는 점이 있다.","rubric":[{"point":"목적 (인스턴스 하나)","weight":0.4,"keywords":["인스턴스","하나"]},{"point":"전역 접근점","weight":0.2,"keywords":["전역"]},{"point":"단점","weight":0.4,"keywords":["테스트","결합도"]}],"rubric_keywords":["인스턴스","전역","테스트","결합도"],"sample_answers":[{"tier":"high","text":"싱글톤은 인스턴스를 하나로 보장해 전역 접근점을 제공하지만, 전역 상태가 되어 테스트와 결합도 면에서 단점이 있다.","human_score":0.9},{"tier":"mid","text":"인스턴스 하나만 만드는 패턴이고 단점은 테스트가 어렵다.","human_score":0.65},{"tier":"low","text":"객체를 하나만 쓰는 거다.","human_score":0.2}]}
{"id":"g005","topic":"소프트웨어 개발 보안","difficulty":2,"question":"SQL 인젝션 공격의 원인과 대응 방안 하나를 서술하시오.","model_answer":"SQL 인젝션은 사용자 입력을 검증 없이 SQL 문에 직접 연결할 때 발생하며, 대응 방안으로는 파라미터 바인딩(Prepared Statement)을 사용해 입력값을 데이터로만 취급하게 만드는 것이 있다.","rubric":[{"point":"원인","weight":0.5,"keywords":["사용자 입력","검증","직접 연결"]},{"point":"대응 방안","weight":0.5,"keywords":["파라미터 바인딩","Prepared Statement"]}],"rubric_keywords":["사용자 입력","파라미터 바인딩","Prepared Statement"],"sample_answers":[{"tier":"high","text":"사용자 입력을 검증 없이 SQL에 직접 연결할 때 발생하며, 파라미터 바인딩(Prepared Statement)으로 막을 수 있다.","human_score":0.95},{"tier":"mid","text":"입력값을 검증하지 않아 발생하고 Prepared Statement로 막는다.","human_score":0.7},{"tier":"low","text":"해킹 공격이다.","human_score":0.05}]}
```

- [ ] **Step 5: Create `backend/tests/eval/__init__.py`** (empty).

- [ ] **Step 6: Create `backend/tests/eval/conftest.py`** (lightweight — full agent client fixtures live in their own tests):

```python
"""Shared fixtures for app.eval tests."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tiny_golden_path() -> Path:
    """Path to the 2-item fixture (relative to this test file)."""
    return Path(__file__).resolve().parent / "fixtures" / "tiny_golden.jsonl"
```

- [ ] **Step 7: Create `backend/tests/eval/fixtures/tiny_golden.jsonl`** (2 valid lines for fast unit tests):

```jsonl
{"id":"t001","topic":"테스트","difficulty":1,"question":"테스트 문항입니다. 답하시오.","model_answer":"모범 답안.","rubric":[{"point":"기본","weight":1.0,"keywords":["답"]}],"rubric_keywords":["답"],"sample_answers":[{"tier":"high","text":"답입니다","human_score":0.9},{"tier":"mid","text":"답","human_score":0.6},{"tier":"low","text":"모르겠다","human_score":0.1}]}
{"id":"t002","topic":"테스트","difficulty":1,"question":"두번째 테스트 문항입니다.","model_answer":"답.","rubric":[{"point":"기본","weight":1.0,"keywords":["답"]}],"rubric_keywords":["답"],"sample_answers":[{"tier":"high","text":"답입니다","human_score":0.95},{"tier":"mid","text":"답","human_score":0.5},{"tier":"low","text":"X","human_score":0.0}]}
```

- [ ] **Step 8: Write `backend/tests/eval/test_dataset.py`** with 4 tests:

```python
"""Tests for app.eval.dataset."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.eval.dataset import DatasetLoadError, GoldenItem, SampleAnswer, load_golden


def test_load_golden_returns_two_items(tiny_golden_path: Path) -> None:
    items = load_golden(tiny_golden_path)
    expected_count = 2
    assert len(items) == expected_count
    assert items[0].id == "t001"


def test_load_golden_each_item_has_3_sample_answers(tiny_golden_path: Path) -> None:
    items = load_golden(tiny_golden_path)
    expected_samples = 3
    for item in items:
        assert len(item.sample_answers) == expected_samples
    # tiers in the fixture
    assert {s.tier for s in items[0].sample_answers} == {"high", "mid", "low"}


def test_sample_answer_rejects_invalid_tier() -> None:
    with pytest.raises(ValidationError):
        SampleAnswer(tier="medium", text="x", human_score=0.5)


def test_load_golden_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_golden(tmp_path / "nope.jsonl")


def test_load_golden_raises_on_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(DatasetLoadError, match="empty"):
        load_golden(p)


def test_load_golden_raises_on_malformed_line(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("{this is not json}", encoding="utf-8")
    with pytest.raises(DatasetLoadError):
        load_golden(p)


def test_project_golden_v1_loads() -> None:
    """Smoke-load the real project golden_v1.jsonl."""
    root = Path(__file__).resolve().parents[3]  # backend/tests/eval → repo root
    items = load_golden(root / "data" / "eval" / "golden_v1.jsonl")
    expected_seed = 5
    assert len(items) >= expected_seed
    # at least one item from each major topic in the seed
    topics = {i.topic for i in items}
    assert "정규화" in topics
```

- [ ] **Step 9: Run pytest** — expect 7 passed:

```bash
cd backend && uv run pytest tests/eval/test_dataset.py -v
```

- [ ] **Step 10: Lint + types** — same gates as prior plans. mypy strict, ruff strict. Apply PLR2004 named locals.

- [ ] **Step 11: import-linter** — expect 5/0 (app.eval depends on nobody else yet).

- [ ] **Step 12: Commit + push:**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/eval/ backend/tests/eval/ data/eval/
git commit -m "feat(eval): add golden dataset schema, loader, and 5 seed items"
git push
```

---

## Task 2: Metric calculators

**Files:**
- Create: `backend/app/eval/metrics.py`
- Create: `backend/tests/eval/test_metrics.py`

- [ ] **Step 1: Implement `backend/app/eval/metrics.py`**:

```python
"""Stateless metric calculators for the eval harness."""
from __future__ import annotations

import math
from dataclasses import dataclass


_DEFAULT_TOLERANCE = 0.15
_DEFAULT_K = 5


def grading_accuracy(
    predictions: list[float],
    ground_truth: list[float],
    *,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> float:
    """Fraction of (pred, truth) pairs where |pred - truth| <= tolerance."""
    if len(predictions) != len(ground_truth):
        raise ValueError(
            f"length mismatch: {len(predictions)} predictions vs "
            f"{len(ground_truth)} ground truth scores"
        )
    if not predictions:
        return 0.0
    within = sum(
        1 for p, t in zip(predictions, ground_truth, strict=True) if abs(p - t) <= tolerance
    )
    return within / len(predictions)


def retrieval_recall_at_k(
    keywords: list[str],
    retrieved_chunk_texts: list[str],
    *,
    k: int = _DEFAULT_K,
) -> float:
    """Fraction of keywords appearing in at least one of the top-k chunks."""
    if not keywords:
        return 0.0
    top_k_text = " ".join(retrieved_chunk_texts[:k])
    hits = sum(1 for kw in keywords if kw in top_k_text)
    return hits / len(keywords)


@dataclass
class LatencyTracker:
    """Collect per-case durations (seconds) and compute p50/p95."""

    durations: list[float]

    def add(self, seconds: float) -> None:
        self.durations.append(seconds)

    def _percentile(self, pct: float) -> float:
        if not self.durations:
            return 0.0
        # nearest-rank method (no scipy dep)
        ordered = sorted(self.durations)
        rank = max(0, min(len(ordered) - 1, math.ceil(pct * len(ordered)) - 1))
        return ordered[rank]

    def p50(self) -> float:
        half = 0.5
        return self._percentile(half)

    def p95(self) -> float:
        return self._percentile(0.95)

    def count(self) -> int:
        return len(self.durations)
```

- [ ] **Step 2: Write `backend/tests/eval/test_metrics.py`**:

```python
"""Tests for app.eval.metrics."""
import pytest

from app.eval.metrics import LatencyTracker, grading_accuracy, retrieval_recall_at_k


def test_grading_accuracy_all_match() -> None:
    expected = 1.0
    assert grading_accuracy([0.5, 0.7], [0.5, 0.7], tolerance=0.0) == expected


def test_grading_accuracy_partial() -> None:
    # two within tolerance, one outside
    result = grading_accuracy([0.5, 0.6, 0.9], [0.55, 0.7, 0.4], tolerance=0.15)
    expected = 2 / 3
    assert abs(result - expected) < 1e-9


def test_grading_accuracy_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        grading_accuracy([0.5], [0.5, 0.7])


def test_grading_accuracy_empty_inputs() -> None:
    assert grading_accuracy([], []) == 0.0


def test_retrieval_recall_at_k_full() -> None:
    chunks = ["1NF는 원자값을 가진다", "2NF는 부분 종속을 제거한다"]
    recall = retrieval_recall_at_k(["원자값", "부분 종속"], chunks, k=5)
    expected = 1.0
    assert recall == expected


def test_retrieval_recall_at_k_partial() -> None:
    chunks = ["1NF는 원자값을 가진다", "HTTP는 무상태 프로토콜이다"]
    recall = retrieval_recall_at_k(["원자값", "부분 종속"], chunks, k=5)
    expected = 0.5
    assert recall == expected


def test_retrieval_recall_at_k_respects_k() -> None:
    chunks = ["chunk1", "chunk2", "chunk3", "원자값", "부분 종속"]
    # only top 3 are considered
    recall = retrieval_recall_at_k(["원자값"], chunks, k=3)
    expected = 0.0
    assert recall == expected


def test_retrieval_recall_at_k_empty_keywords() -> None:
    assert retrieval_recall_at_k([], ["x"]) == 0.0


def test_latency_p50_and_p95() -> None:
    tracker = LatencyTracker(durations=[])
    for d in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
        tracker.add(d)
    expected_count = 10
    assert tracker.count() == expected_count
    # nearest-rank: p50 of 10 items = ceil(0.5*10)=5 -> index 4 -> 5.0
    p50_expected = 5.0
    assert tracker.p50() == p50_expected
    # p95 of 10 items = ceil(0.95*10)=10 -> index 9 -> 10.0
    p95_expected = 10.0
    assert tracker.p95() == p95_expected


def test_latency_empty_returns_zero() -> None:
    tracker = LatencyTracker(durations=[])
    assert tracker.p50() == 0.0
    assert tracker.p95() == 0.0
```

- [ ] **Step 3: Run pytest** — expect 10 passed.

- [ ] **Step 4: Lint + types.**

- [ ] **Step 5: Commit + push:**

```bash
git add backend/app/eval/metrics.py backend/tests/eval/test_metrics.py
git commit -m "feat(eval): add Grading Accuracy + Retrieval Recall@5 + LatencyTracker"
git push
```

---

## Task 3: Runner (orchestrator) with mock + real modes

**Files:**
- Create: `backend/app/eval/runner.py`
- Create: `backend/tests/eval/test_runner.py`

- [ ] **Step 1: Implement `backend/app/eval/runner.py`**:

```python
"""Eval runner — iterate the golden set, call Grader + Retriever, compute metrics."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.eval.dataset import GoldenItem, load_golden
from app.eval.metrics import LatencyTracker, grading_accuracy, retrieval_recall_at_k


class _GraderCallable(Protocol):
    """Anything that takes (question, model_answer, rubric, user_answer) → score 0..1."""

    def __call__(
        self,
        question: str,
        model_answer: str,
        rubric: list[dict[str, object]],
        user_answer: str,
    ) -> float: ...


class _RetrieverCallable(Protocol):
    """Anything that takes a query string → list of chunk text."""

    def __call__(self, query: str) -> list[str]: ...


@dataclass(frozen=True)
class EvalConfig:
    """Parameters for a single eval run."""

    dataset_path: Path
    git_sha: str = "dev"
    tag: str = ""


@dataclass
class PerCaseResult:
    item_id: str
    topic: str
    tier: str
    predicted_score: float
    human_score: float
    delta: float


@dataclass
class EvalReport:
    config: EvalConfig
    timestamp_iso: str
    item_count: int
    case_count: int
    grading_accuracy: float
    retrieval_recall_at_5: float
    latency_p50: float
    latency_p95: float
    per_case: list[PerCaseResult] = field(default_factory=list)

    def passes_targets(self) -> bool:
        # spec §6.2 targets
        accuracy_target = 0.80
        recall_target = 0.75
        latency_target = 8.0
        return (
            self.grading_accuracy >= accuracy_target
            and self.retrieval_recall_at_5 >= recall_target
            and self.latency_p95 <= latency_target
        )


def run_eval(
    *,
    config: EvalConfig,
    grader: _GraderCallable,
    retriever: _RetrieverCallable,
) -> EvalReport:
    """Execute one eval pass against the dataset."""
    items: list[GoldenItem] = load_golden(config.dataset_path)
    predictions: list[float] = []
    truths: list[float] = []
    recalls: list[float] = []
    latency = LatencyTracker(durations=[])
    per_case: list[PerCaseResult] = []

    for item in items:
        # retrieval: query the retriever once per item
        chunks = retriever(item.question)
        recalls.append(
            retrieval_recall_at_k(item.rubric_keywords, chunks, k=5)
        )

        # grading: 3 sample answers per item
        for sample in item.sample_answers:
            t0 = time.perf_counter()
            score = grader(
                item.question, item.model_answer, item.rubric, sample.text
            )
            latency.add(time.perf_counter() - t0)
            predictions.append(score)
            truths.append(sample.human_score)
            per_case.append(
                PerCaseResult(
                    item_id=item.id,
                    topic=item.topic,
                    tier=sample.tier,
                    predicted_score=score,
                    human_score=sample.human_score,
                    delta=abs(score - sample.human_score),
                )
            )

    return EvalReport(
        config=config,
        timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        item_count=len(items),
        case_count=len(predictions),
        grading_accuracy=grading_accuracy(predictions, truths, tolerance=0.15),
        retrieval_recall_at_5=sum(recalls) / max(1, len(recalls)),
        latency_p50=latency.p50(),
        latency_p95=latency.p95(),
        per_case=per_case,
    )


def to_json(report: EvalReport) -> str:
    """Serialize an EvalReport to JSON (for history.csv + debugging)."""
    return json.dumps(
        {
            "git_sha": report.config.git_sha,
            "tag": report.config.tag,
            "timestamp": report.timestamp_iso,
            "item_count": report.item_count,
            "case_count": report.case_count,
            "grading_accuracy": report.grading_accuracy,
            "retrieval_recall_at_5": report.retrieval_recall_at_5,
            "latency_p50": report.latency_p50,
            "latency_p95": report.latency_p95,
            "passes_targets": report.passes_targets(),
        },
        ensure_ascii=False,
    )
```

- [ ] **Step 2: Write `backend/tests/eval/test_runner.py`** — uses fake grader + retriever, no real LLM:

```python
"""Tests for app.eval.runner."""
from pathlib import Path

from app.eval.dataset import GoldenItem
from app.eval.runner import EvalConfig, run_eval, to_json


def _exact_grader(_q: str, _m: str, _r: list[dict[str, object]], user: str) -> float:
    """Returns the human_score baked into the fixture for each sample."""
    # The tiny fixture's high=0.9/0.95, mid=0.5/0.6, low=0.0/0.1
    if "답입니다" in user:
        # high tier — slightly different per item but always near 0.9
        return 0.92
    if user == "답":
        return 0.55
    return 0.05


def _good_retriever(query: str) -> list[str]:
    return ["답을 포함하는 청크 텍스트", "다른 청크"]


def _bad_retriever(_query: str) -> list[str]:
    return ["관계 없는 청크", "또 다른 무관한 청크"]


def test_runner_processes_all_cases(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path, git_sha="abc", tag="t")
    report = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    expected_items = 2
    expected_cases = 6  # 2 items × 3 samples
    assert report.item_count == expected_items
    assert report.case_count == expected_cases


def test_runner_grading_accuracy_within_tolerance(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    report = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    # _exact_grader is close enough that most predictions are within 0.15.
    # Score should be >= 0.66 (4/6 minimum on this fixture).
    accuracy_floor = 0.5
    assert report.grading_accuracy >= accuracy_floor


def test_runner_recall_responds_to_retriever_quality(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    good = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    bad = run_eval(config=config, grader=_exact_grader, retriever=_bad_retriever)
    assert good.retrieval_recall_at_5 > bad.retrieval_recall_at_5


def test_runner_latency_tracker_populated(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    report = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    assert report.latency_p50 >= 0.0
    assert report.latency_p95 >= report.latency_p50


def test_passes_targets_when_metrics_above_thresholds(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    # build a manual high-quality report
    from app.eval.runner import EvalReport

    report = EvalReport(
        config=config,
        timestamp_iso="2026-06-01T00:00:00Z",
        item_count=2,
        case_count=6,
        grading_accuracy=0.83,
        retrieval_recall_at_5=0.80,
        latency_p50=2.0,
        latency_p95=7.0,
    )
    assert report.passes_targets() is True


def test_passes_targets_false_on_one_metric_miss(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    from app.eval.runner import EvalReport

    report = EvalReport(
        config=config,
        timestamp_iso="2026-06-01T00:00:00Z",
        item_count=2,
        case_count=6,
        grading_accuracy=0.83,
        retrieval_recall_at_5=0.80,
        latency_p50=2.0,
        latency_p95=9.0,  # over 8.0 target
    )
    assert report.passes_targets() is False


def test_to_json_round_trip(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    report = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    payload = to_json(report)
    import json

    parsed = json.loads(payload)
    assert "grading_accuracy" in parsed
    assert "passes_targets" in parsed
```

- [ ] **Step 3: Run pytest, expect 7 passed.**
- [ ] **Step 4: Lint + types.**
- [ ] **Step 5: Commit + push:**

```bash
git add backend/app/eval/runner.py backend/tests/eval/test_runner.py
git commit -m "feat(eval): add runner orchestrator with grading + retrieval + latency metrics"
git push
```

---

## Task 4: HTML report rendering

**Files:**
- Create: `backend/app/eval/templates/report.html.j2`
- Create: `backend/app/eval/report.py`
- Create: `backend/tests/eval/test_report.py`

- [ ] **Step 1: Create the Jinja2 template `backend/app/eval/templates/report.html.j2`**:

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>StudyMate Eval — {{ report.config.tag or report.config.git_sha }}</title>
  <style>
    :root {
      --bg: #0b0e15; --panel: #141826; --panel-line: #262d3e;
      --ink: #f1f3f8; --ink-mid: #b4bbcb; --ink-soft: #828a9d;
      --cyan: #7fe2ec; --amber: #f3bd6f; --danger: #f47878;
    }
    * { box-sizing: border-box; }
    body { background: var(--bg); color: var(--ink); font-family: -apple-system, "Pretendard Variable", sans-serif; padding: 40px; max-width: 1100px; margin: 0 auto; }
    h1 { font-style: italic; font-size: 48px; letter-spacing: -0.02em; margin: 0; }
    .meta { font-family: ui-monospace, monospace; font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-soft); margin: 8px 0 32px; border-bottom: 1px solid var(--panel-line); padding-bottom: 12px; }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 40px; }
    .card { border: 1px solid var(--panel-line); padding: 22px; background: linear-gradient(180deg, var(--panel), rgba(20,24,38,0.4)); }
    .card .label { font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: 0.28em; text-transform: uppercase; color: var(--ink-soft); }
    .card .value { font-size: 56px; line-height: 1; margin: 12px 0 4px; font-style: italic; }
    .card.pass .value { color: var(--cyan); }
    .card.fail .value { color: var(--danger); }
    .card .target { font-family: ui-monospace, monospace; font-size: 11px; color: var(--ink-mid); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid var(--panel-line); padding: 8px 12px; text-align: left; }
    th { font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-soft); }
    tr.miss td { color: var(--amber); }
  </style>
</head>
<body>
  <h1>StudyMate Eval</h1>
  <p class="meta">
    {{ report.timestamp_iso }} · {{ report.config.git_sha }}
    {% if report.config.tag %} · {{ report.config.tag }}{% endif %}
    · {{ report.case_count }} cases / {{ report.item_count }} items
  </p>

  <div class="metrics">
    <div class="card {{ 'pass' if report.grading_accuracy >= 0.80 else 'fail' }}">
      <div class="label">Grading Accuracy</div>
      <div class="value">{{ "%.2f"|format(report.grading_accuracy * 100) }}%</div>
      <div class="target">target ≥ 80% · tolerance ±0.15</div>
    </div>
    <div class="card {{ 'pass' if report.retrieval_recall_at_5 >= 0.75 else 'fail' }}">
      <div class="label">Retrieval Recall@5</div>
      <div class="value">{{ "%.2f"|format(report.retrieval_recall_at_5 * 100) }}%</div>
      <div class="target">target ≥ 75%</div>
    </div>
    <div class="card {{ 'pass' if report.latency_p95 <= 8.0 else 'fail' }}">
      <div class="label">Latency p95</div>
      <div class="value">{{ "%.2f"|format(report.latency_p95) }}s</div>
      <div class="target">target ≤ 8s · p50 {{ "%.2f"|format(report.latency_p50) }}s</div>
    </div>
  </div>

  <h2>Per-Case Detail</h2>
  <table>
    <thead><tr><th>Item</th><th>Topic</th><th>Tier</th><th>Predicted</th><th>Human</th><th>|Δ|</th></tr></thead>
    <tbody>
    {% for c in report.per_case %}
      <tr class="{{ 'miss' if c.delta > 0.15 else '' }}">
        <td>{{ c.item_id }}</td>
        <td>{{ c.topic }}</td>
        <td>{{ c.tier }}</td>
        <td>{{ "%.2f"|format(c.predicted_score) }}</td>
        <td>{{ "%.2f"|format(c.human_score) }}</td>
        <td>{{ "%.2f"|format(c.delta) }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</body>
</html>
```

- [ ] **Step 2: Create `backend/app/eval/report.py`**:

```python
"""Render an EvalReport to HTML + append to history.csv."""
from __future__ import annotations

import csv
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.eval.runner import EvalReport


def _env() -> Environment:
    templates_dir = Path(__file__).parent / "templates"
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html"]),
    )


def render_html(report: EvalReport) -> str:
    """Render an EvalReport to a full HTML string."""
    template = _env().get_template("report.html.j2")
    return template.render(report=report)


def save_report(
    report: EvalReport,
    *,
    output_dir: Path,
    filename_suffix: str = "",
) -> Path:
    """Write the HTML report + append a row to history.csv. Returns HTML path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_ts = report.timestamp_iso.replace(":", "-")
    suffix = f"_{filename_suffix}" if filename_suffix else ""
    html_path = output_dir / f"{safe_ts}_{report.config.git_sha}{suffix}.html"
    html_path.write_text(render_html(report), encoding="utf-8")

    history_path = output_dir / "history.csv"
    write_header = not history_path.exists()
    with history_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow([
                "timestamp", "git_sha", "tag", "item_count", "case_count",
                "grading_accuracy", "retrieval_recall_at_5",
                "latency_p50", "latency_p95", "passes_targets",
            ])
        writer.writerow([
            report.timestamp_iso, report.config.git_sha, report.config.tag,
            report.item_count, report.case_count,
            f"{report.grading_accuracy:.4f}",
            f"{report.retrieval_recall_at_5:.4f}",
            f"{report.latency_p50:.3f}",
            f"{report.latency_p95:.3f}",
            "PASS" if report.passes_targets() else "FAIL",
        ])
    return html_path
```

- [ ] **Step 3: Write `backend/tests/eval/test_report.py`** (no LLM, no network):

```python
"""Tests for app.eval.report — HTML render + history.csv append."""
import csv
from pathlib import Path

from app.eval.report import render_html, save_report
from app.eval.runner import EvalConfig, EvalReport, PerCaseResult


def _sample_report(tmp_path: Path) -> EvalReport:
    return EvalReport(
        config=EvalConfig(dataset_path=tmp_path / "dummy.jsonl", git_sha="abc1234", tag="test"),
        timestamp_iso="2026-06-01T12:34:56Z",
        item_count=2,
        case_count=6,
        grading_accuracy=0.83,
        retrieval_recall_at_5=0.80,
        latency_p50=2.5,
        latency_p95=6.2,
        per_case=[
            PerCaseResult(item_id="t001", topic="테스트", tier="high",
                          predicted_score=0.92, human_score=0.9, delta=0.02),
            PerCaseResult(item_id="t001", topic="테스트", tier="low",
                          predicted_score=0.55, human_score=0.1, delta=0.45),
        ],
    )


def test_render_html_contains_metrics(tmp_path: Path) -> None:
    report = _sample_report(tmp_path)
    html = render_html(report)
    assert "<title>StudyMate Eval" in html
    assert "Grading Accuracy" in html
    assert "83.00%" in html
    assert "80.00%" in html
    assert "6.20s" in html


def test_render_html_marks_failing_metric_card(tmp_path: Path) -> None:
    report = _sample_report(tmp_path)
    report.latency_p95 = 9.5  # above target
    html = render_html(report)
    # the latency card should be marked fail
    assert 'class="card fail"' in html


def test_save_report_creates_html_and_history(tmp_path: Path) -> None:
    report = _sample_report(tmp_path)
    out = tmp_path / "out"
    html_path = save_report(report, output_dir=out)
    assert html_path.exists()
    assert (out / "history.csv").exists()
    rows = list(csv.reader((out / "history.csv").open(encoding="utf-8")))
    expected_header_then_one_data_row = 2
    assert len(rows) == expected_header_then_one_data_row
    assert rows[0][0] == "timestamp"
    assert rows[1][1] == "abc1234"
    assert rows[1][-1] == "PASS"


def test_save_report_appends_without_duplicating_header(tmp_path: Path) -> None:
    report = _sample_report(tmp_path)
    out = tmp_path / "out"
    save_report(report, output_dir=out)
    save_report(report, output_dir=out, filename_suffix="run2")
    rows = list(csv.reader((out / "history.csv").open(encoding="utf-8")))
    expected_header_plus_two = 3
    assert len(rows) == expected_header_plus_two
```

- [ ] **Step 4: Run pytest, expect 4 passed.**
- [ ] **Step 5: Lint + types.**
- [ ] **Step 6: Commit + push:**

```bash
git add backend/app/eval/templates/ backend/app/eval/report.py backend/tests/eval/test_report.py
git commit -m "feat(eval): add HTML report renderer + history.csv appender"
git push
```

---

## Task 5: Public API + module re-exports + import-linter

**Files:**
- Modify: `backend/app/eval/__init__.py`

- [ ] **Step 1: Modify `backend/app/eval/__init__.py`**:

```python
"""Evaluation harness.

Owns the golden dataset format, metric calculators, runner, and HTML
report. Imported by nobody — this is a top-of-the-stack tool.
"""

from app.eval.dataset import GoldenItem, SampleAnswer, load_golden
from app.eval.metrics import LatencyTracker, grading_accuracy, retrieval_recall_at_k
from app.eval.report import render_html, save_report
from app.eval.runner import EvalConfig, EvalReport, PerCaseResult, run_eval, to_json

__all__ = [
    "EvalConfig",
    "EvalReport",
    "GoldenItem",
    "LatencyTracker",
    "PerCaseResult",
    "SampleAnswer",
    "grading_accuracy",
    "load_golden",
    "render_html",
    "retrieval_recall_at_k",
    "run_eval",
    "save_report",
    "to_json",
]
```

- [ ] **Step 2: Run import-linter + full pytest. 5/0 + all tests pass.**
- [ ] **Step 3: Lint + types.**
- [ ] **Step 4: Commit + push:**

```bash
git add backend/app/eval/__init__.py
git commit -m "feat(eval): export public surface (run_eval, GoldenItem, EvalReport, etc.)"
git push
```

---

## Task 6: Typer CLI + Makefile targets

**Files:**
- Create: `backend/scripts/eval.py`
- Modify: `Makefile`
- Create: `data/eval/reports/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create `backend/scripts/eval.py`**:

```python
"""CLI to run the eval harness against the golden set.

Usage:
    cd backend
    uv run python -m scripts.eval mock          # no LLM, fixed-score fake grader
    uv run python -m scripts.eval run           # real Anthropic + RAG; needs ANTHROPIC_API_KEY
    uv run python -m scripts.eval show-latest   # print the latest history.csv row
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer

from app.core.settings import settings
from app.eval.dataset import load_golden
from app.eval.report import save_report
from app.eval.runner import EvalConfig, run_eval, to_json


app = typer.Typer(add_completion=False, help="Run the StudyMate eval harness")


_DEFAULT_REPORTS_DIR = settings.studymate_db.parent / "eval" / "reports"


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        return result.stdout.strip() or "dev"
    except (FileNotFoundError, OSError):  # pragma: no cover
        return "dev"


def _fake_grader(
    _q: str, _m: str, _r: list[dict[str, object]], user: str
) -> float:
    """Deterministic mock grader — long answers score higher (rough proxy)."""
    length_floor = 50
    length_target = 200
    length = len(user)
    if length < length_floor:
        return 0.1
    if length >= length_target:
        return 0.9
    # linear between 0.1 and 0.9
    return 0.1 + 0.8 * ((length - length_floor) / (length_target - length_floor))


def _fake_retriever(_query: str) -> list[str]:
    return [
        "정규화 1NF 원자값",
        "정규화 2NF 부분 함수 종속",
        "정규화 3NF 이행적 함수 종속",
        "SQL JOIN 매칭 NULL",
        "TCP SYN-ACK 핸드셰이크",
    ]


@app.command()
def mock() -> None:
    """Run eval with the fake grader + fake retriever (no API calls)."""
    dataset = settings.studymate_db.parent / "eval" / "golden_v1.jsonl"
    typer.echo(f"Loading dataset: {dataset}")
    items = load_golden(dataset)
    typer.echo(f"  {len(items)} items, {sum(len(i.sample_answers) for i in items)} cases")

    config = EvalConfig(dataset_path=dataset, git_sha=_git_sha(), tag="mock")
    report = run_eval(config=config, grader=_fake_grader, retriever=_fake_retriever)
    html_path = save_report(report, output_dir=_DEFAULT_REPORTS_DIR)
    typer.echo(to_json(report))
    typer.echo(f"HTML report: {html_path}")


@app.command()
def run() -> None:
    """Run eval against real Anthropic + real RAG retriever."""
    if not settings.anthropic_api_key:
        typer.echo("ERROR: ANTHROPIC_API_KEY missing in .env", err=True)
        raise typer.Exit(code=2)

    from anthropic import Anthropic  # noqa: PLC0415
    from app.agents.nodes.grader import grader_node  # noqa: PLC0415
    from app.rag.retriever import default_retriever  # noqa: PLC0415

    client = Anthropic(api_key=settings.anthropic_api_key)
    retriever_inst = default_retriever()

    def _real_grader(
        question: str, model_answer: str, rubric: list[dict[str, object]], user: str
    ) -> float:
        state: dict[str, Any] = {
            "question": question,
            "model_answer": model_answer,
            "rubric": rubric,
            "user_answer": user,
        }
        result = grader_node(state, client=client, model=settings.anthropic_model_sonnet)
        return float(result.get("score", 0.5))

    def _real_retriever(query: str) -> list[str]:
        chunks = retriever_inst.retrieve(query, k=5)
        return [c.text for c in chunks]

    dataset = settings.studymate_db.parent / "eval" / "golden_v1.jsonl"
    items = load_golden(dataset)
    typer.echo(f"Loading {len(items)} items from {dataset}")
    typer.echo("Running real eval (this calls Anthropic — costs $$)...")

    config = EvalConfig(dataset_path=dataset, git_sha=_git_sha(), tag="real")
    report = run_eval(config=config, grader=_real_grader, retriever=_real_retriever)
    html_path = save_report(report, output_dir=_DEFAULT_REPORTS_DIR)
    typer.echo(to_json(report))
    typer.echo(f"HTML report: {html_path}")
    if not report.passes_targets():
        typer.echo("REGRESSION: one or more metrics below targets.", err=True)
        raise typer.Exit(code=1)


@app.command("show-latest")
def show_latest() -> None:
    """Print the latest row of history.csv."""
    history = _DEFAULT_REPORTS_DIR / "history.csv"
    if not history.exists():
        typer.echo("(no history yet — run `eval mock` or `eval run` first)")
        raise typer.Exit(code=0)
    rows = list(csv.reader(history.open(encoding="utf-8")))
    if len(rows) < 2:  # only header
        typer.echo("(history is empty)")
        raise typer.Exit(code=0)
    header, latest = rows[0], rows[-1]
    typer.echo(json.dumps(dict(zip(header, latest, strict=True)), ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app() or 0)
```

- [ ] **Step 2: Modify `Makefile`** — extend `.PHONY` and add 3 targets:

After the `seed-reset:` target's recipe, append:

```makefile

eval:
	cd backend && uv run python -m scripts.eval run

eval-mock:
	cd backend && uv run python -m scripts.eval mock

eval-latest:
	cd backend && uv run python -m scripts.eval show-latest
```

Also extend the `.PHONY` line at the top with `eval eval-mock eval-latest` and add 3 `@echo` lines to the help recipe:

```
	@echo "  eval          run eval with real Anthropic + RAG (costs ~$$0.50)"
	@echo "  eval-mock     run eval with fake grader + retriever (no API)"
	@echo "  eval-latest   print latest history.csv row"
```

- [ ] **Step 3: Create `data/eval/reports/.gitkeep`** (empty).

- [ ] **Step 4: Modify root `.gitignore`** — add the reports HTML files but keep history.csv tracked. Append:

```
# Eval HTML reports are large + transient; only history.csv is tracked
data/eval/reports/*.html
!data/eval/reports/.gitkeep
```

- [ ] **Step 5: Verify `uv run python -m scripts.eval mock` runs and prints JSON + writes a report.**

```bash
cd backend && uv run python -m scripts.eval mock
```

- [ ] **Step 6: Lint + types** on scripts:

```bash
cd backend && uv run ruff check scripts && uv run ruff format --check scripts && uv run mypy scripts
```

- [ ] **Step 7: Commit + push:**

```bash
git add backend/scripts/eval.py Makefile data/eval/reports/.gitkeep .gitignore
git commit -m "feat(eval): add typer CLI (mock/run/show-latest) and make eval targets"
git push
```

---

## Task 7: GitHub Actions — eval unit tests on every PR + manual full-eval workflow

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `.github/workflows/eval.yml`

- [ ] **Step 1: `.github/workflows/ci.yml`** already runs `uv run pytest` which covers the new `tests/eval/`. Verify by reading the existing yaml — no edit needed unless tests/eval/ is excluded somewhere (it isn't). Just confirm.

- [ ] **Step 2: Create `.github/workflows/eval.yml`** — manual-trigger full eval that needs `ANTHROPIC_API_KEY` secret:

```yaml
name: Eval (full, manual)

on:
  workflow_dispatch:
    inputs:
      tag:
        description: "Optional tag for the report (e.g. 'pre-release')"
        required: false
        default: ""

jobs:
  full-eval:
    name: Full eval against golden set
    runs-on: ubuntu-latest
    timeout-minutes: 30
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.5.4"
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run eval (mock — fast smoke first)
        run: uv run python -m scripts.eval mock

      - name: Run full eval (real Anthropic)
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: uv run python -m scripts.eval run

      - name: Upload HTML report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: data/eval/reports/*.html
```

- [ ] **Step 3: Validate yaml syntax:**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/eval.yml'))"
```

- [ ] **Step 4: Commit + push:**

```bash
git add .github/workflows/eval.yml
git commit -m "ci: add manual-trigger full-eval workflow (workflow_dispatch + ANTHROPIC secret)"
git push
```

---

## Task 8: Manual full-eval verification (sets baseline metrics)

This task requires `ANTHROPIC_API_KEY` + credit + seeded RAG.

- [ ] **Step 1: Confirm prerequisites:**

```bash
grep ANTHROPIC_API_KEY .env | grep -v "^#"
cd backend && uv run python -m scripts.seed status
```

- [ ] **Step 2: Run mock eval first (sanity):**

```bash
make eval-mock
```

Expected: JSON output + a `mock` row appended to `data/eval/reports/history.csv`.

- [ ] **Step 3: Run full eval against real Anthropic:**

```bash
make eval
```

Expected:
- 5 items × 3 samples = 15 Grader calls (≈$0.05 with Sonnet 4.6).
- HTML report saved to `data/eval/reports/<timestamp>_<sha>_real.html`.
- Latest row in history.csv shows three real metrics + PASS/FAIL flag.

- [ ] **Step 4: Open the HTML report in a browser:**

```bash
make eval-latest
```

Then open the HTML path it printed.

- [ ] **Step 5: Commit history.csv + dev-log entry:**

```bash
git add data/eval/reports/history.csv
git commit -m "data(eval): record V1 baseline metrics (mock + real)"
git push
```

---

## Acceptance Criteria

Plan 6 is complete when **all** of the following hold:

1. `cd backend && uv run pytest -v` passes 100% (Plans 1-5 + new tests/eval/, ~125 tests).
2. `cd backend && uv run lint-imports --config .importlinter` reports `5 kept, 0 broken`.
3. `cd backend && uv run mypy app tests` passes.
4. `make eval-mock` runs end-to-end, prints JSON, writes HTML, appends history.csv.
5. `.github/workflows/eval.yml` parses as valid yaml; manually triggerable via Actions UI.
6. With ANTHROPIC_API_KEY + credit + seeded RAG, `make eval` runs the full real-LLM eval and prints PASS or FAIL with concrete numbers.

---

## What's Next

Plan 7: **Polish & Optional Containerization**. Error handling per spec §8 (Sentry wiring, asyncRewake on Stop hooks, structured error envelopes), session-resume UI ("이어서 풀기"), SSE streaming for token-by-token Grader output (request/response → live), final README + portfolio doc, and *optional* Dockerfile + Docker Compose for the interviewer who insists. After Plan 7 the project is V1-complete and ready for the demo cycle.
