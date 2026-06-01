"""Tests for app.api.schemas.sessions."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.schemas.sessions import (
    CreateSessionRequest,
    RubricItemDTO,
    SessionStateDTO,
    SubmitAnswerRequest,
)


def test_create_session_defaults():
    req = CreateSessionRequest()
    expected_target = 5
    assert req.user_id == "local-user"
    assert req.target_count == expected_target
    assert req.user_intent == "자유 학습"


def test_create_session_rejects_zero_target_count():
    with pytest.raises(ValidationError):
        CreateSessionRequest(target_count=0)


def test_create_session_rejects_huge_target_count():
    huge_target = 100
    with pytest.raises(ValidationError):
        CreateSessionRequest(target_count=huge_target)


def test_submit_answer_rejects_empty():
    with pytest.raises(ValidationError):
        SubmitAnswerRequest(user_answer="")


def test_submit_answer_caps_at_4000_chars():
    too_long = "x" * 4001
    with pytest.raises(ValidationError):
        SubmitAnswerRequest(user_answer=too_long)


def test_session_state_dto_round_trips():
    state = SessionStateDTO(
        session_id="s1",
        user_id="u1",
        status="awaiting_answer",
        topic="정규화",
        difficulty=2,
        target_weakness=True,
        question="q?",
        rubric=[RubricItemDTO(point="p", weight=1.0, keywords=["k"])],
        created_at=datetime.now(tz=UTC),
    )
    restored = SessionStateDTO.model_validate(state.model_dump())
    assert restored == state
