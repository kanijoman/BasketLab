"""Play-by-play parsing without any database dependency.

Pure modules shared by the DB-backed analyzers (``src.database``, ``src.services``) and
the live-game runtime. Nothing in this package may import ``pymongo``, ``src.database``
or ``src.services`` (enforced by ``tests/test_pbp_shims.py``).
"""
