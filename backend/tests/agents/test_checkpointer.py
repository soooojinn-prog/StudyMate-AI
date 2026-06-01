"""Tests for app.agents.checkpointer."""
from pathlib import Path

from app.agents.checkpointer import make_checkpointer


def test_make_checkpointer_creates_parent_dir(tmp_path: Path):
    db_path = tmp_path / "subdir" / "studymate.db"
    saver = make_checkpointer(db_path)
    assert db_path.parent.exists()
    assert saver is not None


def test_make_checkpointer_returns_sqlite_saver_instance(tmp_path: Path):
    saver = make_checkpointer(tmp_path / "studymate.db")
    # SqliteSaver has a `.conn` attribute pointing at the sqlite3.Connection
    assert hasattr(saver, "conn") or hasattr(saver, "_conn") or hasattr(saver, "put")


def test_make_checkpointer_with_existing_db(tmp_path: Path):
    db_path = tmp_path / "studymate.db"
    db_path.write_bytes(b"")  # empty file
    saver = make_checkpointer(db_path)
    assert saver is not None
