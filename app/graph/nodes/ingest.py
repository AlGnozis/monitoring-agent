"""ingest node: compute the idempotency key and short-circuit known events."""

from typing import Any

from app.graph.deps import GraphDeps
from app.state import MonitorState, Status, compute_event_hash


def ingest_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    entry = state.raw_entry
    event_hash = compute_event_hash(entry.source, entry.entry_id)
    update: dict[str, Any] = {"event_hash": event_hash}

    # idempotency (invariant #2): already DONE -> reflect prior result, route to END
    if deps.audit.is_processed(event_hash):
        record = deps.audit.get(event_hash)
        update["status"] = Status.DONE
        if record is not None:
            update["ticket_id"] = record.ticket_id
            update["notified"] = True
    return update
