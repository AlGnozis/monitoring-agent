"""enrich_rag node: retrieve related knowledge for the incident."""

from typing import Any

from app.graph.deps import GraphDeps
from app.state import MonitorState


def enrich_rag_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    triage = state.triage
    assert triage is not None  # only reached on the incident path (after triage)
    query = f"{triage.topic} {triage.affected_system} {state.raw_entry.title}"
    # retrieve degrades gracefully: missing index -> RagContext(context_empty=True)
    return {"rag_context": deps.retrieve(query)}
