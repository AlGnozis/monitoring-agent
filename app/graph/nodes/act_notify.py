"""act_notify node: email the owner with the plan (idempotent external action)."""

from typing import Any

from app.graph.deps import GraphDeps
from app.state import MonitorState


def _format_body(state: MonitorState) -> str:
    triage = state.triage
    plan = state.action_plan
    owner = state.owner
    assert triage is not None and plan is not None and owner is not None
    recommendations = "\n".join(f"- {rec}" for rec in plan.recommendations) or "- (нет рекомендаций)"
    ticket_line = f"Заявка: {state.ticket_id}" if state.ticket_id else "Заявка: не создана"
    return (
        f"Здравствуйте, {owner.owner_name} (команда {owner.team})!\n\n"
        f"Зафиксирован инцидент по системе «{triage.affected_system}» "
        f"(severity: {triage.severity}, тема: {triage.topic}).\n\n"
        f"Суть: {plan.summary}\n\n"
        f"Рекомендации:\n{recommendations}\n\n"
        f"{ticket_line}\n"
        f"Эскалация: {plan.escalate_to}\n"
    )


def act_notify_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    assert state.event_hash is not None
    assert state.owner is not None and state.triage is not None
    if deps.audit.is_processed(state.event_hash):
        return {}
    subject = f"[{state.triage.severity}] Инцидент: {state.triage.affected_system}"
    deps.notify.send_notification(
        to=state.owner.owner_email,
        subject=subject,
        body=_format_body(state),
        ref=state.raw_entry.entry_id,
    )
    return {"notified": True}
