"""Production wiring of GraphDeps (real GigaChat / RAG / adapters / store).

Imported lazily by build.run_monitor so unit tests can build the graph with fakes
without loading the LLM stack.
"""

from collections.abc import Callable
from typing import Any, cast

from langchain_core.messages import HumanMessage, SystemMessage

from app.adapters.factory import get_notify_adapter, get_ticket_adapter
from app.config import Settings, get_settings
from app.graph.deps import GraphDeps
from app.graph.owners import known_systems, make_owner_resolver
from app.llm.gigachat_client import build_gigachat
from app.llm.prompts import PLAN_SYSTEM, TRIAGE_SYSTEM, plan_user, triage_user
from app.llm.schemas import PlanOutput, TriageOutput
from app.rag.retriever import retrieve
from app.state import FeedEntry, RagContext
from app.store.audit import AuditStore


def _total_tokens(raw: Any) -> int:
    """Total tokens from a raw chat result; tolerant of providers that omit usage."""
    usage = getattr(raw, "usage_metadata", None)
    if usage:
        return int(usage.get("total_tokens") or 0)
    meta = getattr(raw, "response_metadata", None) or {}
    return int((meta.get("token_usage") or {}).get("total_tokens") or 0)


def make_triage(settings: Settings) -> Callable[[FeedEntry], tuple[TriageOutput, int]]:
    llm = build_gigachat(model=settings.gigachat_model, temperature=0.0, settings=settings)
    # include_raw keeps the raw AIMessage alongside the parsed model so we can read token usage
    structured = llm.with_structured_output(TriageOutput, include_raw=True)
    systems = ", ".join(known_systems(settings.owners_path))
    system_prompt = (
        f"{TRIAGE_SYSTEM}\n\n"
        f"Поле affected_system заполняй РОВНО одним значением из списка "
        f'(латиницей, как здесь), иначе "unknown": {systems}.'
    )

    def triage(entry: FeedEntry) -> tuple[TriageOutput, int]:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=triage_user(entry))]
        out = cast(dict[str, Any], structured.invoke(messages))
        parsed = out["parsed"]
        model = parsed if isinstance(parsed, TriageOutput) else TriageOutput.model_validate(parsed)
        return model, _total_tokens(out["raw"])

    return triage


def make_plan(settings: Settings) -> Callable[[FeedEntry, RagContext], tuple[PlanOutput, int]]:
    llm = build_gigachat(model=settings.gigachat_model, temperature=0.2, settings=settings)
    structured = llm.with_structured_output(PlanOutput, include_raw=True)

    def plan(entry: FeedEntry, context: RagContext) -> tuple[PlanOutput, int]:
        messages = [SystemMessage(content=PLAN_SYSTEM), HumanMessage(content=plan_user(entry, context))]
        out = cast(dict[str, Any], structured.invoke(messages))
        parsed = out["parsed"]
        model = parsed if isinstance(parsed, PlanOutput) else PlanOutput.model_validate(parsed)
        return model, _total_tokens(out["raw"])

    return plan


def default_deps(settings: Settings | None = None) -> GraphDeps:
    settings = settings or get_settings()
    return GraphDeps(
        triage=make_triage(settings),
        retrieve=lambda query: retrieve(query, kb_path=settings.kb_path),
        resolve_owner=make_owner_resolver(settings.owners_path),
        plan=make_plan(settings),
        ticket=get_ticket_adapter(settings),
        notify=get_notify_adapter(settings),
        audit=AuditStore(settings.audit_db_path),
    )
