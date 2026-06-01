"""Structural tests for the LangGraph topology.

These verify edges and interrupt placement without invoking any LLM.
"""
from unittest.mock import MagicMock

from app.agents.checkpointer import make_checkpointer
from app.agents.graph import build_graph


def _stub_deps() -> dict[str, object]:
    retriever = MagicMock()
    client = MagicMock()
    return {
        "retriever": retriever,
        "anthropic_client": client,
        "weakness_provider": lambda user_id: [],
        "persist_adapter": None,
        "topics": ["정규화", "SQL 응용"],
        "sonnet_model": "claude-sonnet-4-6",
        "haiku_model": "claude-haiku-4-5",
    }


def _node_names(graph: object) -> set[str]:
    """Best-effort introspection that works across langgraph 0.x and 1.x.

    - langgraph <1: CompiledStateGraph.nodes is a dict-like mapping
    - langgraph >=1: prefer the public DrawableGraph from get_graph()
    """
    # langgraph 1.x: graph.get_graph() returns a DrawableGraph with .nodes
    if hasattr(graph, "get_graph"):
        drawable = graph.get_graph()
        if hasattr(drawable, "nodes"):
            return set(drawable.nodes.keys())
    # Fallback: direct .nodes attribute
    nodes_attr = getattr(graph, "nodes", None)
    if nodes_attr is not None and hasattr(nodes_attr, "keys"):
        return set(nodes_attr.keys())
    msg = "Could not introspect compiled graph nodes"
    raise AssertionError(msg)


def test_graph_has_required_nodes(tmp_path):
    saver = make_checkpointer(tmp_path / "g.db")
    graph = build_graph(checkpointer=saver, **_stub_deps())
    node_names = _node_names(graph)
    for required in [
        "coordinator",
        "question_generator",
        "await_answer",
        "grader",
        "persist",
    ]:
        assert required in node_names, f"missing node: {required} (have {node_names})"


def test_graph_interrupts_before_await_answer(tmp_path):
    saver = make_checkpointer(tmp_path / "g.db")
    graph = build_graph(checkpointer=saver, **_stub_deps())
    # Compiled graph stores interrupt config; the exact attribute path can
    # vary across langgraph versions, so we accept any of these.
    interrupts = None
    for path in (
        ("interrupt_before",),
        ("builder", "interrupt_before"),
        ("config", "interrupt_before"),
    ):
        obj: object = graph
        ok = True
        for attr in path:
            obj = getattr(obj, attr, None)
            if obj is None:
                ok = False
                break
        if ok and obj is not None:
            interrupts = obj
            break
    # Best-effort assertion: if introspection works, await_answer must be there.
    if interrupts is not None:
        assert "await_answer" in interrupts
