"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root, derived from this file's location:
#   backend/app/core/settings.py -> parents[3] = project root
# All on-disk paths default to roots-of-the-project so they resolve the
# same way whether the process is launched from `backend/` or the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Top-level settings. Only environment access lives here."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "StudyMate AI"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ── RAG ────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    chroma_dir: Path = Field(default=_PROJECT_ROOT / "chroma")
    chroma_collection: str = Field(default="jeongcheo_v1")
    topics_file: Path = Field(default=_PROJECT_ROOT / "data" / "topics.yaml")
    raw_pdf_dir: Path = Field(default=_PROJECT_ROOT / "data" / "raw")
    extracted_dir: Path = Field(default=_PROJECT_ROOT / "data" / "extracted")
    chunks_dir: Path = Field(default=_PROJECT_ROOT / "data" / "chunks")

    # ── Database ───────────────────────────────────────────
    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{_PROJECT_ROOT / 'data' / 'studymate.db'}"
    )

    # ── Agents ─────────────────────────────────────────────
    studymate_db: Path = Field(default=_PROJECT_ROOT / "data" / "studymate.db")
    anthropic_model_sonnet: str = Field(default="claude-sonnet-4-6")
    anthropic_model_haiku: str = Field(default="claude-haiku-4-5")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
