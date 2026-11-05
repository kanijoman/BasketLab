"""The classifier of database failures lives with the data layer (``src/database/db_health.py``, issue #334); the server keeps this name for its routes and tests."""
from src.database.db_health import HINTS, classify_db_error, hint_for  # noqa: F401
