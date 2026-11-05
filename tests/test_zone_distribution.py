"""The zone counts of every team and of every player of a competition, the reference of the rating of a zone (issue #760).

One pass over the games gives each shot with its team and its player (the same rows that ``export_shots`` publishes for the web: ``owned_shots`` is shared, so the server and the
browser cannot count different shots). What each entity shot must be what the existing endpoints give when filtered by that team or that player.
"""
import sys
from pathlib import Path

import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402

from src.local_data.shots_export import export_shots  # noqa: E402
from src.shotcharts.fbcyl_zones import stream_zone_counts_fbcyl  # noqa: E402
from src.shotcharts.feb_zones import ZONE_META, aggregate_zones, stream_zone_counts_feb  # noqa: E402
from src.shotcharts.owned_shots import iter_owned_shots  # noqa: E402
from src.shotcharts.zone_distribution import zone_counts_by_owner  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


def _collection(name, docs):
    col = mongomock.MongoClient()["v"][name]
    if docs:
        col.insert_many(docs)
    return col


@pytest.fixture(scope="module")
def feb():
    return _collection(FEB, games.build_games())


@pytest.fixture(scope="module")
def fbcyl():
    return _collection(FBCYL, fbcyl_games.build_games())


@pytest.mark.parametrize("name, fixture", [(FEB, "feb"), (FBCYL, "fbcyl")])
def test_the_owned_shots_are_the_rows_the_web_gets(name, fixture, request):
    col = request.getfixturevalue(fixture)
    assert [list(row) for row in iter_owned_shots(col, name.startswith("FBCYL"))] == export_shots(col, name)["shots"]


@pytest.mark.parametrize("name, fixture, stream", [(FEB, "feb", stream_zone_counts_feb), (FBCYL, "fbcyl", stream_zone_counts_fbcyl)])
def test_each_team_has_what_the_team_filter_of_the_endpoint_counts(name, fixture, stream, request):
    col = request.getfixturevalue(fixture)
    by_team = zone_counts_by_owner(col, name, "team")
    assert len(by_team) >= 2
    for team_id, counts in by_team.items():
        assert counts == stream(col, team_id=team_id, player_filter=None), team_id


@pytest.mark.parametrize("name, fixture, stream", [(FEB, "feb", stream_zone_counts_feb), (FBCYL, "fbcyl", stream_zone_counts_fbcyl)])
def test_each_player_has_what_the_player_filter_of_the_endpoint_counts(name, fixture, stream, request):
    col = request.getfixturevalue(fixture)
    by_player = zone_counts_by_owner(col, name, "player")
    assert len(by_player) >= 2
    for player_id, counts in by_player.items():
        assert counts == stream(col, team_id=None, player_filter=player_id), player_id


@pytest.mark.parametrize("name, fixture, stream", [(FEB, "feb", stream_zone_counts_feb), (FBCYL, "fbcyl", stream_zone_counts_fbcyl)])
def test_the_teams_add_up_to_the_competition(name, fixture, stream, request):
    col = request.getfixturevalue(fixture)
    league = aggregate_zones(stream(col, team_id=None, player_filter=None))
    teams = list(zone_counts_by_owner(col, name, "team").values())
    for zone in league:
        assert sum(t[zone["zone"]]["fga"] for t in teams) == zone["fga"] and sum(t[zone["zone"]]["fgm"] for t in teams) == zone["fgm"]


def test_every_zone_is_in_every_table_even_without_shots(feb):
    for counts in zone_counts_by_owner(feb, FEB, "team").values():
        assert set(counts) == set(ZONE_META)


def test_a_shot_without_player_counts_for_its_team_and_for_no_player():
    docs = games.build_games()
    col = _collection(FEB + "_orphans", docs)
    rows = list(iter_owned_shots(col, False))
    orphans = [r for r in rows if r[1] is None]
    teams = zone_counts_by_owner(col, FEB, "team")
    players = zone_counts_by_owner(col, FEB, "player")
    total = lambda tables: sum(c[z]["fga"] for c in tables.values() for z in c)  # noqa: E731
    assert total(teams) == len(rows) and total(players) == len(rows) - len(orphans)
    assert None not in players and "None" not in players


def test_nothing_is_rated_against_a_competition_without_shots():
    col = _collection(FEB + "_empty", [])
    assert zone_counts_by_owner(col, FEB, "team") == {} and zone_counts_by_owner(col, FEB, "player") == {}
