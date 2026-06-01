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
            writer.writerow(
                [
                    "timestamp",
                    "git_sha",
                    "tag",
                    "item_count",
                    "case_count",
                    "grading_accuracy",
                    "retrieval_recall_at_5",
                    "latency_p50",
                    "latency_p95",
                    "passes_targets",
                ]
            )
        writer.writerow(
            [
                report.timestamp_iso,
                report.config.git_sha,
                report.config.tag,
                report.item_count,
                report.case_count,
                f"{report.grading_accuracy:.4f}",
                f"{report.retrieval_recall_at_5:.4f}",
                f"{report.latency_p50:.3f}",
                f"{report.latency_p95:.3f}",
                "PASS" if report.passes_targets() else "FAIL",
            ]
        )
    return html_path
