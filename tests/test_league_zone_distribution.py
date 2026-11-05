"""The reference of the server charts' zone colours (issue #765): how each team, or each player, of the competition shot in the analyzer's own zones.

The same rule as the web (#760): a zone is above/below the upper/lower quartile of the entities, weighted by their attempts. The counts are taken in one pass over the shots with the
analyzer's classification, so the colour of a chart and the number written on it come from the same zones.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
import pytest  # noqa: E402
from db_helpers import new_mock_db  # noqa: E402

from src.shotcharts.fbcyl_zones import iter_shot_dicts_fbcyl  # noqa: E402
from src.shotcharts.feb_zones import iter_shots_feb  # noqa: E402
from src.shotcharts.league_zones import league_zone_distribution  # noqa: E402
from src.shotcharts.zone_analysis import ZoneAnalyzer  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


def _collection(name, docs):
    col = new_mock_db()[name]
    if docs:
        col.insert_many(docs)
    return col


@pytest.fixture(scope="module")
def az():
    return ZoneAnalyzer()


@pytest.fixture(scope="module")
def feb():
    return _collection(FEB, games.build_games())


@pytest.fixture(scope="module")
def fbcyl():
    return _collection(FBCYL, fbcyl_games.build_games())


def _made_total(stats):
    return {zone: (s["made"], s["total"]) for zone, s in stats.items()}


@pytest.mark.parametrize("fixture, name, stream", [("feb", FEB, iter_shots_feb), ("fbcyl", FBCYL, iter_shot_dicts_fbcyl)])
def test_each_team_has_what_the_chart_of_that_team_counts(fixture, name, stream, az, request):
    """The entity of a team is exactly the zone table the analyzer builds from that team's shots (FEB and FBCYL)."""
    col = request.getfixturevalue(fixture)
    entities = league_zone_distribution(az, col, fbcyl=name.startswith("FBCYL"), by="team")
    assert entities and len(entities) >= 2
    team_ids = sorted({row["team_id"] for row in _owned(col, name)})
    expected = sorted(sorted(_made_total(az.analyze_zone_performance(stream(col, team_id=t, player_filter=None))["zone_stats"]).items()) for t in team_ids)
    assert sorted(sorted(_made_total(e).items()) for e in entities) == expected


def _owned(col, name):
    from src.shotcharts.owned_shots import iter_owned_shots

    return [{"team_id": t, "player_id": p} for t, p, *_ in iter_owned_shots(col, name.startswith("FBCYL"))]


@pytest.mark.parametrize("fixture, name", [("feb", FEB), ("fbcyl", FBCYL)])
def test_the_entities_add_up_to_every_shot_of_the_competition(fixture, name, az, request):
    col = request.getfixturevalue(fixture)
    fbcyl_flag = name.startswith("FBCYL")
    total = sum(1 for _ in _owned(col, name))
    by_team = league_zone_distribution(az, col, fbcyl=fbcyl_flag, by="team")
    assert sum(z["total"] for e in by_team for z in e.values()) == total


@pytest.mark.parametrize("fixture, name", [("feb", FEB), ("fbcyl", FBCYL)])
def test_by_player_counts_only_shots_with_a_known_player(fixture, name, az, request):
    col = request.getfixturevalue(fixture)
    rows = _owned(col, name)
    named = sum(1 for r in rows if r["player_id"])
    by_player = league_zone_distribution(az, col, fbcyl=name.startswith("FBCYL"), by="player")
    assert sum(z["total"] for e in by_player for z in e.values()) == named
    assert len(by_player) == len({r["player_id"] for r in rows if r["player_id"]})


def test_every_zone_of_the_analyzer_is_in_every_entity(az, feb):
    for entity in league_zone_distribution(az, feb, by="team"):
        assert set(entity) == set(az.zones.zones)


def test_a_failure_or_an_empty_competition_gives_none_so_the_chart_keeps_its_static_colours(az):
    from unittest.mock import MagicMock

    broken = MagicMock()
    broken.find.side_effect = RuntimeError("db down")
    assert league_zone_distribution(az, broken, by="team") is None
    assert league_zone_distribution(az, _collection(FEB + "_empty", []), by="team") is None


def test_the_shots_are_streamed_not_held_in_a_list(az, monkeypatch):
    """A league has tens of thousands of shots: only the counts of each entity may stay in memory (512 MB server)."""
    seen = {}

    def rows(collection, fbcyl):
        seen["called"] = True
        return ((("t1", "p1", 7.5, 1.2, i % 2 == 0, "restricted_area") for i in range(30)))

    monkeypatch.setattr("src.shotcharts.league_zones.iter_owned_shots", rows)
    entities = league_zone_distribution(az, object(), by="team")
    assert seen["called"] and len(entities) == 1 and sum(z["total"] for z in entities[0].values()) == 30
