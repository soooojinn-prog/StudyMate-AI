"""Dashboard endpoints — read-only stats over the learning tables."""

from __future__ import annotations

from collections import defaultdict
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from app.api.dependencies import DbSessionDep
from app.api.schemas.dashboard import (
    DashboardStatsDTO,
    RecentAnswerDTO,
    TopicStatDTO,
    WeakTopicDTO,
)
from app.learning.analytics import compute_weakness
from app.learning.repository import SessionRepository

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


_DEFAULT_LOOKBACK_DAYS = 30
_MAX_RECENT_ROWS = 10


@router.get("/stats", response_model=DashboardStatsDTO)
def stats(user_id: str, db: DbSessionDep) -> DashboardStatsDTO:
    if not user_id.strip():
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="user_id_required")
    repo = SessionRepository(db)
    answers = repo.recent_answers(user_id, days=_DEFAULT_LOOKBACK_DAYS)

    weak = compute_weakness(repo, user_id=user_id, lookback_days=_DEFAULT_LOOKBACK_DAYS)

    # topic_stats — every topic with ≥ 1 answer in the window
    by_topic: dict[str, list[float]] = defaultdict(list)
    for a in answers:
        by_topic[a.question_instance.topic].append(a.score)
    topic_stats = [
        TopicStatDTO(
            topic=t,
            answer_count=len(scores),
            avg_score=round(sum(scores) / len(scores), 3),
        )
        for t, scores in sorted(by_topic.items())
    ]

    recent = [
        RecentAnswerDTO(
            session_id=a.question_instance.session_id,
            topic=a.question_instance.topic,
            score=a.score,
            graded_at=a.graded_at,
        )
        for a in answers[:_MAX_RECENT_ROWS]
    ]

    return DashboardStatsDTO(
        user_id=user_id,
        weak_topics=[
            WeakTopicDTO(topic=w.topic, avg_score=w.avg_score, sample_count=w.sample_count)
            for w in weak
        ],
        topic_stats=topic_stats,
        recent_answers=recent,
        total_answers=len(answers),
    )
