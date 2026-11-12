"""The daily roster sweep (A5, #905): which teams to ask FEB for, in which order, and what is kept between runs.

The current season is swept whole every day (signings and departures); the closed seasons only once (their rosters do not change), a team at a time, newest first, so a first load that is
too long for one run finishes over several (``budget``) and never asks twice for what it has. A team FEB did not answer is not marked as swept: the next run asks for it again.
The page is the real roster of team 1008631 (``tests/fixtures/feb_team_page_1008631.html.gz``); the network is the only fake."""
import gzip
import json
from pathlib import Path

import pytest

import sys

import mongomock
import pymongo

from src.market.roster_run import plan_sweep, sweep_into, teams_by_season
from src.market.roster_store import read_rosters, read_swept, write_season

PAGE = gzip.open(Path(__file__).resolve().parent / "fixtures" / "feb_team_page_1008631.html.gz", "rb").read()
TEAMS = {"2026": ["1", "2"], "2025": ["1", "3"], "2024": ["4"]}


class _Response:
    def __init__(self, status=200):
        self.content, self.status = PAGE, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


def _get(failing=()):
    calls = []

    def get(url, **_):
        calls.append(url.rsplit("/", 1)[-1])
        return _Response(500) if url.rsplit("/", 1)[-1] in failing else _Response()
    get.calls = calls
    return get


class TestPlan:
    def test_the_current_season_is_always_swept_whole_and_the_closed_ones_only_for_the_teams_not_swept_yet(self):
        plan = plan_sweep(TEAMS, swept={"2026": {"1", "2"}, "2025": {"1"}})
        assert plan == [("2026", "1"), ("2026", "2"), ("2025", "3"), ("2024", "4")]

    def test_the_order_is_current_season_first_then_the_closed_ones_newest_first(self):
        assert [s for s, _ in plan_sweep(TEAMS, swept={})] == ["2026", "2026", "2025", "2025", "2024"]

    def test_the_budget_limits_the_backlog_of_closed_seasons_and_never_the_current_season_regression(self):
        """Bug found in the first version: the budget counted the current season too, which is re-swept every day, so a first load of the closed seasons never got past it."""
        assert plan_sweep(TEAMS, swept={}, budget=1) == [("2026", "1"), ("2026", "2"), ("2025", "1")]
        assert plan_sweep(TEAMS, swept={}, budget=0) == [("2026", "1"), ("2026", "2")]

    def test_only_the_seasons_asked_for_are_planned(self):
        assert plan_sweep(TEAMS, swept={}, seasons=["2024", "2025"]) == [("2025", "1"), ("2025", "3"), ("2024", "4")]

    def test_the_current_season_is_the_latest_of_the_games_even_if_a_filter_leaves_it_out(self):
        """Asking for 2025 only must not turn 2025 into 'the current season' and re-sweep it every time."""
        assert plan_sweep(TEAMS, swept={"2025": {"1", "3"}}, seasons=["2025"]) == []

    def test_nothing_to_sweep_and_the_same_plan_twice(self):
        assert plan_sweep({}, swept={}) == []
        assert plan_sweep(TEAMS, swept={}) == plan_sweep(TEAMS, swept={})


