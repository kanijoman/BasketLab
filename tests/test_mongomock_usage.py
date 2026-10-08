"""In-memory Mongo databases are created through ``tests/db_helpers.new_mock_db``
(or the ``conftest`` fixtures), never with ad-hoc ``mongomock.MongoClient()`` (issue #117)."""
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ALLOWED = {"db_helpers.py", Path(__file__).name}


def test_tests_do_not_create_mongomock_clients_directly():
    offenders = [
        p.name
        for p in TESTS.glob("*.py")
        if p.name not in ALLOWED and "mongomock.MongoClient(" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
