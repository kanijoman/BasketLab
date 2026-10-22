"""A package uses every game of the two teams, not just the ones of the match's collection (issue #456).

Found with the Copa de España (2026-10-21): in a knockout tie each team has 0-1 games in its collection, and a rival of another division
(Alimerka Oviedo, 1ª FEB) has none, so the package carried no data. The games of both teams in the other competitions and phases of the
season now feed THEIR tables; the league baselines (league rates, spread, zones) still come from the match's own collection, as before.
"""
import copy
import json
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.live_prep.db_source import build_package_from_db
from src.live_prep.game_sources import source_collections
from src.live_prep.round_packages import build_round_packages_from_db

OWN, RIVAL = "982047", "981204"
COPA = "COPA_ESPAÑA_2026_2027_Play-offs_1_16_Final"
GROUP = "COPA_ESPAÑA_2026_2027_FASE_DE_GRUPOS_A"
SEGUNDA = "SEGUNDA_FEB_2026_2027_Liga_Regular_A"
PRIMERA = "PRIMERA_FEB_2026_2027_Liga_Regular_Único"
OLD = "SEGUNDA_FEB_2025_2026_Liga_Regular_A"
FBCYL = "FBCYL_1_FASE-GRUPO_A-1_2026_"


def game(doc, home, away, code):
    """The sample game played by other teams (every id of the two teams replaced; the players stay the same)."""
    text = json.dumps(doc).replace(f'"{OWN}"', "@H@").replace(f'"{RIVAL}"', "@A@").replace("@H@", f'"{home}"').replace("@A@", f'"{away}"')
    out = json.loads(text)
    out["_id"] = code
    return out


class Handler:
    """What the sources use of a MongoDBHandler, over mongomock."""

    def __init__(self, collections):
        self.db = new_mock_db()
        for name, docs in collections.items():
            if docs:
                self.db[name].insert_many([copy.deepcopy(d) for d in docs])
        self.repository = MagicMock()
        self.repository.connection.get_collection.side_effect = lambda name: self.db[name]
        self.repository.connection.get_database.return_value = self.db


@pytest.fixture
def world(feb_game_doc):
    g = lambda home, away, code: game(feb_game_doc, home, away, code)
    return {
        COPA: [g(OWN, RIVAL, 1)],
        GROUP: [g(OWN, "333", 2), g("444", RIVAL, 3)],
        SEGUNDA: [g(OWN, "555", 4), g("555", "666", 5)],
        PRIMERA: [g(RIVAL, "777", 6)],
        OLD: [g(OWN, "555", 7)],
        FBCYL: [g(OWN, "555", 8)],
    }


def names(sources):
    return [name for name, _ in sources]


class TestSourceCollections:
    def test_the_own_collection_comes_first_and_is_the_only_league_source_of_a_regular_group(self, world):
        sources = source_collections(Handler(world), SEGUNDA, [OWN, RIVAL])
        assert sources[0] == (SEGUNDA, True) and [lg for _, lg in sources[1:]] == [False] * (len(sources) - 1)

    def test_other_collections_of_the_season_with_a_game_of_the_teams_are_sources(self, world):
        assert set(names(source_collections(Handler(world), COPA, [OWN, RIVAL]))) == {COPA, GROUP, SEGUNDA, PRIMERA}

    def test_a_collection_without_games_of_the_teams_is_not_read(self, world):
        world[SEGUNDA] = [world[SEGUNDA][1]]   # only 555 - 666
        assert SEGUNDA not in names(source_collections(Handler(world), COPA, [OWN, RIVAL]))

    def test_other_seasons_and_fbcyl_are_left_out(self, world):
        found = names(source_collections(Handler(world), COPA, [OWN, RIVAL]))
        assert OLD not in found and FBCYL not in found

    def test_internal_collections_are_left_out(self, world):
        world["COLLECTION_META"] = [{"_id": "x", "HEADER": {"TEAM": [{"id": OWN}]}}]
        assert "COLLECTION_META" not in names(source_collections(Handler(world), COPA, [OWN, RIVAL]))

    def test_a_database_that_cannot_list_its_collections_gives_the_own_collection_only(self):
        handler = MagicMock()
        handler.repository.connection.get_database.return_value.list_collection_names.side_effect = RuntimeError("down")
        assert source_collections(handler, COPA, [OWN, RIVAL]) == [(COPA, True)]


