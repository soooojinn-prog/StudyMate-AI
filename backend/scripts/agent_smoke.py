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
from typing import Any

import typer
from anthropic import Anthropic

from app.agents.checkpointer import make_checkpointer
from app.agents.graph import build_graph, resume_session, run_session
from app.core.settings import settings
from app.rag.ingest.topics import load_topics
from app.rag.retriever import default_retriever

app = typer.Typer(add_completion=False, help="Manual smoke for the agent graph")


def _print_adapter(payload: dict[str, Any]) -> None:
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
