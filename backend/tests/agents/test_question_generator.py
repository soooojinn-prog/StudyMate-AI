"""Tests for app.agents.nodes.question_generator."""

from unittest.mock import MagicMock

import pytest

from app.agents.nodes.question_generator import question_generator_node


def _mock_retriever(chunk_ids: list[str], texts: list[str]):
    retriever = MagicMock()

    class _C:
        def __init__(self, cid: str, text: str):
            self.id = cid
            self.text = text

    retriever.retrieve.return_value = [_C(i, t) for i, t in zip(chunk_ids, texts, strict=True)]
    return retriever


def test_qgen_produces_question_and_rubric(make_anthropic_client):
    expected_rubric_items = 2
    client = make_anthropic_client(
        {
            "question": "정규화의 목적을 서술하시오.",
            "model_answer": "데이터 중복 감소와 이상현상 방지.",
            "rubric": [
                {"point": "목적 명시", "weight": 0.6, "keywords": ["이상현상"]},
                {"point": "예시 제시", "weight": 0.4, "keywords": []},
            ],
        }
    )
    retriever = _mock_retriever(["c1", "c2"], ["1NF는 원자값", "2NF는 부분 함수 종속 제거"])
    state = {"user_id": "u1", "session_id": "s1", "topic": "정규화", "difficulty": 2}
    result = question_generator_node(
        state, client=client, model="claude-sonnet-4-6", retriever=retriever
    )
    assert result["question"] == "정규화의 목적을 서술하시오."
    assert result["model_answer"].startswith("데이터")
    assert len(result["rubric"]) == expected_rubric_items
    assert result["ref_chunk_ids"] == ["c1", "c2"]


def test_qgen_calls_retriever_with_topic(make_anthropic_client):
    client = make_anthropic_client(
        {
            "question": "q",
            "model_answer": "a",
            "rubric": [{"point": "p", "weight": 1.0, "keywords": []}],
        }
    )
    retriever = _mock_retriever(["c1"], ["chunk text"])
    state = {"user_id": "u1", "session_id": "s1", "topic": "SQL 응용", "difficulty": 1}
    question_generator_node(state, client=client, model="claude-sonnet-4-6", retriever=retriever)
    retriever.retrieve.assert_called_once()
    call_args = retriever.retrieve.call_args
    # the query must mention the topic
    assert "SQL 응용" in str(call_args)


def test_qgen_raises_on_invalid_llm_output(make_anthropic_client):
    client = make_anthropic_client({"question": "q"})  # missing model_answer and rubric
    retriever = _mock_retriever(["c1"], ["x"])
    state = {"user_id": "u1", "session_id": "s1", "topic": "정규화", "difficulty": 1}
    # tasks downstream (Grader) need a valid rubric — fail loudly
    with pytest.raises(ValueError, match="invalid"):
        question_generator_node(
            state, client=client, model="claude-sonnet-4-6", retriever=retriever
        )


def test_qgen_works_with_no_retriever_results(make_anthropic_client):
    """Retriever returning empty list should still work — Sonnet handles bare-topic generation."""
    client = make_anthropic_client(
        {
            "question": "정규화는 무엇인가?",
            "model_answer": "데이터 모델링 기법.",
            "rubric": [{"point": "정의", "weight": 1.0, "keywords": []}],
        }
    )
    retriever = MagicMock()
    retriever.retrieve.return_value = []
    state = {"user_id": "u1", "session_id": "s1", "topic": "정규화", "difficulty": 1}
    result = question_generator_node(
        state, client=client, model="claude-sonnet-4-6", retriever=retriever
    )
    assert result["question"]
    assert result["ref_chunk_ids"] == []
