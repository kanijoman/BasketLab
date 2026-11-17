"""The canonical format of the external sources (#884, D0): ACB, FIBA and NCAA games become the FEB document so that no pipeline forks (the lesson of ``is_fbcyl``).

What the format adds to the FEB document: ``_league`` (the source), ids with the prefix of the source (``ncaa:401``: a FIBA id can never be taken for a FEB one) and the length of a game by source (NCAA men play
two halves of 20 minutes). The tests badge REAL FEB games (``tests/local_vectors/games.py``: overtime included) as each source and check what ``validate_game`` finds in them and in what is broken.
"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import games  # noqa: E402

from market_helpers import badged  # noqa: E402

from src.market.canonical import game_minutes, period_scheme, source_id, split_source_id, validate_game  # noqa: E402
from src.services.competition_catalogue import EXTERNAL_LEAGUES  # noqa: E402


@pytest.fixture(scope="module")
def feb_games():
    return games.build_games()


class TestSourceIds:
    @pytest.mark.parametrize("source", EXTERNAL_LEAGUES)
    def test_an_id_carries_its_source(self, source):
        assert source_id(source, 401) == f"{source}:401" == source_id(source, " 401 ")
        assert split_source_id(f"{source}:401") == (source, "401")

    def test_an_id_that_already_has_its_prefix_is_not_prefixed_twice(self):
        assert source_id("ncaa", "ncaa:401") == "ncaa:401"

    @pytest.mark.parametrize("bad", ["", "  ", None])
    def test_an_empty_id_is_refused(self, bad):
        with pytest.raises(ValueError):
            source_id("fiba", bad)

    def test_a_feb_id_or_a_foreign_prefix_is_not_an_external_id(self):
        assert split_source_id("2477341") is None                  # FEB ids are digits, never prefixed
        assert split_source_id("euroleague:7") is None
        assert split_source_id("ncaa:") is None
        with pytest.raises(ValueError):
            source_id("euroleague", "7")
        with pytest.raises(ValueError):
            source_id("ncaa", "acb:7")                              # another source's id is not rewritten into this one


class TestPeriodScheme:
    @pytest.mark.parametrize("source, gender, periods, minutes", [
        ("fiba", "M", 4, 10), ("fiba", "F", 4, 10), ("acb", "M", 4, 10),
        ("ncaa", "M", 2, 20),                                        # NCAA men: two halves
        ("ncaa", "F", 4, 10),                                        # NCAA women: four quarters
    ])
    def test_the_regulation_of_each_source(self, source, gender, periods, minutes):
        scheme = period_scheme(source, gender)
        assert (scheme.periods, scheme.minutes, scheme.overtime_minutes) == (periods, minutes, 5)

    @pytest.mark.parametrize("source, gender, played, total", [
        ("fiba", "M", 4, 40), ("fiba", "M", 5, 45), ("fiba", "F", 6, 50),
        ("ncaa", "M", 2, 40), ("ncaa", "M", 3, 45), ("ncaa", "F", 4, 40), ("ncaa", "F", 5, 45),
    ])
    def test_the_minutes_of_a_game_count_its_overtimes(self, source, gender, played, total):
        assert game_minutes(source, gender, played) == total

    def test_a_game_cannot_have_fewer_periods_than_its_regulation(self):
        with pytest.raises(ValueError):
            game_minutes("fiba", "M", 3)
        with pytest.raises(ValueError):
            game_minutes("ncaa", "M", 1)

    def test_an_unknown_source_or_gender_is_refused(self):
        with pytest.raises(ValueError):
            period_scheme("euroleague", "M")
        with pytest.raises(ValueError):
            period_scheme("ncaa", "X")


class TestValidateGame:
    @pytest.mark.parametrize("source", EXTERNAL_LEAGUES)
    def test_a_real_game_badged_as_a_source_is_valid(self, feb_games, source):
        assert validate_game(badged(feb_games[0], source), "M") == []

    def test_a_game_with_an_overtime_is_valid(self, feb_games):
        overtime = next(g for g in feb_games if len(g["HEADER"]["QUARTERS"]["QUARTER"]) > 4)
        assert validate_game(badged(overtime, "fiba"), "F") == []

    def test_a_raw_feb_game_is_not_canonical_and_says_what_lacks(self, feb_games):
        problems = validate_game(feb_games[0], "M")
        assert any("_league" in p for p in problems)

    def test_the_prefix_of_every_id_must_be_the_source_of_the_game(self, feb_games):
        doc = badged(feb_games[0], "ncaa")
        doc["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["id"] = "acb:77"
        doc["HEADER"]["TEAM"][1]["id"] = "5"                                # a FEB-looking id
        problems = validate_game(doc, "M")
        assert any("player" in p and "acb:77" in p for p in problems)
        assert any("team" in p and "'5'" in p for p in problems)

    def test_the_play_by_play_ids_carry_the_prefix_too_or_nothing_could_be_counted_for_a_team(self, feb_games):
        doc = badged(feb_games[0], "fiba")
        line = next(line for line in doc["PLAYBYPLAY"]["LINES"] if line.get("idTeam"))
        line["idTeam"] = line["idTeam"].split(":")[1]                          # a converter that forgot to prefix the team of the lines
        assert any("play-by-play" in p and "idTeam" in p for p in validate_game(doc, "M"))

    def test_the_teams_of_the_box_are_the_teams_of_the_header(self, feb_games):
        doc = badged(feb_games[0], "fiba")
        doc["BOXSCORE"]["TEAM"][1]["id"] = "fiba:999"
        assert any("box" in p and "fiba:999" in p for p in validate_game(doc, "M"))

    @pytest.mark.parametrize("path, value, word", [
        (("HEADER", "TEAM", 0, "pts"), None, "pts"),
        (("HEADER", "TEAM", 0, "pts"), "many", "pts"),
        (("HEADER", "TEAM", 1, "name"), "", "name"),
        (("HEADER", "starttime"), "2025-10-03T12:30", "starttime"),
        (("HEADER", "starttime"), None, "starttime"),
    ])
    def test_the_header_fields_the_pipelines_read_are_checked(self, feb_games, path, value, word):
        doc = badged(feb_games[0], "acb")
        node = doc
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        assert any(word in p for p in validate_game(doc, "M"))

    def test_ncaa_men_are_two_halves_and_a_game_cut_short_is_invalid(self, feb_games):
        halves = badged(feb_games[0], "ncaa")
        halves["HEADER"]["QUARTERS"]["QUARTER"] = halves["HEADER"]["QUARTERS"]["QUARTER"][:2]
        assert validate_game(halves, "M") == []                              # two periods are a whole game for NCAA men
        assert any("periods" in p for p in validate_game(halves, "F"))       # and half a game for NCAA women (four quarters)
        short = badged(feb_games[0], "fiba")
        short["HEADER"]["QUARTERS"]["QUARTER"] = short["HEADER"]["QUARTERS"]["QUARTER"][:3]
        assert any("periods" in p for p in validate_game(short, "M"))

    def test_the_gender_is_required(self, feb_games):
        with pytest.raises(ValueError):
            validate_game(badged(feb_games[0], "fiba"), "")

    def test_validating_does_not_change_the_game_and_gives_the_same_answer_twice(self, feb_games):
        doc = badged(feb_games[3], "ncaa")
        before = copy.deepcopy(doc)
        assert validate_game(doc, "M") == validate_game(doc, "M")
        assert doc == before
