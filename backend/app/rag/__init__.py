"""RAG (Retrieval-Augmented Generation) module.

This is the single public surface for retrieval. Outside callers should
import only what is re-exported here. The internal subpackages
(`ingest`, `store`, `embedder`) are implementation details.
"""
from app.rag.ingest.pipeline import IngestPipeline
from app.rag.retriever import Retriever, default_retriever

__all__ = ["IngestPipeline", "Retriever", "default_retriever"]
