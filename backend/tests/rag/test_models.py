"""Tests for app.rag.models."""

import pytest
from pydantic import ValidationError

from app.rag.models import Chunk, ChunkMetadata, ExtractedPage


def test_chunk_metadata_defaults_to_concept_type():
    meta = ChunkMetadata(source="2024.pdf", page=1, topic="정규화")
    assert meta.chunk_type == "concept"
    assert meta.difficulty is None


def test_chunk_metadata_rejects_out_of_range_difficulty():
    with pytest.raises(ValidationError):
        ChunkMetadata(source="x.pdf", page=1, topic="x", difficulty=4)


def test_chunk_round_trips_through_dict():
    chunk = Chunk(
        id="abc",
        text="hello",
        metadata=ChunkMetadata(source="x.pdf", page=1, topic="정규화"),
    )
    payload = chunk.model_dump()
    restored = Chunk.model_validate(payload)
    assert restored == chunk


def test_extracted_page_minimal():
    expected_page = 12
    page = ExtractedPage(source="2024.pdf", page=expected_page, text="some text")
    assert page.page == expected_page
