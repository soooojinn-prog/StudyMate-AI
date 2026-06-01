"""SQLAlchemy 2.0 declarative models for learning records.

Matches spec §5.1 exactly. The LangGraph SqliteSaver uses its own
tables in the same SQLite file — no schema collision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.learning.database import Base


def _now() -> datetime:
    return datetime.now(tz=UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(
        String(32), default="topic"
    )  # 'weakness' | 'topic' | 'review'
    target_topic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, default=5)
    thread_id: Mapped[str] = mapped_column(String(36))  # LangGraph checkpointer key
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list[QuestionInstance]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class QuestionInstance(Base):
    __tablename__ = "question_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("study_sessions.id"))
    seq: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(128))
    difficulty: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    model_answer: Mapped[str] = mapped_column(Text)
    rubric_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    ref_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[StudySession] = relationship(back_populates="questions")
    answer: Mapped[Answer | None] = relationship(
        back_populates="question_instance", uselist=False, cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("question_instance_id", name="uq_one_answer_per_question"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_instances.id"), unique=True
    )
    user_answer: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    feedback: Mapped[str] = mapped_column(Text)
    missing_points_json: Mapped[list[str]] = mapped_column(JSON)
    graded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    question_instance: Mapped[QuestionInstance] = relationship(back_populates="answer")