class TestPackages:
    def test_a_team_without_games_in_the_collection_gets_its_season_from_the_other_competitions(self, world):
        """The Leonesa-Oviedo case: the rival's only games are in another division."""
        world[COPA] = []
        package = build_package_from_db(Handler(world), COPA, OWN, RIVAL, "2026")
        assert package.baselines["sample_games"]["own"] == 2 and package.baselines["sample_games"]["rival"] == 2
        assert package.tables["players"] and package.tables["rival_players"]

    def test_a_game_that_is_in_two_collections_counts_once(self, world):
        world[SEGUNDA] = [world[SEGUNDA][0]]
        world[GROUP] = [world[SEGUNDA][0]]
        package = build_package_from_db(Handler(world), COPA, OWN, RIVAL, "2026")
        assert package.baselines["sample_games"]["own"] == 2   # the Copa game + the shared one

    def test_the_league_baselines_of_a_regular_collection_come_only_from_it(self, world):
        """A group of a regular league is its own league: the other division and the other group are not part of its baselines."""
        package = build_package_from_db(Handler(world), SEGUNDA, OWN, "555", "2026")
        alone = build_package_from_db(Handler({SEGUNDA: world[SEGUNDA]}), SEGUNDA, OWN, "555", "2026")
        assert package.baselines["sample_games"]["league"] == 2
        assert package.baselines["league_rates"] == alone.baselines["league_rates"]
        assert package.tables["zones"]["league"] == alone.tables["zones"]["league"]

    def test_a_season_with_one_collection_gives_the_same_package_as_before_regression(self, world):
        """No other source: nothing changes (the single-collection behaviour of every package published so far)."""
        only = {COPA: world[COPA] + world[GROUP]}
        new = build_package_from_db(Handler(only), COPA, OWN, RIVAL, "2026")
        from src.live_prep.package_builder import build_package
        old = build_package(iter(only[COPA]), COPA, "2026", OWN, RIVAL, created_at=new.created_at)
        assert new.baselines == old.baselines and new.tables == old.tables

    def test_the_games_are_read_one_at_a_time_with_a_projection(self, world):
        handler = Handler(world)
        calls = []
        real = handler.db.__getitem__
        handler.repository.connection.get_collection.side_effect = lambda name: calls.append(name) or real(name)
        build_package_from_db(handler, COPA, OWN, RIVAL, "2026")
        assert COPA in calls and SEGUNDA in calls


class TestRounds:
    def match(self, home, away):
        return {"code": "9", "start": "2026-10-21T20:00", "round": 1, "home": {"id": home, "name": "H"}, "away": {"id": away, "name": "A"}}

    def test_a_round_bundle_uses_the_games_of_all_competitions_for_every_team(self, world):
        world[COPA] = []
        built = build_round_packages_from_db(Handler(world), COPA, [self.match(OWN, RIVAL)], season="2026")
        package = built[0]["package"]
        assert package.baselines["sample_games"]["own"] == 2 and package.baselines["sample_games"]["rival"] == 2

    def test_games_of_other_competitions_feed_the_teams_not_the_league(self, world):
        built = build_round_packages_from_db(Handler(world), SEGUNDA, [self.match(OWN, "555")], season="2026")
        assert built[0]["package"].baselines["sample_games"]["league"] == 2


class TestLeagueOfAPhase:
    """Issue #464: a knockout tie has 1 game in its own collection (the 1/16 of the Copa has 16): the league baselines of a phase come from the whole competition."""

    def test_the_other_phases_of_the_competition_are_league_sources_of_a_knockout(self, world):
        sources = dict(source_collections(Handler(world), COPA, [OWN, RIVAL]))
        assert sources[COPA] is True and sources[GROUP] is True
        assert sources[SEGUNDA] is False and sources[PRIMERA] is False      # other competitions: their games feed the teams, not the league

    def test_a_phase_without_games_of_the_teams_still_gives_its_league(self, world):
        world[GROUP] = [world[GROUP][0]]
        other = "COPA_ESPAÑA_2026_2027_FASE_DE_GRUPOS_B"
        world[other] = [game(world[GROUP][0], "801", "802", 90)]
        assert dict(source_collections(Handler(world), COPA, [OWN, RIVAL]))[other] is True

    def test_the_league_of_a_knockout_counts_the_group_stage(self, world):
        package = build_package_from_db(Handler(world), COPA, OWN, RIVAL, "2026")
        assert package.baselines["sample_games"]["league"] == 3       # the tie + the two games of the group stage
        assert package.baselines["sample_games"]["own"] == 3          # all the games of the team, as before

    def test_the_group_stage_is_a_league_for_its_own_package_too_regression(self, world):
        """The groups of a cup are one pool of teams: from a group, the other phases of the cup do not become league (only a knockout pools them)."""
        sources = dict(source_collections(Handler(world), GROUP, [OWN, RIVAL]))
        assert sources[GROUP] is True and sources[COPA] is False

    def test_the_two_groups_of_a_regular_league_stay_two_leagues(self, world):
        other = "SEGUNDA_FEB_2026_2027_Liga_Regular_B"
        world[other] = [game(world[SEGUNDA][0], OWN, "888", 91)]
        assert dict(source_collections(Handler(world), SEGUNDA, [OWN, RIVAL]))[other] is False

    def test_the_playoffs_of_a_regular_league_pool_its_groups(self, world):
        playoffs = "SEGUNDA_FEB_2026_2027_Eliminatorias_de_Ascenso"
        world[playoffs] = [game(world[SEGUNDA][0], OWN, "999", 92)]
        sources = dict(source_collections(Handler(world), playoffs, [OWN, "999"]))
        assert sources[playoffs] is True and sources[SEGUNDA] is True

    def test_a_database_that_fails_reading_the_phase_keeps_the_own_collection(self):
        handler = MagicMock()
        handler.repository.connection.get_database.return_value.list_collection_names.side_effect = RuntimeError("down")
        assert source_collections(handler, COPA, [OWN]) == [(COPA, True)]
