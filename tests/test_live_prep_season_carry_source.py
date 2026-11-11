"""Issue #825: the final ratings of the previous season, by teamCode, from the archive.

Read from the header of each game of the regular league of the same competition one season earlier (no replay of the play-by-play: the rating only needs the final score).
Whatever fails or is missing gives no carry: the package is what it was before.
"""
import copy

import pytest

from src.live_prep.package_builder import SeasonAccumulator
from src.live_prep.round_packages import build_round_packages_from_db
from src.live_prep.season_carry import carry_ratings, previous_collections
from test_live_prep_game_sources import OLD, OWN, RIVAL, SEGUNDA, Handler, game

CODE_OWN, CODE_RIVAL = "33002601", "08160700"


def played(doc, home, away, code, start):
    """A game of last season: ``home`` and ``away`` are ``(id, teamCode, points)``; the header lists the home team first."""
    out = copy.deepcopy(doc)
    out["_id"], out["HEADER"]["starttime"] = code, start
    for slot, (team_id, team_code, points) in zip(out["HEADER"]["TEAM"], (home, away)):
        slot.update({"id": team_id, "teamCode": team_code, "pts": str(points)})
    return out


@pytest.fixture
def world(feb_game_doc):
    """Last season (other ids): the team of ``CODE_OWN`` beat the team of ``CODE_RIVAL`` twice, once at each court. This season: the sample game under the new ids."""
    old = [played(feb_game_doc, ("11", CODE_OWN, 90), ("22", CODE_RIVAL, 60), 1, "05-10-2025 - 12:00"),
           played(feb_game_doc, ("22", CODE_RIVAL, 70), ("11", CODE_OWN, 80), 2, "05-11-2025 - 12:00")]
    return {OLD: old, SEGUNDA: [game(feb_game_doc, OWN, RIVAL, 10)]}


def test_the_collections_of_the_previous_season_are_the_regular_league_of_the_same_competition(world):
    handler = Handler({**world, "SEGUNDA_FEB_2024_2025_Liga_Regular_B": [], "SEGUNDA_FEB_2024_2025_Play-offs_1_16_Final": [{"_id": 1}], "PRIMERA_FEB_2025_2026_Liga_Regular_Único": [{"_id": 1}]})
    assert previous_collections(handler, SEGUNDA) == [OLD]


def test_the_final_ratings_are_by_team_code_and_the_winner_is_above_the_loser(world):
    ratings = carry_ratings(Handler(world), SEGUNDA)
    assert set(ratings) == {CODE_OWN, CODE_RIVAL} and ratings[CODE_OWN] > 0 > ratings[CODE_RIVAL]


@pytest.mark.parametrize("collection", ["FBCYL_1_FASE-GRUPO_A-1_2026_", "NOT_A_SEASON", "SEGUNDA_FEB_2020_2021_Liga_Regular_A"])
def test_no_previous_season_gives_no_carry(world, collection):
    assert carry_ratings(Handler({**world, collection: []}), collection) == {}


def test_a_failing_archive_gives_no_carry():
    class Broken:
        repository = None

    assert carry_ratings(Broken(), SEGUNDA) == {}


def test_the_package_of_the_season_starts_from_the_last_rating(world, feb_game_doc):
    """The round packages of the second game of the team already feel last season: the same team beats the same rival by the same margin, with and without the carry."""
    first = game(feb_game_doc, OWN, RIVAL, 10)
    first["HEADER"]["starttime"] = "04-10-2026 - 12:00"
    world[SEGUNDA] = [first]
    match = {"code": "m2", "start": None, "round": 2, "home": {"id": OWN, "name": "A"}, "away": {"id": RIVAL, "name": "B"}}
    carried = build_round_packages_from_db(Handler(world), SEGUNDA, [match], season="2026-2027")[0]["package"]
    plain = build_round_packages_from_db(Handler({SEGUNDA: world[SEGUNDA]}), SEGUNDA, [match], season="2026-2027")[0]["package"]
    gap = lambda package: package.baselines["net_rtg_prior"] if hasattr(package, "baselines") else package.tables["baselines"]["net_rtg_prior"]
    assert gap(carried) > gap(plain)


def test_the_package_of_one_pair_also_starts_from_the_last_rating(world):
    from src.live_prep.db_source import build_package_from_db

    carried = build_package_from_db(Handler(world), SEGUNDA, OWN, RIVAL, "2026-2027")
    plain = build_package_from_db(Handler({SEGUNDA: world[SEGUNDA]}), SEGUNDA, OWN, RIVAL, "2026-2027")
    assert carried.baselines["net_rtg_prior"] > plain.baselines["net_rtg_prior"]
