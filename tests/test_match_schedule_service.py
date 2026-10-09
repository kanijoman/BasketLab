"""Upcoming / live matches of a team from the FEB calendar (issue #119)."""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.scraper.calendar_parser import parse_calendar
from src.services.match_schedule_service import MatchScheduleService, normalize_name

HTML = (Path(__file__).parent / "fixtures" / "feb_calendar_snippet.html").read_bytes()
ALL = parse_calendar(HTML)
SCHED = [m for m in ALL if m.kind == "scheduled"]
TEAM = SCHED[0].home_id                      # plays one of the scheduled matches
NOW = datetime.fromisoformat(SCHED[0].start)  # kick-off of the first scheduled match


def _db(competition="LF CHALLENGE", season="2026", codes=(2524697, 2524698, 2524699), meta=None):
    games = new_mock_db()["LF_CHALLENGE_2026"]
    if codes:
        games.insert_many([{"_id": c, "_competition": competition, "_season": season} for c in codes])
    metas = new_mock_db()["COLLECTION_META"]
    if meta:
        metas.insert_one(meta)
    db = MagicMock()
    db.repository.connection.get_collection.side_effect = lambda name: metas if name == "COLLECTION_META" else games
    return db


COMPETITIONS = [
    {"name": "LF ENDESA", "results_url": "https://baloncestoenvivo.feb.es/calendario.aspx?g=4&t=2026&nm=lfendesa"},
    {"name": "LF CHALLENGE", "results_url": "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"},
]


def _service(db=None, calendar=ALL, status=None, now=NOW, competitions=COMPETITIONS):
    return MatchScheduleService(
        db or _db(), fetch_calendar=lambda url: calendar,
        match_status=status or (lambda code: "scheduled"), now=lambda: now,
        competitions=lambda: competitions)


class TestCalendarUrl:
    @pytest.mark.parametrize("name, norm", [("LF CHALLENGE", "lfchallenge"), ("LF2", "lf2"), ("Liga Endesa", "ligaendesa"),
                                            ("LEB  ORO", "leboro"), ("Primera FEB", "primerafeb")])
    def test_names_are_compared_without_case_spaces_or_accents(self, name, norm):
        assert normalize_name(name) == norm

    def test_looked_up_by_competition_name_in_febs_list_with_the_games_season(self):
        """FEB's calendar address needs its internal competition id (g=67), not derivable from our games."""
        url = _service().calendar_url("LF_CHALLENGE_2026")
        assert url == "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"

    def test_the_season_comes_from_the_collection_not_from_the_current_one(self):
        url = _service(_db(season="2024")).calendar_url("LF_CHALLENGE_2026")
        assert "t=2024" in url and "g=67" in url

    def test_stored_metadata_wins_over_the_lookup(self):
        meta = {"_id": "LF_CHALLENGE_2026", "competition_url": "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2030&nm=otra"}
        assert _service(_db(meta=meta)).calendar_url("LF_CHALLENGE_2026").endswith("nm=otra")

    def test_unknown_when_the_competition_is_not_in_febs_list(self):
        assert _service(competitions=[COMPETITIONS[0]]).calendar_url("LF_CHALLENGE_2026") is None

    def test_unknown_when_febs_list_cannot_be_read(self):
        def boom():
            raise ConnectionError("feb down")

        svc = MatchScheduleService(_db(), fetch_calendar=lambda u: ALL, competitions=boom, now=lambda: NOW)
        assert svc.calendar_url("LF_CHALLENGE_2026") is None

    def test_unknown_when_the_collection_has_no_games_or_metadata(self):
        assert _service(_db(codes=())).calendar_url("LF_CHALLENGE_2026") is None


class TestUpcoming:
    def test_lists_the_scheduled_matches_of_the_team(self):
        out = _service().upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["warning"] is None
        m = out["matches"][0]
        assert m["code"] == SCHED[0].code and m["status"] == "scheduled"
        assert m["opponent"] == {"id": SCHED[0].away_id, "name": SCHED[0].away_name} and m["is_home"] is True
        assert m["start"] == SCHED[0].start and m["starts_in_min"] == 0

    def test_other_teams_matches_are_not_listed(self):
        out = _service().upcoming("LF_CHALLENGE_2026", TEAM)
        assert all(TEAM in (m["home"]["id"], m["away"]["id"]) for m in out["matches"])

    def test_sorted_by_kick_off_and_limited(self):
        cal = [type(m)(**{**m.__dict__, "start": f"2027-0{i + 1}-10T18:00"}) for i, m in enumerate(SCHED)]
        # make the same team play all three
        cal = [type(m)(**{**m.__dict__, "home_id": TEAM}) for m in cal]
        out = _service(calendar=cal, now=datetime(2026, 12, 1)).upcoming("LF_CHALLENGE_2026", TEAM, limit=2)
        assert [m["start"][:7] for m in out["matches"]] == ["2027-01", "2027-02"]

    def test_matches_that_started_long_ago_are_dropped(self):
        out = _service(now=datetime(2030, 1, 1)).upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"] == []

    def test_a_match_that_just_started_is_kept(self):
        out = _service(now=NOW.replace(minute=(NOW.minute + 30) % 60)).upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"]

    def test_a_result_row_not_in_the_database_is_checked_and_listed_when_live(self):
        cal = [type(m)(**{**m.__dict__, "home_id": TEAM}) for m in ALL]  # round-1 results involve TEAM too
        calls = []

        def status(code):
            calls.append(code)
            return "live" if code == "2524699" else "finished"

        db = _db(codes=(2524697, 2524698))  # 2524699 is not stored yet
        out = _service(db, calendar=cal, status=status).upcoming("LF_CHALLENGE_2026", TEAM)
        live = [m for m in out["matches"] if m["status"] == "live"]
        assert [m["code"] for m in live] == ["2524699"] and out["matches"][0]["status"] == "live"
        assert "2524697" not in calls and "2524698" not in calls  # already in the DB: never asked

    def test_status_lookups_are_capped_and_failures_tolerated(self):
        cal = [type(m)(**{**m.__dict__, "home_id": TEAM}) for m in ALL[:3]] * 5
        calls = []

        def status(code):
            calls.append(code)
            raise ConnectionError("feb down")

        out = _service(_db(codes=()), calendar=cal, status=status).upcoming("LF_CHALLENGE_2026", TEAM)
        assert len(calls) <= 3 and out["matches"] == [] or all(m["status"] != "live" for m in out["matches"])

    def test_calendar_failure_is_reported_as_a_warning_not_raised(self):
        def boom(url):
            raise ConnectionError("calendario no disponible")

        svc = MatchScheduleService(_db(), fetch_calendar=boom, match_status=lambda c: "scheduled", now=lambda: NOW)
        out = svc.upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"] == [] and "calendario" in out["warning"].lower()

    def test_team_missing_from_the_calendar_warns(self):
        out = _service().upcoming("LF_CHALLENGE_2026", "999")
        assert out["matches"] == [] and "no aparece" in out["warning"].lower()

    def test_unknown_calendar_url_warns(self):
        out = _service(_db(codes=())).upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"] == [] and out["warning"]

    def test_fbcyl_collections_are_not_supported(self):
        out = _service().upcoming("FBCYL_1A_2026", TEAM)
        assert out["matches"] == [] and "FEB" in out["warning"]
