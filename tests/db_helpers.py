"""Shared helpers for tests that need an in-memory MongoDB."""
import mongomock


def new_mock_db(name: str = "basketlab_test"):
    """Return a fresh, empty mongomock database."""
    return mongomock.MongoClient()[name]
