"""Adapter factories — the ONLY place that branches on the `ADAPTERS` selector.

Business logic depends on the `TicketAdapter` / `NotifyAdapter` Protocols, never on
the mode (CLAUDE.md § Rules #5). `real` is intentionally unimplemented (invariant #4:
mock-only) and raises a clear error if selected.
"""

from app.adapters.notify import MockNotifyAdapter, NotifyAdapter
from app.adapters.ticket import MockTicketAdapter, TicketAdapter
from app.config import Settings, get_settings


def get_ticket_adapter(settings: Settings | None = None) -> TicketAdapter:
    settings = settings or get_settings()
    if settings.adapters == "real":
        raise NotImplementedError("real TicketAdapter is not implemented (mock-only, invariant #4)")
    return MockTicketAdapter(db_path=settings.tickets_db_path)


def get_notify_adapter(settings: Settings | None = None) -> NotifyAdapter:
    settings = settings or get_settings()
    if settings.adapters == "real":
        raise NotImplementedError("real NotifyAdapter is not implemented (mock-only, invariant #4)")
    return MockNotifyAdapter(outbox_dir=settings.outbox_path)
