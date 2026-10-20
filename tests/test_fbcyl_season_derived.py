"""Season figures of FBCYL from the ``DERIVED`` stored in each game (issue #432, after #373): the consumers that FEB already had.

A team is identified by its ``teamIdExtern`` (stable) and NOT by the ``teamIdIntern`` of the moves, which changes in every game: the stored
``DERIVED.TEAM`` carries both (``id`` / ``ext_id``). The names come from ``stats.teams[].name``. Games that are not ``reliable`` (#390) are
left out of the figures that depend on the possessions, as in FEB.
"""
import copy
import gzip
import json
from pathlib import Path

import pytest

from db_helpers import new_mock_db
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder as Builder
from src.database.possession_stats_helpers import exact_season_stats, possession_projection
from src.pbp.game_derived import derive_game_fields
from src.services.pbp_extended_stats_service import PBPExtendedStatsService, clear_cache
from src.services.pbp_situation_stats_service import PBPSituationStatsService

FIXTURE = Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz"
HOME_EXT, AWAY_EXT = "39675", "40288"


@pytest.fixture(scope="module")
def game():
    return json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))


def renumbered(game, uuid, home, away):
    """The same game as another match of the season: new uuid and new (per-game) intern ids, the extern ones are the stable identity."""
    other = copy.deepcopy(game)
    mapping = {str(t["teamIdIntern"]): str(new) for t, new in zip(game["stats"]["teams"], (home, away))}
    for move in other["moves"]:
        if str(move.get("idTeam")) in mapping:                       # the end of a period has team 0
            move["idTeam"] = int(mapping[str(move["idTeam"])])
    for team, new in zip(other["stats"]["teams"], (home, away)):
        team["teamIdIntern"] = new
    other["uuid"], other["_id"] = uuid, uuid
    return other


@pytest.fixture(scope="module")
def season(game):
    docs = [{**game, "_id": game["uuid"]}, renumbered(game, "g2", 50001, 50002)]
    for doc in docs:
        doc["DERIVED"] = derive_game_fields(doc)
    return docs


class FakeDb:
    def __init__(self, col):
        self.repository = type("R", (), {"connection": type("C", (), {"get_collection": staticmethod(lambda name: col)})()})()


def collection(docs):
    col = new_mock_db(f"s{id(docs)}")["FBCYL_X"]
    col.insert_many(copy.deepcopy(docs))
    return col


def test_the_derived_figures_say_which_team_is_which_across_games(season):
    ids = [[t["id"] for t in d["DERIVED"]["TEAM"]] for d in season]
    ext = [[t["ext_id"] for t in d["DERIVED"]["TEAM"]] for d in season]
    assert ids[0] != ids[1] and ext[0] == ext[1] == [HOME_EXT, AWAY_EXT]


# --- the four routes that read DERIVED ------------------------------------------------------------------------------------------

def test_points_by_origin_groups_by_the_stable_team_and_takes_the_name_from_the_fbcyl_teams(season):
    clear_cache()
    rows = {r["team_id"]: r for r in PBPExtendedStatsService(FakeDb(collection(season))).get_points_by_origin("FBCYL_PBO")}
    assert set(rows) == {HOME_EXT, AWAY_EXT}
    home = rows[HOME_EXT]
    assert home["games"] == 2 and home["games_unreliable"] == 0 and home["team_name"] == season[0]["stats"]["teams"][0]["name"]
    assert home["pts_bench"] == 2 * season[0]["DERIVED"]["TEAM"][0]["pts_bench"]
    assert home["games_paint"] == 0 and home["pts_paint"] is None             # no shot chart in FBCYL
    assert home["opp_pts_bench"] == 2 * season[0]["DERIVED"]["TEAM"][1]["pts_bench"]      # what the rival bench scored in the two games


