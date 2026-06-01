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
