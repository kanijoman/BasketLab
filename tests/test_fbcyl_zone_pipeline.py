"""FBCYL zones across the report pipelines (#150): weekly PNGs, league baseline, team report."""
from unittest.mock import MagicMock

from db_helpers import new_mock_db
from src.services.team_report_service import TeamReportService


def _pt(x, y):
    return {"xnormalize": x, "ynormalize": y}


def _doc():
    mk = lambda tid, uuid, made, miss: {  # noqa: E731
        "teamIdExtern": tid, "name": f"T{tid}",
        "players": [{"uuid": uuid, "name": uuid, "data": {
            "shootingOfTwoSuccessfulPoint": [_pt(11.6, 50.0)] * made,
            "shootingOfTwoFailedPoint": [_pt(11.6, 50.0)] * miss}}]}
    # six teams: with only two, the quartiles of the competition would coincide with its extremes (#760)
    return {"stats": {"teams": [mk(1, "a", 9, 1), mk(2, "b", 2, 8), mk(3, "c", 4, 6), mk(4, "d", 5, 5), mk(5, "e", 6, 4), mk(6, "f", 7, 3)]}}


def _coll():
    c = new_mock_db()["FBCYL_Q"]
    c.insert_one(_doc())
    return c






def test_team_report_loads_fbcyl_zones_rated_against_the_league():
    db = MagicMock()
    db.connection.get_collection.return_value = _coll()
    svc = TeamReportService(db, stats=MagicMock())
    zones = {z["zone"]: z for z in svc._load_zones("FBCYL_1A_2026", "1")}
    assert zones["key_area"]["fga"] == 10 and zones["key_area"]["rating"] == "above"
