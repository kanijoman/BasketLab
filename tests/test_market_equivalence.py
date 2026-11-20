"""The movements between competitions of the equivalence graph (#891, E1a of epic #872): who played in two competitions in consecutive seasons, and how well, from REAL rows of ``talent-data``.

``tests/fixtures/talent_rows_movers.json.gz`` (``scripts/capture_talent_movers.py``) has 1,369 rows of 257 persons of the senior leagues of FEB: those who moved between neighbouring levels (LF2 and LF Challenge,
LF Challenge and LF Endesa, Segunda and Primera FEB, Tercera and Segunda FEB, Tercera FEB and Liga U) and those who stayed in one. What E1a does is the table the estimator (E1b) reads: the observation of each
person in each competition and season (the percentiles of his eight axes as z), the movements between competitions in consecutive seasons and the stayers, with who is the same person, and nothing else: no model.
"""
import gzip
import json
import random
from pathlib import Path

import pytest

from src.market.equivalence import AXES, MIN_ELIGIBLE_AXES, edge_counts, movements, node_levels, node_of, observations, person_of, stayers, z_of

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "talent_rows_movers.json.gz"
DATA = json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))
COMPETITIONS, ROWS = DATA["competitions"], DATA["rows"]
REAL_OBSERVATIONS = observations(ROWS, COMPETITIONS)


def row(person="feb:1", comp="feb|lfchallenge|2025", pct=60.0, minutes=20000, linked_to=None, age=24, **over):
    return {"person_id": person, "linked_to": linked_to, "comp": comp, "eligible": True, "age": age, "minutes": minutes, "pct": {a: pct for a in AXES}, **over}


COMPS = {
    "feb|l.f.-2|2024": {"competition": "L.F.-2", "league": "feb", "gender": "F", "category": "senior", "level": 3, "season": "2024"},
    "feb|l.f.-2|2025": {"competition": "L.F.-2", "league": "feb", "gender": "F", "category": "senior", "level": 3, "season": "2025"},
    "feb|l.f.-2|2026": {"competition": "L.F.-2", "league": "feb", "gender": "F", "category": "senior", "level": 3, "season": "2026"},
    "feb|lfchallenge|2025": {"competition": "LF CHALLENGE", "league": "feb", "gender": "F", "category": "senior", "level": 2, "season": "2025"},
    "feb|lfchallenge|2024": {"competition": "LF CHALLENGE", "league": "feb", "gender": "F", "category": "senior", "level": 2, "season": "2024"},
    "feb|lfendesa|2026": {"competition": "LF ENDESA", "league": "feb", "gender": "F", "category": "senior", "level": 1, "season": "2026"},
    "feb|primerafeb|2025": {"competition": "PRIMERA FEB", "league": "feb", "gender": "M", "category": "senior", "level": 2, "season": "2025"},
    "feb|copaespaa|2025": {"competition": "COPA ESPAÑA", "league": "feb", "gender": "M", "category": "senior", "level": None, "season": "2025"},
    "feb|cesp|2025": {"competition": "C ESP CLUBES JR FEM", "league": "feb", "gender": "F", "category": "formacion", "level": None, "season": "2025"},
    "fbcyl|1126-1|2026": {"competition": "1ª División cadete femenino", "league": "fbcyl", "gender": "F", "category": "formacion", "level": None, "season": "2026"},
}


class TestTheNodes:
    @pytest.mark.parametrize("comp, node", [("feb|lfchallenge|2025", "F|feb|LF CHALLENGE"), ("feb|l.f.-2|2024", "F|feb|L.F.-2"), ("feb|primerafeb|2025", "M|feb|PRIMERA FEB"),
                                            ("feb|lfchallenge|2024", "F|feb|LF CHALLENGE")])
    def test_a_senior_league_is_a_node_of_its_sex_the_same_in_every_season(self, comp, node):
        assert node_of(COMPS[comp]) == node

    @pytest.mark.parametrize("comp", ["feb|copaespaa|2025", "feb|cesp|2025", "fbcyl|1126-1|2026"])
    def test_a_cup_and_the_formation_are_not_nodes_of_this_graph(self, comp):
        """A cup shares its players with the league at the same time (it is not a level) and the formation is E3's question (potential, not the level of a league)."""
        assert node_of(COMPS[comp]) is None

    def test_the_sex_is_part_of_the_node_so_men_and_women_never_meet(self):
        assert node_of({**COMPS["feb|lfchallenge|2025"], "gender": "M"}) != node_of(COMPS["feb|lfchallenge|2025"])
        assert node_of({**COMPS["feb|lfchallenge|2025"], "gender": None}) is None                                     # a competition that does not say its sex is not guessed

    def test_the_person_is_the_one_a_player_of_another_source_is_linked_to(self):
        assert person_of({"person_id": "fbcyl:abc", "linked_to": "feb:7"}) == "feb:7" and person_of({"person_id": "feb:7", "linked_to": None}) == "feb:7"


