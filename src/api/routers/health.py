"""Public health endpoints (no secrets): is the database reachable from this server?"""
from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api import deps
from src.api.db_health import classify_db_error, hint_for

router = APIRouter()


def _failure(kind: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"connected": False, "error": kind, "hint": hint_for(kind)})


@router.get("", summary="Liveness and deployed commit (public, no database needed)")
def liveness() -> Dict[str, Any]:
    """``commit`` = Render's ``RENDER_GIT_COMMIT``: the post-deploy check waits until it is the pushed one."""
    return {"status": "ok", "commit": os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_COMMIT") or None}


@router.get("/db", summary="Database connectivity (public, no credentials)")
def database_health():
    started = time.perf_counter()
    try:
        handler = deps._create_handler()
    except Exception as exc:  # noqa: BLE001 - classified, never echoed
        return _failure(classify_db_error(exc))
    if not handler.is_connected():
        return _failure(getattr(handler.connection, "last_error_kind", None) or "unreachable")
    try:
        names = handler.connection.get_database().list_collection_names()
    except Exception as exc:  # noqa: BLE001
        return _failure(classify_db_error(exc))
    body: Dict[str, Any] = {"connected": True, "collections": len(names),
                            "latency_ms": round((time.perf_counter() - started) * 1000)}
    return body
