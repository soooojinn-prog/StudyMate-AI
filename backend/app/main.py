"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import _build_graph_singleton
from app.api.routes import health
from app.api.session_store import SessionStore
from app.core.logging import configure_logging
from app.core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    app.state.session_store = SessionStore()
    # Defer expensive graph build until a real ANTHROPIC_API_KEY is configured.
    # Tests inject their own graph via dependency overrides.
    if settings.anthropic_api_key:
        app.state.graph = _build_graph_singleton()
    else:
        app.state.graph = None
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health.router)

    from app.api.routes import sessions  # noqa: PLC0415 (local import to avoid circular dep)

    app.include_router(sessions.router)
    return app


app = create_app()
