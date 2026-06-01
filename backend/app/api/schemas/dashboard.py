"""DTOs for /dashboard/stats."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WeakTopicDTO(BaseModel):
    topic: str
    avg_score: float
    sample_count: int


class TopicStatDTO(BaseModel):
    topic: str
    answer_count: int
    avg_score: float


class RecentAnswerDTO(BaseModel):
    session_id: str
    topic: str
    score: float
    graded_at: datetime


class DashboardStatsDTO(BaseModel):
    user_id: str
    weak_topics: list[WeakTopicDTO] = Field(default_factory=list)
    topic_stats: list[TopicStatDTO] = Field(default_factory=list)
    recent_answers: list[RecentAnswerDTO] = Field(default_factory=list)
    total_answers: int = 0
