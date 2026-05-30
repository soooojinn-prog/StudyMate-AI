"""Smoke test: ruff and mypy CLIs are installed and callable."""

import subprocess


def test_ruff_invokable() -> None:
    result = subprocess.run(
        ["uv", "run", "ruff", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ruff" in result.stdout.lower()


def test_mypy_invokable() -> None:
    result = subprocess.run(
        ["uv", "run", "mypy", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "mypy" in result.stdout.lower()
