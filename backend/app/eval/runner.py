"""Eval runner — iterate the golden set, call Grader + Retriever, compute metrics."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.eval.dataset import GoldenItem, load_golden
from app.eval.metrics import LatencyTracker, grading_accuracy, retrieval_recall_at_k

_ACCURACY_TARGET = 0.80
_RECALL_TARGET = 0.75
_LATENCY_TARGET_SECONDS = 8.0
_GRADING_TOLERANCE = 0.15
_RETRIEVAL_K = 5


class _GraderCallable(Protocol):
    """Anything that takes (question, model_answer, rubric, user_answer) → score 0..1."""

    def __call__(
        self,
        question: str,
        model_answer: str,
        rubric: list[dict[str, object]],
        user_answer: str,
        /,
    ) -> float: ...


class _RetrieverCallable(Protocol):
    """Anything that takes a query string → list of chunk text."""

    def __call__(self, query: str, /) -> list[str]: ...


@dataclass(frozen=True)
class EvalConfig:
    """Parameters for a single eval run."""

    dataset_path: Path
    git_sha: str = "dev"
    tag: str = ""


@dataclass
class PerCaseResult:
    """One grading case outcome (item × sample answer)."""

    item_id: str
    topic: str
    tier: str
    predicted_score: float
    human_score: float
    delta: float


@dataclass
class EvalReport:
    """Aggregate metrics + per-case detail for a single eval run."""

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
        """True if all three metrics meet the spec §6.2 targets."""
        return (
            self.grading_accuracy >= _ACCURACY_TARGET
            and self.retrieval_recall_at_5 >= _RECALL_TARGET
            and self.latency_p95 <= _LATENCY_TARGET_SECONDS
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
        recalls.append(retrieval_recall_at_k(item.rubric_keywords, chunks, k=_RETRIEVAL_K))

        # grading: 3 sample answers per item
        for sample in item.sample_answers:
            t0 = time.perf_counter()
            score = grader(item.question, item.model_answer, item.rubric, sample.text)
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
        grading_accuracy=grading_accuracy(predictions, truths, tolerance=_GRADING_TOLERANCE),
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
