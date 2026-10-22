"""Fatigue with a thin baseline and a short stint (issue #479, feedback of 0.3.2).

In the demo Cultural - Melilla the alert said "riesgo de fatiga muy alto, 3:35 seguidos" for O. Siquier. Her baseline was 2 games and 4 stints
(usual stint 1:48, 6 minutes a game): 215 s were 2x the usual stint and the index saturated, although 3:35 on court is nothing. Agreed rules
(thresholds confirmed by the user, 21-22/10/2026; the default stint of 5:00 chosen with the Zamora-Leon data):

1. a baseline of fewer than 3 games or 8 stints is not trusted: the default stint (5:00) is used and the minutes components are left out;
2. an absolute floor: no fatigue alert below 5:00 seconds on court, no critical one below 7:00;
3. the card says the usual stint of the player.
"""
from src.live_core.config import RuleConfig
from src.live_core.rules_rotation import fatigue_index
from tests.test_live_core_advice import OWN, _player, engine, snap

SIQUIER = {"avg_min": 370, "p90_min": 700, "avg_stint": 108, "games": 2, "stints": 4}      # the real baseline of the demo
VETERAN = {"avg_min": 1500, "p90_min": 1900, "avg_stint": 300, "games": 8, "stints": 40}


def fatigue(stint, minutes, baseline, elapsed=1500):
    players = {"p1": _player("O. SIQUIER", OWN, stint=stint, minutes=minutes)}
    return [a for a in engine(baselines={"p1": baseline}).evaluate(snap(elapsed=elapsed, players=players)) if a.id == "fatigue_high"]


class TestThinBaseline:
    def test_the_demo_case_does_not_alert_regression(self):
        """3:35 on court with a baseline of 2 games and 4 stints (21/10/2026): nothing."""
        assert fatigue(215, 215, SIQUIER) == []
        assert fatigue(199, 199, SIQUIER) == []

    def test_a_thin_baseline_uses_the_default_stint_and_no_minutes_component(self):
        index, parts = fatigue_index(215, 215, 1500, SIQUIER)
        assert set(parts) == {"stint"} and parts["stint"] == 0.0           # 215 s against the default 300 s: not even above it

    def test_a_baseline_with_enough_sample_is_trusted(self):
        _, parts = fatigue_index(450, 900, 1500, VETERAN)
        assert {"stint", "minutes"} <= set(parts) and parts["stint"] > 0.4

    def test_each_minimum_counts_separately(self):
        few_games = {**VETERAN, "games": 2}
        few_stints = {**VETERAN, "stints": 7}
        assert set(fatigue_index(450, 900, 1500, few_games)[1]) == {"stint"}
        assert set(fatigue_index(450, 900, 1500, few_stints)[1]) == {"stint"}

    def test_a_baseline_without_the_sample_fields_is_trusted_as_before(self):
        """Older packages and the tests' baselines have no ``games``/``stints``: nothing changes for them."""
        old = {"avg_min": 1500, "p90_min": 1900, "avg_stint": 300}
        assert set(fatigue_index(450, 900, 1500, old)[1]) == {"stint", "minutes", "projection"}

    def test_the_minimums_are_in_the_configuration(self):
        cfg = RuleConfig(fatigue_min_games=5)
        assert set(fatigue_index(450, 900, 1500, {**VETERAN, "games": 4}, cfg)[1]) == {"stint"}


class TestAbsoluteFloor:
    BIG = {"avg_min": 1500, "p90_min": 1900, "avg_stint": 100, "games": 20, "stints": 200}    # a player of short stints, well known

    def test_no_alert_below_five_minutes_on_court_whatever_the_baseline(self):
        assert fatigue(299, 1400, self.BIG) == []

    def test_between_five_and_seven_minutes_it_is_at_most_a_warning(self):
        alerts = fatigue(360, 1500, self.BIG)
        assert alerts and {a.severity for a in alerts} == {"warning"}
        assert "critical" not in {a.evidence["level"] for a in alerts}

    def test_from_seven_minutes_it_can_be_critical(self):
        assert "critical" in {a.severity for a in fatigue(600, 1500, self.BIG)}

    def test_the_floors_are_in_the_configuration(self):
        cfg = RuleConfig(fatigue_floor_warning_s=120)
        index, _ = fatigue_index(150, 1400, 1500, self.BIG, cfg)
        assert index > 0
        assert cfg.fatigue_floor_critical_s > cfg.fatigue_floor_warning_s


class TestCard:
    def test_the_message_says_the_usual_stint_of_the_player(self):
        [alert] = fatigue(480, 1500, VETERAN)
        assert "su tramo habitual: 5:00" in alert.message

    def test_the_evidence_carries_the_usual_stint_and_the_sample(self):
        [alert] = fatigue(480, 1500, VETERAN)
        assert alert.evidence["avg_stint_s"] == 300 and alert.evidence["sample"] == {"games": 8, "stints": 40, "trusted": True}

    def test_a_player_without_a_trusted_baseline_says_it_uses_the_default(self):
        [alert] = fatigue(850, 850, {**SIQUIER, "avg_stint": 108})
        assert "tramo habitual: 5:00" in alert.message and alert.evidence["sample"]["trusted"] is False
