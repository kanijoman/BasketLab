"""Per-game derived fields stored in the match document (#372): exact possessions and validated rebounds / turnovers.

The season pipelines only see the aggregated box score, so the exact figures of ``team_game_possessions`` are stored in
``DERIVED.TEAM`` (aligned with ``BOXSCORE.TEAM``) when the game is ingested, and read from there with a box-score fallback.
"""
from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields
from tests.test_game_possessions import _alternating, _game, _rebound_game


def test_derived_fields_follow_the_order_of_the_box_score_teams():
    game = _game(_alternating(10), a_box={"p2a": 5, "p2m": 5, "pts": 10}, b_box={"p2a": 5, "p2m": 5, "pts": 10})

    derived = derive_game_fields(game)

    assert derived["v"] == DERIVED_VERSION
    assert [t["id"] for t in derived["TEAM"]] == ["A", "B"]
    first = derived["TEAM"][0]
    assert (first["possessions"], first["possessions_source"], first["quality_level"]) == (5, "pbp", "ok")


def test_derived_fields_carry_the_reliability_of_the_game_by_its_impact():
    out = derive_game_fields(_game(_alternating(10), a_box={"p2a": 5, "p2m": 5, "pts": 10}, b_box={"p2a": 5, "p2m": 5, "pts": 10}))

    assert DERIVED_VERSION >= 5
    assert all(t["reliable"] is True and t["unknown_pts_pct"] == 0 for t in out["TEAM"])


def test_derived_rebounds_and_turnovers_are_the_validated_ones_with_team_rebounds():
    out = derive_game_fields(_rebound_game(a_orb_player=2, a_orb_team=1, b_drb=3, box_ro=2, box_rd=3))

    a, b = out["TEAM"]
    assert (a["orb"], a["orb_source"]) == (3, "pbp")
    assert (b["drb"], b["drb_source"]) == (3, "pbp")


def test_a_game_that_cannot_be_read_has_no_derived_fields():
    assert derive_game_fields({"HEADER": {"TEAM": []}, "BOXSCORE": {"TEAM": []}}) is None
    assert derive_game_fields({"moves": [], "stats": {"teams": []}}) is None


# ---------------------------------------------------------------- stored on ingestion

def _repo():
    from unittest.mock import MagicMock

    from db_helpers import new_mock_db

    from src.database.repository import BasketballRepository

    db = new_mock_db("derived")
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: db[name]
    return BasketballRepository(conn), db


def test_inserting_a_game_with_pbp_stores_the_derived_fields():
    repo, db = _repo()
    game = _game(_alternating(10), a_box={"p2a": 5}, b_box={"p2a": 5})

    assert repo.insert_boxscore("FEB_X", "77", game)

    stored = db["FEB_X"].find_one({"_id": 77})
    assert [t["id"] for t in stored["DERIVED"]["TEAM"]] == ["A", "B"]


def test_inserting_a_game_that_cannot_be_derived_still_stores_it_without_the_field():
    repo, db = _repo()

    assert repo.insert_boxscore("FEB_X", "78", {"HEADER": {"TEAM": []}, "BOXSCORE": {"TEAM": []}})

    assert "DERIVED" not in db["FEB_X"].find_one({"_id": 78})
