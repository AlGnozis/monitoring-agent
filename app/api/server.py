"""FastAPI surface: POST /trigger, GET /health, GET /audit[/{event_hash}].

All responses are JSON; errors use the unified shape {"error": <code>, "message": <msg>}
(invariant #1). Dependencies are provided via FastAPI Depends so tests can override
them with fakes (no network / no GigaChat).
"""

from functools import lru_cache
from typing import Any

import requests
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_settings
from app.graph.build import run_monitor
from app.graph.deps import GraphDeps
from app.ingest.sources import Source, get_source
from app.state import EventRecord, MonitorState

app = FastAPI(title="monitoring-agent")


# --- dependency providers (overridable in tests) ---
@lru_cache
def _runtime_deps() -> GraphDeps:
    from app.graph.wiring import default_deps  # lazy: keep LLM stack out of import time

    return default_deps()


def provide_deps() -> GraphDeps:
    return _runtime_deps()


def provide_source() -> Source:
    return get_source()


# --- helpers ---
def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _record_dict(record: EventRecord) -> dict[str, Any]:
    return {
        "event_hash": record.event_hash,
        "status": record.status,
        "ticket_id": record.ticket_id,
        "owner_email": record.owner_email,
        "notified_at": record.notified_at.isoformat() if record.notified_at else None,
        "created_at": record.created_at.isoformat(),
        "tokens_total": record.tokens_total,
    }


# --- unified JSON error handlers (invariant #1) ---
@app.exception_handler(RequestValidationError)
async def _on_validation_error(_: Any, exc: RequestValidationError) -> JSONResponse:
    return _error(422, "validation", str(exc))


@app.exception_handler(Exception)
async def _on_unhandled(_: Any, exc: Exception) -> JSONResponse:
    return _error(500, "internal", str(exc))


# --- endpoints ---
class TriggerRequest(BaseModel):
    entry_id: str


@app.post("/trigger")
def trigger(
    body: TriggerRequest,
    source: Source = Depends(provide_source),
    deps: GraphDeps = Depends(provide_deps),
) -> Any:
    entry = source.get(body.entry_id)
    if entry is None:
        return _error(404, "entry_not_found", f"no entry with id {body.entry_id}")
    result = run_monitor(MonitorState(raw_entry=entry), deps=deps)
    return {"status": result.status, "event_hash": result.event_hash, "ticket_id": result.ticket_id}


@app.get("/health")
def health() -> Any:
    base = get_settings().embedding_service_url.rstrip("/")
    try:
        ok = requests.get(f"{base}/health", timeout=2).status_code == 200
    except requests.RequestException:
        ok = False
    if not ok:
        return _error(503, "embedding_service_down", "embedding-service is not reachable")
    return {"status": "ok", "embedding_service": "ok"}


@app.get("/audit")
def audit_list(limit: int = 20, deps: GraphDeps = Depends(provide_deps)) -> dict[str, Any]:
    records = deps.audit.list_records(limit)
    return {"records": [_record_dict(r) for r in records], "total": len(records)}


@app.get("/audit/{event_hash}")
def audit_get(event_hash: str, deps: GraphDeps = Depends(provide_deps)) -> Any:
    record = deps.audit.get(event_hash)
    if record is None:
        return _error(404, "not_found", f"no audit record for {event_hash}")
    return _record_dict(record)
