"""Shared fixtures for app.rag tests."""
from pathlib import Path

import pytest

from app.rag.embedder import FakeEmbedder
from app.rag.models import Chunk, ChunkMetadata


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder(dim=16)


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            id="a1",
            text="정규화는 데이터 중복을 줄이기 위한 작업이다.",
            metadata=ChunkMetadata(source="x.pdf", page=1, topic="정규화"),
        ),
        Chunk(
            id="a2",
            text="1NF는 원자값만 허용한다.",
            metadata=ChunkMetadata(source="x.pdf", page=1, topic="정규화"),
        ),
        Chunk(
            id="b1",
            text="HTTP는 상태 비저장 프로토콜이다.",
            metadata=ChunkMetadata(source="y.pdf", page=2, topic="네트워크"),
        ),
    ]


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    d = tmp_path / "chroma"
    d.mkdir()
    return d
