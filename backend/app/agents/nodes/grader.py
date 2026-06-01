"""Grader node — strict JSON, 1 retry, half-score fallback."""
from __future__ import annotations

import json
from typing import Any

from app.agents.models import GradingRequest
from app.agents.prompts import GRADER_SYSTEM, grader_prompt
from app.agents.state import GradingResult, SessionState

_RETRY_LIMIT = 1
_FALLBACK_SCORE = 0.5


def _call_sonnet(
    client: Any, model: str, system: str, user_message: str
) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return str(resp.content[0].text).strip()


def _try_parse(raw: str) -> GradingResult | None:
    try:
        data = json.loads(raw)
        return GradingResult.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None


def grader_node(
    state: SessionState,
    *,
    client: Any,
    model: str,
) -> dict[str, Any]:
    """LangGraph node: grade the user's answer per the rubric."""
    request = GradingRequest(
        question=state.get("question", ""),
        model_answer=state.get("model_answer", ""),
        rubric=list(state.get("rubric", [])),
        user_answer=state.get("user_answer", ""),
    )
    prompt = grader_prompt(
        request.question, request.model_answer, request.rubric, request.user_answer
    )

    for _ in range(_RETRY_LIMIT + 1):
        raw = _call_sonnet(client, model, GRADER_SYSTEM, prompt)
        parsed = _try_parse(raw)
        if parsed is not None:
            return {
                "score": parsed.score,
                "rationale": parsed.rationale,
                "feedback": parsed.feedback,
                "missing_points": parsed.missing_points,
            }

    # Both attempts failed — record a fallback so the session doesn't crash.
    return {
        "score": _FALLBACK_SCORE,
        "rationale": "grader_parse_failed",
        "feedback": "parse_failed — 채점 결과를 정상적으로 파싱하지 못했습니다. 재시도해 주세요.",
        "missing_points": [],
    }
