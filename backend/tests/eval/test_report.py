"""Tests for app.eval.report — HTML render + history.csv append."""

import csv
from pathlib import Path

from app.eval.report import render_html, save_report
from app.eval.runner import EvalConfig, EvalReport, PerCaseResult

_EXPECTED_HEADER_THEN_ONE_DATA_ROW = 2
_EXPECTED_HEADER_PLUS_TWO_DATA_ROWS = 3


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
            PerCaseResult(
                item_id="t001",
                topic="테스트",
                tier="high",
                predicted_score=0.92,
                human_score=0.9,
                delta=0.02,
            ),
            PerCaseResult(
                item_id="t001",
                topic="테스트",
                tier="low",
                predicted_score=0.55,
                human_score=0.1,
                delta=0.45,
            ),
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
    assert len(rows) == _EXPECTED_HEADER_THEN_ONE_DATA_ROW
    assert rows[0][0] == "timestamp"
    assert rows[1][1] == "abc1234"
    assert rows[1][-1] == "PASS"


def test_save_report_appends_without_duplicating_header(tmp_path: Path) -> None:
    report = _sample_report(tmp_path)
    out = tmp_path / "out"
    save_report(report, output_dir=out)
    save_report(report, output_dir=out, filename_suffix="run2")
    rows = list(csv.reader((out / "history.csv").open(encoding="utf-8")))
    assert len(rows) == _EXPECTED_HEADER_PLUS_TWO_DATA_ROWS
