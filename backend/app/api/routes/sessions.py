"""Session lifecycle endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import GraphDep, SessionStoreDep
from app.api.schemas.sessions import (
    CreateSessionRequest,
    RubricItemDTO,
    SessionStateDTO,
)
from app.api.session_store import SessionRecord

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _state_to_dto(
    *,
    raw: dict[str, Any],
    record: SessionRecord,
    status_label: str,
) -> SessionStateDTO:
    rubric_dtos = [
        RubricItemDTO(
            point=str(r.get("point", "")),
            weight=float(r.get("weight", 0.0)),
            keywords=list(r.get("keywords", [])),
        )
        for r in raw.get("rubric", [])
    ]
    return SessionStateDTO(
        session_id=record.session_id,
        user_id=record.user_id,
        status=status_label,  # type: ignore[arg-type]
        topic=raw.get("topic"),
        difficulty=raw.get("difficulty"),
        target_weakness=raw.get("target_weakness"),
        question=raw.get("question"),
        model_answer=raw.get("model_answer"),
        rubric=rubric_dtos,
        ref_chunk_ids=list(raw.get("ref_chunk_ids", [])),
        user_answer=raw.get("user_answer"),
        score=raw.get("score"),
        rationale=raw.get("rationale"),
        feedback=raw.get("feedback"),
        missing_points=list(raw.get("missing_points", [])),
        questions_done=int(raw.get("questions_done", 0)),
        target_count=record.target_count,
        created_at=record.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionStateDTO)
def create_session(
    req: CreateSessionRequest, graph: GraphDep, store: SessionStoreDep
) -> SessionStateDTO:
    if graph is None:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="agent_graph_unavailable — set ANTHROPIC_API_KEY and restart",
        )
    session_id = str(uuid.uuid4())
    record = SessionRecord(
        session_id=session_id,
        user_id=req.user_id,
        target_count=req.target_count,
        user_intent=req.user_intent,
        created_at=datetime.now(tz=UTC),
    )
    store.add(record)

    config = {"configurable": {"thread_id": session_id}}
    initial = {
        "user_id": req.user_id,
        "session_id": session_id,
        "questions_done": 0,
        "target_count": req.target_count,
    }
    raw_state = graph.invoke(initial, config=config) or {}
    return _state_to_dto(raw=raw_state, record=record, status_label="awaiting_answer")
