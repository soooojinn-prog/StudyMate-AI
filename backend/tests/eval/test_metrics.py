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
    tolerance = 1e-9
    assert abs(result - expected) < tolerance


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
