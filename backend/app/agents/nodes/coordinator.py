"""Coordinator node — decides (topic, difficulty, target_weakness)."""

from __future__ import annotations

import json
from typing import Any

from app.agents.models import CoordinatorDecision
from app.agents.prompts import COORDINATOR_SYSTEM, coordinator_prompt
from app.agents.state import SessionState


def _call_haiku(client: Any, model: str, system: str, user_message: str) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=200,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return str(resp.content[0].text).strip()


def _parse_decision(raw: str, topics: list[str], weak_topics: list[str]) -> CoordinatorDecision:
    try:
        data = json.loads(raw)
        decision = CoordinatorDecision.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return CoordinatorDecision(
            topic=topics[0], difficulty=1, target_weakness=False, reason="fallback: parse"
        )

    # enforce topic allowlist
    if decision.topic not in topics:
        replacement = weak_topics[0] if weak_topics else topics[0]
        decision = decision.model_copy(
            update={"topic": replacement, "reason": "fallback: allowlist"}
        )

    # if target_weakness=True but topic isn't in weak_topics, replace with a weak topic
    if decision.target_weakness and weak_topics and decision.topic not in weak_topics:
        decision = decision.model_copy(
            update={"topic": weak_topics[0], "reason": "fallback: prefer weak"}
        )

    return decision


def coordinator_node(
    state: SessionState,
    *,
    client: Any,
    model: str,
    topics: list[str],
    weak_topics: list[str],
    user_intent: str,
) -> dict[str, Any]:
    """LangGraph node: decide next (topic, difficulty, target_weakness)."""
    prompt = coordinator_prompt(user_intent, weak_topics, topics)
    raw = _call_haiku(client, model, COORDINATOR_SYSTEM, prompt)
    decision = _parse_decision(raw, topics, weak_topics)
    return {
        "topic": decision.topic,
        "difficulty": decision.difficulty,
        "target_weakness": decision.target_weakness,
    }
