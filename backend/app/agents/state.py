"""Shared graph state and nested value objects."""
from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class RubricItem(BaseModel):
    """One scored criterion within a grading rubric."""

    point: str
    weight: float = Field(ge=0.0, le=1.0)
    keywords: list[str] = Field(default_factory=list)


class QuestionPayload(BaseModel):
    """The QuestionGenerator's structured output."""

    question: str
    model_answer: str
    rubric: list[RubricItem]


class GradingResult(BaseModel):
    """The Grader's structured output."""

    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    feedback: str
    missing_points: list[str] = Field(default_factory=list)


class SessionState(TypedDict, total=False):
    """LangGraph shared state.

    session_id is used directly as the LangGraph checkpointer thread_id
    (1:1 mapping; see spec §4.2).
    """

    user_id: str
    session_id: str

    # Coordinator output
    topic: str
    difficulty: int
    target_weakness: bool

    # QuestionGenerator output
    question: str
    model_answer: str
    # serialized RubricItem (LangGraph state must be JSON-friendly)
    rubric: list[dict[str, object]]
    ref_chunk_ids: list[str]

    # learner input (set by API layer between QGen and Grader)
    user_answer: str

    # Grader output
    score: float
    rationale: str
    feedback: str
    missing_points: list[str]

    # loop control
    questions_done: int
    target_count: int
