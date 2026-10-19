"""Season figures per team and period (Q1-Q4 and OT together), with the rival's, from ``DERIVED`` (#353)."""
from unittest.mock import MagicMock

import pytest

from db_helpers import new_mock_db
from src.services.pbp_extended_stats_service import PBPExtendedStatsService, clear_cache


def _period(p, **kw):
    base = {"p": p, "minutes": 10 if p <= 4 else 5}
    for k in ("pts", "poss", "fga", "fgm", "fg3m", "fta", "ftm", "tov", "orb", "drb", "fouls"):
        base[k] = 0
        base[f"opp_{k}"] = 0
    base.update(kw)
    return base


def _team(tid, periods, reliable=True):
    return {"id": tid, "reliable": reliable, "periods": periods}


def _game(match_id, a_periods, b_periods, reliable=True, version=5):
    return {"_id": match_id, "HEADER": {"TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
            "DERIVED": {"v": version, "TEAM": [_team("A", a_periods, reliable), _team("B", b_periods, reliable)]}}


def _service(*games):
    clear_cache()
    db = new_mock_db("per")
    db["G"].insert_many(list(games))
    handler = MagicMock()
    handler.repository.connection.get_collection.side_effect = lambda name: db[name]
    return PBPExtendedStatsService(handler)


def _team_rows(*games):
    return {r["team_name"]: r for r in _service(*games).get_by_period("G")}


def test_sums_per_period_and_overtimes_are_grouped():
    out = _team_rows(
        _game(1, [_period(5, pts=6, opp_pts=4, minutes=5), _period(2, pts=10, opp_pts=12), _period(1, pts=20, opp_pts=15)], []),
        _game(2, [_period(1, pts=18, opp_pts=21), _period(2, pts=14, opp_pts=10), _period(5, pts=3, opp_pts=2, minutes=5),
                  _period(6, pts=2, opp_pts=2, minutes=5)], []),
    )["Local"]["periods"]

    assert list(out) == ["1", "2", "OT"]                  # Q1-Q4 in order, overtimes last, whatever order Mongo returns
    assert (out["1"]["pts"], out["1"]["opp_pts"], out["1"]["games"]) == (38, 36, 2)
    assert out["1"]["pts_per_game"] == 19.0 and out["2"]["pts_per_game"] == 12.0
    assert (out["OT"]["pts"], out["OT"]["games"], out["OT"]["minutes"]) == (11, 2, 15)   # 5 + 5 + 5 minutes
    assert out["OT"]["pts_per_game"] == 5.5          # per game that went to overtime


def test_efficiency_four_factors_and_pace_of_a_period():
    out = _team_rows(_game(1, [_period(1, pts=20, opp_pts=15, poss=10, opp_poss=12, fga=15, fgm=8, fg3m=2, fta=6, tov=2, orb=3, drb=5,
                                       opp_drb=7, opp_orb=2, opp_fga=10, opp_fgm=5, opp_fg3m=1, opp_fta=4, opp_tov=3, fouls=4)], []))["Local"]["periods"]["1"]

    assert out["ortg"] == pytest.approx(200.0) and out["drtg"] == pytest.approx(125.0) and out["net_rating"] == pytest.approx(75.0)
    assert out["efg_pct"] == pytest.approx((8 + 1) / 15 * 100)
    assert out["tov_pct"] == pytest.approx(2 / (15 + 0.44 * 6 + 2) * 100)
    assert out["orb_pct"] == pytest.approx(3 / (3 + 7) * 100) and out["drb_pct"] == pytest.approx(5 / (5 + 2) * 100)
    assert out["ftr"] == pytest.approx(40.0) and out["fouls_per_game"] == 4.0
    assert out["pace"] == pytest.approx(10 * 40 / 10)
    assert out["opp_efg_pct"] == pytest.approx((5 + 0.5) / 10 * 100) and out["opp_ftr"] == pytest.approx(40.0)


def test_ratios_are_none_without_the_denominator():
    out = _team_rows(_game(1, [_period(1)], []))["Local"]["periods"]["1"]

    assert out["ortg"] is None and out["efg_pct"] is None and out["tov_pct"] is None and out["orb_pct"] is None


def test_unreliable_games_are_left_out_and_counted():
    row = _team_rows(_game(1, [_period(1, pts=20)], []), _game(2, [_period(1, pts=50)], [], reliable=False))["Local"]

    assert (row["games"], row["games_unreliable"], row["periods"]["1"]["pts"]) == (1, 1, 20)


def test_games_below_the_current_version_are_ignored_and_periods_missing_in_all_games_are_absent():
    assert _service(_game(1, [_period(1, pts=20)], [], version=4)).get_by_period("G") == []
    row = _team_rows(_game(1, [_period(1, pts=20)], []))["Local"]

    assert sorted(row["periods"]) == ["1"]


def test_results_are_cached_per_collection():
    service = _service(_game(1, [_period(1, pts=20)], []))
    first = service.get_by_period("G")
    service._db.repository.connection.get_collection.side_effect = RuntimeError("no second query")

    assert service.get_by_period("G") is first


def test_endpoint_returns_the_rows():
    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.deps import get_db

    service = _service(_game(1, [_period(1, pts=20)], []))
    app.dependency_overrides[get_db] = lambda: service._db
    try:
        response = TestClient(app).get("/api/v1/possessions/G/by-period")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()[0]["periods"]["1"]["pts"] == 20
