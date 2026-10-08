"""Regression tests for the housekeeping follow-ups.

- FEB team-name index must target ``HEADER.TEAM.name`` (``HEADER.localTeam`` does
  not exist in FEB documents; see docs/DATA_FORMATS.md).
- ``datetime.utcnow()`` is deprecated: ``utc_now_naive`` replaces it and keeps
  the naive-UTC representation already stored in MongoDB.
"""
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from db_helpers import new_mock_db

from src.database.indexes import IndexManager
from src.utils.time_utils import utc_now_naive

SRC = Path(__file__).resolve().parents[1] / "src"


def test_feb_team_name_index_uses_header_team_name_regression():
    coll = new_mock_db("db")["FEB_LF2_2025_A"]
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.return_value = coll
    assert IndexManager(conn).ensure_indexes("FEB_LF2_2025_A") is True
    keys = [tuple(k for k, _ in idx["key"]) for idx in coll.index_information().values()]
    assert ("HEADER.TEAM.name",) in keys
    assert all("localTeam" not in k[0] for k in keys)


def test_utc_now_naive_is_naive_utc_and_warning_free():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        now = utc_now_naive()
    assert now.tzinfo is None
    assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - now).total_seconds()) < 5


def test_no_deprecated_utcnow_in_src():
    offenders = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*.py")
        if re.search(r"datetime\.utcnow\(", p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