class TestTheZ:
    @pytest.mark.parametrize("pct, z", [(50, 0.0), (84.13, 1.0), (15.87, -1.0), (97.72, 2.0)])
    def test_a_percentile_is_the_z_of_the_normal(self, pct, z):
        assert z_of(pct) == pytest.approx(z, abs=0.01)

    def test_the_extremes_are_cut_so_that_a_zero_or_a_hundred_is_not_infinite(self):
        assert z_of(0) == pytest.approx(-2.576, abs=0.01) and z_of(100) == pytest.approx(2.576, abs=0.01) and z_of(0) < z_of(1) < z_of(50) < z_of(99) < z_of(100)


class TestTheObservations:
    def test_a_player_who_played_enough_with_every_axis_is_an_observation_with_his_z(self):
        (obs,) = observations([row(pct=84.13)], COMPS)
        assert (obs.person, obs.node, obs.season, obs.age) == ("feb:1", "F|feb|LF CHALLENGE", 2025, 24) and obs.z == pytest.approx((1.0,) * len(AXES), abs=0.01)

    def test_who_did_not_play_enough_or_has_no_profile_is_not(self):
        rows = [row("feb:2", eligible=False), row("feb:3", pct=None), row("feb:4", minutes=0, eligible=True)]
        rows[1]["pct"] = None
        assert [o.person for o in observations(rows, COMPS)] == ["feb:4"]                                                 # ``eligible`` is the one that says it: the minutes alone do not

    def test_an_axis_the_row_does_not_have_leaves_the_row_out_never_a_zero(self):
        broken = row("feb:5")
        del broken["pct"]["blk"]
        assert observations([broken], COMPS) == [] and MIN_ELIGIBLE_AXES == len(AXES) == 8

    def test_a_person_who_played_in_two_teams_of_one_competition_and_season_has_the_row_with_more_minutes(self):
        rows = [row("feb:1", pct=30.0, minutes=5000), row("feb:1", pct=70.0, minutes=15000), row("feb:1", pct=10.0, minutes=100)]
        (obs,) = observations(rows, COMPS)
        assert obs.z[0] == pytest.approx(z_of(70.0)) and obs.minutes == 15000

    def test_a_player_of_another_source_who_is_linked_counts_as_the_person_of_feb(self):
        rows = [row("feb:7", comp="feb|lfchallenge|2024", minutes=10000), row("fbcyl:abc", comp="feb|lfchallenge|2024", linked_to="feb:7", minutes=9000)]
        assert [o.person for o in observations(rows, COMPS)] == ["feb:7"]                                                 # the same person in one competition: his best row, once

    def test_the_cup_and_the_formation_are_left_out(self):
        assert observations([row(comp="feb|copaespaa|2025"), row(comp="feb|cesp|2025")], COMPS) == []


class TestTheMovements:
    def test_a_person_in_two_competitions_in_consecutive_seasons_is_a_movement_with_his_z_in_each(self):
        rows = [row("feb:1", comp="feb|l.f.-2|2024", pct=70.0), row("feb:1", comp="feb|lfchallenge|2025", pct=40.0, age=25)]
        (move,) = movements(observations(rows, COMPS))
        assert (move.person, move.from_node, move.to_node, move.from_season, move.to_season, move.age) == ("feb:1", "F|feb|L.F.-2", "F|feb|LF CHALLENGE", 2024, 2025, 25)
        assert move.z_from[0] == pytest.approx(z_of(70.0)) and move.z_to[0] == pytest.approx(z_of(40.0))

    def test_two_seasons_apart_or_the_same_season_are_not_movements(self):
        far = [row("feb:1", comp="feb|l.f.-2|2024"), row("feb:1", comp="feb|lfendesa|2026")]
        same = [row("feb:1", comp="feb|lfchallenge|2025"), row("feb:1", comp="feb|l.f.-2|2025")]
        assert movements(observations(far, COMPS)) == []
        assert movements(observations(same, COMPS)) == []                                                              # two competitions at once are not a change of level (that is another kind of evidence)

    def test_the_same_competition_in_two_seasons_is_a_stayer_not_a_movement(self):
        rows = [row("feb:1", comp="feb|lfchallenge|2024", pct=70.0), row("feb:1", comp="feb|lfchallenge|2025", pct=60.0)]
        obs = observations(rows, COMPS)
        assert movements(obs) == [] and [(s.from_season, s.to_season, s.from_node) for s in stayers(obs)] == [(2024, 2025, "F|feb|LF CHALLENGE")]

    def test_men_and_women_do_not_mix_even_if_a_person_were_in_both(self):
        rows = [row("feb:1", comp="feb|lfchallenge|2024"), row("feb:1", comp="feb|primerafeb|2025")]
        assert movements(observations(rows, COMPS)) == []

    def test_the_same_pair_of_competitions_is_one_movement_per_person_and_pair_of_seasons(self):
        rows = [row("feb:1", comp="feb|l.f.-2|2024", minutes=9000), row("feb:1", comp="feb|lfchallenge|2025", minutes=8000), row("feb:1", comp="feb|lfchallenge|2025", minutes=100)]
        assert len(movements(observations(rows, COMPS))) == 1


