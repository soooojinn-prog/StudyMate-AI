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

import typer

from app.core.settings import settings
from app.eval.dataset import load_golden
from app.eval.report import save_report
from app.eval.runner import EvalConfig, run_eval, to_json

app = typer.Typer(add_completion=False, help="Run the StudyMate eval harness")


_DEFAULT_REPORTS_DIR = settings.studymate_db.parent / "eval" / "reports"
_HISTORY_MIN_ROWS_WITH_DATA = 2  # header + at least one data row


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or "dev"
    except (FileNotFoundError, OSError):  # pragma: no cover
        return "dev"


def _fake_grader(_q: str, _m: str, _r: list[dict[str, object]], user: str) -> float:
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
    from app.agents.state import SessionState  # noqa: PLC0415
    from app.rag.retriever import default_retriever  # noqa: PLC0415

    client = Anthropic(api_key=settings.anthropic_api_key)
    retriever_inst = default_retriever()

    def _real_grader(
        question: str, model_answer: str, rubric: list[dict[str, object]], user: str
    ) -> float:
        state: SessionState = {
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
    if len(rows) < _HISTORY_MIN_ROWS_WITH_DATA:  # only header
        typer.echo("(history is empty)")
        raise typer.Exit(code=0)
    header, latest = rows[0], rows[-1]
    typer.echo(json.dumps(dict(zip(header, latest, strict=True)), ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app() or 0)
