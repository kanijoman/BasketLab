"""FBCYL zones across the report pipelines (#150): weekly PNGs, league baseline, team report."""
from unittest.mock import MagicMock

from db_helpers import new_mock_db
from src.shotcharts.league_zones import league_zone_stats
from src.shotcharts.zone_analysis import ZoneAnalyzer
from src.services.team_report_service import TeamReportService


def _pt(x, y):
    return {"xnormalize": x, "ynormalize": y}


def _doc():
    mk = lambda tid, uuid, made, miss: {  # noqa: E731
        "teamIdExtern": tid, "name": f"T{tid}",
        "players": [{"uuid": uuid, "name": uuid, "data": {
            "shootingOfTwoSuccessfulPoint": [_pt(11.6, 50.0)] * made,
            "shootingOfTwoFailedPoint": [_pt(11.6, 50.0)] * miss}}]}
    return {"stats": {"teams": [mk(1, "a", 8, 2), mk(2, "b", 2, 8)]}}


def _coll():
    c = new_mock_db()["FBCYL_Q"]
    c.insert_one(_doc())
    return c


def test_weekly_fbcyl_shots_use_one_orientation_for_every_team_regression():
    """FBCYL coordinates are already folded into one half: the second team of a document must
    not be mirrored (team index 1 flips left/right in the FEB conversion)."""
    from services.weekly_report_service import _extract_shots

    db = MagicMock()
    db.connection.get_collection.return_value = _coll()
    first, _, _ = _extract_shots(db, "FBCYL_Q", "1")
    second, _, _ = _extract_shots(db, "FBCYL_Q", "2")
    assert {s["team"] for s in first} == {"0"}
    assert {s["team"] for s in second} == {"0"}


def test_league_zone_stats_supports_fbcyl_collections():
    stats = league_zone_stats(ZoneAnalyzer(), _coll(), fbcyl=True)
    assert stats is not None and sum(z["total"] for z in stats.values()) == 20


def test_team_report_loads_fbcyl_zones_rated_against_the_league():
    db = MagicMock()
    db.connection.get_collection.return_value = _coll()
    svc = TeamReportService(db, stats=MagicMock())
    zones = {z["zone"]: z for z in svc._load_zones("FBCYL_1A_2026", "1")}
    assert zones["paint"]["fga"] == 10 and zones["paint"]["rating"] == "above"
