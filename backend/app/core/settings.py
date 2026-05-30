"""Application settings loaded from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # ── RAG ────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_dim: int = Field(default=1024)
    chroma_dir: Path = Field(default=Path("./chroma"))
    chroma_collection: str = Field(default="jeongcheo_v1")
    topics_file: Path = Field(default=Path("./data/topics.yaml"))
    raw_pdf_dir: Path = Field(default=Path("./data/raw"))
    extracted_dir: Path = Field(default=Path("./data/extracted"))
    chunks_dir: Path = Field(default=Path("./data/chunks"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
