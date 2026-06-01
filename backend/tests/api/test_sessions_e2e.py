"""End-to-end /sessions flow with mocked graph that mimics LangGraph semantics."""
from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def _payload(text: str):
    return type("M", (), {"content": [type("C", (), {"text": text})()]})()


def test_full_session_lifecycle(client: TestClient, fake_graph: MagicMock):
    # Phase 1: POST /sessions returns awaiting_answer
    create_state = {
        "topic": "정규화",
        "question": "정규화의 목적을 서술하시오.",
        "model_answer": "이상현상 방지.",
        "rubric": [{"point": "목적", "weight": 1.0, "keywords": ["이상현상"]}],
        "ref_chunk_ids": ["c1"],
    }
    fake_graph.invoke.return_value = create_state
    create_resp = client.post("/sessions", json={"user_id": "u1", "target_count": 3})
    assert create_resp.status_code == HTTPStatus.CREATED
    sid = create_resp.json()["session_id"]
    assert create_resp.json()["status"] == "awaiting_answer"

    # Phase 2: POST /sessions/{id}/answer returns graded
    fake_graph.invoke.return_value = {
        **create_state,
        "user_answer": "데이터 중복을 줄이기 위함.",
        "score": 0.5,
        "rationale": "목적 절반만",
        "feedback": "이상현상을 명시하세요.",
        "missing_points": ["이상현상"],
        "questions_done": 1,
    }
    answer_resp = client.post(
        f"/sessions/{sid}/answer",
        json={"user_answer": "데이터 중복을 줄이기 위함."},
    )
    assert answer_resp.status_code == HTTPStatus.OK
    expected_score = 0.5
    assert answer_resp.json()["score"] == expected_score
    assert answer_resp.json()["status"] == "graded"

    # Phase 3: GET /sessions/{id} returns the same graded snapshot
    fake_graph.get_state.return_value = MagicMock(values=fake_graph.invoke.return_value)
    get_resp = client.get(f"/sessions/{sid}")
    assert get_resp.status_code == HTTPStatus.OK
    assert get_resp.json()["score"] == expected_score
    assert get_resp.json()["session_id"] == sid
