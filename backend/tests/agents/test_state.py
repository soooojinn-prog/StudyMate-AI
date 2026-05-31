"""Tests for app.agents.state."""
import pytest
from pydantic import ValidationError

from app.agents.state import GradingResult, QuestionPayload, RubricItem, SessionState


def test_rubric_item_rejects_out_of_range_weight():
    with pytest.raises(ValidationError):
        RubricItem(point="x", weight=1.5)


def test_rubric_item_defaults_empty_keywords():
    item = RubricItem(point="정규화 정의", weight=0.3)
    assert item.keywords == []


def test_question_payload_round_trips():
    payload = QuestionPayload(
        question="정규화의 목적을 서술하시오.",
        model_answer="이상현상 방지.",
        rubric=[RubricItem(point="목적 명시", weight=0.5, keywords=["이상현상"])],
    )
    restored = QuestionPayload.model_validate(payload.model_dump())
    assert restored == payload


def test_grading_result_rejects_score_above_one():
    with pytest.raises(ValidationError):
        GradingResult(score=1.5, rationale="ok", feedback="")


def test_session_state_is_partial_typed_dict():
    # SessionState uses total=False — empty dict is valid
    state: SessionState = {}
    state["user_id"] = "u1"
    state["topic"] = "정규화"
    assert state["topic"] == "정규화"
