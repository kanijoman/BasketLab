"""Roster sweep of Mercado (#874): birth date, height, position and full name of every FEB team of a season.

The page is the real roster of team 1008631 (``tests/fixtures/feb_team_page_1008631.html.gz``); the network is the only fake.
"""
import gzip
from pathlib import Path

from src.market.roster_sweep import season_team_ids, sweep_rosters

PAGE = gzip.open(Path(__file__).parent / "fixtures" / "feb_team_page_1008631.html.gz", "rb").read()


class _Response:
    def __init__(self, content=PAGE, status=200):
        self.content, self.status = content, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


def _get(failing=()):
    calls = []

    def get(url, **_):
        calls.append(url)
        return _Response(status=500) if any(url.endswith(f"/{t}") for t in failing) else _Response()
    get.calls = calls
    return get


def _game(season, *team_ids, collection="SEGUNDA_FEB_2026_2027_Liga_Regular"):
    return {"_id": "1", "_collection": collection, "_season": season,
            "BOXSCORE": {"TEAM": [{"id": t, "PLAYER": [{"id": "1", "name": "A. B C"}]} for t in team_ids]}}


def test_season_team_ids_groups_the_teams_of_every_season_and_skips_games_without_box_score():
    games = [_game("2026", "10", "11"), _game("2026", "11", "12"), _game("2025", "20"), {"_id": "x"}]
    assert season_team_ids(games) == {"2025": ["20"], "2026": ["10", "11", "12"]}


def test_the_sweep_returns_one_row_per_player_with_a_person_id_and_the_season():
    rows, missing = sweep_rosters({"2026": ["1008631"]}, get=_get(), sleep=lambda s: None, delay=0)
    assert missing == []
    assert rows and all(r["person_id"].startswith("feb:") and r["season"] == "2026" and r["team_id"] == "1008631" for r in rows)
    assert any(r["birth"] and r["height"] and r["position"] for r in rows)


def test_rows_are_sorted_and_the_second_run_is_identical():
    first, _ = sweep_rosters({"2026": ["1008631"]}, get=_get(), sleep=lambda s: None, delay=0)
    second, _ = sweep_rosters({"2026": ["1008631"]}, get=_get(), sleep=lambda s: None, delay=0)
    assert first == second == sorted(first, key=lambda r: (r["season"], r["team_id"], r["person_id"]))


def test_a_team_that_fails_is_reported_and_the_rest_are_swept():
    rows, missing = sweep_rosters({"2026": ["1008631", "999"]}, get=_get(failing=["999"]), sleep=lambda s: None, delay=0)
    assert missing == [("2026", "999")] and rows


def test_the_sweep_waits_between_requests_and_never_before_the_first():
    slept = []
    sweep_rosters({"2026": ["1", "2", "3"]}, get=_get(), sleep=slept.append, delay=1.5)
    assert slept == [1.5, 1.5]


def test_the_same_team_in_one_season_is_asked_once():
    get = _get()
    sweep_rosters({"2026": ["1008631", "1008631"]}, get=get, sleep=lambda s: None, delay=0)
    assert len(get.calls) == 1
