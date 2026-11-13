"""What the refresh remembers between runs (#924): which collections are CLOSED (nothing left to check for a week) and which matches keep failing (asked a limited number of times).

The thresholds are the user's (13/11/2026): a collection whose last game is more than 14 days old and that was up to date at its last check is checked again every 7 days, not every run;
a match that fails is asked again until it has failed 20 times over at least 7 days, then it is «unavailable» and asked once a month. The state lives in ``COLLECTION_META`` (it travels in the
archive) and is saved with DAYS, never times: a time would change the archive on every refresh.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_helpers import new_mock_db  # noqa: E402

from src.services.refresh_state import (CLOSED_AFTER_DAYS, MAX_ATTEMPTS, MIN_DAYS_BEFORE_UNAVAILABLE, RECHECK_CLOSED_EVERY_DAYS, REVIEW_UNAVAILABLE_EVERY_DAYS,  # noqa: E402
                                        is_closed, load_state, record_check, record_failure, record_success, save_state, should_ask, unavailable_codes)

TODAY = date(2026, 11, 13)


def _days_ago(n):
    return date.fromordinal(TODAY.toordinal() - n).isoformat()


def test_the_thresholds_are_the_ones_the_user_set():
    assert (CLOSED_AFTER_DAYS, RECHECK_CLOSED_EVERY_DAYS, MAX_ATTEMPTS, MIN_DAYS_BEFORE_UNAVAILABLE, REVIEW_UNAVAILABLE_EVERY_DAYS) == (14, 7, 20, 7, 30)


@pytest.mark.parametrize("last_game, checked, closed", [
    (_days_ago(15), _days_ago(0), True), (_days_ago(15), _days_ago(6), True), (_days_ago(200), _days_ago(3), True),
    (_days_ago(14), _days_ago(1), False),            # exactly 14 days is not MORE than 14
    (_days_ago(15), _days_ago(7), False),            # 7 days since the last check: it is due
    (_days_ago(15), _days_ago(30), False), (_days_ago(2), _days_ago(1), False), (_days_ago(0), _days_ago(0), False),
])
def test_a_collection_is_closed_when_its_last_game_is_over_14_days_old_and_it_was_checked_less_than_7_days_ago(last_game, checked, closed):
    assert is_closed({"checked": checked, "last_game": last_game}, TODAY) is closed


@pytest.mark.parametrize("state", [None, {}, {"checked": _days_ago(1)}, {"last_game": _days_ago(30)}, {"checked": "mañana", "last_game": _days_ago(30)}, {"checked": _days_ago(1), "last_game": ""},
                                   {"checked": _days_ago(-3), "last_game": _days_ago(30)}])
def test_without_both_dates_or_with_dates_that_cannot_be_read_or_come_from_the_future_a_collection_is_never_closed(state):
    assert is_closed(state, TODAY) is False


def test_the_last_game_may_come_as_the_datetime_the_freshness_check_gives():
    assert is_closed({"checked": _days_ago(1), "last_game": _days_ago(30) + "T14:00"}, TODAY) is True


def test_a_check_that_leaves_an_old_collection_up_to_date_closes_it_and_anything_else_opens_it():
    state = record_check({}, True, _days_ago(30) + "T11:00", TODAY)
    assert state == {"checked": TODAY.isoformat(), "last_game": _days_ago(30)}
    assert "checked" not in record_check(dict(state), False, _days_ago(30), TODAY)                  # a match is missing
    assert "checked" not in record_check(dict(state), True, _days_ago(3), TODAY)                    # a recent game: it may still change
    assert "checked" not in record_check(dict(state), True, None, TODAY)                            # nothing known of its games: not closed by guessing
    assert "checked" not in record_check(dict(state), None, _days_ago(30), TODAY)                   # a calendar that could not be read says nothing


def test_checking_keeps_the_failed_matches_it_does_not_touch_them():
    state = {"failed": {"9": {"n": 3, "first": _days_ago(2), "last": _days_ago(0), "why": "No data"}}}
    assert record_check(state, True, _days_ago(30), TODAY)["failed"] == state["failed"]


def test_a_match_that_fails_is_asked_again_until_it_has_failed_20_times_over_at_least_7_days():
    state = {}
    for i in range(MAX_ATTEMPTS - 1):                                                             # 19 attempts over 19 days: not enough attempts
        record_failure(state, "9", "No data", date.fromordinal(TODAY.toordinal() - 30 + i))
    assert state["failed"]["9"]["n"] == 19 and not state["failed"]["9"].get("unavailable") and should_ask(state, "9", TODAY)
    record_failure(state, "9", "No data", TODAY)                                                  # the 20th, over more than 7 days
    assert state["failed"]["9"]["n"] == 20 and state["failed"]["9"]["unavailable"] is True and unavailable_codes(state) == ["9"]
    assert should_ask(state, "9", TODAY) is False


def test_20_failures_in_less_than_7_days_are_not_enough():
    state = {}
    for i in range(25):                                                                           # hourly refreshes of a weekend: 25 attempts in a day
        record_failure(state, "9", "No data", TODAY)
    assert state["failed"]["9"]["n"] == 25 and not state["failed"]["9"].get("unavailable") and should_ask(state, "9", TODAY)
    record_failure(state, "9", "No data", date.fromordinal(TODAY.toordinal() + MIN_DAYS_BEFORE_UNAVAILABLE))
    assert state["failed"]["9"]["unavailable"] is True


def test_an_unavailable_match_is_asked_again_once_a_month_and_a_new_failure_restarts_the_month():
    state = {"failed": {"9": {"n": 20, "first": _days_ago(60), "last": _days_ago(10), "why": "No data", "unavailable": True}}}
    assert should_ask(state, "9", TODAY) is False                                                 # 10 days: still quiet
    state["failed"]["9"]["last"] = _days_ago(30)
    assert should_ask(state, "9", TODAY) is True                                                  # 30 days: reviewed
    record_failure(state, "9", "No data", TODAY)
    assert state["failed"]["9"]["unavailable"] is True and state["failed"]["9"]["last"] == TODAY.isoformat() and should_ask(state, "9", TODAY) is False


def test_a_match_that_arrives_is_forgotten_and_a_match_never_seen_is_always_asked():
    state = {"failed": {"9": {"n": 4, "first": _days_ago(5), "last": _days_ago(1), "why": "No data"}}}
    record_success(state, "9")
    assert "failed" not in state or "9" not in state["failed"]
    assert should_ask(state, "9", TODAY) and should_ask(state, "never seen", TODAY) and should_ask({}, "1", TODAY) and should_ask(None, "1", TODAY)
    record_success({}, "9")                                                                       # nothing to forget: no error


def test_the_reason_is_kept_short_and_the_codes_are_text():
    state = {}
    record_failure(state, 123, "x" * 500, TODAY)
    assert list(state["failed"]) == ["123"] and len(state["failed"]["123"]["why"]) <= 120


def _db():
    class _Db:
        pass

    db = _Db()
    db.repository = _Db()
    db.repository.connection = _Db()
    mock = new_mock_db()
    db.repository.connection.get_collection = lambda name: mock[name]
    db.mock = mock
    return db


def test_the_state_is_saved_in_the_collection_meta_without_touching_what_is_there_and_loaded_back():
    db = _db()
    db.mock["COLLECTION_META"].insert_one({"_id": "C1", "competition_url": "https://x", "group_label": "A"})
    save_state(db, "C1", {"checked": "2026-11-13", "last_game": "2026-01-07", "failed": {"9": {"n": 2, "first": "2026-11-12", "last": "2026-11-13", "why": "No data"}}})
    doc = db.mock["COLLECTION_META"].find_one({"_id": "C1"})
    assert doc["competition_url"] == "https://x" and doc["refresh"]["checked"] == "2026-11-13"
    assert load_state(db, "C1")["failed"]["9"]["n"] == 2 and load_state(db, "nothing here") == {}


def test_saving_an_empty_state_removes_it_and_creates_nothing_for_a_collection_that_has_no_meta():
    db = _db()
    db.mock["COLLECTION_META"].insert_one({"_id": "C1", "x": 1, "refresh": {"checked": "2026-11-13", "last_game": "2026-01-01"}})
    save_state(db, "C1", {})
    assert "refresh" not in db.mock["COLLECTION_META"].find_one({"_id": "C1"})
    save_state(db, "NEW", {})
    assert db.mock["COLLECTION_META"].find_one({"_id": "NEW"}) is None


def test_the_saved_state_has_no_times_and_is_the_same_whatever_the_order_so_the_archive_does_not_change_between_runs():
    db = _db()
    save_state(db, "C1", {"failed": {"9": {"n": 1, "first": "2026-11-13", "last": "2026-11-13", "why": "No data"}, "10": {"n": 1, "first": "2026-11-13", "last": "2026-11-13", "why": "No data"}},
                          "last_game": "2026-01-07", "checked": "2026-11-13"})
    first = db.mock["COLLECTION_META"].find_one({"_id": "C1"})["refresh"]
    save_state(db, "C1", {"checked": "2026-11-13", "last_game": "2026-01-07", "failed": {"10": {"why": "No data", "last": "2026-11-13", "first": "2026-11-13", "n": 1}, "9": {"n": 1, "first": "2026-11-13", "last": "2026-11-13", "why": "No data"}}})
    second = db.mock["COLLECTION_META"].find_one({"_id": "C1"})["refresh"]
    assert list(first) == list(second) and list(first["failed"]) == ["10", "9"] and first == second
    assert all(len(v) == 10 for v in (first["checked"], first["last_game"]))                                       # dates, not datetimes
