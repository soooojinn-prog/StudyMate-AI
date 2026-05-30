"""Tests for the health endpoint."""

from http import HTTPStatus

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body
    assert "version" in body
