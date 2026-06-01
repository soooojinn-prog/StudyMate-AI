"""FastAPI Depends() factories.

The graph and its expensive components (BGE-M3 embedder, Anthropic client,
ChromaDB store) are built once at app startup and reused across requests.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request

from app.agents.wiring import build_default_graph
from app.api.session_store import SessionStore


def _build_graph_singleton() -> Any:
    """Construct the agent graph for the API singleton.

    Delegates to `app.agents.wiring.build_default_graph` so the API
    layer doesn't itself import `app.rag` (would break import-linter
    contract 1).
    """
    return build_default_graph()


def get_graph(request: Request) -> Any:
    """Return the graph singleton attached to app.state by the lifespan."""
    return request.app.state.graph


def get_session_store(request: Request) -> SessionStore:
    """Return the session-store singleton attached to app.state by the lifespan."""
    store: SessionStore = request.app.state.session_store
    return store


GraphDep = Annotated[Any, Depends(get_graph)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
