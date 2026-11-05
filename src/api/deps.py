"""FastAPI dependency providers for BasketLab.

All route handlers that need a database connection should declare a
parameter ``db: MongoDBHandler = Depends(get_db)`` so the handler is
provided with a fully connected (or at least initialised) database handler.

The handler is a module-level singleton — MongoDB connections are
thread-safe and re-usable across requests.
"""

from __future__ import annotations

from fastapi import HTTPException

from src.database.shared_handler import shared_handler


# The handler is shared with the jobs that publish data (``src/database/shared_handler.py``); the old name stays for the routes and the tests.
_create_handler = shared_handler


def get_db():
    """FastAPI dependency that yields the shared MongoDBHandler.

    Raises ``HTTP 503`` when the database is not reachable so callers
    receive a clean JSON error instead of an unhandled exception.
    """
    from src.database.db_health import classify_db_error, hint_for

    try:
        handler = _create_handler()
    except Exception as exc:  # noqa: BLE001 - never a bare 500: say what is wrong (no secrets)
        raise HTTPException(status_code=503, detail=f"Base de datos no disponible: {hint_for(classify_db_error(exc))}") from exc
    if not handler.is_connected():
        kind = getattr(getattr(handler, "connection", None), "last_error_kind", None)
        raise HTTPException(
            status_code=503,
            detail=f"Database not connected. {hint_for(kind) if kind else 'Check MongoDB credentials.'}",
        )
    return handler
