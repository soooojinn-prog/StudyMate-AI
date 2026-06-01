"""Default wiring for the agent graph against project settings.

`app.api` can't import `app.rag` directly (import-linter contract 1).
This module sits in `app.agents` (which is allowed to depend on
`app.rag`) and owns the responsibility of stitching every concrete
dependency together so the API layer only needs `app.agents` imports.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from anthropic import Anthropic

from app.agents.checkpointer import make_checkpointer
from app.agents.graph import build_graph
from app.core.settings import settings
from app.rag.ingest.topics import load_topics
from app.rag.retriever import default_retriever


def build_default_graph(
    *,
    persist_adapter: Callable[[dict[str, Any]], None] | None = None,
    weakness_provider: Callable[[str], list[str]] | None = None,
) -> Any:
    """Build the StudyMate agent graph from project settings.

    The two callbacks are optional so this can be used both at app
    startup (real persist + real weakness) and from one-off smoke
    scripts (None → no-op).
    """
    client = Anthropic(api_key=settings.anthropic_api_key)
    retriever = default_retriever()
    topics = load_topics(settings.topics_file)
    saver = make_checkpointer(settings.studymate_db)
    return build_graph(
        checkpointer=saver,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=weakness_provider or (lambda _uid: []),
        persist_adapter=persist_adapter,
        topics=topics,
        sonnet_model=settings.anthropic_model_sonnet,
        haiku_model=settings.anthropic_model_haiku,
    )
