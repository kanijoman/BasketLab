"""Admin API key for destructive / ingestion / training endpoints (issue #115).

Set ``ADMIN_API_KEY`` and send it as the ``X-Admin-Key`` header. Without the variable
the protected routes stay open in development (local use) and are closed (503) when
``ENVIRONMENT=production``, so a deployment can never be accidentally public.
The variable is read per request so it can be rotated without code changes.
"""
import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException


def require_admin(x_admin_key: Optional[str] = Header(None)) -> None:
    expected = os.getenv("ADMIN_API_KEY", "")
    if not expected:
        if os.getenv("ENVIRONMENT", "development") == "production":
            raise HTTPException(status_code=503, detail="ADMIN_API_KEY no está configurada en el servidor")
        return
    if not x_admin_key or not hmac.compare_digest(x_admin_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Clave de administración requerida o incorrecta")
