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


# --- a game FEB never marks as finished (issue #724) --------------------------------------------------------------------------------------------------------
# Match 2537218 of 3a FEB (B-B) was played on 11-10-2026 and FEB still says status 1 («SCHEDULED») with its four quarters filled in: the rule above skipped it in every refresh,
# for weeks, and the refresh went red every time because the calendar lists it as played and it is not stored. A game cannot be live 8 hours after it started: past that time,
# with the score of the four quarters in (``HEADER.QUARTERS.QUARTER``: ``{n, scoreA, scoreB}``), the game is assumed finished and stored (a refresh of the last days still
# replaces it if FEB corrects it).
from datetime import datetime, timedelta  # noqa: E402

REAL_QUARTERS = [{"n": "1", "scoreA": "13", "scoreB": "19"}, {"n": "2", "scoreA": "27", "scoreB": "19"}, {"n": "3", "scoreA": "10", "scoreB": "32"}, {"n": "4", "scoreA": "11", "scoreB": "19"}]


def _started(hours_ago, status="1", quarters=REAL_QUARTERS):
    started = datetime.now() - timedelta(hours=hours_ago)
    header = {"status": status, "statusText": "SCHEDULED", "starttime": started.strftime("%d-%m-%Y - %H:%M")}
    if quarters is not None:
        header["QUARTERS"] = {"QUARTER": quarters}
    return {"HEADER": header}


@pytest.mark.parametrize("status", ["1", "2", "0"])
def test_a_game_with_its_four_quarters_that_started_long_ago_is_stored_whatever_status_feb_shows(status):
    job, db = _run(_started(24 * 4, status=status))
    db.insert_boxscore.assert_called_once()
    assert job["skipped"] == 0 and job["errors"] == []


def test_an_overtime_game_has_its_four_quarters_and_more():
    job, db = _run(_started(24, quarters=REAL_QUARTERS + [{"n": "5", "scoreA": "7", "scoreB": "5"}]))
    db.insert_boxscore.assert_called_once()


@pytest.mark.parametrize("hours", [0.5, 3, 7, 7.9])
def test_a_game_that_started_less_than_eight_hours_ago_is_still_in_progress_even_with_four_quarters(hours):
    job, db = _run(_started(hours))
    db.insert_boxscore.assert_not_called()
    assert job["skipped"] == 1


@pytest.mark.parametrize("quarters", [None, [], REAL_QUARTERS[:1], REAL_QUARTERS[:3]])
def test_a_game_without_its_four_quarters_is_not_stored_however_old_it_is(quarters):
    """Nothing says it was played to the end (postponed, or never played, or still at the third quarter)."""
    job, db = _run(_started(24 * 10, quarters=quarters))
    db.insert_boxscore.assert_not_called()
    assert job["skipped"] == 1


@pytest.mark.parametrize("hole", [{"n": "4", "scoreA": None, "scoreB": "19"}, {"n": "4", "scoreA": "11", "scoreB": ""}, {"n": "4"}, {"n": "4", "scoreA": "x", "scoreB": "2"}])
def test_a_quarter_without_both_scores_is_not_filled(hole):
    job, db = _run(_started(24 * 10, quarters=REAL_QUARTERS[:3] + [hole]))
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

    now = datetime(2026, 11, 4, 20, 0)
    doc = {"HEADER": {"status": "1", "starttime": "04-11-2026 - 12:00", "QUARTERS": {"QUARTER": REAL_QUARTERS}}}
    assert STALE_AFTER == timedelta(hours=8)
    assert is_in_progress(doc, now=datetime(2026, 11, 4, 19, 59))                       # one minute short of the 8 h: still in progress
    assert is_in_progress(doc, now=now)                                                 # exactly 8 h: not more than 8 h yet
    assert not is_in_progress(doc, now=datetime(2026, 11, 4, 20, 1))
    assert not is_in_progress({"HEADER": {"status": "3"}}, now=now)                       # a finished one is never in progress
