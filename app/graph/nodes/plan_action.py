"""plan_action node: produce summary + recommendations via the (injected) LLM."""

from typing import Any

from app.graph.deps import GraphDeps
from app.state import MonitorState, RagContext


def plan_action_node(state: MonitorState, deps: GraphDeps) -> dict[str, Any]:
    context = state.rag_context or RagContext(chunks=[], context_empty=True)
    plan, tokens = deps.plan(state.raw_entry, context)
    return {"action_plan": plan, "tokens": state.tokens + tokens}
