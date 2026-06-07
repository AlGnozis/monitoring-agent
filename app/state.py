"""Canonical data contract for the monitoring graph.

Single source of truth for everything that flows through the LangGraph state machine
(CLAUDE.md § Style: shared models live in `app/state.py`):

- enums `Severity`, `Status`;
- stage payloads `FeedEntry`, `TriageOutput`, `RagContext`, `OwnerInfo`, `PlanOutput`;
- `MonitorState` — the accumulating graph state (Pydantic, flows node-to-node);
- `EventRecord` — the row persisted to `audit.db` (SQLModel table);
- `compute_event_hash` — idempotency key helper (invariant #2).

All structured-output models are flat to satisfy the GigaChat schema constraints
(invariant #5: no `anyOf`, no `type:object` without `properties`, no `type:array`
without `items`). `llm/schemas.py` (Task 5) re-exports `TriageOutput` / `PlanOutput`
and adds GigaChat binding helpers — it does not redefine them.
"""

import hashlib
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


class Severity(StrEnum):
    """Incident severity. Member value == name so it serialises as a plain string."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Status(StrEnum):
    """Terminal/observable lifecycle status recorded in the audit store."""

    PENDING = "PENDING"  # in flight, default before the graph finishes
    DROPPED = "DROPPED"  # triage decided it is not an actionable incident (noise)
    DONE = "DONE"  # full pipeline succeeded (ticket + notification)
    FAILED = "FAILED"  # a node raised; see MonitorState.error / EventRecord


class FeedEntry(BaseModel):
    """One normalised item from a source (fake feed or live RSS)."""

    entry_id: str
    title: str
    body: str
    source: str
    published_at: datetime | None = None


class TriageOutput(BaseModel):
    """GigaChat structured output of the triage node (flat, GigaChat-safe)."""

    is_incident: bool
    severity: Severity
    topic: str
    affected_system: str


class RagContext(BaseModel):
    """Retrieved knowledge for the entry; `context_empty` drives graceful degradation."""

    chunks: list[str] = Field(default_factory=list)
    context_empty: bool = True


class OwnerInfo(BaseModel):
    """Resolved owner of the affected system (from owners.yaml / RAG lookup)."""

    affected_system: str
    owner_name: str
    owner_email: str
    team: str


class PlanOutput(BaseModel):
    """GigaChat structured output of the plan_action node (flat, GigaChat-safe)."""

    summary: str
    recommendations: list[str] = Field(default_factory=list)
    escalate_to: str


class MonitorState(BaseModel):
    """Accumulating state passed between graph nodes.

    Starts from `raw_entry`; each node fills in its slice. `event_hash` is the
    idempotency key checked before every external action (invariant #2).
    """

    raw_entry: FeedEntry
    event_hash: str | None = None
    triage: TriageOutput | None = None
    rag_context: RagContext | None = None
    owner: OwnerInfo | None = None
    action_plan: PlanOutput | None = None
    ticket_id: str | None = None
    notified: bool = False
    status: Status = Status.PENDING
    timings: dict[str, float] = Field(default_factory=dict)
    tokens: int = 0
    error: str | None = None


class EventRecord(SQLModel, table=True):
    """Audit row persisted to `audit.db` (table `records`)."""

    __tablename__ = "records"

    event_hash: str = SQLField(primary_key=True)
    status: Status = SQLField(default=Status.PENDING)
    ticket_id: str | None = SQLField(default=None)
    owner_email: str | None = SQLField(default=None)
    notified_at: datetime | None = SQLField(default=None)
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))
    timings_json: str | None = SQLField(default=None)
    tokens_total: int = SQLField(default=0)


def compute_event_hash(source_id: str, entry_id: str) -> str:
    """Idempotency key (invariant #2): ``sha256(source_id + entry_id)``.

    Concatenation matches the invariant literally; collisions across differently
    split (source_id, entry_id) pairs are theoretically possible — raise with
    pipeline-keeper if a separator is preferred.
    """
    return hashlib.sha256(f"{source_id}{entry_id}".encode()).hexdigest()
