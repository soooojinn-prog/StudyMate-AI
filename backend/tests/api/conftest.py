"""Shared fixtures for app.api tests."""
from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_graph, get_session_store
from app.api.session_store import SessionStore
from app.main import create_app


@pytest.fixture
def fake_graph() -> MagicMock:
    """A mock graph that records invoke / update_state calls."""
    return MagicMock()


@pytest.fixture
def session_store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def client(fake_graph: MagicMock, session_store: SessionStore) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_graph] = lambda: fake_graph
    app.dependency_overrides[get_session_store] = lambda: session_store
    with TestClient(app) as test_client:
        yield test_client
