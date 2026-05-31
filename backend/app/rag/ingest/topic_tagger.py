"""Topic classification via Anthropic Haiku."""

from __future__ import annotations

import json
from typing import Any

from app.rag.models import Chunk, ChunkMetadata

FALLBACK_TOPIC = "기타"


_PROMPT = """다음 텍스트를 가장 잘 설명하는 주제 하나를 아래 목록에서 골라 JSON으로 답하시오.

목록:
{topics}

텍스트:
\"\"\"
{text}
\"\"\"

응답 형식 (다른 말 금지):
{{"topic": "<목록 중 하나>"}}
"""


def _classify_one(
    client: Any, model: str, text: str, allowed: list[str]
) -> str:
    topic_list = "\n".join(f"- {t}" for t in allowed)
    prompt = _PROMPT.format(topics=topic_list, text=text[:1200])
    resp = client.messages.create(
        model=model,
        max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )
    body = resp.content[0].text.strip()
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, AttributeError):
        return FALLBACK_TOPIC
    topic = str(parsed.get("topic", "")).strip()
    if topic not in allowed:
        return FALLBACK_TOPIC
    return topic


def tag_chunks(
    chunks: list[Chunk],
    *,
    topics: list[str],
    client: Any,
    model: str = "claude-haiku-4-5",
) -> list[Chunk]:
    """Classify each chunk's topic using Anthropic Haiku.

    Returns a NEW list of Chunks with `metadata.topic` filled in.
    Original chunks are not mutated.
    """
    allowed = [*topics, FALLBACK_TOPIC]
    out: list[Chunk] = []
    for c in chunks:
        topic = _classify_one(client, model, c.text, allowed)
        new_meta = ChunkMetadata(
            source=c.metadata.source,
            page=c.metadata.page,
            topic=topic,
            chunk_type=c.metadata.chunk_type,
            difficulty=c.metadata.difficulty,
        )
        out.append(
            Chunk(id=c.id, text=c.text, metadata=new_meta, embedding=c.embedding)
        )
    return out
