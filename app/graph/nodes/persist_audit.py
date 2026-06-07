"""persist_audit node: write the terminal EventRecord to the audit store."""

import json
from datetime import UTC, datetime
from typing import Any

from app.graph.deps import GraphDeps
from app.state import EventRecord, MonitorState, Status


def persist_audit_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    assert state.event_hash is not None
    # DROPPED/FAILED are set upstream; anything that reaches the end of the happy path is DONE
    status = state.status if state.status in (Status.DROPPED, Status.FAILED) else Status.DONE
    record = EventRecord(
        event_hash=state.event_hash,
        status=status,
        ticket_id=state.ticket_id,
        owner_email=state.owner.owner_email if state.owner else None,
        notified_at=datetime.now(UTC) if state.notified else None,
        timings_json=json.dumps(state.timings) if state.timings else None,
        tokens_total=state.tokens,
    )
    deps.audit.save(record)
    return {"status": status}
