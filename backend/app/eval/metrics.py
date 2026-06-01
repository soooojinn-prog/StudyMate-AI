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
