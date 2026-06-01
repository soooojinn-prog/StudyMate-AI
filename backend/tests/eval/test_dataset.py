"""Tests for app.eval.dataset."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.eval.dataset import DatasetLoadError, SampleAnswer, load_golden


def test_load_golden_returns_two_items(tiny_golden_path: Path) -> None:
    items = load_golden(tiny_golden_path)
    expected_count = 2
    assert len(items) == expected_count
    assert items[0].id == "t001"


def test_load_golden_each_item_has_3_sample_answers(tiny_golden_path: Path) -> None:
    items = load_golden(tiny_golden_path)
    expected_samples = 3
    for item in items:
        assert len(item.sample_answers) == expected_samples
    # tiers in the fixture
    assert {s.tier for s in items[0].sample_answers} == {"high", "mid", "low"}


def test_sample_answer_rejects_invalid_tier() -> None:
    with pytest.raises(ValidationError):
        SampleAnswer(tier="medium", text="x", human_score=0.5)


def test_load_golden_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_golden(tmp_path / "nope.jsonl")


def test_load_golden_raises_on_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(DatasetLoadError, match="empty"):
        load_golden(p)


def test_load_golden_raises_on_malformed_line(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("{this is not json}", encoding="utf-8")
    with pytest.raises(DatasetLoadError):
        load_golden(p)


def test_project_golden_v1_loads() -> None:
    """Smoke-load the real project golden_v1.jsonl."""
    root = Path(__file__).resolve().parents[3]  # backend/tests/eval → repo root
    items = load_golden(root / "data" / "eval" / "golden_v1.jsonl")
    expected_seed = 5
    assert len(items) >= expected_seed
    # at least one item from each major topic in the seed
    topics = {i.topic for i in items}
    assert "정규화" in topics
