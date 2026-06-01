"""FastAPI Depends() factories.

The graph and its expensive components (BGE-M3 embedder, Anthropic client,
ChromaDB store) are built once at app startup and reused across requests.
"""

from __future__ import annotations

from typing import Annotated, Any

from anthropic import Anthropic
from fastapi import Depends, Request

from app.agents import build_graph, make_checkpointer
from app.api.session_store import SessionStore
from app.core.settings import settings
from app.rag.ingest.topics import load_topics
from app.rag.retriever import default_retriever


def _build_graph_singleton() -> Any:
    """Construct the agent graph with real Anthropic + real retriever."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    retriever = default_retriever()
    topics = load_topics(settings.topics_file)
    saver = make_checkpointer(settings.studymate_db)
    return build_graph(
        checkpointer=saver,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: [],
        persist_adapter=None,
        topics=topics,
        sonnet_model=settings.anthropic_model_sonnet,
        haiku_model=settings.anthropic_model_haiku,
    )


def get_graph(request: Request) -> Any:
    """Return the graph singleton attached to app.state by the lifespan."""
    return request.app.state.graph


def get_session_store(request: Request) -> SessionStore:
    """Return the session-store singleton attached to app.state by the lifespan."""
    store: SessionStore = request.app.state.session_store
    return store


GraphDep = Annotated[Any, Depends(get_graph)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
