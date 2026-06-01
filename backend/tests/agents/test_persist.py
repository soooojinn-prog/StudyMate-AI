"""Tests for app.agents.nodes.persist — deterministic, no LLM."""

from unittest.mock import MagicMock

from app.agents.nodes.persist import persist_node


def test_persist_increments_questions_done():
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "questions_done": 0,
        "target_count": 5,
        "score": 0.8,
        "topic": "정규화",
    }
    result = persist_node(state, adapter=None)
    expected_count = 1
    assert result["questions_done"] == expected_count


def test_persist_calls_adapter_when_provided():
    adapter = MagicMock()
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "questions_done": 2,
        "target_count": 5,
        "score": 0.4,
        "topic": "네트워크",
        "question": "q",
        "user_answer": "a",
        "rationale": "r",
        "feedback": "fb",
    }
    persist_node(state, adapter=adapter)
    adapter.assert_called_once()
    payload = adapter.call_args.args[0]
    expected_score = 0.4
    assert payload["session_id"] == "s1"
    assert payload["score"] == expected_score
    assert payload["topic"] == "네트워크"


def test_persist_works_when_starting_at_zero():
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "score": 0.5,
        "topic": "x",
    }
    result = persist_node(state, adapter=None)
    expected_count = 1
    assert result["questions_done"] == expected_count  # defaults questions_done to 0 → +1


def test_persist_does_not_explode_on_missing_optional_fields():
    state = {"user_id": "u1", "session_id": "s1"}
    # no score, no topic — adapter still gets called with whatever's there
    adapter = MagicMock()
    persist_node(state, adapter=adapter)
    adapter.assert_called_once()
