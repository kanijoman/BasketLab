"""Backfill of ``DERIVED`` in the FEB games already stored (#372)."""
from db_helpers import new_mock_db
from src.pbp.game_derived import DERIVED_VERSION
from src.services.derived_backfill import backfill_collection
from tests.test_game_possessions import _alternating, _game


def _col():
    return new_mock_db("backfill")["FEB_X"]


def test_games_without_derived_fields_get_them():
    col = _col()
    col.insert_one({"_id": 1, **_game(_alternating(10), a_box={"p2a": 5}, b_box={"p2a": 5})})

    result = backfill_collection(col)

    assert result == {"updated": 1, "skipped": 0, "unreadable": 0}
    assert [t["id"] for t in col.find_one({"_id": 1})["DERIVED"]["TEAM"]] == ["A", "B"]


def test_games_already_at_the_current_version_are_left_alone():
    col = _col()
    col.insert_one({"_id": 1, **_game(_alternating(10)), "DERIVED": {"v": DERIVED_VERSION, "TEAM": []}})

    assert backfill_collection(col) == {"updated": 0, "skipped": 1, "unreadable": 0}
    assert col.find_one({"_id": 1})["DERIVED"]["TEAM"] == []


def test_an_older_version_is_recomputed_and_unreadable_games_are_counted():
    col = _col()
    col.insert_one({"_id": 1, **_game(_alternating(10)), "DERIVED": {"v": DERIVED_VERSION - 1, "TEAM": []}})
    col.insert_one({"_id": 2, "HEADER": {"TEAM": []}, "BOXSCORE": {"TEAM": []}})

    assert backfill_collection(col) == {"updated": 1, "skipped": 0, "unreadable": 1}
    assert col.find_one({"_id": 1})["DERIVED"]["v"] == DERIVED_VERSION
    assert "DERIVED" not in col.find_one({"_id": 2})


def test_backfill_reads_the_shotchart_so_the_paint_points_are_not_lost_regression():
    """Bug: the projection of the backfill left out SHOTCHART, so every backfilled game had no paint points."""
    col = _col()
    shot = {"m": "1", "x": 6.0, "y": 50.0, "team": 0, "quarter": 1, "t": "09:50", "player": "1"}
    col.insert_one({"_id": 1, **_game(_alternating(10), a_box={"p2a": 5}, b_box={"p2a": 5}), "SHOTCHART": {"SHOTS": [shot]}})

    backfill_collection(col)

    assert col.find_one({"_id": 1})["DERIVED"]["TEAM"][0]["pts_paint"] == 2


def test_require_env_fails_without_the_connection_string_instead_of_trying_a_default_database(monkeypatch, capsys):
    from src.services.derived_backfill import main

    monkeypatch.delenv("MONGODB_CONNECTION_STRING", raising=False)

    assert main(["--require-env"]) == 2
    assert "MONGODB_CONNECTION_STRING" in capsys.readouterr().err
