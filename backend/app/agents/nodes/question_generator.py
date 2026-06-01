"""QuestionGenerator node — RAG context + Sonnet → question + model_answer + rubric."""

from __future__ import annotations

import json
from typing import Any

from app.agents.models import QuestionGenerationRequest
from app.agents.prompts import QGEN_SYSTEM, qgen_prompt
from app.agents.state import QuestionPayload, SessionState

_RETRIEVAL_K = 5


def _call_sonnet(client: Any, model: str, system: str, user_message: str) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return str(resp.content[0].text).strip()


def _parse_question(raw: str) -> QuestionPayload:
    try:
        data = json.loads(raw)
        return QuestionPayload.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        msg = f"QuestionGenerator returned invalid payload: {e}"
        raise ValueError(msg) from e


def question_generator_node(
    state: SessionState,
    *,
    client: Any,
    model: str,
    retriever: Any,
) -> dict[str, Any]:
    """LangGraph node: produce a question + model answer + rubric for the topic."""
    topic = state.get("topic", "")
    difficulty = state.get("difficulty", 1)

    # Build retrieval query from topic and difficulty
    query = f"{topic} 난이도 {difficulty}"
    chunks = retriever.retrieve(query, k=_RETRIEVAL_K)
    chunk_texts = [c.text for c in chunks]
    chunk_ids = [c.id for c in chunks]

    # Validate the request shape (catches bad state early in dev)
    QuestionGenerationRequest(topic=topic, difficulty=difficulty, context_chunks=chunk_texts)

    raw = _call_sonnet(client, model, QGEN_SYSTEM, qgen_prompt(topic, difficulty, chunk_texts))
    payload = _parse_question(raw)

    return {
        "question": payload.question,
        "model_answer": payload.model_answer,
        "rubric": [item.model_dump() for item in payload.rubric],
        "ref_chunk_ids": chunk_ids,
    }
