"""Tests for app.eval.runner."""

import json
from pathlib import Path

from app.eval.runner import EvalConfig, EvalReport, run_eval, to_json


def _exact_grader(_q: str, _m: str, _r: list[dict[str, object]], user: str) -> float:
    """Deterministic grader keyed on the tiny fixture's sample texts."""
    # tiny fixture: high="답입니다", mid="답", low="모르겠다"/"X"
    if "답입니다" in user:
        return 0.92
    if user == "답":
        return 0.55
    return 0.05


def _good_retriever(_query: str) -> list[str]:
    """Returns chunks containing the rubric_keyword '답'."""
    return ["답을 포함하는 청크 텍스트", "다른 청크"]


def _bad_retriever(_query: str) -> list[str]:
    """Returns chunks without '답'."""
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
    accuracy_floor = 0.5
    assert report.grading_accuracy >= accuracy_floor


def test_runner_recall_responds_to_retriever_quality(
    tiny_golden_path: Path,
) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    good = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    bad = run_eval(config=config, grader=_exact_grader, retriever=_bad_retriever)
    assert good.retrieval_recall_at_5 > bad.retrieval_recall_at_5


def test_runner_latency_tracker_populated(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    report = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    assert report.latency_p50 >= 0.0
    assert report.latency_p95 >= report.latency_p50


def test_passes_targets_when_metrics_above_thresholds(
    tiny_golden_path: Path,
) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    expected_items = 2
    expected_cases = 6
    report = EvalReport(
        config=config,
        timestamp_iso="2026-06-01T00:00:00Z",
        item_count=expected_items,
        case_count=expected_cases,
        grading_accuracy=0.83,
        retrieval_recall_at_5=0.80,
        latency_p50=2.0,
        latency_p95=7.0,
    )
    assert report.passes_targets() is True


def test_passes_targets_false_on_one_metric_miss(
    tiny_golden_path: Path,
) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    expected_items = 2
    expected_cases = 6
    report = EvalReport(
        config=config,
        timestamp_iso="2026-06-01T00:00:00Z",
        item_count=expected_items,
        case_count=expected_cases,
        grading_accuracy=0.83,
        retrieval_recall_at_5=0.80,
        latency_p50=2.0,
        latency_p95=9.5,  # over 8.0 target
    )
    assert report.passes_targets() is False


def test_to_json_round_trip(tiny_golden_path: Path) -> None:
    config = EvalConfig(dataset_path=tiny_golden_path)
    report = run_eval(config=config, grader=_exact_grader, retriever=_good_retriever)
    payload = to_json(report)
    parsed = json.loads(payload)
    assert "grading_accuracy" in parsed
    assert "passes_targets" in parsed
