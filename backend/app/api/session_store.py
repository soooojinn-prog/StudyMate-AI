"""In-process registry of session metadata.

The LangGraph checkpointer owns the actual graph state. This module only
tracks who created which session and when. Plan 5 replaces with SQLAlchemy.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SessionRecord:
    session_id: str
    user_id: str
    target_count: int
    user_intent: str
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class SessionStore:
    """Thread-safe in-memory registry."""

    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = threading.Lock()

    def add(self, record: SessionRecord) -> None:
        with self._lock:
            self._records[record.session_id] = record

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._records.get(session_id)

    def all(self) -> list[SessionRecord]:
        with self._lock:
            return list(self._records.values())
