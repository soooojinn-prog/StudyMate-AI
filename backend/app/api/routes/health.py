"""Health check endpoint."""

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.settings import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


def _read_version() -> str:
    try:
        return version("studymate-backend")
    except PackageNotFoundError:
        return "0.0.0-dev"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=_read_version(),
    )
