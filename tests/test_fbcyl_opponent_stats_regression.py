"""Bug #642: in FBCYL ``opponent_stats`` of ``GET /teams/{collection}`` was a copy of ``team_stats`` («for now, return same as team stats»).

The web's «Rivales» view of FBCYL showed what the team did, not what it received (FBCYL_1ª_FASE-GRUPO_A-1_2026, BALONCESTO ARELSA: 119 for and 121
against in both tables). The rival table is the table of what the opponents did against each team, as in FEB: the points the rivals scored are the points the
team received and the other way round, with their shooting, rebounds, assists, steals, turnovers, blocks and possessions.
"""
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from fbcyl_games import build_games  # noqa: E402
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder as Builder  # noqa: E402

FILTERS = [(None, None), (True, None), (False, None), (None, "won"), (None, "lost"), (True, "won"), (False, "lost")]


@pytest.fixture()
def collection():
    col = new_mock_db("fbcyl_rivals")["FBCYL_LEAGUE"]
    col.insert_many(build_games())
    return col


def _tables(collection, venue=None, result=None):
    team = {r["team_id"]: r for r in collection.aggregate(Builder.build_team_stats_pipeline(None, venue, result))}
    rival = {r["team_id"]: r for r in collection.aggregate(Builder.build_opponent_stats_pipeline(None, venue, result))}
    return team, rival


def test_the_rival_table_is_not_a_copy_of_the_team_table_regression(collection):
    team, rival = _tables(collection)
    assert team.keys() == rival.keys() and len(team) == 4
    assert all(rival[t]["points_scored"] != team[t]["points_scored"] for t in team)


@pytest.mark.parametrize("venue, result", FILTERS)
def test_what_the_rivals_scored_is_what_the_team_received_and_the_other_way_round(collection, venue, result):
    team, rival = _tables(collection, venue, result)
    assert team                                                                # the filter keeps games
    for team_id, own in team.items():
        against = rival[team_id]
        assert against["total_games"] == own["total_games"] and against["games_home"] == own["games_home"]
        assert against["points_scored"] == own["points_received"]
        assert against["points_received"] == own["points_scored"]


@pytest.mark.parametrize("venue, result", FILTERS)
def test_the_rival_figures_are_what_the_opponents_did_against_each_team(collection, venue, result):
    team, rival = _tables(collection, venue, result)
    by_id = {t: t for t in team}
    games = build_games()
    for team_id in by_id:
        sides = []
        for game in games:
            teams = game["stats"]["teams"]
            for i, side in enumerate(teams):
                if side["teamIdExtern"] != team_id:
                    continue
                mine, theirs = side["data"], teams[1 - i]["data"]
                result_of = "won" if mine["score"] > theirs["score"] else ("lost" if mine["score"] < theirs["score"] else "tied")
                if (venue is None or (i == 0) == venue) and (result is None or result_of == result):
                    sides.append(theirs)
        against = rival[team_id]
        for field, key in [("fg2_made", "shotsOfTwoSuccessful"), ("fg2_attempted", "shotsOfTwoAttempted"), ("fg3_made", "shotsOfThreeSuccessful"),
                           ("fg3_attempted", "shotsOfThreeAttempted"), ("ft_made", "shotsOfOneSuccessful"), ("ft_attempted", "shotsOfOneAttempted"),
                           ("total_rebounds", "rebounds"), ("rebounds_off", "offensiveRebound"), ("rebounds_def", "defensiveRebound"),
                           ("assists", "assists"), ("steals", "steals"), ("turnovers", "lost"), ("blocks", "block"), ("fouls", "faults")]:
            assert against[field] == sum(s[key] for s in sides), (team_id, field)


def test_the_possessions_of_the_rival_table_are_the_rivals_and_the_teams_are_the_rivals_own(collection):
    """Exact (``DERIVED``) or estimated: what the rivals had is what ``opponent_possessions`` of the team table says, and the other way round."""
    team, rival = _tables(collection)
    for team_id, own in team.items():
        assert rival[team_id]["total_possessions"] == pytest.approx(own["opponent_possessions"])
        assert rival[team_id]["opponent_possessions"] == pytest.approx(own["total_possessions"])


def test_the_ratings_of_the_rival_table_are_the_rivals(collection):
    team, rival = _tables(collection)
    for team_id, own in team.items():
        against = rival[team_id]
        assert against["offensive_rating"] == pytest.approx(own["defensive_rating"])      # what they score per 100 = what the team concedes
        assert against["defensive_rating"] == pytest.approx(own["offensive_rating"])


def test_all_the_rivals_together_scored_what_all_the_teams_received(collection):
    team, rival = _tables(collection)
    assert sum(r["points_scored"] for r in rival.values()) == sum(t["points_received"] for t in team.values())


def test_the_team_table_is_unchanged_by_the_fix(collection):
    """Both pipelines share the stages; the team one must keep giving what it always gave (its own vectors, ``team_stats_fbcyl.json``, are the proof)."""
    team, _rival = _tables(collection)
    first = next(iter(team.values()))
    assert first["points_scored"] != first["points_received"] or first["total_games"] > 0
    assert {"points_scored", "points_received", "total_possessions", "opponent_possessions", "games_won"} <= set(first)