def test_by_period_situations_and_timeouts_have_fbcyl_rows_too(season):
    clear_cache()
    db = FakeDb(collection(season))
    periods = {r["team_id"]: r for r in PBPExtendedStatsService(db).get_by_period("FBCYL_PER")}
    assert set(periods) == {HOME_EXT, AWAY_EXT} and sorted(periods[HOME_EXT]["periods"]) == ["1", "2", "3", "4"]
    assert periods[HOME_EXT]["games"] == 2
    service = PBPSituationStatsService(db)
    situations = {r["team_id"]: r for r in service.get_situations("FBCYL_SIT")}
    assert set(situations) == {HOME_EXT, AWAY_EXT} and situations[HOME_EXT]["games"] == 2
    assert {r["team_id"] for r in service.get_timeout_effects("FBCYL_TO")} == {HOME_EXT, AWAY_EXT}


def test_an_unreliable_game_is_left_out_and_counted(season):
    clear_cache()
    docs = copy.deepcopy(season)
    for team in docs[1]["DERIVED"]["TEAM"]:
        team["reliable"] = False
    row = next(r for r in PBPExtendedStatsService(FakeDb(collection(docs))).get_points_by_origin("FBCYL_UNREL") if r["team_id"] == HOME_EXT)
    assert (row["games"], row["games_unreliable"]) == (1, 1)


def test_feb_collections_still_group_by_their_team_id_and_header_name(feb_game_doc):
    clear_cache()
    doc = {**feb_game_doc, "_id": 1, "DERIVED": derive_game_fields(feb_game_doc)}
    rows = PBPExtendedStatsService(FakeDb(collection([doc]))).get_points_by_origin("FEB_X")
    assert {r["team_id"] for r in rows} == {str(t["id"]) for t in feb_game_doc["BOXSCORE"]["TEAM"]}
    assert all(r["team_name"] for r in rows)


# --- the season team pipeline of FBCYL ------------------------------------------------------------------------------------------------

def test_the_season_possessions_are_the_exact_count_of_each_game(season):
    out = {str(r["team_id"]): r for r in collection(season).aggregate(Builder.build_team_stats_pipeline())}
    exact = sum(d["DERIVED"]["TEAM"][0]["possessions"] for d in season)
    assert out[HOME_EXT]["total_possessions"] == pytest.approx(exact)
    assert out[HOME_EXT]["opponent_possessions"] == pytest.approx(sum(d["DERIVED"]["TEAM"][1]["possessions"] for d in season))
    assert out[HOME_EXT]["possessions_per_game"] == pytest.approx(exact / 2)


def test_a_game_without_derived_uses_the_box_estimate_and_a_season_can_mix_both(season):
    plain = copy.deepcopy(season[1])
    plain.pop("DERIVED")
    out = {str(r["team_id"]): r for r in collection([season[0], plain]).aggregate(Builder.build_team_stats_pipeline())}
    box = season[0]["stats"]["teams"][0]["data"]
    estimate = box["shotsOfTwoAttempted"] + box["shotsOfThreeAttempted"] + 0.44 * box["shotsOfOneAttempted"] + box["lost"] - box["offensiveRebound"]
    assert out[HOME_EXT]["total_possessions"] == pytest.approx(season[0]["DERIVED"]["TEAM"][0]["possessions"] + estimate)


# --- the single-team route ------------------------------------------------------------------------------------------------------------

def test_exact_season_stats_finds_the_team_by_its_extern_id_in_every_game(season):
    stats = exact_season_stats(season, HOME_EXT)
    assert stats["games"] == 2 and stats["games_by_source"] == {"pbp": 2}
    assert stats["possessions_per_game"] == pytest.approx(83.0)
    assert exact_season_stats(season, "00000") is None


def test_the_possession_projection_keeps_what_the_tracker_and_the_box_need():
    projection = possession_projection(True)
    assert {"moves.move", "moves.period", "moves.min", "moves.sec", "moves.idTeam", "moves.actorId", "stats.teams.data",
            "stats.teams.teamIdIntern", "stats.teams.teamIdExtern", "stats.periodDurationList"} <= set(projection)
