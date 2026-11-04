"""Regression: in-progress FEB matches must not be stored.

Bug: a match that is still being played already shows a score, so the scraper's
"played" filter accepts it. It was stored half-finished and ``document_exists``
then skipped it forever, so the final box score never replaced the partial one.
FEB marks finished matches with ``HEADER.status == '3'`` (``FINISHED``).
"""

import pytest
from unittest.mock import MagicMock

from src.services.feb_match_ingest import store_feb_match as _store_feb_match


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


# --- a game FEB never marked as finished (issue #724) --------------------------------------------------------------------------------------------------------
# Match 2537218 of 3a FEB (B-B) was played on 11-10-2026 and FEB still says status 1 («SCHEDULED») with a final score of 61-89: the rule above skipped it in every refresh,
# for weeks, and the refresh went red every time because the calendar lists it as played and it is not stored. A game cannot be live two days after it started: past that
# time, with a score, what FEB shows is what the game is, and it is stored (a refresh of the last days still replaces it if FEB corrects it).
from datetime import datetime, timedelta  # noqa: E402


def _started(hours_ago, status="1", score=(61, 89)):
    started = datetime.now() - timedelta(hours=hours_ago)
    teams = [{"id": "1", "name": "A", "pts": None if score is None else str(score[0])}, {"id": "2", "name": "B", "pts": None if score is None else str(score[1])}]
    return {"HEADER": {"status": status, "statusText": "SCHEDULED", "starttime": started.strftime("%d-%m-%Y - %H:%M"), "TEAM": teams}}


@pytest.mark.parametrize("status", ["1", "2", "0"])
def test_a_game_with_a_score_that_started_days_ago_is_stored_whatever_status_feb_shows(status):
    job, db = _run(_started(24 * 4, status=status))
    db.insert_boxscore.assert_called_once()
    assert job["skipped"] == 0 and job["errors"] == []


@pytest.mark.parametrize("hours", [0.5, 3, 12, 47])
def test_a_game_that_started_recently_is_still_in_progress(hours):
    job, db = _run(_started(hours))
    db.insert_boxscore.assert_not_called()
    assert job["skipped"] == 1


@pytest.mark.parametrize("score", [None, (0, 0)])
def test_a_game_with_no_score_is_not_stored_however_old_it_is(score):
    """Nothing to store: a game FEB lists with no result (postponed, or never played) is not a finished one."""
    job, db = _run(_started(24 * 10, score=score))
    db.insert_boxscore.assert_not_called()
    assert job["skipped"] == 1


def test_a_game_whose_date_cannot_be_read_stays_in_progress():
    doc = _started(24 * 4)
    doc["HEADER"]["starttime"] = "not a date"
    job, db = _run(doc)
    db.insert_boxscore.assert_not_called()
    assert job["skipped"] == 1


def test_is_in_progress_takes_the_clock_so_the_rule_can_be_checked_exactly():
    from src.services.feb_match_ingest import STALE_AFTER, is_in_progress

    now = datetime(2026, 11, 4, 12, 0)
    doc = {"HEADER": {"status": "1", "starttime": "01-11-2026 - 12:00", "TEAM": [{"pts": "61"}, {"pts": "89"}]}}
    assert STALE_AFTER == timedelta(hours=48)
    assert not is_in_progress(doc, now=now)
    assert is_in_progress(doc, now=datetime(2026, 11, 3, 11, 59))                      # one minute short of the 48 h: still in progress
    assert not is_in_progress(doc, now=datetime(2026, 11, 3, 12, 1))
