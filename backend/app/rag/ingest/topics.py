"""Topic catalog loader."""
from __future__ import annotations

from pathlib import Path

import yaml


class TopicLoadError(ValueError):
    """Raised when the topics yaml is malformed."""


def load_topics(path: Path) -> list[str]:
    """Load and validate the topic list from a yaml file.

    Raises:
        FileNotFoundError: file does not exist.
        TopicLoadError: yaml is missing `topics:` key, or has duplicates.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"topics file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "topics" not in data or not isinstance(data["topics"], list):
        raise TopicLoadError(
            f"{path}: expected top-level 'topics:' list, got {type(data.get('topics')).__name__}"
        )
    topics = [str(t).strip() for t in data["topics"]]
    seen: set[str] = set()
    dupes: list[str] = []
    for t in topics:
        if t in seen:
            dupes.append(t)
        seen.add(t)
    if dupes:
        raise TopicLoadError(f"{path}: duplicate topics: {dupes}")
    return topics
