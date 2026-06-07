"""resolve_owner node: map the affected system to its owner."""

from typing import Any

from app.graph.deps import GraphDeps
from app.state import MonitorState


def resolve_owner_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    triage = state.triage
    assert triage is not None
    return {"owner": deps.resolve_owner(triage.affected_system)}
