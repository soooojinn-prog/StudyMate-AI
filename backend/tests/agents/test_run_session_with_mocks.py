"""Integration test for run_session + resume_session with mocked LLM/retriever.

This is the most important test in Plan 3 — it verifies the entire
graph flows correctly with the interrupt and resume cycle.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.agents.checkpointer import make_checkpointer
from app.agents.graph import build_graph, resume_session, run_session

# Expected values for the full-cycle assertions (extracted to avoid PLR2004).
_EXPECTED_SCORE = 0.83
_EXPECTED_QUESTIONS_DONE = 1
_EXPECTED_PERSISTS = 1
_RESTART_EXPECTED_SCORE = 0.6


def _client_with_sequence(payloads: list[dict[str, object]]) -> MagicMock:
    """Build a fake client whose .messages.create returns each payload in turn."""
    client = MagicMock()
    responses = []
    for p in payloads:
        text = json.dumps(p, ensure_ascii=False)
        responses.append(type("M", (), {"content": [type("C", (), {"text": text})()]})())
    client.messages.create.side_effect = responses
    return client


def _retriever_returning(chunks: list[tuple[str, str]]) -> MagicMock:
    retriever = MagicMock()

    class _C:
        def __init__(self, cid: str, text: str):
            self.id = cid
            self.text = text

    retriever.retrieve.return_value = [_C(cid, text) for cid, text in chunks]
    return retriever


def test_run_then_resume_completes_full_cycle(tmp_path: Path) -> None:
    # Coordinator → QGen (with retrieval) → AWAIT → Grader → Persist
    client = _client_with_sequence(
        [
            # Coordinator
            {
                "topic": "정규화",
                "difficulty": 2,
                "target_weakness": True,
                "reason": "weak",
            },
            # QGen
            {
                "question": "정규화의 목적을 서술하시오.",
                "model_answer": "데이터 중복 감소와 이상현상 방지.",
                "rubric": [
                    {"point": "목적", "weight": 0.6, "keywords": ["이상현상"]},
                    {"point": "예시", "weight": 0.4, "keywords": []},
                ],
            },
            # Grader
            {
                "score": 0.83,
                "rationale": "목적 일부 누락",
                "feedback": "이상현상을 명시하세요",
                "missing_points": ["이상현상"],
            },
        ]
    )
    retriever = _retriever_returning([("c1", "1NF 원자값"), ("c2", "2NF 부분종속")])

    persist_calls: list[dict[str, object]] = []
    saver = make_checkpointer(tmp_path / "g.db")
    graph = build_graph(
        checkpointer=saver,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: ["정규화"],
        persist_adapter=persist_calls.append,
        topics=["정규화", "SQL 응용"],
        sonnet_model="claude-sonnet-4-6",
        haiku_model="claude-haiku-4-5",
    )

    # Phase 1: run until the AWAIT_ANSWER interrupt
    state_at_pause = run_session(graph=graph, user_id="u1", session_id="s1", target_count=5)
    assert state_at_pause["topic"] == "정규화"
    assert state_at_pause["question"] == "정규화의 목적을 서술하시오."
    assert state_at_pause["ref_chunk_ids"] == ["c1", "c2"]
    # grader should not have run yet
    assert "score" not in state_at_pause or state_at_pause.get("score") is None

    # Phase 2: resume with the learner's answer
    final = resume_session(
        graph=graph,
        session_id="s1",
        user_answer="정규화는 데이터 중복을 줄이는 작업입니다.",
    )
    assert final["score"] == _EXPECTED_SCORE
    assert final["missing_points"] == ["이상현상"]
    assert final["questions_done"] == _EXPECTED_QUESTIONS_DONE
    assert len(persist_calls) == _EXPECTED_PERSISTS
    assert persist_calls[0]["session_id"] == "s1"


def test_resume_after_process_restart(tmp_path: Path) -> None:
    """The checkpointer should persist state across graph instances (same DB)."""
    client = _client_with_sequence(
        [
            {"topic": "정규화", "difficulty": 1, "target_weakness": False, "reason": ""},
            {
                "question": "q?",
                "model_answer": "a.",
                "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
            },
            {"score": 0.6, "rationale": "ok", "feedback": "ok", "missing_points": []},
        ]
    )
    retriever = _retriever_returning([("c1", "x")])
    db = tmp_path / "g.db"

    # Run graph #1 to the pause
    saver1 = make_checkpointer(db)
    graph1 = build_graph(
        checkpointer=saver1,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: [],
        persist_adapter=None,
        topics=["정규화"],
        sonnet_model="claude-sonnet-4-6",
        haiku_model="claude-haiku-4-5",
    )
    run_session(graph=graph1, user_id="u1", session_id="s99", target_count=5)
    del graph1, saver1

    # New graph instance, same DB → resume should work
    saver2 = make_checkpointer(db)
    graph2 = build_graph(
        checkpointer=saver2,
        retriever=retriever,
        anthropic_client=client,
        weakness_provider=lambda _uid: [],
        persist_adapter=None,
        topics=["정규화"],
        sonnet_model="claude-sonnet-4-6",
        haiku_model="claude-haiku-4-5",
    )
    final = resume_session(graph=graph2, session_id="s99", user_answer="my answer")
    assert final["score"] == _RESTART_EXPECTED_SCORE
