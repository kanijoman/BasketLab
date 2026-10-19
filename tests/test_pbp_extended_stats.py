"""Season points by origin, bench and paint per team, with the rival's (``opp_``), from ``DERIVED`` (#352)."""
from unittest.mock import MagicMock

import pytest

from db_helpers import new_mock_db
from src.services.pbp_extended_stats_service import PBPExtendedStatsService, clear_cache


def _team(tid, **kw):  # noqa: D103
    base = {"id": tid, "pts": 0, "possessions": 70.0, "reliable": True, "pts_off_tov": 0, "poss_off_tov": 0, "pts_off_steal": 0,
            "poss_off_steal": 0, "pts_second_chance": 0, "poss_second_chance": 0, "pts_bench": 0, "pts_paint": 0,
            "pts_by_origin": {}}
    base.update(kw)
    return base


def _game(match_id, a, b, version=5):
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


def test_bench_share_is_the_bench_points_over_the_team_points():
    out = _rows(_game(1, dict(pts_bench=20, pts=80), dict(pts_bench=21, pts=70)))

    assert out["Local"]["bench_pct"] == pytest.approx(25.0)
    assert out["Visitante"]["bench_pct"] == pytest.approx(30.0)


def test_unreliable_games_are_left_out_and_counted():
    out = _rows(_game(1, dict(pts_off_tov=10, poss_off_tov=8), dict()),
                _game(2, dict(pts_off_tov=50, poss_off_tov=9, reliable=False), dict()))["Local"]

    assert (out["games"], out["games_unreliable"], out["pts_off_tov"]) == (1, 1, 10)


def test_games_without_the_current_version_are_ignored():
    rows = _service(_game(1, dict(pts_off_tov=10), dict(), version=4)).get_points_by_origin("G")

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