class TestTheRealRows:
    @pytest.fixture()
    def obs(self):
        return REAL_OBSERVATIONS

    def test_every_real_row_is_an_observation_of_a_senior_league_and_the_z_are_finite(self, obs):
        assert len(obs) == len({(o.person, o.node, o.season) for o in obs}) <= len(ROWS)
        assert {o.node.split("|")[0] for o in obs} == {"F", "M"} and all(len(o.z) == 8 and all(-2.6 < v < 2.6 for v in o.z) for o in obs)

    def test_the_movements_are_between_different_competitions_of_one_sex_in_consecutive_seasons(self, obs):
        moves = movements(obs)
        assert len(moves) > 150
        assert all(m.from_node != m.to_node and m.to_season - m.from_season == 1 and m.from_node.split("|")[0] == m.to_node.split("|")[0] for m in moves)

    def test_the_neighbouring_levels_the_sample_was_taken_for_have_movements_in_both_directions(self, obs):
        counts = edge_counts(movements(obs), node_levels(COMPETITIONS))
        for a, b in (("F|feb|L.F.-2", "F|feb|LF CHALLENGE"), ("M|feb|SEGUNDA FEB", "M|feb|PRIMERA FEB"), ("M|feb|SEGUNDA FEB", "M|feb|TERCERA FEB")):
            edge = counts[tuple(sorted((a, b)))]
            assert edge["up"] > 0 and edge["down"] > 0 and edge["persons"] >= 30, (a, b, edge)

    def test_the_stayers_are_in_one_competition_for_two_seasons_in_a_row(self, obs):
        same = stayers(obs)
        assert len(same) > 20 and all(s.from_node == s.to_node and s.to_season - s.from_season == 1 for s in same)

    def test_the_answer_does_not_depend_on_the_order_of_the_rows(self):
        shuffled = list(ROWS)
        random.Random(7).shuffle(shuffled)
        assert movements(observations(shuffled, COMPETITIONS)) == movements(observations(ROWS, COMPETITIONS))
        assert stayers(observations(shuffled, COMPETITIONS)) == stayers(observations(ROWS, COMPETITIONS))


class TestTheEdges:
    def test_an_edge_is_unordered_and_counts_persons_up_and_down_by_the_level_of_the_competitions(self):
        rows = [row("feb:1", comp="feb|l.f.-2|2024"), row("feb:1", comp="feb|lfchallenge|2025"),            # up: level 3 to 2
                row("feb:2", comp="feb|lfchallenge|2024"), row("feb:2", comp="feb|l.f.-2|2025")]            # down: level 2 to 3
        counts = edge_counts(movements(observations(rows, COMPS)), node_levels(COMPS))
        assert counts == {("F|feb|L.F.-2", "F|feb|LF CHALLENGE"): {"up": 1, "down": 1, "unranked": 0, "persons": 2}}

    def test_a_person_who_moved_twice_between_the_same_two_competitions_counts_once_in_persons_and_twice_in_movements(self):
        rows = [row("feb:1", comp="feb|l.f.-2|2024"), row("feb:1", comp="feb|lfchallenge|2025"), row("feb:1", comp="feb|l.f.-2|2026")]
        edge = edge_counts(movements(observations(rows, COMPS)), node_levels(COMPS))[("F|feb|L.F.-2", "F|feb|LF CHALLENGE")]
        assert edge["persons"] == 1 and edge["up"] + edge["down"] == 2

    def test_a_competition_with_no_level_has_unranked_movements(self):
        comps = {"a|2024": {"competition": "LIGA U", "league": "feb", "gender": "M", "category": "senior", "level": None, "season": "2024"},
                 "b|2025": {"competition": "TERCERA FEB", "league": "feb", "gender": "M", "category": "senior", "level": 4, "season": "2025"}}
        counts = edge_counts(movements(observations([row("feb:1", comp="a|2024"), row("feb:1", comp="b|2025")], comps)), node_levels(comps))
        assert counts == {("M|feb|LIGA U", "M|feb|TERCERA FEB"): {"up": 0, "down": 0, "unranked": 1, "persons": 1}}
