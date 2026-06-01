"""POST /sessions/{id}/answer — submit learner answer + resume graph."""
from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_submit_answer_returns_grading(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {
        "topic": "정규화",
        "question": "q",
        "rubric": [],
        "ref_chunk_ids": [],
    }
    create_resp = client.post("/sessions", json={"user_id": "u1"})
    session_id = create_resp.json()["session_id"]

    fake_graph.invoke.side_effect = None
    fake_graph.invoke.return_value = {
        "topic": "정규화",
        "question": "q",
        "rubric": [],
        "user_answer": "answer text",
        "score": 0.83,
        "rationale": "ok",
        "feedback": "보강 가이드",
        "missing_points": ["이상현상"],
        "questions_done": 1,
    }
    response = client.post(
        f"/sessions/{session_id}/answer",
        json={"user_answer": "answer text"},
    )
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["status"] == "graded"
    expected_score = 0.83
    assert body["score"] == expected_score
    assert body["missing_points"] == ["이상현상"]
    fake_graph.update_state.assert_called_once()


def test_submit_answer_rejects_unknown_session(client: TestClient):
    response = client.post(
        "/sessions/00000000-0000-0000-0000-000000000000/answer",
        json={"user_answer": "x"},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_submit_answer_rejects_empty(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {"question": "q", "rubric": [], "ref_chunk_ids": []}
    create_resp = client.post("/sessions", json={})
    sid = create_resp.json()["session_id"]
    response = client.post(f"/sessions/{sid}/answer", json={"user_answer": ""})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_submit_answer_503_when_graph_disabled(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {"question": "q", "rubric": [], "ref_chunk_ids": []}
    create_resp = client.post("/sessions", json={})
    sid = create_resp.json()["session_id"]

    from app.api.dependencies import get_graph  # noqa: PLC0415

    client.app.dependency_overrides[get_graph] = lambda: None
    response = client.post(f"/sessions/{sid}/answer", json={"user_answer": "a"})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
