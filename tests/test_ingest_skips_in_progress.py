"""Regression: in-progress FEB matches must not be stored.

Bug: a match that is still being played already shows a score, so the scraper's
"played" filter accepts it. It was stored half-finished and ``document_exists``
then skipped it forever, so the final box score never replaced the partial one.
FEB marks finished matches with ``HEADER.status == '3'`` (``FINISHED``).
"""

import pytest
from unittest.mock import MagicMock

from src.api.routers.scrape import _store_feb_match


def _job():
    return {"done": 0, "skipped": 0, "errors": [], "current_match": None}


def _run(doc):
    job, db, scraper = _job(), MagicMock(), MagicMock()
    db.document_exists.return_value = False
    scraper.fetch_boxscore.return_value = doc
    _store_feb_match(job, db, scraper, MagicMock(), "COL", "1001")
    return job, db


@pytest.mark.parametrize("status", ["1", "2", 2, "0"])
def test_in_progress_match_is_not_stored_regression(status):
    job, db = _run({"HEADER": {"status": status, "statusText": "LIVE"}})
    db.insert_boxscore.assert_not_called()
    assert job["skipped"] == 1
    assert job["done"] == 1
    assert job["errors"] == []


@pytest.mark.parametrize("status", ["3", 3])
def test_finished_match_is_stored(status):
    job, db = _run({"HEADER": {"status": status, "statusText": "FINISHED"}})
    db.insert_boxscore.assert_called_once()
    assert job["skipped"] == 0


def test_match_without_status_is_still_stored():
    """Older documents carry no status field: keep storing them."""
    job, db = _run({"HEADER": {}})
    db.insert_boxscore.assert_called_once()
    assert job["skipped"] == 0
