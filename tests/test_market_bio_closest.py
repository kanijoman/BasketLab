"""The bio by the CLOSEST season (#996): height, position and nationality change with the years (a cadet grows, plays elsewhere, uses another passport), so for a row of a season the
value comes from the nearest season whatever the source says it (FEB roster or a linked external player); how far it is does not matter unless something is closer. A tie goes to
the same team, then to the source of higher priority, then to the later season. The date of birth never changes: a different one is flagged (``bio_conflict``), never averaged. All
the different nationalities are reported (``nationalities``), ``nationality`` being the first. Built from the same rows ``attach_bio`` gets in production."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market.external_bio import external_bio  # noqa: E402
from src.market.season_rows import attach_bio  # noqa: E402


def _row(person="feb:1", team="10"):
    return {"person_id": person, "team_id": team, "league": "feb", "name": "A. B C"}


def _roster(season="2025", team="10", **over):
    return {"person_id": "feb:1", "season": season, "team_id": team, "name": "ANA BEATRIZ CASTRO", "birth": "2004-05-06", "height": None, "position": None, "nationality": None, **over}


def _ext(season, **over):
    return {"source": "fiba", "season": season, "birth": None, "height": None, "nationality": None, **over}


def _one(roster, external, season="2025"):
    (row,) = attach_bio([_row()], roster, season, external={"feb:1": external} if external else None)
    return row


class TestClosestSeason:
    def test_a_more_recent_external_value_beats_an_older_feb_one(self):
        row = _one([_roster("2023", height=170)], [_ext("2025", height="185")])
        assert row["height"] == 185 and row["bio_from"]["height"] == "fiba:2025"

    def test_an_older_external_value_loses_to_a_closer_feb_one(self):
        row = _one([_roster("2025", team="11", height=181)], [_ext("2021", height="170")])
        assert row["height"] == 181 and row["bio_from"]["height"] == "2025:11"

    def test_far_data_is_used_when_nothing_is_closer(self):
        row = _one([], [_ext("2015", height="170")], season="2025")
        assert row["height"] == 170 and row["bio_from"]["height"] == "fiba:2015"

    def test_a_tie_goes_to_the_same_team_then_the_source_priority_then_the_later_season(self):
        same_team = _one([_roster("2024", team="10", height=170), _roster("2026", team="11", height=190)], [])
        assert same_team["height"] == 170
        priority = _one([_roster("2024", team="11", height=170)], [_ext("2024", height="180")])
        assert priority["height"] == 170                                                    # FEB before FIBA at the same distance
        later = _one([], [_ext("2024", height="170"), _ext("2026", height="180")])
        assert later["height"] == 180

    def test_the_own_roster_of_the_season_and_team_still_wins_and_leaves_no_trace(self):
        row = _one([_roster("2025", height=178)], [_ext("2025", height="190")])
        assert row["height"] == 178 and row["bio_from"] == {}

    def test_position_is_closest_too(self):
        row = _one([_roster("2023", position="Base")], [_ext("2025", position="Escolta")])
        assert row["position"] == "Escolta"


class TestBirth:
    def test_birth_is_immutable_and_a_different_date_is_flagged_not_averaged(self):
        row = _one([_roster("2025", birth="2004-05-06")], [_ext("2025", birth="2004-05-07")])
        assert row["birth"] == "2004-05-06" and row["bio_conflict"] == ["birth"]

    def test_the_same_date_is_no_conflict_and_no_candidate_says_nothing(self):
        assert _one([_roster()], [_ext("2025", birth="2004-05-06")])["bio_conflict"] == []
        assert attach_bio([_row("fbcyl:u1")], [], "2025")[0]["bio_conflict"] == []


class TestNationalities:
    def test_every_different_passport_is_reported_and_the_first_is_the_closest(self):
        row = _one([_roster("2025", nationality="ESPAÑA")], [_ext("2023", nationality="SLO"), _ext("2022", nationality="ESP")])
        assert row["nationalities"] == ["ESPAÑA", "ESLOVENIA"] and row["nationality"] == "ESPAÑA"

    def test_the_same_country_written_two_ways_is_one_nationality_and_never_a_conflict(self):
        row = _one([_roster("2025", nationality="ESPAÑA")], [_ext("2025", nationality="ESP")])
        assert row["nationalities"] == ["ESPAÑA"] and row["bio_conflict"] == []

    def test_a_closer_passport_comes_first_even_from_another_source(self):
        row = _one([_roster("2020", nationality="ESPAÑA")], [_ext("2025", nationality="SLO")])
        assert row["nationality"] == "ESLOVENIA" and row["nationalities"] == ["ESLOVENIA", "ESPAÑA"]

    def test_nobody_says_it_is_empty_not_a_guess(self):
        row = _one([_roster()], [])
        assert row["nationality"] is None and row["nationalities"] == []


class TestExternalBioPerSeason:
    def _game(self, season, **p):
        return {"_season": season, "BOXSCORE": {"TEAM": [{"PLAYER": [dict({"id": "fiba:1", "birth": "2008-05-05", "height": "190", "nationality": "ESP"}, **p)]}]}}

    def test_one_candidate_per_season_with_what_that_season_says(self):
        found = external_bio([self._game("2023", height="185"), self._game("2025", height="190", nationality="SLO")], {"fiba:1": "feb:1"})["feb:1"]
        assert [(c["season"], c["height"], c["nationality"]) for c in found] == [("2023", "185", "ESP"), ("2025", "190", "SLO")]

    def test_the_answer_does_not_depend_on_the_order_of_the_games(self):
        games = [self._game(s, height=h) for s, h in (("2023", "185"), ("2025", "190"), ("2025", "191"), ("2024", "188"))]
        expected = external_bio(games, {"fiba:1": "feb:1"})
        random.Random(7).shuffle(games)
        assert external_bio(games, {"fiba:1": "feb:1"}) == expected
