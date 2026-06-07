"""Assemble and run the monitoring StateGraph.

Flow: ingest -> triage -> enrich_rag -> resolve_owner -> plan_action
      -> act_ticket -> act_notify -> persist_audit
Conditional edges: known event -> END (idempotency); non-incident -> persist_audit (drop).
`recursion_limit` is set here, in one place (invariant #6).
"""

import time
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from app.graph.deps import GraphDeps
from app.graph.nodes.act_notify import act_notify_node
from app.graph.nodes.act_ticket import act_ticket_node
from app.graph.nodes.enrich_rag import enrich_rag_node
from app.graph.nodes.ingest import ingest_node
from app.graph.nodes.persist_audit import persist_audit_node
from app.graph.nodes.plan_action import plan_action_node
from app.graph.nodes.resolve_owner import resolve_owner_node
from app.graph.nodes.triage import triage_node
from app.state import MonitorState, Status

RECURSION_LIMIT = 10

_Node = Callable[[MonitorState, GraphDeps], dict[str, Any]]


def _wrap(name: str, node: _Node, deps: GraphDeps) -> Callable[[MonitorState], dict[str, Any]]:
    """Bind deps and record per-node timing (merged into the accumulating state.timings)."""

    def runner(state: MonitorState) -> dict[str, Any]:
        started = time.perf_counter()
        update = node(state, deps)
        update["timings"] = {**state.timings, name: round(time.perf_counter() - started, 4)}
        return update

    return runner


def _route_after_ingest(state: MonitorState) -> str:
    return "processed" if state.status == Status.DONE else "continue"


def _route_after_triage(state: MonitorState) -> str:
    return "incident" if state.triage is not None and state.triage.is_incident else "drop"


def build_graph(deps: GraphDeps) -> Any:
    builder = StateGraph(MonitorState)
    nodes: dict[str, _Node] = {
        "ingest": ingest_node,
        "triage": triage_node,
        "enrich_rag": enrich_rag_node,
        "resolve_owner": resolve_owner_node,
        "plan_action": plan_action_node,
        "act_ticket": act_ticket_node,
        "act_notify": act_notify_node,
        "persist_audit": persist_audit_node,
    }
    for name, node in nodes.items():
        # langgraph's overloaded add_node typing doesn't accept our wrapped callable cleanly
        builder.add_node(name, _wrap(name, node, deps))  # type: ignore[call-overload]

    builder.set_entry_point("ingest")
    builder.add_conditional_edges("ingest", _route_after_ingest, {"processed": END, "continue": "triage"})
    builder.add_conditional_edges("triage", _route_after_triage, {"incident": "enrich_rag", "drop": "persist_audit"})
    builder.add_edge("enrich_rag", "resolve_owner")
    builder.add_edge("resolve_owner", "plan_action")
    builder.add_edge("plan_action", "act_ticket")  # human_gate is an iter-2 insertion point here
    builder.add_edge("act_ticket", "act_notify")
    builder.add_edge("act_notify", "persist_audit")
    builder.add_edge("persist_audit", END)
    return builder.compile()


def run_monitor(state: MonitorState, *, deps: GraphDeps | None = None, graph: Any | None = None) -> MonitorState:
    """Run one entry through the graph and return the final MonitorState."""
    if deps is None:
        from app.graph.wiring import default_deps  # lazy: avoids importing the LLM stack for tests

        deps = default_deps()
    graph = graph or build_graph(deps)
    result = graph.invoke(state, config={"recursion_limit": RECURSION_LIMIT})
    return result if isinstance(result, MonitorState) else MonitorState.model_validate(result)
