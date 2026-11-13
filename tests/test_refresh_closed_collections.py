"""The refresh stops checking what cannot have changed and stops asking for ever for what does not arrive (#924).

Measured on 13/11/2026: a refresh with nothing new took 25 minutes because every active collection cost ~27 requests and 2.5 MB, 327 of them, and the matches that fail were asked on every
run. A collection that is CLOSED (last game over 14 days old, up to date at its last check) is checked every 7 days; a match that failed 20 times over 7 days is UNAVAILABLE and asked monthly.
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_competition_refresh import ENTRY, _db, _scraper  # noqa: E402

from src.services.competition_refresh import RefreshEntry, needs_attention, refresh_all, to_markdown  # noqa: E402
from src.services.refresh_state import load_state  # noqa: E402

NOW = datetime(2026, 11, 13, 13, 0)
NAME = "LF_CHALLENGE_LF_CHALLENGE_2026_A"
OLD = "2026-10-04T14:00"           # 40 days before NOW
RECENT = "2026-11-10T20:00"


def _fresh(up_to_date=True, last_game=OLD, missing=()):
    return lambda collection: {"collection": collection, "up_to_date": up_to_date if not missing else False, "missing_codes": list(missing), "games_in_db": 5, "calendar_results": 5,
                               "last_game": last_game, "warning": None}


def _meta(db):
    return db.repository.connection.get_collection("COLLECTION_META")


def _never(collection):
    raise AssertionError("the freshness check must not run for a closed collection")


def _run(db, scraper=None, freshness=None, now=NOW, **kw):
    return refresh_all(db, [RefreshEntry(**ENTRY)], scraper=scraper or _scraper(["1"]), freshness=freshness or _fresh(), now=lambda: now, **kw)


class TestClosedCollections:
    def test_a_closed_collection_is_not_scraped_and_not_checked(self):
        db = _db()
        _meta(db).insert_one({"_id": NAME, "competition_url": ENTRY["competition_url"], "refresh": {"checked": "2026-11-11", "last_game": "2026-10-04"}})
        scraper = _scraper(["1"])
        report = _run(db, scraper, _never)
        scraper.get_page_content.assert_not_called()
        scraper.get_matches.assert_not_called()
        assert report[0]["collection"] == NAME and report[0]["closed"] is True and report[0]["fatal"] is None and needs_attention(report) is False

    def test_force_checks_it_anyway(self):
        db = _db()
        _meta(db).insert_one({"_id": NAME, "refresh": {"checked": "2026-11-11", "last_game": "2026-10-04"}})
        scraper = _scraper(["1"])
        report = _run(db, scraper, force=True)
        scraper.get_matches.assert_called_once()
        assert not report[0].get("closed") and report[0]["freshness"]["up_to_date"] is True

    def test_a_collection_never_checked_or_checked_a_week_ago_is_checked(self):
        for refresh in ({}, {"checked": "2026-11-06", "last_game": "2026-10-04"}):
            db = _db()
            if refresh:
                _meta(db).insert_one({"_id": NAME, "refresh": refresh})
            scraper = _scraper(["1"])
            _run(db, scraper)
            scraper.get_matches.assert_called_once()

    def test_a_check_that_leaves_an_old_collection_up_to_date_closes_it_and_the_next_runs_skip_it_for_a_week(self):
        db = _db()
        _run(db)
        assert load_state(db, NAME) == {"checked": "2026-11-13", "last_game": "2026-10-04"}
        again = _scraper(["1"])
        assert _run(db, again, _never, now=NOW + timedelta(days=3))[0]["closed"] is True
        again.get_matches.assert_not_called()
        due = _scraper(["1"])
        _run(db, due, now=NOW + timedelta(days=7))
        due.get_matches.assert_called_once()
        assert load_state(db, NAME)["checked"] == "2026-11-20"

    @pytest.mark.parametrize("fresh", [_fresh(last_game=RECENT), _fresh(missing=["7"]), _fresh(up_to_date=None), _fresh(last_game=None)])
    def test_a_recent_game_a_missing_match_an_unreadable_calendar_or_no_known_game_never_closes_a_collection(self, fresh):
        db = _db()
        _run(db, freshness=fresh)
        assert "checked" not in load_state(db, NAME)

    def test_a_scrape_that_fails_never_closes_it_and_a_closed_one_that_is_checked_and_found_lacking_opens(self):
        db = _db()
        broken = _scraper(["1"])
        broken.get_matches.side_effect = RuntimeError("FEB down")
        report = _run(db, broken)
        assert report[0]["fatal"] and load_state(db, NAME) == {}
        _meta(db).update_one({"_id": NAME}, {"$set": {"refresh": {"checked": "2026-11-05", "last_game": "2026-10-04"}}}, upsert=True)
        _run(db, freshness=_fresh(missing=["8"]))                                           # due, and a played match is missing now
        assert "checked" not in load_state(db, NAME)

    def test_a_competition_with_all_its_groups_closed_is_not_even_discovered_in_feb(self):
        db = _db()
        for group in ("A", "B"):
            _meta(db).insert_one({"_id": f"LF_CHALLENGE_LF_CHALLENGE_2026_{group}", "competition_url": ENTRY["competition_url"], "season_value": "2026", "group_label": group,
                                  "refresh": {"checked": "2026-11-12", "last_game": "2026-09-20"}})
        scraper = _scraper(["1"])
        entry = RefreshEntry(**{**ENTRY, "group_value": "", "group_label": "", "groups": "all"})
        report = refresh_all(db, [entry], scraper=scraper, freshness=_never, now=lambda: NOW)
        scraper.get_groups_for_season.assert_not_called()
        assert [r["collection"] for r in report] == ["LF_CHALLENGE_LF_CHALLENGE_2026_A", "LF_CHALLENGE_LF_CHALLENGE_2026_B"] and all(r["closed"] for r in report)

    def test_one_open_group_means_the_competition_is_discovered_again_so_a_new_phase_is_found(self):
        db = _db()
        _meta(db).insert_one({"_id": "LF_CHALLENGE_LF_CHALLENGE_2026_A", "competition_url": ENTRY["competition_url"], "season_value": "2026", "group_label": "A", "refresh": {"checked": "2026-11-12", "last_game": "2026-09-20"}})
        _meta(db).insert_one({"_id": "LF_CHALLENGE_LF_CHALLENGE_2026_B", "competition_url": ENTRY["competition_url"], "season_value": "2026", "group_label": "B", "refresh": {"checked": "2026-11-01", "last_game": "2026-09-20"}})
        scraper = _scraper(["1"])
        scraper.get_groups_for_season.return_value = [("A", "1"), ("B", "2"), ("Final", "3")]
        entry = RefreshEntry(**{**ENTRY, "group_value": "", "group_label": "", "groups": "all"})
        report = refresh_all(db, [entry], scraper=scraper, freshness=_fresh(), now=lambda: NOW)
        scraper.get_groups_for_season.assert_called_once()
        assert len(report) == 3 and [bool(r.get("closed")) for r in report] == [True, False, False]          # the closed group is skipped, the due one and the new phase are scraped

    def test_the_report_counts_the_closed_collections_and_says_what_they_are(self):
        db = _db()
        _meta(db).insert_one({"_id": NAME, "refresh": {"checked": "2026-11-11", "last_game": "2026-10-04"}})
        text = to_markdown(_run(db, freshness=_never))
        assert "cerrada" in text.lower() and NAME in text and "Error" not in text


class TestMetaKeepsTheStateWhenTheSelectionIsSavedAgain:
    def test_saving_the_scrape_selection_does_not_erase_the_refresh_state_regression(self):
        """``save_feb_meta`` used ``replace_one``: on every scrape it would have wiped the state this file keeps."""
        db = _db()
        _meta(db).insert_one({"_id": NAME, "competition_url": "old", "refresh": {"checked": "2026-11-11", "last_game": "2026-10-04"}})
        from src.services.collection_meta import save_feb_meta

        save_feb_meta(db, NAME, RefreshEntry(**ENTRY))
        doc = _meta(db).find_one({"_id": NAME})
        assert doc["refresh"] == {"checked": "2026-11-11", "last_game": "2026-10-04"} and doc["competition_url"] == ENTRY["competition_url"] and doc["group_label"] == "A"


def _failing(code="9", reason=None):
    scraper = _scraper([code])
    scraper.fetch_boxscore.side_effect = (lambda c, s: (_ for _ in ()).throw(RuntimeError(reason))) if reason else (lambda c, s: None)
    return scraper


class TestMatchesThatKeepFailing:
    def _days(self, db, n, start=NOW, scraper=None, fresh=None):
        last = None
        for i in range(n):
            last = _run(db, scraper or _failing(), fresh or _fresh(up_to_date=False, last_game=RECENT, missing=["9"]), now=start + timedelta(days=i))
        return last

    def test_the_match_is_asked_every_run_until_it_has_failed_20_times_over_7_days(self):
        db = _db()
        self._days(db, 19)
        entry = load_state(db, NAME)["failed"]["9"]
        assert entry["n"] == 19 and not entry.get("unavailable") and entry["first"] == "2026-11-13" and entry["why"].startswith("No data")
        self._days(db, 1, start=NOW + timedelta(days=19))
        assert load_state(db, NAME)["failed"]["9"]["unavailable"] is True

    def test_an_unavailable_match_is_not_asked_nor_listed_as_an_error_nor_does_it_turn_the_run_red(self):
        db = _db()
        self._days(db, 20)
        quiet = _failing()
        report = _run(db, quiet, _fresh(up_to_date=False, last_game=OLD, missing=["9"]), now=NOW + timedelta(days=21))
        quiet.fetch_boxscore.assert_not_called()
        assert report[0]["job"]["unavailable"] == ["9"] and report[0]["job"]["errors"] == []
        assert report[0]["freshness"]["up_to_date"] is True and needs_attention(report) is False
        text = to_markdown(report)
        assert "No disponibles" in text and "9" in text

    def test_it_is_asked_again_a_month_later_and_if_it_arrived_it_is_stored_and_forgotten(self):
        db = _db()
        self._days(db, 20)
        arrived = _scraper(["9"])
        _run(db, arrived, _fresh(), now=NOW + timedelta(days=19 + 30))
        arrived.fetch_boxscore.assert_called_once()
        assert db.stored[NAME] == {9} and "failed" not in load_state(db, NAME)

    def test_a_match_that_fails_a_few_times_and_then_arrives_is_stored_and_its_failures_forgotten(self):
        db = _db()
        self._days(db, 3)
        assert load_state(db, NAME)["failed"]["9"]["n"] == 3
        _run(db, _scraper(["9"]), _fresh(), now=NOW + timedelta(days=3))
        assert "failed" not in load_state(db, NAME)

    def test_a_network_error_counts_like_any_other_failure_and_keeps_its_reason(self):
        db = _db()
        _run(db, _failing(reason="Connection reset"), _fresh(up_to_date=False, last_game=RECENT, missing=["9"]))
        assert "Connection reset" in load_state(db, NAME)["failed"]["9"]["why"]

    def test_a_game_still_being_played_is_not_a_failure(self):
        db = _db()
        _run(db, _scraper(["9"], in_progress=["9"]), _fresh(last_game=RECENT))
        assert "failed" not in load_state(db, NAME)

    def test_each_match_has_its_own_count(self):
        db = _db()
        scraper = _scraper(["9", "10"])
        scraper.fetch_boxscore.side_effect = lambda code, session: None if code == "9" else {"HEADER": {"status": "3"}}
        _run(db, scraper, _fresh(last_game=RECENT, missing=["9"]))
        assert list(load_state(db, NAME)["failed"]) == ["9"] and db.stored[NAME] == {10}


class TestFbcylMatchesThatKeepFailing:
    """FBCYL answered 500 for some matches (4 on 13/11/2026): they were asked on every run, with no limit."""

    PARAMS = {"competition_id": "7242", "season": "2026", "gender": "F", "territory": "1", "category": "1130", "competition_label": "LIGA UEMC G7242"}

    def _scraper(self, fail=("bad",)):
        scraper = MagicMock()
        scraper.get_matches.return_value = ["ok", *fail]
        scraper.get_match_complete_data.side_effect = lambda uuid, league_ctx=None: None if uuid in fail else {"uuid": uuid}
        return scraper

    def _db(self):
        db = _db()
        db.document_exists.side_effect = lambda col, uid: uid in db.stored.get(col, set())
        db.insert_fbcyl_match.side_effect = lambda col, uid, doc: db.stored.setdefault(col, set()).add(uid)
        return db

    def test_a_match_that_fails_20_times_over_a_week_stops_being_asked_and_is_reported_apart(self):
        from src.services.fbcyl_match_ingest import scrape_fbcyl_collection

        db = self._db()
        for i in range(20):
            job = scrape_fbcyl_collection(db, self.PARAMS, self._scraper(), today=date(2026, 11, 13) + timedelta(days=i))
        name = job["collection"]
        assert load_state(db, name)["failed"]["bad"]["unavailable"] is True
        quiet = self._scraper()
        job = scrape_fbcyl_collection(db, self.PARAMS, quiet, today=date(2026, 11, 13) + timedelta(days=21))
        assert job["unavailable"] == ["bad"] and job["errors"] == [] and quiet.get_match_complete_data.call_count == 0       # "ok" is stored, "bad" is not asked

    def test_a_match_that_arrives_after_failing_is_stored_and_forgotten(self):
        from src.services.fbcyl_match_ingest import scrape_fbcyl_collection

        db = self._db()
        for i in range(3):
            job = scrape_fbcyl_collection(db, self.PARAMS, self._scraper(), today=date(2026, 11, 13) + timedelta(days=i))
        assert load_state(db, job["collection"])["failed"]["bad"]["n"] == 3
        arrived = self._scraper()
        arrived.get_match_complete_data.side_effect = lambda uuid, league_ctx=None: {"uuid": uuid}          # the site answers now
        scrape_fbcyl_collection(db, self.PARAMS, arrived, today=date(2026, 11, 16))
        assert "failed" not in load_state(db, job["collection"]) and db.stored[job["collection"]] == {"ok", "bad"}
