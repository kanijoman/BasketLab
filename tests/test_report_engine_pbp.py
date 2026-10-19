"""The report engine with the figures that come from the play-by-play (#358): points after turnovers, second chance, paint and bench.

Only the ones that are stable from game to game (split-half reliability 0.70-0.93 over 120 team-seasons) are classified by quartiles:
the after-timeout possessions, the first possession of each period, the first and last two minutes against the rest of the period and
the effect of the timeouts are noise (0.04-0.35) and stay descriptive in the web page. The league figures and the team's come from
``PBPExtendedStatsService`` (``TeamReportService`` merges them into the season row and the quartiles).
"""
from unittest.mock import MagicMock

import pytest

from src.report_engine import build_team_report
from src.report_engine.catalog import BY_KEY, GROUPS
from src.report_engine.templates import THEMES
from src.services.team_report_service import TeamReportService

PBP_KEYS = ["pts_off_tov_per_game", "opp_pts_off_tov_per_game", "pts_second_chance_per_game", "opp_pts_second_chance_per_game",
            "pts_paint_per_game", "opp_pts_paint_per_game", "bench_pct"]


def test_the_stable_pbp_figures_are_in_their_own_group_and_every_theme_has_its_texts():
    assert "Origen de los puntos" in GROUPS
    for key in PBP_KEYS:
        stat = BY_KEY[key]
        assert stat.group == "Origen de los puntos"
        assert {"side", "s_own", "w_own", "s_riv", "w_riv", "drill", "neutralize", "exploit"} <= set(THEMES[stat.theme])


def test_what_the_team_concedes_is_lower_is_better_and_the_bench_share_is_neutral():
    assert [BY_KEY[k].higher_is_better for k in PBP_KEYS] == [True, False, True, False, True, False, None]


def _quartiles(**extra):
    base = {k: {"q1": 8.0, "q2": 10.0, "q3": 12.0} for k in PBP_KEYS if k != "bench_pct"}
    base["bench_pct"] = {"q1": 25.0, "q2": 33.0, "q3": 40.0}
    base.update(extra)
    return base


def _stats(**kw):
    s = {"games_played": 20, **{k: 10.0 for k in PBP_KEYS if k != "bench_pct"}, "bench_pct": 33.0}
    s.update(kw)
    return s


def _keys(items):
    return [i["key"] for i in items]


def test_a_team_that_scores_a_lot_after_turnovers_and_concedes_little_in_the_paint_has_those_strengths():
    report = build_team_report("A", _stats(pts_off_tov_per_game=15.0, opp_pts_paint_per_game=6.0), _quartiles(), None, "own")

    assert {"pts_off_tov_per_game", "opp_pts_paint_per_game"} <= set(_keys(report["strengths"]))


def test_conceding_a_lot_after_its_own_turnovers_and_of_second_chance_are_weaknesses():
    report = build_team_report("A", _stats(opp_pts_off_tov_per_game=15.0, opp_pts_second_chance_per_game=15.0), _quartiles(), None, "own")

    assert {"opp_pts_off_tov_per_game", "opp_pts_second_chance_per_game"} <= set(_keys(report["weaknesses"]))


def test_the_rival_mode_turns_them_into_a_game_plan():
    report = build_team_report("A", _stats(pts_second_chance_per_game=15.0, opp_pts_paint_per_game=15.0), _quartiles(), None, "rival")

    assert {t["key"] for t in report["tactics"]} >= {"pts_second_chance_per_game", "opp_pts_paint_per_game"}
    assert all(t["text"] for t in report["tactics"])


def test_the_bench_share_never_makes_a_finding_but_describes_the_profile():
    long_bench = build_team_report("A", _stats(bench_pct=45.0), _quartiles(), None, "own")
    short_bench = build_team_report("A", _stats(bench_pct=15.0), _quartiles(), None, "own")

    assert "bench_pct" not in _keys(long_bench["strengths"] + long_bench["weaknesses"])
    assert any("banquillo" in line.lower() for line in long_bench["profile"])
    assert any("titulares" in line.lower() for line in short_bench["profile"])


# ---------------------------------------------------------------- the service merges them from the pbp season rows

TEAM = {"team_id": "7", "games_played": 20, "points_per_game": 80.0}
QUARTILES = {"points_per_game": {"q1": 70, "q2": 78, "q3": 85}}


class FakeStats:
    def load_season_data(self, collection):
        return {"team_stats": [TEAM], "opponent_stats": []}

    def get_quartiles(self, collection):
        return dict(QUARTILES)

    def get_consistency(self, collection):
        return {}

    def get_teams_with_ids(self, collection):
        return [{"id": "7", "name": "Equipo A"}]


def _pbp_rows():
    rows = []
    for i, tid in enumerate(["7", "8", "9", "10", "11"]):
        row = {"team_id": tid, "team_name": f"T{tid}", "games": 3, "games_doubtful": 0}
        for key in PBP_KEYS:
            row[key] = 20.0 if (tid == "7" and key == "pts_second_chance_per_game") else 8.0 + i
        rows.append(row)
    return rows


def _build(pbp, mode="own"):
    return TeamReportService(MagicMock(), stats=FakeStats(), zones=lambda c, t: [], pbp=pbp).build("col", "7", mode)


def test_the_service_adds_the_team_figures_and_the_league_quartiles_of_the_pbp_rows():
    report = _build(lambda collection: _pbp_rows())

    assert "pts_second_chance_per_game" in _keys(report["strengths"])
    assert any(d["key"] == "pts_second_chance_per_game" for d in report["differentials"])


def test_a_collection_without_pbp_rows_still_gives_the_usual_report():
    report = _build(lambda collection: [])

    assert "points_per_game" in [f["key"] for f in report["strengths"]] and not any(k in PBP_KEYS for k in _keys(report["strengths"]))


def test_a_failure_loading_the_pbp_rows_does_not_break_the_report():
    def boom(collection):
        raise RuntimeError("db")

    assert _build(boom)["team"] == "Equipo A"


def test_a_team_without_pbp_rows_gets_no_pbp_findings():
    rows = [r for r in _pbp_rows() if r["team_id"] != "7"]

    assert not any(k in PBP_KEYS for k in _keys(_build(lambda c: rows)["strengths"]))


@pytest.mark.parametrize("mode", ["own", "rival"])
def test_both_modes_work_with_the_pbp_figures(mode):
    assert _build(lambda c: _pbp_rows(), mode)["mode"] == mode
