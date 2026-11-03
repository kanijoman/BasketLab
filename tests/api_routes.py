"""The operations of the API as the OpenAPI schema lists them: ``{(METHOD, path): operation}``.

``app.routes`` is not a stable way to list them: since FastAPI 0.16x an included router is kept as a nested ``_IncludedRouter`` instead of being flattened, so a loop over
``app.routes`` finds none of the ``/api/v1`` routes (the CI has the newer version, a development machine may not) and a test that checks "every route is X" passes without checking
anything. The OpenAPI schema is the same in every version. A route that is not in the schema (the docs) is not an operation of the API.
"""
from typing import Any, Dict, Tuple

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
ADMIN_HEADER = "x-admin-key"


def api_operations(app: Any) -> Dict[Tuple[str, str], Dict[str, Any]]:
    operations: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for path, item in app.openapi()["paths"].items():
        for method, operation in item.items():
            if method in HTTP_METHODS:
                operations[(method.upper(), path)] = operation
    assert any(path.startswith("/api/v1/") for _, path in operations), "the API routes are not in the schema"
    return operations


def takes_the_admin_key(operation: Dict[str, Any]) -> bool:
    """``Depends(require_admin)`` reads the ``X-Admin-Key`` header, which the schema lists as a header parameter of the operation."""
    return any(p.get("in") == "header" and p.get("name", "").lower() == ADMIN_HEADER for p in operation.get("parameters", []))
