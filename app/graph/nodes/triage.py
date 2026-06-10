"""triage node: classify the entry via the (injected) LLM triage callable."""

from typing import Any

from app.graph.deps import GraphDeps
from app.state import MonitorState, Status


def triage_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    triage, tokens = deps.triage(state.raw_entry)
    update: dict[str, Any] = {"triage": triage, "tokens": state.tokens + tokens}
    if not triage.is_incident:
        update["status"] = Status.DROPPED  # noise -> routed straight to persist_audit
    return update
