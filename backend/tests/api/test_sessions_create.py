"""POST /sessions — start a new learning session."""
from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_create_session_returns_question(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {
        "user_id": "local-user",
        "session_id": "ignored-by-route",
        "topic": "정규화",
        "difficulty": 2,
        "target_weakness": False,
        "question": "정규화의 목적을 서술하시오.",
        "model_answer": "이상현상 방지.",
        "rubric": [{"point": "목적", "weight": 1.0, "keywords": ["이상현상"]}],
        "ref_chunk_ids": ["c1"],
        "questions_done": 0,
        "target_count": 5,
    }
    response = client.post("/sessions", json={"user_id": "u1", "target_count": 5})
    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body["status"] == "awaiting_answer"
    assert body["question"] == "정규화의 목적을 서술하시오."
    assert body["topic"] == "정규화"
    assert body["user_id"] == "u1"
    assert body["session_id"]


def test_create_session_uses_defaults(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {
        "topic": "x",
        "question": "q",
        "rubric": [],
        "ref_chunk_ids": [],
    }
    response = client.post("/sessions", json={})
    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    expected_target = 5
    assert body["user_id"] == "local-user"
    assert body["target_count"] == expected_target


def test_create_session_rejects_invalid_target(client: TestClient):
    response = client.post("/sessions", json={"target_count": 0})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_session_returns_503_when_graph_disabled(
    client: TestClient, fake_graph: MagicMock,
):
    from app.api.dependencies import get_graph  # noqa: PLC0415

    client.app.dependency_overrides[get_graph] = lambda: None
    response = client.post("/sessions", json={})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
