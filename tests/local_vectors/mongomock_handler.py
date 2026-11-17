"""The handler over an in-memory database that the vector generators build their fixtures on (#916).

The real ``deps._create_handler`` creates its ``MongoClient`` from ``pymongo``, so it is built with the client swapped for mongomock's. The swap is undone at once and the handler is not left in the
cache of the API: a ``pymongo`` left patched made a later test that looks for a real mongod find mongomock instead.
"""
import mongomock
import pymongo

from src.api import deps


def mongomock_handler():
    """The API's own handler on mongomock; ``pymongo.MongoClient`` and the handler cache are as they were found."""
    original = pymongo.MongoClient
    pymongo.MongoClient = mongomock.MongoClient
    try:
        deps._create_handler.cache_clear()
        return deps._create_handler()
    finally:
        pymongo.MongoClient = original
        deps._create_handler.cache_clear()
