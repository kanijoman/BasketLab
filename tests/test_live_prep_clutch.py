"""The package carries the clutch analytics of each player (issue #274): ``tables.players[pid].clutch``.

The state counts the totals of each game (``test_live_core_clutch.py``); ``_PlayerAcc`` adds them over the season and
``clutch.summarize`` shrinks them to what the player does the rest of the time.
"""
import pytest

from src.live_core.clutch import MIN_SECONDS, empty
from src.live_prep.package_builder import SeasonAccumulator, _PlayerAcc, build_package

A, B = "982047", "981204"


def game_line(minutes=1200, clutch=None, q4=None, stats=None, with_clutch=True):
    p = {"name": "Ana", "minutes": minutes, "pf": 0, "stint": 0, "stint_sum": 600, "stints_done": 2, "on_court": False,
         "stats": {"fg2m": 3, "fg2a": 6, "fg3m": 1, "fg3a": 3, "ftm": 2, "fta": 3, "orb": 1, "drb": 3, "tov": 2, "stl": 1,
                   "ast": 2, "blk": 0, **(stats or {})}}
    if with_clutch:
        p["clutch"], p["q4"] = {**empty(), **(clutch or {})}, {**empty(), **(q4 or {})}
    return p


def baseline(acc):
    from src.live_core.profiles import league_distribution
    return acc.baseline(league_distribution([]), {"pts": 14.0, "orb": 1.5, "stl": 1.4, "ast": 3.5, "fg3m": 1.7, "fta": 3.5}, 0.72)


def test_the_clutch_totals_of_every_game_are_added_over_the_season():
    acc = _PlayerAcc("Ana", A)
    acc.add(game_line(clutch=dict(sec=150, fga=3, fta=2, ftm=1, tov=1, pts=4), q4=dict(sec=400, fga=5, pts=8)))
    acc.add(game_line(clutch=dict(sec=120, fga=2, fta=0, ftm=0, tov=0, pts=3), q4=dict(sec=300, fga=4, pts=5)))
    assert acc.clutch == dict(sec=270, fga=5, fta=2, ftm=1, tov=1, pts=7) and acc.q4["sec"] == 700 and acc.q4["fga"] == 9
    c = baseline(acc)["clutch"]
    assert c["basis"] == "clutch" and c["sample"] == "ok" and c["sec"] == 270 and c["fga"] == 5 and c["pts"] == 7


def test_the_summary_is_shrunk_to_the_season_of_the_player():
    acc = _PlayerAcc("Ana", A)
    for _ in range(2):
        acc.add(game_line(minutes=1200, clutch=dict(sec=150, fga=4, fta=0, tov=1, pts=10)))
    c = baseline(acc)["clutch"]
    raw = (8 + 0.44 * 0 + 2) / 300 * 600
    assert c["usage"] < raw and c["pps_season"] == pytest.approx(2 * (2 * 3 + 3 * 1 + 2) / (2 * (6 + 3) + 0.44 * 2 * 3), abs=1e-3)
    assert c["effective"] == (c["pps"] > c["pps_season"]) and c["ft_pct"] > 0


def test_a_small_clutch_sample_falls_back_to_the_fourth_period_and_says_so():
    acc = _PlayerAcc("Ana", A)
    acc.add(game_line(clutch=dict(sec=MIN_SECONDS - 100, fga=1), q4=dict(sec=MIN_SECONDS + 100, fga=4, pts=6)))
    c = baseline(acc)["clutch"]
    assert c["basis"] == "q4" and c["sample"] == "small"


def test_without_any_sample_or_with_snapshots_of_an_older_engine_there_is_no_clutch_data():
    acc = _PlayerAcc("Ana", A)
    acc.add(game_line())
    assert baseline(acc)["clutch"] == {"basis": "none", "sample": "none", "sec": 0}
    old = _PlayerAcc("Ana", A)
    old.add(game_line(with_clutch=False))
    assert baseline(old)["clutch"]["basis"] == "none"


def test_every_player_of_the_package_carries_the_clutch_key(feb_game_doc):
    acc = SeasonAccumulator()
    acc.add_game(feb_game_doc)
    package = acc.to_package("FEB_TEST", "2025-2026", A, B, None, "2026-10-08T00:00:00Z")
    players = {**package.tables["players"], **package.tables["rival_players"]}
    assert players and all("clutch" in p and p["clutch"]["basis"] in ("clutch", "q4", "none") for p in players.values())
    again = build_package([feb_game_doc], "FEB_TEST", "2025-2026", A, B, created_at="2026-10-08T00:00:00Z")
    assert again.tables["players"] == package.tables["players"]
