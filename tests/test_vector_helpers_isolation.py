"""The helpers that build the vector fixtures must not leave ``pymongo`` patched for the tests that run after them (#916).

``generate_talent_data.fixture_connection`` and ``generate_web_data.fixture_handler`` swap ``pymongo.MongoClient`` for mongomock to build their handler and never swapped it back, so a later test that
asks "is there a real mongod?" (``test_local_vectors._real_mongod``) pinged mongomock, found one and ran FBCYL's player pipeline (``$substrCP``) on it:
``pytest tests/test_market_vectors.py tests/test_local_vectors.py`` failed in that order and passed in any other. Bug of the order, not of the pipeline: the test below fails on the helpers as they were.
"""
import sys
from pathlib import Path

import pymongo
import pytest

sys.path[:0] = [str(Path(__file__).resolve().parent / "local_vectors")]

import generate_talent_data  # noqa: E402
import generate_web_data  # noqa: E402

from src.database import shared_handler as _shared  # noqa: E402


@pytest.fixture
def restore_pymongo(monkeypatch):
    """Put ``pymongo.MongoClient`` and the handler cache back at the end, so a helper that leaks cannot break the tests after this one (the assertion is the test)."""
    monkeypatch.setattr(pymongo, "MongoClient", pymongo.MongoClient)
    yield
    _shared.shared_handler.cache_clear()


@pytest.mark.parametrize("helper", [generate_talent_data.fixture_connection, generate_web_data.fixture_handler], ids=["talent", "web"])
def test_a_vector_helper_leaves_pymongo_as_it_found_it_regression(restore_pymongo, helper):
    before = pymongo.MongoClient
    result = helper()
    assert pymongo.MongoClient is before                                    # the real client, so nobody later mistakes mongomock for a mongod
    assert result is not None                                               # and it still hands out a usable mongomock-backed handler
    assert _shared.shared_handler.cache_info().currsize == 0                  # the mongomock handler is not left in the cache of the API either
