"""Season points by origin, bench and paint per team, with the rival's (``opp_``), from ``DERIVED`` (#352)."""
from unittest.mock import MagicMock

import pytest

from db_helpers import new_mock_db
from src.services.pbp_extended_stats_service import PBPExtendedStatsService, clear_cache


def _team(tid, **kw):  # noqa: D103
    base = {"id": tid, "pts": 0, "possessions": 70.0, "reliable": True, "quality_level": "ok", "pts_off_tov": 0, "poss_off_tov": 0, "pts_off_steal": 0,
            "poss_off_steal": 0, "pts_second_chance": 0, "poss_second_chance": 0, "pts_bench": 0, "pts_paint": 0,
            "pts_fastbreak": 0, "poss_transition": 0, "pts_by_origin": {}}
    base.update(kw)
    return base


def _game(match_id, a, b, version=6):
    return {"_id": match_id, "HEADER": {"TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
            "DERIVED": {"v": version, "TEAM": [_team("A", **{"pts": 80, **a}), _team("B", **{"pts": 70, **b})]}}


def _service(*games):
    clear_cache()
    db = new_mock_db("ext")
    db["G"].insert_many(list(games))
    handler = MagicMock()
    handler.repository.connection.get_collection.side_effect = lambda name: db[name]
    return PBPExtendedStatsService(handler)


def _rows(*games):
    return {r["team_name"]: r for r in _service(*games).get_points_by_origin("G")}


def test_sums_and_averages_per_game_with_the_rival_figures_as_opp():
    out = _rows(
        _game(1, dict(pts_off_tov=10, poss_off_tov=8, pts_second_chance=6, pts_bench=20, pts_paint=30, pts=80),
              dict(pts_off_tov=4, poss_off_tov=5, pts_second_chance=2, pts_bench=12, pts_paint=20, pts=70)),
        _game(2, dict(pts_off_tov=6, poss_off_tov=4, pts_second_chance=4, pts_bench=10, pts_paint=24, pts=60),
              dict(pts_off_tov=8, poss_off_tov=6, pts_second_chance=0, pts_bench=8, pts_paint=26, pts=64)),
    )["Local"]

    assert out["games"] == 2
    assert (out["pts_off_tov"], out["pts_off_tov_per_game"], out["opp_pts_off_tov"]) == (16, 8.0, 12)
    assert (out["pts_second_chance"], out["opp_pts_second_chance"]) == (10, 2)
    assert (out["pts_paint"], out["opp_pts_paint"], out["pts_paint_per_game"]) == (54, 46, 27.0)


def test_origin_efficiency_is_points_per_100_possessions_of_that_origin():
    out = _rows(_game(1, dict(pts_off_tov=10, poss_off_tov=8, pts_off_steal=4, poss_off_steal=2, pts_second_chance=6, poss_second_chance=5),
                       dict(pts_off_tov=4, poss_off_tov=5)))["Local"]

    assert out["oer_off_tov"] == pytest.approx(125.0)
    assert out["oer_off_steal"] == pytest.approx(200.0)
    assert out["oer_second_chance"] == pytest.approx(120.0)
    assert out["opp_oer_off_tov"] == pytest.approx(80.0)
    assert out["oer_off_tov"] is not None and out["oer_off_steal"] is not None


def test_the_fast_break_estimate_is_summed_with_its_efficiency_over_the_transition_possessions():
    out = _rows(_game(1, dict(pts_fastbreak=6, poss_transition=10), dict(pts_fastbreak=2, poss_transition=8)),
                _game(2, dict(pts_fastbreak=4, poss_transition=10), dict(pts_fastbreak=4, poss_transition=12)))["Local"]

    assert (out["pts_fastbreak"], out["pts_fastbreak_per_game"], out["opp_pts_fastbreak"]) == (10, 5.0, 6)
    assert out["oer_fastbreak"] == pytest.approx(50.0) and out["opp_oer_fastbreak"] == pytest.approx(30.0)


def test_games_stored_before_the_fast_break_estimate_are_ignored_until_the_backfill_brings_them_up_to_date():
    assert _service(_game(1, dict(pts_off_tov=10), dict(), version=5)).get_points_by_origin("G") == []


def test_bench_share_is_the_bench_points_over_the_team_points():
    out = _rows(_game(1, dict(pts_bench=20, pts=80), dict(pts_bench=21, pts=70)))

    assert out["Local"]["bench_pct"] == pytest.approx(25.0)
    assert out["Visitante"]["bench_pct"] == pytest.approx(30.0)


def test_unreliable_games_are_left_out_and_counted():
    out = _rows(_game(1, dict(pts_off_tov=10, poss_off_tov=8), dict()),
                _game(2, dict(pts_off_tov=50, poss_off_tov=9, reliable=False), dict()))["Local"]

    assert (out["games"], out["games_unreliable"], out["pts_off_tov"]) == (1, 1, 10)


def test_games_used_with_alternation_breaks_are_counted_as_doubtful_but_not_the_ones_left_out():
    row = _rows(_game(1, dict(quality_level="ok"), {}),
                _game(2, dict(quality_level="doubtful"), {}),
                _game(3, dict(quality_level="unreliable"), {}),                          # many breaks but reliable by its impact: used
                _game(4, dict(quality_level="unreliable", reliable=False), {}))["Local"]   # left out: counted as excluded, not as doubtful

    assert (row["games"], row["games_doubtful"], row["games_unreliable"]) == (3, 2, 1)


def test_games_without_the_current_version_are_ignored():
    rows = _service(_game(1, dict(pts_off_tov=10), dict(), version=5)).get_points_by_origin("G")

    assert rows == []


def test_paint_is_none_when_no_game_has_a_shotchart_and_efficiency_is_none_without_possessions():
    out = _rows(_game(1, dict(pts_paint=None), dict()))["Local"]

    assert out["pts_paint"] is None and out["pts_paint_per_game"] is None
    assert out["oer_off_steal"] is None           # no possession after a steal


def test_results_are_cached_per_collection():
    service = _service(_game(1, dict(pts_off_tov=10, poss_off_tov=8), dict()))
    first = service.get_points_by_origin("G")

    service._db.repository.connection.get_collection.side_effect = RuntimeError("no second query")

    assert service.get_points_by_origin("G") is first


# ---------------------------------------------------------------- endpoint

def test_endpoint_returns_the_rows_and_is_public_read_only():
    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.deps import get_db

    service = _service(_game(1, dict(pts_off_tov=10, poss_off_tov=8), dict()))
    app.dependency_overrides[get_db] = lambda: service._db
    try:
        response = TestClient(app).get("/api/v1/possessions/G/points-by-origin")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert [r["team_name"] for r in response.json()] == ["Local", "Visitante"]
    assert response.json()[0]["pts_off_tov"] == 10


# -- turnovers without the steals, and everything per 100 possessions (#602, #603) -----------------------------------------------------------------------

def test_the_turnover_origin_leaves_the_steals_out_because_they_have_their_own_column():
    """``pts_off_tov`` of DERIVED counts the possessions that start after a turnover OR a steal; the table shows the steals apart, so «tras pérdida» is what is left (#602)."""
    out = _rows(_game(1, dict(pts_off_tov=10, poss_off_tov=8, pts_off_steal=4, poss_off_steal=3),
                      dict(pts_off_tov=7, poss_off_tov=6, pts_off_steal=2, poss_off_steal=2)))["Local"]
    assert (out["pts_off_loss"], out["pts_off_loss_per_game"]) == (6, 6.0)                       # 10 - 4: the points after a turnover that was not a steal
    assert out["oer_off_loss"] == pytest.approx(6 / 5 * 100)                                      # over the 8 - 3 possessions that started that way
    assert out["opp_pts_off_loss"] == 5 and out["opp_oer_off_loss"] == pytest.approx(5 / 4 * 100)
    assert out["pts_off_tov"] == 10 and out["pts_off_steal"] == 4                                 # what was there stays (consumers of the endpoint)


def test_a_team_with_only_steals_has_zero_points_after_a_plain_turnover_and_none_for_the_efficiency():
    out = _rows(_game(1, dict(pts_off_tov=4, poss_off_tov=3, pts_off_steal=4, poss_off_steal=3), dict()))["Local"]
    assert out["pts_off_loss"] == 0 and out["oer_off_loss"] is None                              # no possession of that origin: not a 0 %


def test_the_points_of_each_origin_per_100_possessions_of_the_team():
    out = _rows(
        _game(1, dict(pts_off_tov=10, poss_off_tov=8, pts_off_steal=4, poss_off_steal=2, pts_second_chance=7, pts_bench=20, pts_paint=30, pts_fastbreak=6, possessions=80.0),
              dict(pts_off_tov=4, pts_bench=12, pts_paint=20, pts_fastbreak=2, possessions=60.0)),
        _game(2, dict(pts_off_tov=2, poss_off_tov=2, pts_second_chance=3, pts_bench=10, pts_paint=24, pts_fastbreak=4, possessions=120.0),
              dict(pts_off_tov=0, pts_bench=8, pts_paint=26, pts_fastbreak=0, possessions=100.0)),
    )["Local"]
    assert out["possessions"] == 200.0 and out["opp_possessions"] == 160.0
    assert out["pts_off_loss_per_100"] == pytest.approx((10 - 4 + 2) / 200 * 100)
    assert out["pts_off_steal_per_100"] == pytest.approx(4 / 200 * 100)
    assert out["pts_second_chance_per_100"] == pytest.approx(10 / 200 * 100)
    assert out["pts_bench_per_100"] == pytest.approx(30 / 200 * 100)
    assert out["pts_paint_per_100"] == pytest.approx(54 / 200 * 100)
    assert out["pts_fastbreak_per_100"] == pytest.approx(10 / 200 * 100)


def test_what_the_rival_scores_is_per_100_possessions_of_the_rival_not_of_the_team():
    out = _rows(_game(1, dict(possessions=80.0), dict(pts_bench=12, pts_paint=20, pts_fastbreak=2, pts_off_tov=4, poss_off_tov=1, possessions=60.0)))["Local"]
    assert out["opp_pts_paint_per_100"] == pytest.approx(20 / 60 * 100) and out["opp_pts_fastbreak_per_100"] == pytest.approx(2 / 60 * 100)
    assert out["opp_pts_off_loss_per_100"] == pytest.approx(4 / 60 * 100)


def test_without_possessions_the_per_100_figures_are_missing_not_zero_and_the_paint_keeps_its_rule():
    out = _rows(_game(1, dict(possessions=0.0, pts_paint=None), dict(possessions=0.0)))["Local"]
    assert out["pts_bench_per_100"] is None and out["pts_fastbreak_per_100"] is None
    assert out["pts_paint_per_100"] is None                                                       # no shot chart: unknown, not 0


@pytest.mark.parametrize("version", [6])
def test_the_new_figures_come_with_the_same_games_as_before(version):
    """Nothing about which games count changes: the same reliable games of the current version."""
    out = _rows(_game(1, dict(), dict(), version=version), _game(2, dict(), dict(), version=5))["Local"]
    assert out["games"] == 1
