"""Season after-timeout possessions, first possessions, first / last two minutes and the effect of the timeouts, from ``DERIVED`` (#354, #355)."""
from unittest.mock import MagicMock

import pytest

from db_helpers import new_mock_db
from src.services.pbp_situation_stats_service import PBPSituationStatsService, clear_cache


def _edges(**kw):
    base = {w: {k: 0 for k in ("pts", "opp_pts", "poss", "opp_poss", "tov", "opp_tov")} for w in ("start", "end")}
    for window, values in kw.items():
        base[window].update(values)
    return base


def _period(p, **kw):
    base = {"p": p, "minutes": 10}
    for k in ("pts", "poss", "tov"):
        base[k] = 0
        base[f"opp_{k}"] = 0
    base.update(kw)
    return base


def _tm(caller, pre_net, post_net, p=1, t=300):
    """A timeout entry with a net rating (per 100) before and after, over 5 possessions of each team."""
    def side(net):          # 5 possessions each: the team scores 10 + net/20 * ... keep it simple: own pts = 10 + net/20, rival 10
        return {"pts": 10 + net // 20, "opp_pts": 10, "poss": 5, "opp_poss": 5, "tov": 1, "opp_tov": 1}
    return {"p": p, "t": t, "caller": caller, "pre": side(pre_net), "post": side(post_net)}


def _team(tid, reliable=True, **kw):
    base = {"id": tid, "reliable": reliable, "ato_own": {"n": 0, "pts": 0}, "ato_rival": {"n": 0, "pts": 0},
            "first_poss": {"n": 0, "pts": 0}, "edges": _edges(), "periods": [_period(1)], "timeouts": []}
    base.update(kw)
    return base


def _game(match_id, a, b, version=5):
    return {"_id": match_id, "HEADER": {"TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
            "DERIVED": {"v": version, "TEAM": [_team("A", **a), _team("B", **b)]}}


def _service(*games):
    clear_cache()
    db = new_mock_db("sit")
    db["G"].insert_many(list(games))
    handler = MagicMock()
    handler.repository.connection.get_collection.side_effect = lambda name: db[name]
    return PBPSituationStatsService(handler)


def _rows(method, *games):
    return {r["team_name"]: r for r in getattr(_service(*games), method)("G")}


# ---------------------------------------------------------------- situations

def test_after_timeout_and_first_possessions_are_summed_with_points_per_possession():
    out = _rows("get_situations",
                _game(1, dict(ato_own={"n": 2, "pts": 3}, ato_rival={"n": 1, "pts": 2}, first_poss={"n": 1, "pts": 2}), {}),
                _game(2, dict(ato_own={"n": 1, "pts": 2}, ato_rival={"n": 1, "pts": 0}, first_poss={"n": 2, "pts": 1}), {}))["Local"]

    assert out["games"] == 2
    assert (out["ato_own"]["n"], out["ato_own"]["pts"], out["ato_own"]["ppp"]) == (3, 5, pytest.approx(5 / 3))
    assert (out["ato_rival"]["n"], out["ato_rival"]["ppp"]) == (2, 1.0)
    assert (out["first_poss"]["n"], out["first_poss"]["pts"], out["first_poss"]["ppp"]) == (3, 3, 1.0)


def test_edges_give_the_net_rating_and_the_difference_with_the_rest_of_the_period():
    edges = _edges(start={"pts": 10, "opp_pts": 6, "poss": 10, "opp_poss": 10, "tov": 2, "opp_tov": 1},
                   end={"pts": 4, "opp_pts": 8, "poss": 10, "opp_poss": 10, "tov": 3, "opp_tov": 2})
    period = _period(1, pts=40, opp_pts=30, poss=40, opp_poss=40, tov=8, opp_tov=7)
    out = _rows("get_situations", _game(1, dict(edges=edges, periods=[period]), {}))["Local"]["edges"]

    assert out["start"]["net_rating"] == pytest.approx((10 / 10 - 6 / 10) * 100)
    assert out["end"]["net_rating"] == pytest.approx((4 / 10 - 8 / 10) * 100)
    assert out["start"]["pts_per_game"] == 10 and out["start"]["tov_pct"] == pytest.approx(20.0)
    # the rest of the period: 40-10-4 = 26 points for, 30-6-8 = 16 against, over 40-10-10 = 20 possessions each
    assert out["rest"]["net_rating"] == pytest.approx((26 / 20 - 16 / 20) * 100)
    assert out["start"]["vs_rest"] == pytest.approx(out["start"]["net_rating"] - out["rest"]["net_rating"])


def test_unreliable_games_are_left_out_of_the_situations_and_counted():
    row = _rows("get_situations", _game(1, dict(ato_own={"n": 1, "pts": 2}), {}),
                _game(2, dict(ato_own={"n": 5, "pts": 9}, reliable=False), {}))["Local"]

    assert (row["games"], row["games_unreliable"], row["ato_own"]["n"]) == (1, 1, 1)


def test_ratios_without_possessions_are_none():
    out = _rows("get_situations", _game(1, {}, {}))["Local"]

    assert out["ato_own"]["ppp"] is None and out["first_poss"]["ppp"] is None and out["edges"]["start"]["net_rating"] is None


# ---------------------------------------------------------------- timeouts

def test_timeouts_called_by_the_team_and_by_the_rival_are_summarised_apart():
    own = [_tm("own", 0, 40), _tm("own", 40, 0), _tm("own", 0, 80)]
    rival = [_tm("rival", 40, 0)]
    out = _rows("get_timeout_effects", _game(1, dict(timeouts=own + rival), {}))["Local"]

    assert out["own"]["n"] == 3 and out["rival"]["n"] == 1
    assert out["own"]["pct_caller_improves"] == pytest.approx(2 / 3 * 100)      # two of the three improved the caller
    assert out["rival"]["pct_caller_improves"] == pytest.approx(100.0)          # our net fell after the rival's timeout: the caller improved
    assert out["own"]["net_rating_before"] is not None and out["own"]["delta_net_rating"] == pytest.approx(
        out["own"]["net_rating_after"] - out["own"]["net_rating_before"])


def test_a_team_without_analysable_timeouts_has_empty_groups():
    out = _rows("get_timeout_effects", _game(1, {}, {}))["Local"]

    assert out["own"]["n"] == 0 and out["own"]["pct_caller_improves"] is None and out["own"]["delta_net_rating"] is None


def test_games_below_the_current_version_are_ignored():
    assert _service(_game(1, dict(ato_own={"n": 1, "pts": 2}), {}, version=4)).get_situations("G") == []


def test_results_are_cached_per_collection():
    service = _service(_game(1, dict(ato_own={"n": 1, "pts": 2}), {}))
    first = service.get_situations("G")
    service._db.repository.connection.get_collection.side_effect = RuntimeError("no second query")

    assert service.get_situations("G") is first


def test_endpoints_return_the_rows():
    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.deps import get_db

    service = _service(_game(1, dict(ato_own={"n": 1, "pts": 2}, timeouts=[_tm("own", 0, 40)]), {}))
    app.dependency_overrides[get_db] = lambda: service._db
    try:
        client = TestClient(app)
        situations, timeouts = client.get("/api/v1/possessions/G/situations"), client.get("/api/v1/possessions/G/timeouts")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert situations.status_code == 200 and situations.json()[0]["ato_own"]["n"] == 1
    assert timeouts.status_code == 200 and timeouts.json()[0]["own"]["n"] == 1
