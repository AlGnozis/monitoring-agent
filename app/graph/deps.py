"""Dependency container injected into graph nodes.

Lightweight on purpose (no langchain import) so graph wiring/tests can build a graph
with fakes without pulling the LLM stack. Real wiring lives in `app.graph.wiring`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.adapters.notify import NotifyAdapter
from app.adapters.ticket import TicketAdapter
from app.state import FeedEntry, OwnerInfo, PlanOutput, RagContext, TriageOutput
from app.store.audit import AuditStore


@dataclass
class GraphDeps:
    triage: Callable[[FeedEntry], tuple[TriageOutput, int]]
    retrieve: Callable[[str], RagContext]
    resolve_owner: Callable[[str], OwnerInfo]
    plan: Callable[[FeedEntry, RagContext], tuple[PlanOutput, int]]
    ticket: TicketAdapter
    notify: NotifyAdapter
    audit: AuditStore
