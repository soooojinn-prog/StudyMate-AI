"""GET /sessions/{id} — snapshot the latest graph state."""

from http import HTTPStatus
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_get_session_returns_current_state(client: TestClient, fake_graph: MagicMock):
    fake_graph.invoke.return_value = {
        "topic": "정규화",
        "question": "q",
        "rubric": [],
        "ref_chunk_ids": [],
    }
    create_resp = client.post("/sessions", json={"user_id": "u1"})
    sid = create_resp.json()["session_id"]

    fake_graph.get_state.return_value = MagicMock(
        values={
            "topic": "정규화",
            "question": "q",
            "score": 0.7,
            "rubric": [],
        }
    )
    response = client.get(f"/sessions/{sid}")
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    expected_score = 0.7
    assert body["session_id"] == sid
    assert body["score"] == expected_score
    assert body["topic"] == "정규화"


def test_get_session_404_for_unknown(client: TestClient):
    response = client.get("/sessions/nonexistent")
    assert response.status_code == HTTPStatus.NOT_FOUND
