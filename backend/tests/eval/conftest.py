"""Shared fixtures for app.eval tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tiny_golden_path() -> Path:
    """Path to the 2-item fixture (relative to this test file)."""
    return Path(__file__).resolve().parent / "fixtures" / "tiny_golden.jsonl"
