"""SqliteSaver factory — single source for the checkpointer DB path.

Plan 5 will create the StudySession/QuestionInstance/Answer tables in
the same SQLite file. LangGraph's checkpointer uses its own tables
(`checkpoints`, `writes`, `versions`) so there's no collision.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def make_checkpointer(db_path: Path) -> SqliteSaver:
    """Build a LangGraph SqliteSaver rooted at the given file.

    Creates the parent directory if it doesn't exist.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)
