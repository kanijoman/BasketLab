"""FastAPI dependency providers for BasketLab.

All route handlers that need a database connection should declare a
parameter ``db: MongoDBHandler = Depends(get_db)`` so the handler is
provided with a fully connected (or at least initialised) database handler.

The handler is a module-level singleton — MongoDB connections are
thread-safe and re-usable across requests.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException


@lru_cache(maxsize=1)
def _create_handler():
    """Lazy-initialise MongoDBHandler once per process."""
    import sys
    import os
    # Ensure 'src/' is importable as a package root in both run modes.
    _src = os.path.join(os.path.dirname(__file__), "..", "..")
    if _src not in sys.path:
        sys.path.insert(0, os.path.abspath(_src))

    # Import after path is set up.
    from src.database import MongoDBHandler  # noqa: PLC0415
    handler = MongoDBHandler()
    return handler


def get_db():
    """FastAPI dependency that yields the shared MongoDBHandler.

    Raises ``HTTP 503`` when the database is not reachable so callers
    receive a clean JSON error instead of an unhandled exception.
    """
    from src.api.db_health import classify_db_error, hint_for

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
