"""Tests for app.rag.ingest.topic_tagger — Anthropic client is mocked."""
from unittest.mock import MagicMock

from app.rag.ingest.topic_tagger import tag_chunks
from app.rag.models import Chunk, ChunkMetadata


def _chunk(id: str, text: str) -> Chunk:
    return Chunk(
        id=id, text=text, metadata=ChunkMetadata(source="x.pdf", page=1, topic="untagged")
    )


def test_assigns_topic_from_anthropic_response():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "정규화"}')]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "1NF는 원자값만 허용한다.")]
    tagged = tag_chunks(
        chunks, topics=["정규화", "네트워크"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].metadata.topic == "정규화"
    fake_client.messages.create.assert_called_once()


def test_falls_back_to_default_on_unknown_topic():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "외계어"}')]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "이상한 문장")]
    tagged = tag_chunks(
        chunks, topics=["정규화", "네트워크"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].metadata.topic == "기타"


def test_falls_back_to_default_on_malformed_json():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="not json at all")]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "x")]
    tagged = tag_chunks(
        chunks, topics=["정규화"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].metadata.topic == "기타"


def test_makes_one_call_per_chunk():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "정규화"}')]
    fake_client.messages.create.return_value = fake_response

    expected_call_count = 3
    chunks = [_chunk(f"c{i}", f"chunk {i}") for i in range(expected_call_count)]
    tag_chunks(chunks, topics=["정규화"], client=fake_client, model="claude-haiku-4-5")
    assert fake_client.messages.create.call_count == expected_call_count


def test_preserves_other_chunk_fields():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"topic": "정규화"}')]
    fake_client.messages.create.return_value = fake_response

    chunks = [_chunk("c1", "원본 텍스트")]
    tagged = tag_chunks(
        chunks, topics=["정규화"], client=fake_client, model="claude-haiku-4-5"
    )
    assert tagged[0].id == "c1"
    assert tagged[0].text == "원본 텍스트"
    assert tagged[0].metadata.source == "x.pdf"
    assert tagged[0].metadata.page == 1
