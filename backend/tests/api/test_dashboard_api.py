"""GET /dashboard/stats — returns weakness + topic-level stats."""

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_db_session
from app.learning.database import Base
from app.learning.models import StudySession, User
from app.learning.repository import SessionRepository
from app.main import create_app


def _payload(topic: str, score: float) -> dict[str, Any]:
    return {
        "user_id": "u1",
        "session_id": "s1",
        "topic": topic,
        "difficulty": 2,
        "question": "q",
        "model_answer": "m",
        "rubric": [],
        "ref_chunk_ids": [],
        "user_answer": "ua",
        "score": score,
        "rationale": "r",
        "feedback": "f",
        "missing_points": [],
    }


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


def _seed_history(session: Session) -> None:
    session.add(User(id="u1", nickname="n", created_at=datetime.now(tz=UTC)))
    session.add(
        StudySession(
            id="s1",
            user_id="u1",
            mode="topic",
            target_count=10,
            thread_id="s1",
            started_at=datetime.now(tz=UTC),
        )
    )
    session.flush()
    repo = SessionRepository(session)
    for s in [0.3, 0.4, 0.35]:
        repo.record_answer(_payload("네트워크", s))
    for s in [0.8, 0.85, 0.9]:
        repo.record_answer(_payload("정규화", s))
    session.commit()


def test_stats_returns_weakness_and_topic_stats(client: TestClient, db_session: Session) -> None:
    _seed_history(db_session)
    response = client.get("/dashboard/stats", params={"user_id": "u1"})
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["user_id"] == "u1"
    expected_total = 6
    assert body["total_answers"] == expected_total
    assert body["weak_topics"][0]["topic"] == "네트워크"
    topics = {t["topic"] for t in body["topic_stats"]}
    assert topics == {"네트워크", "정규화"}


def test_stats_empty_for_unknown_user(client: TestClient, db_session: Session) -> None:
    response = client.get("/dashboard/stats", params={"user_id": "ghost"})
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total_answers"] == 0
    assert body["weak_topics"] == []
