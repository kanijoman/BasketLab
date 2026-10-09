"""Safe classification of database failures (no credentials, hosts or raw messages leak out).

Production once answered ``500 Internal Server Error`` on every database endpoint because building the
handler raised (``MONGODB_CONNECTION_STRING`` missing / credentials rejected): the failure is now turned
into a kind + an actionable hint, shown by ``get_db`` (503) and by the public ``/api/v1/health/db``.
"""
from __future__ import annotations

from typing import Optional

from pymongo import errors as pme

HINTS = {
    "missing_config": "Falta la variable MONGODB_CONNECTION_STRING en el servidor (Render → Environment).",
    "auth_failed": "MongoDB rechazó la autenticación: revisar usuario y contraseña de la cadena de conexión (Atlas → Database Access).",
    "not_authorized": "El usuario de MongoDB no tiene permisos sobre la base de datos BASKETBALL (Atlas → Database Access).",
    "unreachable": "No se alcanza el servidor MongoDB: revisar Atlas → Network Access (IPs permitidas) y que el clúster esté activo.",
    "invalid_config": "La cadena de conexión de MongoDB no es válida.",
    "error": "Error inesperado al conectar con MongoDB (ver los logs del servidor).",
}


def classify_db_error(exc: BaseException) -> str:
    """Kind of failure: missing_config | auth_failed | not_authorized | unreachable | invalid_config | error."""
    if isinstance(exc, RuntimeError) and "MONGODB_CONNECTION_STRING" in str(exc):
        return "missing_config"
    if isinstance(exc, pme.OperationFailure):
        text = str(exc).lower()
        if getattr(exc, "code", None) == 13 or "not authorized" in text or "unauthorized" in text:
            return "not_authorized"
        return "auth_failed" if getattr(exc, "code", None) == 18 or "auth" in text else "error"
    if isinstance(exc, (pme.ServerSelectionTimeoutError, pme.ConnectionFailure)):
        return "unreachable"
    if isinstance(exc, (pme.ConfigurationError, pme.InvalidURI)):
        return "invalid_config"
    return "error"


def hint_for(kind: Optional[str]) -> str:
    return HINTS.get(kind or "error", HINTS["error"])
