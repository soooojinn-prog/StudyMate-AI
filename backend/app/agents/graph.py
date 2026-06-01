"""LangGraph topology + public run/resume API.

Topology (linear with one interrupt):
    START -> coordinator -> question_generator -> await_answer -> grader -> persist -> END

`await_answer` is a no-op node placed where `interrupt_before` triggers,
so the graph pauses after QuestionGenerator and before Grader runs. The
API layer (Plan 4) collects the learner's answer, writes it into state,
then calls `resume_session(thread_id, user_answer)`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.coordinator import coordinator_node
from app.agents.nodes.grader import grader_node
from app.agents.nodes.persist import persist_node
from app.agents.nodes.question_generator import question_generator_node
from app.agents.state import SessionState

WeaknessProvider = Callable[[str], list[str]]
PersistAdapter = Callable[[dict[str, Any]], None] | None


def _await_answer_node(state: SessionState) -> dict[str, Any]:
    """No-op pause point. The actual answer is injected by resume_session()."""
    return {}


def build_graph(
    *,
    checkpointer: Any,
    retriever: Any,
    anthropic_client: Any,
    weakness_provider: WeaknessProvider,
    persist_adapter: PersistAdapter,
    topics: list[str],
    sonnet_model: str,
    haiku_model: str,
    user_intent: str = "자유 학습",
) -> Any:
    """Compile the StudyMate learning-session graph with the given dependencies."""
    sg: StateGraph = StateGraph(SessionState)

    def _coordinator(state: SessionState) -> dict[str, Any]:
        weak_topics = weakness_provider(state.get("user_id", "")) or []
        return coordinator_node(
            state,
            client=anthropic_client,
            model=haiku_model,
            topics=topics,
            weak_topics=weak_topics,
            user_intent=user_intent,
        )

    def _qgen(state: SessionState) -> dict[str, Any]:
        return question_generator_node(
            state, client=anthropic_client, model=sonnet_model, retriever=retriever
        )

    def _grader(state: SessionState) -> dict[str, Any]:
        return grader_node(state, client=anthropic_client, model=sonnet_model)

    def _persist(state: SessionState) -> dict[str, Any]:
        # SessionState is a TypedDict so it's structurally a dict[str, Any].
        # Cast both args to dodge invariant TypedDict / Protocol arg-type errors.
        return persist_node(dict(state), adapter=persist_adapter)  # type: ignore[arg-type]

    sg.add_node("coordinator", _coordinator)
    sg.add_node("question_generator", _qgen)
    sg.add_node("await_answer", _await_answer_node)
    sg.add_node("grader", _grader)
    sg.add_node("persist", _persist)

    sg.add_edge(START, "coordinator")
    sg.add_edge("coordinator", "question_generator")
    sg.add_edge("question_generator", "await_answer")
    sg.add_edge("await_answer", "grader")
    sg.add_edge("grader", "persist")
    sg.add_edge("persist", END)

    return sg.compile(checkpointer=checkpointer, interrupt_before=["await_answer"])


def run_session(
    *,
    graph: Any,
    user_id: str,
    session_id: str,
    target_count: int = 5,
) -> Any:
    """Invoke the graph for a new session; returns state at the AWAIT_ANSWER pause."""
    config = {"configurable": {"thread_id": session_id}}
    initial: SessionState = {
        "user_id": user_id,
        "session_id": session_id,
        "questions_done": 0,
        "target_count": target_count,
    }
    return graph.invoke(initial, config=config)


def resume_session(
    *,
    graph: Any,
    session_id: str,
    user_answer: str,
) -> Any:
    """Inject the learner's answer into state and resume through Grader/Persist."""
    config = {"configurable": {"thread_id": session_id}}
    # update_state writes the answer into the snapshot; next invoke() picks it up
    graph.update_state(config, {"user_answer": user_answer})
    return graph.invoke(None, config=config)
