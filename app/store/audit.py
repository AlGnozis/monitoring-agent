"""SQLite audit store for EventRecord + idempotency check.

`is_processed(event_hash)` is the idempotency guard (invariant #2) consulted before
external actions and on repeat triggers: an event counts as processed once a DONE
record exists. The store owns only the `records` table (Ticket lives in its own db).
"""

from pathlib import Path

from sqlmodel import Session, SQLModel, col, create_engine, select

from app.config import get_settings
from app.state import EventRecord, Status


class AuditStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_settings().audit_db_path
        # check_same_thread=False: the store is touched from the API and poller threads
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False})
        # create only our table, not every SQLModel table registered elsewhere
        SQLModel.metadata.create_all(self.engine, tables=[EventRecord.__table__])  # type: ignore[attr-defined]

    def is_processed(self, event_hash: str) -> bool:
        """True if a DONE record already exists for this event (idempotency, invariant #2)."""
        with Session(self.engine) as session:
            record = session.get(EventRecord, event_hash)
            return record is not None and record.status == Status.DONE

    def get(self, event_hash: str) -> EventRecord | None:
        with Session(self.engine) as session:
            return session.get(EventRecord, event_hash)

    def save(self, record: EventRecord) -> None:
        """Upsert by primary key (event_hash)."""
        with Session(self.engine) as session:
            session.merge(record)
            session.commit()

    def list_records(self, limit: int = 20) -> list[EventRecord]:
        with Session(self.engine) as session:
            statement = select(EventRecord).order_by(col(EventRecord.created_at).desc()).limit(limit)
            return list(session.exec(statement))
