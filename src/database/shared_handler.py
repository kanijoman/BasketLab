"""The database handler of the process, shared by the server and by the jobs that publish data (issue #334).

It lived in ``src/api/deps.py``; the publication (``run_web_data.py``, ``run_local_reports.py``) took it from there, so it could not outlive the server. ``src/api/deps.py`` now
imports it under its old name (``_create_handler``: the tests and the dependency of the routes still call it so).
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def shared_handler():
    """Lazy-initialise MongoDBHandler once per process."""
    import os
    import sys

    # Ensure the repository root is importable as a package root in both run modes.
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    # Import after path is set up (and late: ``patch("src.database.MongoDBHandler")`` in the tests must be seen).
    from src.database import MongoDBHandler  # noqa: PLC0415

    return MongoDBHandler()
