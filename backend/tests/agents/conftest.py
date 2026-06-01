"""Shared agent test fixtures."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def make_anthropic_client():
    """Returns a factory that builds a fake Anthropic client with canned JSON."""

    def factory(payload: dict[str, Any]) -> MagicMock:
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps(payload, ensure_ascii=False))]
        client.messages.create.return_value = response
        return client

    return factory


@pytest.fixture
def topics_default() -> list[str]:
    return ["정규화", "SQL 응용", "네트워크"]
