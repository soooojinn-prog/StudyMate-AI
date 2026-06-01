"""HTTP request/response shapes for /sessions endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SessionStatus = Literal["awaiting_answer", "graded", "completed"]


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="local-user")
    target_count: int = Field(default=5, ge=1, le=20)
    user_intent: str = Field(default="자유 학습")


class RubricItemDTO(BaseModel):
    point: str
    weight: float
    keywords: list[str]


class SessionStateDTO(BaseModel):
    """The snapshot returned after run_session / resume_session."""

    session_id: str
    user_id: str
    status: SessionStatus
    topic: str | None = None
    difficulty: int | None = None
    target_weakness: bool | None = None
    question: str | None = None
    model_answer: str | None = None
    rubric: list[RubricItemDTO] = Field(default_factory=list)
    ref_chunk_ids: list[str] = Field(default_factory=list)
    user_answer: str | None = None
    score: float | None = None
    rationale: str | None = None
    feedback: str | None = None
    missing_points: list[str] = Field(default_factory=list)
    questions_done: int = 0
    target_count: int = 5
    created_at: datetime


class SubmitAnswerRequest(BaseModel):
    user_answer: str = Field(min_length=1, max_length=4000)
