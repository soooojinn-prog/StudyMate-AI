"""Deterministic weakness ranking — no LLM, no random."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.learning.repository import SessionRepository

_MIN_SAMPLES_PER_TOPIC = 3
_TOP_N = 3


@dataclass(frozen=True)
class TopicWeakness:
    topic: str
    avg_score: float
    sample_count: int


def compute_weakness(
    repo: SessionRepository,
    *,
    user_id: str,
    lookback_days: int = 30,
) -> list[TopicWeakness]:
    """Return up to top-3 topics with the lowest average score.

    A topic must have at least 3 graded answers in the lookback window to be
    counted (avoids ranking a topic by a single bad answer).
    """
    answers = repo.recent_answers(user_id, days=lookback_days)
    by_topic: dict[str, list[float]] = defaultdict(list)
    for a in answers:
        by_topic[a.question_instance.topic].append(a.score)

    eligible: list[TopicWeakness] = []
    for topic, scores in by_topic.items():
        if len(scores) < _MIN_SAMPLES_PER_TOPIC:
            continue
        eligible.append(
            TopicWeakness(
                topic=topic,
                avg_score=sum(scores) / len(scores),
                sample_count=len(scores),
            )
        )
    eligible.sort(key=lambda w: (w.avg_score, -w.sample_count))
    return eligible[:_TOP_N]
