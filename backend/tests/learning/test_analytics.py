"""Tests for compute_weakness — deterministic, no LLM."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.learning.analytics import compute_weakness
from app.learning.models import StudySession, User
from app.learning.repository import SessionRepository


def _seed_basic(session: Session, user_id: str = "u1", session_id: str = "s1") -> None:
    session.add(User(id=user_id, nickname="n", created_at=datetime.now(tz=UTC)))
    session.add(
        StudySession(
            id=session_id,
            user_id=user_id,
            mode="topic",
            target_count=10,
            thread_id=session_id,
            started_at=datetime.now(tz=UTC),
        )
    )
    session.flush()


def _record_n(repo: SessionRepository, topic: str, scores: list[float]) -> None:
    for s in scores:
        repo.record_answer(
            {
                "user_id": "u1",
                "session_id": "s1",
                "topic": topic,
                "difficulty": 2,
                "question": "q",
                "model_answer": "m",
                "rubric": [],
                "ref_chunk_ids": [],
                "user_answer": "ua",
                "score": s,
                "rationale": "r",
                "feedback": "f",
                "missing_points": [],
            }
        )


def test_compute_weakness_ranks_low_average_first(db_session: Session) -> None:
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    _record_n(repo, "정규화", [0.9, 0.95, 0.92])  # strong
    _record_n(repo, "네트워크", [0.3, 0.4, 0.35])  # weak
    _record_n(repo, "SQL", [0.6, 0.65, 0.7])  # mid
    db_session.commit()

    weak = compute_weakness(repo, user_id="u1", lookback_days=30)
    expected_count = 3
    assert len(weak) == expected_count
    assert weak[0].topic == "네트워크"
    assert weak[1].topic == "SQL"
    assert weak[2].topic == "정규화"


def test_compute_weakness_excludes_topics_with_fewer_than_3_samples(
    db_session: Session,
) -> None:
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    _record_n(repo, "정규화", [0.5, 0.6, 0.7])  # ≥3 — counts
    _record_n(repo, "네트워크", [0.1, 0.2])  # only 2 — excluded
    db_session.commit()
    weak = compute_weakness(repo, user_id="u1", lookback_days=30)
    expected_count = 1
    assert len(weak) == expected_count
    assert weak[0].topic == "정규화"


def test_compute_weakness_returns_at_most_top_3(db_session: Session) -> None:
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    for t in ["a", "b", "c", "d", "e"]:
        _record_n(repo, t, [0.5, 0.5, 0.5])
    db_session.commit()
    weak = compute_weakness(repo, user_id="u1", lookback_days=30)
    expected_top = 3
    assert len(weak) == expected_top


def test_compute_weakness_empty_for_no_data(db_session: Session) -> None:
    _seed_basic(db_session)
    repo = SessionRepository(db_session)
    db_session.commit()
    assert compute_weakness(repo, user_id="u1", lookback_days=30) == []
