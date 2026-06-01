"""Tests for app.learning.models — table creation + round-trip."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.learning.database import Base
from app.learning.models import Answer, QuestionInstance, StudySession, User


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def test_user_round_trip(session: Session) -> None:
    user = User(id="u1", nickname="홍길동", created_at=datetime.now(tz=UTC))
    session.add(user)
    session.commit()
    fetched = session.get(User, "u1")
    assert fetched is not None
    assert fetched.nickname == "홍길동"


def test_full_session_chain(session: Session) -> None:
    user = User(id="u1", nickname="홍길동", created_at=datetime.now(tz=UTC))
    sess = StudySession(
        id="s1",
        user_id="u1",
        mode="weakness",
        target_count=5,
        thread_id="s1",
        started_at=datetime.now(tz=UTC),
    )
    q = QuestionInstance(
        id="q1",
        session_id="s1",
        seq=1,
        topic="정규화",
        difficulty=2,
        question_text="문제",
        model_answer="답",
        rubric_json=[{"point": "p", "weight": 1.0, "keywords": []}],
        ref_chunk_ids=["c1"],
        generated_at=datetime.now(tz=UTC),
    )
    a = Answer(
        id="a1",
        question_instance_id="q1",
        user_answer="학습자 답",
        score=0.7,
        rationale="r",
        feedback="f",
        missing_points_json=[],
        graded_at=datetime.now(tz=UTC),
    )
    session.add_all([user, sess, q, a])
    session.commit()
    expected_score = 0.7
    answer = session.get(Answer, "a1")
    assert answer is not None
    assert answer.score == expected_score
    assert answer.question_instance.topic == "정규화"


def test_one_answer_per_question_constraint(session: Session) -> None:
    user = User(id="u1", nickname="n", created_at=datetime.now(tz=UTC))
    sess = StudySession(
        id="s1",
        user_id="u1",
        mode="topic",
        target_count=1,
        thread_id="s1",
        started_at=datetime.now(tz=UTC),
    )
    q = QuestionInstance(
        id="q1",
        session_id="s1",
        seq=1,
        topic="x",
        difficulty=1,
        question_text="q",
        model_answer="m",
        rubric_json=[],
        ref_chunk_ids=[],
        generated_at=datetime.now(tz=UTC),
    )
    a1 = Answer(
        id="a1",
        question_instance_id="q1",
        user_answer="x",
        score=0.5,
        rationale="r",
        feedback="f",
        missing_points_json=[],
        graded_at=datetime.now(tz=UTC),
    )
    session.add_all([user, sess, q, a1])
    session.commit()

    a2 = Answer(
        id="a2",
        question_instance_id="q1",
        user_answer="y",
        score=0.6,
        rationale="r2",
        feedback="f2",
        missing_points_json=[],
        graded_at=datetime.now(tz=UTC),
    )
    session.add(a2)
    with pytest.raises(IntegrityError):
        session.commit()


def test_cascade_delete_session_removes_questions_and_answers(session: Session) -> None:
    user = User(id="u1", nickname="n", created_at=datetime.now(tz=UTC))
    sess = StudySession(
        id="s1",
        user_id="u1",
        mode="topic",
        target_count=1,
        thread_id="s1",
        started_at=datetime.now(tz=UTC),
    )
    q = QuestionInstance(
        id="q1",
        session_id="s1",
        seq=1,
        topic="x",
        difficulty=1,
        question_text="q",
        model_answer="m",
        rubric_json=[],
        ref_chunk_ids=[],
        generated_at=datetime.now(tz=UTC),
    )
    a = Answer(
        id="a1",
        question_instance_id="q1",
        user_answer="x",
        score=0.5,
        rationale="r",
        feedback="f",
        missing_points_json=[],
        graded_at=datetime.now(tz=UTC),
    )
    session.add_all([user, sess, q, a])
    session.commit()

    session.delete(sess)
    session.commit()
    assert session.get(QuestionInstance, "q1") is None
    assert session.get(Answer, "a1") is None
