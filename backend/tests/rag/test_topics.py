"""Tests for app.rag.ingest.topics."""
from pathlib import Path

import pytest

from app.rag.ingest.topics import TopicLoadError, load_topics


def test_loads_topic_list(tmp_path: Path):
    file = tmp_path / "topics.yaml"
    file.write_text("topics:\n  - 정규화\n  - 네트워크\n", encoding="utf-8")
    assert load_topics(file) == ["정규화", "네트워크"]


def test_rejects_duplicate_topics(tmp_path: Path):
    file = tmp_path / "topics.yaml"
    file.write_text("topics:\n  - 정규화\n  - 정규화\n", encoding="utf-8")
    with pytest.raises(TopicLoadError, match="duplicate"):
        load_topics(file)


def test_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_topics(tmp_path / "nope.yaml")


def test_rejects_missing_topics_key(tmp_path: Path):
    file = tmp_path / "topics.yaml"
    file.write_text("things: [a, b]\n", encoding="utf-8")
    with pytest.raises(TopicLoadError, match="topics"):
        load_topics(file)


def test_project_topics_file_loads():
    """Smoke-load the real project topics.yaml."""
    expected_topic_count = 20
    root = Path(__file__).resolve().parents[3]  # backend → repo root
    topics = load_topics(root / "data" / "topics.yaml")
    assert "정규화" in topics
    assert len(topics) == expected_topic_count
