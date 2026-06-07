"""Ticket adapter contract + mock implementation.

`TicketAdapter.create_ticket` is a locked public signature (CLAUDE.md § Rules #4 —
no change without RFC). The mock writes to its own `tickets.db` and is idempotent by
`event_hash`: a repeated event returns the existing ticket id (defense-in-depth on
top of the audit guard, mirroring the Jira MCP dedup pattern in AI-Factory).
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from app.config import get_settings
from app.logger import log_info


class TicketAdapter(Protocol):
    def create_ticket(self, *, event_hash: str, summary: str, severity: str) -> str:
        """Create (or return existing) ticket; returns the ticket id."""
        ...


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"

    id: int | None = Field(default=None, primary_key=True)
    event_hash: str = Field(index=True, unique=True)
    ticket_id: str
    summary: str
    severity: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MockTicketAdapter:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_settings().tickets_db_path
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(self.engine, tables=[Ticket.__table__])  # type: ignore[attr-defined]

    def create_ticket(self, *, event_hash: str, summary: str, severity: str) -> str:
        with Session(self.engine) as session:
            existing = session.exec(select(Ticket).where(col(Ticket.event_hash) == event_hash)).first()
            if existing is not None:
                return existing.ticket_id

            ticket = Ticket(event_hash=event_hash, ticket_id="", summary=summary, severity=severity)
            session.add(ticket)
            session.flush()  # assigns autoincrement id
            assert ticket.id is not None
            ticket.ticket_id = f"DEMO-{ticket.id:03d}"
            session.add(ticket)
            session.commit()
            log_info(f"created ticket {ticket.ticket_id}", "MockTicketAdapter", "ticket.created", {"event": event_hash})
            return ticket.ticket_id
