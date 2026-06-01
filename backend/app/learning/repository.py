"""Repository wrapping all reads/writes against the learning tables."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.learning.models import Answer, QuestionInstance, StudySession


@dataclass
class AnswerView:
    """Flat read shape for analytics — joins QuestionInstance and Answer."""

    session_id: str
    topic: str
    difficulty: int
    score: float
    seq: int
    graded_at: datetime


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _next_seq(self, session_id: str) -> int:
        # Flush so any unflushed QuestionInstance rows added earlier in this
        # transaction are visible to the MAX(seq) query under autoflush=False.
        self.session.flush()
        stmt = select(func.coalesce(func.max(QuestionInstance.seq), 0)).where(
            QuestionInstance.session_id == session_id
        )
        return int(self.session.execute(stmt).scalar_one() or 0) + 1

    def record_answer(self, payload: dict[str, Any]) -> None:
        """Persist a graded question+answer pair from the Persist node payload."""
        session_id = str(payload["session_id"])
        seq = self._next_seq(session_id)
        q_id = str(uuid.uuid4())
        a_id = str(uuid.uuid4())
        now = datetime.now(tz=UTC)
        self.session.add(
            QuestionInstance(
                id=q_id,
                session_id=session_id,
                seq=seq,
                topic=str(payload.get("topic", "")),
                difficulty=int(payload.get("difficulty", 1)),
                question_text=str(payload.get("question", "")),
                model_answer=str(payload.get("model_answer", "")),
                rubric_json=list(payload.get("rubric", [])),
                ref_chunk_ids=list(payload.get("ref_chunk_ids", [])),
                generated_at=now,
            )
        )
        self.session.add(
            Answer(
                id=a_id,
                question_instance_id=q_id,
                user_answer=str(payload.get("user_answer", "")),
                score=float(payload.get("score", 0.0)),
                rationale=str(payload.get("rationale", "")),
                feedback=str(payload.get("feedback", "")),
                missing_points_json=list(payload.get("missing_points", [])),
                graded_at=now,
            )
        )

    def recent_answers(self, user_id: str, *, days: int) -> list[Answer]:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        stmt = (
            select(Answer)
            .join(QuestionInstance, Answer.question_instance_id == QuestionInstance.id)
            .join(StudySession, QuestionInstance.session_id == StudySession.id)
            .where(StudySession.user_id == user_id)
            .where(Answer.graded_at >= cutoff)
            .order_by(Answer.graded_at.desc())
        )
        # Attach topic/difficulty/seq via the relationship for convenience in analytics.
        rows = list(self.session.execute(stmt).scalars().all())
        for r in rows:
            # Eager-touch the related question (single SELECT under autoflush=False).
            _ = r.question_instance.topic
        return rows
