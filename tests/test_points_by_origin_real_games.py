"""Points by origin on the 16 real games of LF Challenge 2026-27, against the official PDF (#352).

What the PDF confirms (32 team-games): the bench points (``inn`` starters, technical free throws included: all 32 exact) and the paint points (made shots of
the ``SHOTCHART`` in the rim and key zones; never above the PDF, 21 of 32 exact, one point short on average, 8 at most).
Points after turnovers and second chance are defined per possession here, which is more generous than the FEB's own definition
(not reproducible from the play-by-play): never below the PDF, on average 3-4 points above, 14 at most. The bounds are
measured, not goals: tighten them only with a better definition. The fast-break points are an estimate of our own (#398: the official
definition is not reproducible): 10 of 32 exact, 2.6 points of mean error, 1.3 below on average, -11 to +5.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.pbp.game_derived import derive_game_fields

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    with gzip.open(_FIXTURES / name, "rt", encoding="utf-8") if name.endswith(".gz") else open(_FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


PBP = {g["game"]: g for g in _load("pbp_possessions.json.gz")["games"] if g["group"] == "2026-27/lf_challenge"}
EXTRA = _load("points_by_origin_games.json.gz")["games"]
PDF = _load("feb_pdf_ground_truth.json")["games"]
IDS = sorted(EXTRA)


def _doc(gid):
    game, extra = PBP[gid], EXTRA[gid]
    teams = [{"id": t, "TOTAL": box, "PLAYER": [{"id": p, "inn": "1"} for p in starters]}
             for t, box, starters in zip(game["teams"], game["box"], extra["starters"])]
    shots = [{"x": x, "y": y, "m": m, "team": team} for x, y, m, team in extra["shots"]]
    return {"HEADER": {"TEAM": [{"id": t} for t in game["teams"]]}, "BOXSCORE": {"TEAM": teams},
            "PLAYBYPLAY": {"LINES": game["lines"]}, "SHOTCHART": {"SHOTS": shots}}


def _pairs(gid):
    teams = {t["id"]: t for t in derive_game_fields(_doc(gid))["TEAM"]}
    return [(teams[p["team_id"]], p) for p in PDF[gid]["teams"]]


@pytest.mark.parametrize("gid", IDS)
def test_points_by_origin_add_up_to_the_points_of_the_game(gid):
    for team, points in zip(derive_game_fields(_doc(gid))["TEAM"], PBP[gid]["points"]):
        assert sum(team["pts_by_origin"].values()) == points


@pytest.mark.parametrize("gid", IDS)
def test_bench_points_equal_the_pdf(gid):
    for ours, pdf in _pairs(gid):
        assert ours["pts_bench"] == pdf["bench_pts"]


@pytest.mark.parametrize("gid", IDS)
def test_paint_points_are_never_above_the_pdf_and_at_most_eight_below(gid):
    for ours, pdf in _pairs(gid):
        assert 0 <= pdf["paint_pts"] - ours["pts_paint"] <= 8


@pytest.mark.parametrize("gid", IDS)
def test_points_after_turnovers_and_second_chance_are_never_below_the_pdf_and_close_above(gid):
    for ours, pdf in _pairs(gid):
        assert 0 <= ours["pts_off_tov"] - pdf["pts_off_turnovers"] <= 10
        assert 0 <= ours["pts_second_chance"] - pdf["second_chance_pts"] <= 14


def test_mean_paint_error_is_about_a_point():
    pairs = [pair for gid in IDS for pair in _pairs(gid)]

    assert sum(abs(o["pts_paint"] - p["paint_pts"]) for o, p in pairs) / len(pairs) <= 1.5


def test_the_fast_break_estimate_stays_close_to_the_pdf_on_average():
    pairs = [pair for gid in IDS for pair in _pairs(gid)]
    diffs = [o["pts_fastbreak"] - p["fast_break_pts"] for o, p in pairs]

    assert sum(abs(d) for d in diffs) / len(diffs) <= 3.0            # measured 2.56
    assert -2.5 <= sum(diffs) / len(diffs) <= 1.0                    # measured -1.31: a little under, never wildly off
    assert all(-12 <= d <= 6 for d in diffs)
