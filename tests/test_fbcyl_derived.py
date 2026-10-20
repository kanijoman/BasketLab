"""Exact possessions and validated rebounds / turnovers for FBCYL games (issue #373), the counterpart of #351/#372 for FEB.

``tests/fixtures/fbcyl_game_ok.json.gz`` is a real game (LF Castilla y León 2026/27, uuid 6ac24423afc7e7e9628cf9d7) with a clean feed: the figures
below were checked against its box score. What the real feed looks like (17 games measured):

* the team box (``stats.teams[].data``) INCLUDES the team rebounds and turnovers while the moves have almost none (and no team rebounds at
  all), so the box is the reference for them (the opposite of FEB, where the pbp counts teams and the box does not credit them);
* points, field goals and free throws of the moves match the box in 29-33 of 34 team-games;
* there is no starters flag (``starting`` is false for everybody) and no shot chart: the bench is who did not start the game by the moves.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.database.possession_stats_helpers import boxscore_possession_stats
from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields
from src.pbp.game_possessions import analyse_game, team_game_possessions

FIXTURE = Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz"
HOME, AWAY = "46519", "46520"          # teamIdIntern (the ids of the moves); the extern ids are 39675 and 40288


@pytest.fixture(scope="module")
def game():
    return json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))


def test_the_tracker_reads_an_fbcyl_game_and_its_points_match_the_box(game):
    teams = team_game_possessions(game)
    assert set(teams) == {HOME, AWAY}
    assert (teams[HOME]["pts"], teams[AWAY]["pts"]) == (55, 75)
    assert (teams[HOME]["fga"], teams[HOME]["fta"]) == (67, 19) and (teams[AWAY]["fga"], teams[AWAY]["fta"]) == (66, 12)


def test_the_box_is_the_reference_for_rebounds_and_turnovers_because_it_includes_the_team_ones(game):
    """pbp 16 / 24 / 24 against box 16 / 28 / 24 for the home team: the moves have no team rebounds, the box does."""
    home = team_game_possessions(game)[HOME]
    assert (home["orb"], home["orb_source"]) == (16, "pbp")                    # equal: nothing to correct
    assert (home["drb"], home["drb_source"]) == (28, "boxscore")                # the moves lack 4 (team rebounds)
    assert home["tov"] == 24 and home["team_orb"] == 0 and home["team_drb"] == 0
    away = team_game_possessions(game)[AWAY]
    assert (away["orb"], away["orb_source"]) == (10, "boxscore") and (away["drb"], away["drb_source"]) == (36, "boxscore")
    assert (away["tov"], away["tov_source"]) == (22, "boxscore")


def test_the_possessions_are_exact_and_the_game_is_reliable(game):
    teams = team_game_possessions(game)
    assert teams[HOME]["possessions_source"] == teams[AWAY]["possessions_source"] == "pbp"
    assert teams[HOME]["possessions"] == 83 and teams[AWAY]["possessions"] == 83
    assert all(t["reliable"] and t["unknown_pts_pct"] == 0.0 and t["quality_level"] == "ok" for t in teams.values())


def test_the_minutes_of_the_game_come_from_its_periods(game):
    assert team_game_possessions(game)[HOME]["game_minutes"] == 40


def test_a_game_without_moves_or_box_cannot_be_read_regression(game):
    assert analyse_game({"uuid": "x", "moves": [], "stats": game["stats"]}) is None
    assert analyse_game({"uuid": "x", "moves": game["moves"], "stats": {"teams": []}}) is None
    assert analyse_game({}) is None


def test_derived_has_the_same_figures_as_the_feb_one_and_the_two_ids_of_each_team(game):
    derived = derive_game_fields(game)
    assert derived["v"] == DERIVED_VERSION and [t["id"] for t in derived["TEAM"]] == [HOME, AWAY]
    assert [t["ext_id"] for t in derived["TEAM"]] == ["39675", "40288"]
    home = derived["TEAM"][0]
    assert {"pts", "possessions", "possessions_source", "reliable", "orb", "drb", "tov", "pts_by_origin", "pts_bench", "periods", "timeouts"} <= set(home)
    assert sum(home["pts_by_origin"].values()) == home["pts"]                     # every point has an origin
    assert home["pts_paint"] is None                                              # FBCYL has no shot chart
    assert len(home["periods"]) == 4


def test_the_bench_is_who_did_not_start_the_game_by_the_moves(game):
    """No ``starting`` flag in the feed: the starting five is written as ``Entra al campo`` at 0:00 of the 1st period."""
    from src.pbp.game_events import game_events
    from src.pbp.points_by_origin import fbcyl_starters

    started = fbcyl_starters(sorted(game_events(game, True), key=lambda e: (e.elapsed, e.num)))
    assert {team: len(players) for team, players in started.items()} == {HOME: 5, AWAY: 5}
    derived = derive_game_fields(game)
    bench = {t["id"]: t["pts_bench"] for t in derived["TEAM"]}
    assert 0 < bench[HOME] < 55 and 0 < bench[AWAY] < 75


def test_a_feb_document_is_unchanged_by_the_fbcyl_support(feb_game_doc):
    derived = derive_game_fields(feb_game_doc)
    assert derived is not None and "ext_id" not in derived["TEAM"][0]


# --- the box-score fallback ------------------------------------------------------------------------------------------------------

def test_the_box_estimate_reads_the_fbcyl_team_data_regression(game):
    """Bug: it read ``FGA``/``REB_O``/``TO``/``FTA``/``PTS`` of ``stats.teams[]`` that do not exist (the team has ``data{...}``): always 0."""
    stats = boxscore_possession_stats([game], "46519", True)
    assert stats["total_games"] == 1
    # 67 - 16 + 24 + 0.44 * 19
    assert stats["boxscore_possessions"] == pytest.approx(83.4, abs=0.1)
    assert stats["boxscore_oer"] == pytest.approx(55 / 83.4 * 100, abs=0.1)
    assert boxscore_possession_stats([game], "99999", True)["total_games"] == 0


# --- ingestion and backfill -------------------------------------------------------------------------------------------------------

def test_a_new_fbcyl_game_is_stored_with_its_derived_figures(game):
    from db_helpers import new_mock_db
    from src.database.repository import BasketballRepository
    from tests.test_repository_core import _make_connection

    db = new_mock_db("ingest")
    repo = BasketballRepository(_make_connection(db))
    assert repo.insert_fbcyl_match("FBCYL_X", game["uuid"], dict(game))
    stored = db["FBCYL_X"].find_one({"_id": game["uuid"]})
    assert stored["DERIVED"]["v"] == DERIVED_VERSION and [t["id"] for t in stored["DERIVED"]["TEAM"]] == [HOME, AWAY]


def test_an_fbcyl_game_that_cannot_be_derived_is_still_stored():
    from db_helpers import new_mock_db
    from src.database.repository import BasketballRepository
    from tests.test_repository_core import _make_connection

    db = new_mock_db("ingest")
    assert BasketballRepository(_make_connection(db)).insert_fbcyl_match("FBCYL_X", "u1", {"uuid": "u1", "moves": [], "stats": {}})
    assert "DERIVED" not in db["FBCYL_X"].find_one({"_id": "u1"})


def test_the_backfill_stores_derived_in_the_fbcyl_games_already_there(game):
    from db_helpers import new_mock_db
    from src.services.derived_backfill import backfill_collection

    col = new_mock_db("backfill")["FBCYL_X"]
    col.insert_one({**game, "_id": game["uuid"]})
    col.insert_one({"_id": "empty", "uuid": "empty", "moves": [], "stats": {}})
    assert backfill_collection(col, fbcyl=True) == {"updated": 1, "skipped": 0, "unreadable": 1}
    assert col.find_one({"_id": game["uuid"]})["DERIVED"]["TEAM"][0]["id"] == HOME
    assert backfill_collection(col, fbcyl=True)["skipped"] == 1                    # idempotent


def test_the_backfill_picks_fbcyl_collections_by_their_name():
    from src.services.derived_backfill import fbcyl_collection_names

    class Db:
        @staticmethod
        def list_collection_names():
            return ["FBCYL_1a_FASE_2026", "LF_CHALLENGE_2026", "COLLECTION_META"]

    assert fbcyl_collection_names(Db) == ["FBCYL_1a_FASE_2026"]
