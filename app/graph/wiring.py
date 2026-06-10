"""Production wiring of GraphDeps (real GigaChat / RAG / adapters / store).

Imported lazily by build.run_monitor so unit tests can build the graph with fakes
without loading the LLM stack.
"""

from collections.abc import Callable

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


def make_triage(settings: Settings) -> Callable[[FeedEntry], TriageOutput]:
    llm = build_gigachat(model=settings.gigachat_model, temperature=0.0, settings=settings)
    structured = llm.with_structured_output(TriageOutput)
    systems = ", ".join(known_systems(settings.owners_path))
    system_prompt = (
        f"{TRIAGE_SYSTEM}\n\n"
        f"Поле affected_system заполняй РОВНО одним значением из списка "
        f'(латиницей, как здесь), иначе "unknown": {systems}.'
    )

    def triage(entry: FeedEntry) -> TriageOutput:
        result = structured.invoke([SystemMessage(content=system_prompt), HumanMessage(content=triage_user(entry))])
        return result if isinstance(result, TriageOutput) else TriageOutput.model_validate(result)

    return triage


def make_plan(settings: Settings) -> Callable[[FeedEntry, RagContext], PlanOutput]:
    llm = build_gigachat(model=settings.gigachat_model, temperature=0.2, settings=settings)
    structured = llm.with_structured_output(PlanOutput)

    def plan(entry: FeedEntry, context: RagContext) -> PlanOutput:
        result = structured.invoke(
            [SystemMessage(content=PLAN_SYSTEM), HumanMessage(content=plan_user(entry, context))]
        )
        return result if isinstance(result, PlanOutput) else PlanOutput.model_validate(result)

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
