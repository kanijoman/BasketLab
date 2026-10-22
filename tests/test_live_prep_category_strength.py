"""Teams of different divisions in the same package (issue #464): the prior of the matchup does not mix their strengths unadjusted.

Found with the Copa de España: Cultural Leonesa (2ª FEB) against Alimerka Oviedo (1ª FEB). Each team's net rating is measured against the
teams of ITS division, so the gap of two such ratings says nothing about the tie. The package says the teams are of different divisions and, until the
gap between divisions is calibrated with real cross-division games (``LEVEL_GAP_NET_RTG``), shrinks the prior by half; once it is, the net rating prior
is moved by it.
"""
import json

import pytest

from src.live_prep import category_strength as cs
from src.live_prep.game_sources import LEVEL_KEY
from src.live_prep.package_builder import SeasonAccumulator

A, B = "982047", "981204"
STAMP = "2026-10-08T00:00:00Z"


def tagged(doc, level):
    return {**json.loads(json.dumps(doc)), LEVEL_KEY: level}


def remap(doc, mapping):
    text = json.dumps(doc)
    for old, new in mapping.items():
        text = text.replace(f'"{old}"', f'"{new}"')
    return json.loads(text)


class TestAdjust:
    FF = {"efg": 0.04, "tov": -0.02, "orb": 0.01, "ftr": 0.03}

    def test_same_division_or_unknown_changes_nothing(self):
        for own, rival in ((3, 3), (None, 2), (3, None), (None, None)):
            ff, net, info = cs.adjust(self.FF, 4.0, own, rival)
            assert (ff, net, info) == (self.FF, 4.0, None)

    def test_different_divisions_shrink_both_priors_while_the_gap_is_not_calibrated(self, monkeypatch):
        monkeypatch.setattr(cs, "LEVEL_GAP_NET_RTG", None)
        ff, net, info = cs.adjust(self.FF, 4.0, 3, 2)
        assert net == pytest.approx(2.0) and ff["efg"] == pytest.approx(0.02)
        assert info == {"own_level": 3, "rival_level": 2, "adjusted": "shrink"}

    def test_a_calibrated_gap_moves_the_net_prior_by_the_levels_of_difference(self, monkeypatch):
        monkeypatch.setattr(cs, "LEVEL_GAP_NET_RTG", 5.0)
        ff, net, info = cs.adjust(self.FF, 4.0, 3, 2)           # we are a division below: -5 per level
        assert net == pytest.approx(-1.0) and info["adjusted"] == "gap"
        assert cs.adjust(self.FF, 4.0, 2, 4)[1] == pytest.approx(14.0)      # two divisions above
        assert ff["efg"] == pytest.approx(0.02)                 # the factors have no units to move: they are shrunk

    def test_the_most_common_known_level_of_a_team_is_its_division(self):
        assert cs.team_level({3: 10, 2: 1}) == 3
        assert cs.team_level({}) is None
        assert cs.team_level({2: 4, 3: 4}) == 2                 # a tie: the higher division


