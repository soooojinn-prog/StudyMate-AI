"""Tests for app.agents.nodes.coordinator."""

from app.agents.nodes.coordinator import coordinator_node


def test_coordinator_returns_topic_difficulty_target(make_anthropic_client, topics_default):
    expected_difficulty = 2
    client = make_anthropic_client(
        {
            "topic": "정규화",
            "difficulty": expected_difficulty,
            "target_weakness": True,
            "reason": "ok",
        }
    )
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=["정규화"],
        user_intent="약점 보강 학습",
    )
    assert result["topic"] == "정규화"
    assert result["difficulty"] == expected_difficulty
    assert result["target_weakness"] is True


def test_coordinator_falls_back_when_topic_not_in_allowlist(make_anthropic_client, topics_default):
    client = make_anthropic_client(
        {"topic": "존재하지않는주제", "difficulty": 2, "target_weakness": False, "reason": "?"}
    )
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=[],
        user_intent="자유 학습",
    )
    # falls back to first available topic when LLM returns an unknown one
    assert result["topic"] in topics_default


def test_coordinator_uses_weak_topic_when_target_weakness_true_and_no_topic_hint(
    make_anthropic_client, topics_default
):
    # LLM somehow returns target_weakness=true but a non-weak topic
    client = make_anthropic_client(
        {"topic": "네트워크", "difficulty": 1, "target_weakness": True, "reason": ""}
    )
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=["정규화", "SQL 응용"],
        user_intent="약점 보강",
    )
    # when target_weakness, prefer the LLM's choice if it's in weak_topics,
    # otherwise replace with the first weak topic
    assert result["topic"] == "정규화"
    assert result["target_weakness"] is True


def test_coordinator_handles_malformed_json(make_anthropic_client, topics_default):
    expected_difficulty = 1
    client = make_anthropic_client({})  # we'll override the text below
    client.messages.create.return_value.content = [type("R", (), {"text": "not json"})()]
    state = {"user_id": "u1", "session_id": "s1"}
    result = coordinator_node(
        state,
        client=client,
        model="claude-haiku-4-5",
        topics=topics_default,
        weak_topics=[],
        user_intent="자유 학습",
    )
    # fallback to the first topic, difficulty=1, target_weakness=False
    assert result["topic"] == topics_default[0]
    assert result["difficulty"] == expected_difficulty
    assert result["target_weakness"] is False
