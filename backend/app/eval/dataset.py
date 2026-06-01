"""Golden eval dataset — schema + loader."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class SampleAnswer(BaseModel):
    """One human-scored learner answer per question."""

    tier: str = Field(pattern=r"^(high|mid|low)$")
    text: str
    human_score: float = Field(ge=0.0, le=1.0)


class GoldenItem(BaseModel):
    """One question + model answer + rubric + 3 sample answers."""

    id: str
    topic: str
    difficulty: int = Field(ge=1, le=3)
    question: str
    model_answer: str
    rubric: list[dict[str, object]]
    rubric_keywords: list[str] = Field(
        default_factory=list,
        description="Flat keyword list used by Retrieval Recall@5",
    )
    sample_answers: list[SampleAnswer]


class DatasetLoadError(ValueError):
    """Raised when the jsonl file is malformed or violates the schema."""


def load_golden(path: Path) -> list[GoldenItem]:
    """Parse every line of the jsonl into a GoldenItem."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"golden dataset not found: {path}")
    items: list[GoldenItem] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
            items.append(GoldenItem.model_validate(data))
        except (json.JSONDecodeError, ValueError) as e:
            raise DatasetLoadError(f"{path}:{lineno}: {e}") from e
    if not items:
        raise DatasetLoadError(f"{path}: empty dataset")
    return items
