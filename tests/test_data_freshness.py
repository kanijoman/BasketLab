"""Is the database up to date with the FEB calendar? (production data went stale vs a local copy)"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from db_helpers import new_mock_db
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.scraper.calendar_parser import parse_calendar
from src.services.data_freshness_service import DataFreshnessService
from src.services.match_schedule_service import MatchScheduleService

HTML = (Path(__file__).parent / "fixtures" / "feb_calendar_snippet.html").read_bytes()
CAL = parse_calendar(HTML)
RESULT_CODES = [m.code for m in CAL if m.kind == "result"]  # 2524697..99 played in round 1
COMPETITIONS = [{"name": "LF CHALLENGE", "results_url": "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"}]


def _db(codes, dates=None, meta=True):
    games = new_mock_db()["LF_CHALLENGE_2026"]
    if codes:
        games.insert_many([{"_id": int(c), "_competition": "LF CHALLENGE", "_season": "2026",
                            "HEADER": {"starttime": (dates or {}).get(c, "04-10-2026 - 14:00")}} for c in codes])
    metas = new_mock_db()["COLLECTION_META"]
    if meta:
        metas.insert_one({"_id": "LF_CHALLENGE_2026", "competition_url": COMPETITIONS[0]["results_url"]})
    db = MagicMock()
    db.repository.connection.get_collection.side_effect = lambda name: metas if name == "COLLECTION_META" else games
    return db


def _svc(db, calendar=CAL):
    schedule = MatchScheduleService(db, fetch_calendar=lambda u: calendar, competitions=lambda: COMPETITIONS)
    return DataFreshnessService(db, schedule)


class TestCheck:
    def test_up_to_date_when_every_played_match_is_stored(self):
        r = _svc(_db(RESULT_CODES)).check("LF_CHALLENGE_2026")
        assert r["up_to_date"] is True and r["missing_codes"] == [] and r["games_in_db"] == 3 and r["calendar_results"] == 3

    def test_lists_the_played_matches_missing_from_the_database(self):
        r = _svc(_db(RESULT_CODES[:1])).check("LF_CHALLENGE_2026")
        assert r["up_to_date"] is False and r["missing_codes"] == RESULT_CODES[1:]

    def test_an_empty_collection_is_stale_if_matches_were_played(self):
        r = _svc(_db([])).check("LF_CHALLENGE_2026")
        assert r["missing_codes"] == RESULT_CODES and r["games_in_db"] == 0 and r["last_game"] is None

    def test_unplayed_matches_are_not_missing(self):
        r = _svc(_db(RESULT_CODES)).check("LF_CHALLENGE_2026")
        assert not set(r["missing_codes"]) & {m.code for m in CAL if m.kind == "scheduled"}

    def test_reports_the_date_of_the_latest_stored_game(self):
        dates = {RESULT_CODES[0]: "03-10-2026 - 18:00", RESULT_CODES[1]: "04-10-2026 - 14:00", RESULT_CODES[2]: "02-10-2026 - 20:00"}
        r = _svc(_db(RESULT_CODES, dates)).check("LF_CHALLENGE_2026")
        assert r["last_game"] == "2026-10-04T14:00"

    def test_a_calendar_failure_is_a_warning_not_an_error(self):
        db = _db(RESULT_CODES)

        def boom(url):
            raise ConnectionError("feb down")

        svc = DataFreshnessService(db, MatchScheduleService(db, fetch_calendar=boom, competitions=lambda: COMPETITIONS))
        r = svc.check("LF_CHALLENGE_2026")
        assert r["up_to_date"] is None and "calendario" in r["warning"].lower()

    def test_unknown_calendar_is_reported(self):
        db = _db(RESULT_CODES, meta=False)
        svc = DataFreshnessService(db, MatchScheduleService(db, fetch_calendar=lambda u: CAL, competitions=lambda: []))
        assert svc.check("LF_CHALLENGE_2026")["up_to_date"] is None

    def test_fbcyl_is_not_supported(self):
        r = _svc(_db([])).check("FBCYL_1A_2026")
        assert r["up_to_date"] is None and "FEB" in r["warning"]


class TestEndpoint:
    def test_returns_the_service_result(self):
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            with patch("src.api.routers.collections.DataFreshnessService") as svc:
                svc.return_value.check.return_value = {"collection": "X", "up_to_date": False, "missing_codes": ["1"]}
                r = TestClient(app).get("/api/v1/collections/X/freshness")
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 200 and r.json()["missing_codes"] == ["1"]
        svc.return_value.check.assert_called_once_with("X")