class TestSweepInto:
    def test_the_first_run_writes_the_files_of_the_seasons_it_swept_with_the_swept_teams(self, tmp_path):
        summary = sweep_into(tmp_path, TEAMS, get=_get(), sleep=lambda s: None, delay=0)
        assert summary["swept"] == 5 and summary["missing"] == []
        assert read_swept(tmp_path) == {"2026": {"1", "2"}, "2025": {"1", "3"}, "2024": {"4"}}
        assert all(r["person_id"].startswith("feb:") for r in read_rosters(tmp_path))

    def test_the_second_run_asks_only_for_the_current_season_and_changes_no_byte(self, tmp_path):
        sweep_into(tmp_path, TEAMS, get=_get(), sleep=lambda s: None, delay=0)
        before = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
        get = _get()
        summary = sweep_into(tmp_path, TEAMS, get=get, sleep=lambda s: None, delay=0)
        assert sorted(get.calls) == ["1", "2"] and summary["swept"] == 2 and summary["changed"] == []
        assert {p.name: p.read_bytes() for p in tmp_path.glob("*.json")} == before

    def test_a_team_that_fails_is_reported_and_not_marked_so_the_next_run_asks_again(self, tmp_path):
        summary = sweep_into(tmp_path, TEAMS, get=_get(failing={"3"}), sleep=lambda s: None, delay=0)
        assert summary["missing"] == [("2025", "3")]
        assert read_swept(tmp_path)["2025"] == {"1"}
        retry = _get()
        sweep_into(tmp_path, TEAMS, get=retry, sleep=lambda s: None, delay=0)
        assert "3" in retry.calls and read_swept(tmp_path)["2025"] == {"1", "3"}

    def test_a_budget_stops_the_backlog_cleanly_and_the_next_run_goes_on_where_it_was(self, tmp_path):
        first = sweep_into(tmp_path, TEAMS, get=_get(), sleep=lambda s: None, delay=0, budget=2)
        assert first["swept"] == 4 and first["left"] == 1                              # the current season whole (2) and two closed teams
        second = sweep_into(tmp_path, TEAMS, get=_get(), sleep=lambda s: None, delay=0, budget=2)
        assert read_swept(tmp_path) == {"2026": {"1", "2"}, "2025": {"1", "3"}, "2024": {"4"}} and second["left"] == 0 and second["swept"] == 3

    def test_a_player_who_left_the_roster_of_the_current_season_disappears_on_the_next_run(self, tmp_path):
        sweep_into(tmp_path, {"2026": ["1008631"]}, get=_get(), sleep=lambda s: None, delay=0)
        doc = json.loads((tmp_path / "2026.json").read_text(encoding="utf-8"))
        ghost = {**doc["rows"][0], "person_id": "feb:99999999", "name": "SE FUE"}
        write_season(tmp_path, "2026", [*doc["rows"], ghost], teams=doc["teams"])
        assert any(r["person_id"] == "feb:99999999" for r in read_rosters(tmp_path))
        sweep_into(tmp_path, {"2026": ["1008631"]}, get=_get(), sleep=lambda s: None, delay=0)
        assert not any(r["person_id"] == "feb:99999999" for r in read_rosters(tmp_path))

    def test_no_teams_no_files(self, tmp_path):
        assert sweep_into(tmp_path, {}, get=_get(), sleep=lambda s: None, delay=0)["swept"] == 0 and not list(tmp_path.glob("*.json"))


class TestTeamsBySeason:
    """The teams of each season come from the games of the archive, under the SAME season key the Talent rows use (``competitions_of``): a roster stored under another key would never join."""

    @pytest.fixture()
    def connection(self, monkeypatch):
        sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))
        import fbcyl_games
        import games

        monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
        from src.api import deps

        deps._create_handler.cache_clear()
        handler = deps._create_handler()
        db = handler.connection.client["BASKETBALL"]
        for name, season in (("LF_ENDESA_2025_2026_Liga_Regular_Único", "2025"), ("LF_ENDESA_2024_2025_Liga_Regular_Único", "2024")):
            db[name].insert_many(games.build_games())
            db["COLLECTION_META"].insert_one({"_id": name, "league": "FEB", "competition_label": "LF ENDESA", "season_value": season, "season_label": f"{season}/{int(season) + 1}", "group_label": "x"})
        db["FBCYL_1ª_FASE-GRUPO_A-1_2026_"].insert_many(fbcyl_games.build_games())
        yield handler.connection
        deps._create_handler.cache_clear()

    def test_every_team_of_every_season_and_none_of_fbcyl_which_has_no_roster_page(self, connection):
        names = ["LF_ENDESA_2025_2026_Liga_Regular_Único", "LF_ENDESA_2024_2025_Liga_Regular_Único", "FBCYL_1ª_FASE-GRUPO_A-1_2026_"]
        assert teams_by_season(connection, names, []) == {"2024": ["101", "102", "103", "104"], "2025": ["101", "102", "103", "104"]}

    def test_a_collection_that_says_nothing_or_has_no_games_adds_no_season(self, connection):
        connection.client["BASKETBALL"]["archive"].insert_one({"_id": 1})
        connection.client["BASKETBALL"]["EMPTY_FEB_2025_2026_Liga_Regular_A"].insert_one({"_id": 1, "HEADER": {}})
        assert teams_by_season(connection, ["archive", "EMPTY_FEB_2025_2026_Liga_Regular_A"], []) == {}
