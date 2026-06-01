"""Tests for app.agents.nodes.grader."""

from app.agents.nodes.grader import grader_node


def test_grader_produces_score_rationale_feedback(make_anthropic_client):
    client = make_anthropic_client(
        {
            "score": 0.83,
            "rationale": "정규화 1NF, 2NF, 3NF 조건 모두 정확하나 목적 누락.",
            "feedback": "정규화의 목적을 '이상현상 방지'로 보강하세요.",
            "missing_points": ["이상현상"],
        }
    )
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "question": "정규화의 목적을 서술하시오.",
        "model_answer": "이상현상 방지.",
        "rubric": [{"point": "목적", "weight": 0.5, "keywords": ["이상현상"]}],
        "user_answer": "정규화는 데이터 중복을 줄이는 것입니다.",
    }
    result = grader_node(state, client=client, model="claude-sonnet-4-6")
    expected_score = 0.83
    assert result["score"] == expected_score
    assert "정규화" in result["rationale"]
    assert result["missing_points"] == ["이상현상"]


def test_grader_retries_once_on_malformed_then_falls_back(make_anthropic_client):
    client = make_anthropic_client({})
    # first call returns garbage, second call returns valid JSON
    bad = type("R", (), {"text": "not json"})()
    good = type(
        "R",
        (),
        {"text": ('{"score": 0.7, "rationale": "ok", "feedback": "ok", "missing_points": []}')},
    )()
    client.messages.create.side_effect = [
        type("M", (), {"content": [bad]})(),
        type("M", (), {"content": [good]})(),
    ]
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "question": "q",
        "model_answer": "a",
        "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
        "user_answer": "x",
    }
    result = grader_node(state, client=client, model="claude-sonnet-4-6")
    expected_score = 0.7
    expected_call_count = 2
    assert result["score"] == expected_score
    assert client.messages.create.call_count == expected_call_count  # original + 1 retry


def test_grader_falls_back_to_half_score_on_double_failure(make_anthropic_client):
    client = make_anthropic_client({})
    bad1 = type("R", (), {"text": "not json"})()
    bad2 = type("R", (), {"text": "still not json"})()
    client.messages.create.side_effect = [
        type("M", (), {"content": [bad1]})(),
        type("M", (), {"content": [bad2]})(),
    ]
    state = {
        "user_id": "u1",
        "session_id": "s1",
        "question": "q",
        "model_answer": "a",
        "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
        "user_answer": "x",
    }
    result = grader_node(state, client=client, model="claude-sonnet-4-6")
    # spec §8 fallback: 0.5 + error flag
    expected_fallback_score = 0.5
    assert result["score"] == expected_fallback_score
    assert "parse_failed" in result.get("feedback", "")
