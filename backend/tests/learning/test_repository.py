"""Tests for SessionRepository."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.learning.models import StudySession, User
from app.learning.repository import SessionRepository


def _seed_user(session: Session, user_id: str = "u1") -> None:
    session.add(User(id=user_id, nickname="n", created_at=datetime.now(tz=UTC)))
    session.flush()


def _seed_session(session: Session, session_id: str = "s1", user_id: str = "u1") -> None:
    session.add(
        StudySession(
            id=session_id,
            user_id=user_id,
            mode="topic",
            target_count=5,
            thread_id=session_id,
            started_at=datetime.now(tz=UTC),
        )
    )
    session.flush()


def test_record_answer_writes_question_and_answer_rows(db_session: Session) -> None:
    _seed_user(db_session)
    _seed_session(db_session)
    repo = SessionRepository(db_session)

    payload = {
        "user_id": "u1",
        "session_id": "s1",
        "topic": "정규화",
        "difficulty": 2,
        "question": "Q?",
        "model_answer": "A.",
        "rubric": [{"point": "p", "weight": 1.0, "keywords": ["k"]}],
        "ref_chunk_ids": ["c1"],
        "user_answer": "ua",
        "score": 0.7,
        "rationale": "r",
        "feedback": "f",
        "missing_points": ["x"],
    }
    repo.record_answer(payload)
    db_session.commit()

    answers = repo.recent_answers("u1", days=30)
    expected_count = 1
    assert len(answers) == expected_count
    assert answers[0].question_instance.topic == "정규화"
    expected_score = 0.7
    assert answers[0].score == expected_score


def test_record_answer_increments_seq_per_session(db_session: Session) -> None:
    _seed_user(db_session)
    _seed_session(db_session)
    repo = SessionRepository(db_session)
    base_payload = {
        "user_id": "u1",
        "session_id": "s1",
        "topic": "정규화",
        "difficulty": 1,
        "question": "Q",
        "model_answer": "A",
        "rubric": [],
        "ref_chunk_ids": [],
        "user_answer": "ua",
        "rationale": "r",
        "feedback": "f",
        "missing_points": [],
    }
    repo.record_answer({**base_payload, "score": 0.5})
    repo.record_answer({**base_payload, "score": 0.8})
    db_session.commit()
    answers = repo.recent_answers("u1", days=30)
    expected_count = 2
    assert len(answers) == expected_count
    assert {a.question_instance.seq for a in answers} == {1, 2}


def test_recent_answers_filters_by_user(db_session: Session) -> None:
    _seed_user(db_session, "u1")
    _seed_user(db_session, "u2")
    _seed_session(db_session, "s1", "u1")
    _seed_session(db_session, "s2", "u2")
    repo = SessionRepository(db_session)
    for uid, sid in [("u1", "s1"), ("u2", "s2")]:
        repo.record_answer(
            {
                "user_id": uid,
                "session_id": sid,
                "topic": "x",
                "difficulty": 1,
                "question": "q",
                "model_answer": "m",
                "rubric": [],
                "ref_chunk_ids": [],
                "user_answer": "ua",
                "score": 0.5,
                "rationale": "r",
                "feedback": "f",
                "missing_points": [],
            }
        )
    db_session.commit()
    expected_count = 1
    assert len(repo.recent_answers("u1", days=30)) == expected_count
    assert len(repo.recent_answers("u2", days=30)) == expected_count


def test_recent_answers_filters_by_lookback(db_session: Session) -> None:
    _seed_user(db_session)
    _seed_session(db_session)
    repo = SessionRepository(db_session)
    repo.record_answer(
        {
            "user_id": "u1",
            "session_id": "s1",
            "topic": "x",
            "difficulty": 1,
            "question": "q",
            "model_answer": "m",
            "rubric": [],
            "ref_chunk_ids": [],
            "user_answer": "ua",
            "score": 0.5,
            "rationale": "r",
            "feedback": "f",
            "missing_points": [],
        }
    )
    db_session.commit()
    # Backdate the answer beyond the lookback
    answer = repo.recent_answers("u1", days=30)[0]
    answer.graded_at = datetime.now(tz=UTC) - timedelta(days=60)
    db_session.commit()
    assert repo.recent_answers("u1", days=30) == []
