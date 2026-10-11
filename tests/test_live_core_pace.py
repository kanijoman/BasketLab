"""Game pace (possessions per 40 min): current pace, projection to the end and +/- against the habitual pace
of our team and of the rival (issue #209).

Pace = average possessions of both teams (FGA - ORB + TOV + 0.44*FTA) per 40 game-minutes. The projection
blends the pace seen so far with the expected one (the mean of both teams' habitual paces), weighting the
game more as it advances, like the final-margin projection of the Four Factors.
"""
import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from src.live_core.pace import PaceModel

OWN, RIVAL = "1", "2"
BASE = {"pace_own_per_40": 70.0, "pace_rival_per_40": 62.0,
        "sample_games": {"own": 4, "rival": 3, "league": 20}}


def team(possessions):
    """Stats whose possessions are exactly ``possessions`` (field goals only)."""
    return {"fg2m": 0, "fg2a": possessions, "fg3m": 0, "fg3a": 0, "ftm": 0, "fta": 0,
            "orb": 0, "drb": 0, "tov": 0, "tov_team": 0, "stl": 0, "ast": 0, "blk": 0, "pts": 0}


def snap(elapsed=1200, own=36, rival=36):
    return {"period": 3, "remaining": 0, "elapsed": elapsed, "score": {OWN: 40, RIVAL: 38},
            "teams": {OWN: {"name": "A", "stats": team(own)}, RIVAL: {"name": "B", "stats": team(rival)}}}


def model(base=BASE, **cfg):
    return PaceModel(OWN, RIVAL, base, RuleConfig(**cfg))


class TestCurrentPace:
    def test_is_the_mean_possessions_of_both_teams_per_40_minutes(self):
        out = model().evaluate(snap(elapsed=1200, own=36, rival=34))
        assert out["possessions"] == pytest.approx(35.0)
        assert out["current40"] == pytest.approx(70.0)  # 35 possessions in 20 min

    def test_is_not_reliable_during_the_first_minutes(self):
        out = model().evaluate(snap(elapsed=120, own=5, rival=5))
        assert out["reliable"] is False
        assert model().evaluate(snap(elapsed=180, own=5, rival=5))["reliable"] is True

    def test_minimum_time_is_configurable(self):
        assert model(pace_min_elapsed_s=60).evaluate(snap(elapsed=60, own=2, rival=2))["reliable"] is True

    def test_nothing_before_tip_off(self):
        assert model().evaluate(snap(elapsed=0, own=0, rival=0)) is None


class TestPlusMinusAgainstTheHabit:
    def test_is_current_pace_minus_each_teams_habitual_pace(self):
        out = model().evaluate(snap(elapsed=1200, own=36, rival=36))  # current 72
        assert (out["habit_own40"], out["habit_rival40"]) == (70.0, 62.0)
        assert out["delta_own"] == pytest.approx(2.0)
        assert out["delta_rival"] == pytest.approx(10.0)

    def test_negative_when_the_game_is_slower_than_usual(self):
        out = model().evaluate(snap(elapsed=1200, own=30, rival=30))  # current 60
        assert out["delta_own"] == pytest.approx(-10.0) and out["delta_rival"] == pytest.approx(-2.0)

    def test_old_packages_without_the_data_give_no_deltas_instead_of_wrong_ones(self):
        out = model({"pace_per_40": 66.0}).evaluate(snap())
        assert out["habit_own40"] is None and out["delta_own"] is None
        assert out["habit_rival40"] is None and out["delta_rival"] is None

    def test_the_sample_sizes_travel_with_the_analysis(self):
        assert model().evaluate(snap())["sample_games"] == {"own": 4, "rival": 3}


class TestProjection:
    def test_blends_the_current_pace_with_the_expected_one(self):
        out = model().evaluate(snap(elapsed=1200, own=36, rival=36))
        assert out["expected40"] == pytest.approx(66.0)  # mean of 70 and 62
        # halfway: 50 % current (72) + 50 % expected (66)
        assert out["projected40"] == pytest.approx(69.0)

    def test_total_possessions_add_what_is_left_at_the_projected_pace(self):
        out = model().evaluate(snap(elapsed=1200, own=36, rival=36))
        assert out["projected_possessions"] == pytest.approx(36 + 69.0 * 1200 / 2400)

    def test_without_baselines_the_projection_is_the_current_pace(self):
        out = model({}).evaluate(snap(elapsed=1200, own=36, rival=36))
        assert out["expected40"] is None and out["projected40"] == pytest.approx(72.0)

    def test_with_one_habit_only_that_one_is_the_expectation(self):
        out = model({"pace_own_per_40": 70.0}).evaluate(snap(elapsed=1200, own=36, rival=36))
        assert out["expected40"] == pytest.approx(70.0)

    def test_overtime_has_nothing_left_to_project(self):
        out = model().evaluate(snap(elapsed=2700, own=90, rival=90))
        assert out["projected_possessions"] == pytest.approx(90.0)
        assert out["current40"] == pytest.approx(90 / 2700 * 2400)

    def test_late_in_the_game_the_observed_pace_dominates(self):
        out = model().evaluate(snap(elapsed=2280, own=76, rival=76))  # 95 % played
        assert out["projected40"] == pytest.approx(0.95 * out["current40"] + 0.05 * 66.0)


class TestRobustness:
    def test_partial_snapshot_gives_nothing(self):
        broken = snap()
        broken["teams"][OWN]["stats"] = {"pts": 3}
        assert model().evaluate(broken) is None

    def test_teams_missing_from_the_snapshot_give_nothing(self):
        assert model().evaluate({"elapsed": 600, "teams": {}, "score": {}}) is None

    def test_without_a_rival_the_own_possessions_are_used(self):
        out = PaceModel(OWN, None, BASE, RuleConfig()).evaluate(snap(elapsed=1200, own=36, rival=0))
        assert out["current40"] == pytest.approx(72.0) and out["habit_rival40"] is None


class TestAdviceEngineExposesIt:
    def test_analysis_carries_the_pace_next_to_the_four_factors(self):
        engine = AdviceEngine(OWN, RIVAL, team_baselines=BASE)
        analysis = engine.analyze(snap())
        assert analysis["pace"]["delta_own"] == pytest.approx(2.0)
        assert "four_factors" in analysis

    def test_it_is_json_serialisable_numbers_only(self):
        import json

        json.dumps(AdviceEngine(OWN, RIVAL, team_baselines=BASE).analyze(snap()))