class TestAccumulator:
    def package(self, feb_game_doc, own_level, rival_level):
        acc = SeasonAccumulator(track=[A, B])
        acc.add_game(tagged(remap(feb_game_doc, {B: "555"}), own_level))      # A's league game
        acc.add_game(tagged(remap(feb_game_doc, {A: "777"}), rival_level))    # B's league game
        return acc.to_package("COPA", "2026", A, B, None, STAMP)

    def test_the_package_says_the_teams_are_of_different_divisions(self, feb_game_doc):
        p = self.package(feb_game_doc, 3, 2)
        assert p.baselines["cross_division"] == {"own_level": 3, "rival_level": 2, "adjusted": "gap"}

    def test_teams_of_the_same_division_get_no_marker_and_the_same_package_as_before_regression(self, feb_game_doc):
        p = self.package(feb_game_doc, 3, 3)
        assert "cross_division" not in p.baselines

    def test_games_without_a_level_leave_the_package_as_it_always_was_regression(self, feb_game_doc):
        acc = SeasonAccumulator(track=[A, B])
        acc.add_game(remap(feb_game_doc, {B: "555"}))
        acc.add_game(remap(feb_game_doc, {A: "777"}))
        assert "cross_division" not in acc.to_package("C", "2026", A, B, None, STAMP).baselines

    def test_the_net_prior_moves_by_the_calibrated_gap_per_division_and_the_factors_are_shrunk(self, feb_game_doc):
        same = self.package(feb_game_doc, 3, 3).baselines
        below = self.package(feb_game_doc, 3, 2).baselines       # we are a division below the rival
        above = self.package(feb_game_doc, 2, 3).baselines
        assert below["net_rtg_prior"] == pytest.approx(same["net_rtg_prior"] - cs.LEVEL_GAP_NET_RTG, abs=0.01)
        assert above["net_rtg_prior"] == pytest.approx(same["net_rtg_prior"] + cs.LEVEL_GAP_NET_RTG, abs=0.01)
        assert all(abs(below["four_factors_prior"][k]) <= abs(same["four_factors_prior"][k]) for k in same["four_factors_prior"])

    def test_the_calibrated_gap_is_the_one_measured_with_the_copa(self):
        """22/10/2026 (#503): 58 games between divisions of 2024-2026, +23.0 ± 2.3 per division; 20 on purpose."""
        assert cs.LEVEL_GAP_NET_RTG == 20.0


class TestFromTheDatabase:
    """Leonesa (2ª FEB, 3) against Oviedo (1ª FEB, 2) in a Copa tie: each team's division is where its games were played."""

    def world(self, feb_game_doc):
        from tests.test_live_prep_game_sources import COPA, PRIMERA, RIVAL, SEGUNDA, OWN, Handler, game
        return Handler({COPA: [game(feb_game_doc, OWN, RIVAL, 1)], SEGUNDA: [game(feb_game_doc, OWN, "555", 4)], PRIMERA: [game(feb_game_doc, RIVAL, "777", 6)]}), COPA, OWN, RIVAL

    LEVELS = {"SEGUNDA_FEB_2026_2027_Liga_Regular_A": 3, "PRIMERA_FEB_2026_2027_Liga_Regular_Único": 2}

    def test_the_teams_of_different_divisions_are_marked(self, feb_game_doc):
        from src.live_prep.db_source import build_package_from_db
        handler, copa, own, rival = self.world(feb_game_doc)
        p = build_package_from_db(handler, copa, own, rival, "2026", level_of=self.LEVELS.get)
        assert p.baselines["cross_division"]["own_level"] == 3 and p.baselines["cross_division"]["rival_level"] == 2

    def test_without_a_catalog_there_is_nothing_to_say_and_the_package_is_as_before(self, feb_game_doc):
        from src.live_prep.db_source import build_package_from_db
        handler, copa, own, rival = self.world(feb_game_doc)
        p = build_package_from_db(handler, copa, own, rival, "2026", level_of=lambda name: None)
        assert "cross_division" not in p.baselines

    def test_a_failing_catalog_never_stops_the_package(self, feb_game_doc, monkeypatch):
        from src.live_prep import db_source
        handler, copa, own, rival = self.world(feb_game_doc)
        monkeypatch.setattr("src.live_prep.publisher.load_config", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no config")))
        assert db_source.build_package_from_db(handler, copa, own, rival, "2026").baselines["sample_games"]["own"] >= 1

    def test_the_round_bundles_mark_it_too(self, feb_game_doc):
        from src.live_prep.round_packages import build_round_packages_from_db
        handler, copa, own, rival = self.world(feb_game_doc)
        match = {"code": "9", "start": "2026-10-21T20:00", "round": 1, "home": {"id": own, "name": "H"}, "away": {"id": rival, "name": "A"}}
        built = build_round_packages_from_db(handler, copa, [match], season="2026", level_of=self.LEVELS.get)
        assert built[0]["package"].baselines["cross_division"]["adjusted"] == "gap"
