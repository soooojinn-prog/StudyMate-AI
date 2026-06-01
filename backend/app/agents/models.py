"""Pydantic shapes used at LLM I/O boundaries.

These are distinct from `state.py` because LLM outputs need strict
schema validation; SessionState (TypedDict) is more permissive to keep
LangGraph happy.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoordinatorDecision(BaseModel):
    """Haiku's output for the Coordinator node."""

    topic: str
    difficulty: int = Field(ge=1, le=3)
    target_weakness: bool
    reason: str = ""  # short justification, useful for logs


class QuestionGenerationRequest(BaseModel):
    topic: str
    difficulty: int = Field(ge=1, le=3)
    context_chunks: list[str]


class GradingRequest(BaseModel):
    question: str
    model_answer: str
    rubric: list[dict[str, object]]
    user_answer: str
