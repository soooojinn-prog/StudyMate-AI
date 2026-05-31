"""CLI to ingest PDFs into the RAG store.

Usage (from `backend/`):
    uv run python -m scripts.seed all
    uv run python -m scripts.seed status
    uv run python -m scripts.seed reset
"""

from __future__ import annotations

import sys

import typer
from anthropic import Anthropic

from app.core.settings import settings
from app.rag.embedder import BGEM3Embedder
from app.rag.ingest.pipeline import IngestPipeline
from app.rag.ingest.topics import load_topics
from app.rag.store import ChunkStore

app = typer.Typer(add_completion=False, help="Seed the RAG store from data/raw/*.pdf")


def _build_pipeline() -> IngestPipeline:
    if not settings.anthropic_api_key:
        typer.echo(
            "ERROR: ANTHROPIC_API_KEY is not set. Add it to .env at the project root.",
            err=True,
        )
        raise typer.Exit(code=2)
    topics = load_topics(settings.topics_file)
    store = ChunkStore(persist_dir=settings.chroma_dir, collection=settings.chroma_collection)
    embedder = BGEM3Embedder(model_name=settings.embedding_model, dim=settings.embedding_dim)
    client = Anthropic(api_key=settings.anthropic_api_key)
    return IngestPipeline(
        store=store,
        embedder=embedder,
        topics=topics,
        anthropic_client=client,
        anthropic_model="claude-haiku-4-5",
    )


@app.command()
def all() -> None:  # noqa: A001  (typer expects this name)
    """Ingest every *.pdf under settings.raw_pdf_dir."""
    if not settings.raw_pdf_dir.exists():
        typer.echo(f"ERROR: {settings.raw_pdf_dir} does not exist.", err=True)
        raise typer.Exit(code=2)
    pdfs = sorted(settings.raw_pdf_dir.glob("*.pdf"))
    if not pdfs:
        typer.echo(f"No PDFs found in {settings.raw_pdf_dir}. Drop files there first.")
        raise typer.Exit(code=0)

    typer.echo(f"Ingesting {len(pdfs)} PDF(s) from {settings.raw_pdf_dir} …")
    pipeline = _build_pipeline()
    counts = pipeline.run_dir(settings.raw_pdf_dir)
    total = sum(counts.values())
    for name, n in counts.items():
        typer.echo(f"  · {name}  →  {n} chunk(s)")
    typer.echo(f"Done. Total chunks added: {total}")


@app.command()
def status() -> None:
    """Print collection size."""
    store = ChunkStore(persist_dir=settings.chroma_dir, collection=settings.chroma_collection)
    typer.echo(f"Collection '{settings.chroma_collection}': {store.count()} chunks")


@app.command()
def reset() -> None:
    """Drop and recreate the collection (data on disk is purged)."""
    store = ChunkStore(persist_dir=settings.chroma_dir, collection=settings.chroma_collection)
    before = store.count()
    store.reset()
    typer.echo(f"Reset collection '{settings.chroma_collection}' (was {before} chunks).")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app() or 0)
