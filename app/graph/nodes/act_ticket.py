"""act_ticket node: create the ticket (idempotent external action)."""

from typing import Any

from app.graph.deps import GraphDeps
from app.state import MonitorState


def act_ticket_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    assert state.event_hash is not None
    assert state.triage is not None and state.action_plan is not None
    # invariant #2: guard before the external action
    if deps.audit.is_processed(state.event_hash):
        return {}
    ticket_id = deps.ticket.create_ticket(
        event_hash=state.event_hash,
        summary=state.action_plan.summary,
        severity=state.triage.severity,
    )
    return {"ticket_id": ticket_id}
