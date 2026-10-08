"""Rule-based team report engine (replaces the removed LLM analysis, issues #121/#126).

Pure functions: team stats + league quartiles (+ per-game CV) -> structured report.
"""
import pytest

from src.report_engine import ReportConfig, build_team_report
from src.report_engine.rules import classify_quartile

Q = {"q1": 10.0, "q2": 20.0, "q3": 30.0}


def _quartiles(**extra):
    base = {
        "points_per_game": {"q1": 70, "q2": 78, "q3": 85},
        "points_against_per_game": {"q1": 70, "q2": 78, "q3": 85},
        "turnovers_per_game": {"q1": 11, "q2": 13, "q3": 15},
        "fg3_percentage": {"q1": 30, "q2": 33, "q3": 36},
        "three_point_rate": {"q1": 30, "q2": 36, "q3": 42},
        "possessions_per_game": {"q1": 68, "q2": 72, "q3": 76},
    }
    base.update(extra)
    return base


def _stats(**kw):
    s = {"games_played": 20, "points_per_game": 78.0, "points_against_per_game": 78.0,
         "turnovers_per_game": 13.0, "fg3_percentage": 33.0, "three_point_rate": 36.0,
         "possessions_per_game": 72.0}
    s.update(kw)
    return s


def _keys(items):
    return [i["key"] for i in items]


class TestClassifyQuartile:
    @pytest.mark.parametrize("value, level", [(5, 1), (10, 1), (15, 2), (20, 2), (25, 3), (30, 3), (31, 4)])
    def test_levels(self, value, level):
        assert classify_quartile(value, Q) == level

    def test_missing_quartiles_returns_none(self):
        assert classify_quartile(5, {}) is None
        assert classify_quartile(5, {"q1": None, "q2": 1, "q3": 2}) is None


class TestStrengthsAndWeaknesses:
    def test_high_scoring_is_a_strength_and_high_turnovers_a_weakness(self):
        r = build_team_report("A", _stats(points_per_game=90, turnovers_per_game=17), _quartiles(), None)
        assert "points_per_game" in _keys(r["strengths"])
        assert "turnovers_per_game" in _keys(r["weaknesses"])

    def test_lower_is_better_stats_are_inverted(self):
        r = build_team_report("A", _stats(points_against_per_game=65, turnovers_per_game=9), _quartiles(), None)
        assert {"points_against_per_game", "turnovers_per_game"} <= set(_keys(r["strengths"]))
        assert not set(_keys(r["weaknesses"])) & {"points_against_per_game", "turnovers_per_game"}

    def test_median_team_has_neither(self):
        r = build_team_report("A", _stats(), _quartiles(), None)
        assert r["strengths"] == [] and r["weaknesses"] == []

    def test_neutral_stats_are_never_strengths_or_weaknesses(self):
        r = build_team_report("A", _stats(three_point_rate=60), _quartiles(), None)
        assert "three_point_rate" not in _keys(r["strengths"]) + _keys(r["weaknesses"])

    def test_findings_carry_value_quartile_and_spanish_text(self):
        r = build_team_report("A", _stats(points_per_game=90), _quartiles(), None)
        f = next(x for x in r["strengths"] if x["key"] == "points_per_game")
        assert f["value"] == 90.0 and f["quartile"] == 4
        assert f["label"] and f["text"]

    def test_stats_without_quartiles_or_value_are_skipped(self):
        r = build_team_report("A", _stats(points_per_game=90), {}, None)
        assert r["strengths"] == [] and r["weaknesses"] == []
        r2 = build_team_report("A", {"games_played": 3}, _quartiles(), None)
        assert r2["strengths"] == [] and r2["weaknesses"] == []


class TestDifferentials:
    def test_advantage_and_disadvantage_vs_league_median(self):
        r = build_team_report("A", _stats(points_per_game=90, turnovers_per_game=17), _quartiles(), None)
        d = {x["key"]: x for x in r["differentials"]}
        assert d["points_per_game"]["advantage"] is True
        assert d["points_per_game"]["diff_pct"] == pytest.approx((90 - 78) / 78 * 100)
        assert d["turnovers_per_game"]["advantage"] is False

    def test_small_gaps_below_threshold_are_ignored(self):
        r = build_team_report("A", _stats(points_per_game=79), _quartiles(), None)
        assert "points_per_game" not in _keys(r["differentials"])

    def test_threshold_is_configurable(self):
        cfg = ReportConfig(diff_threshold_pct=0.5)
        r = build_team_report("A", _stats(points_per_game=79), _quartiles(), None, config=cfg)
        assert "points_per_game" in _keys(r["differentials"])

    def test_zero_median_does_not_divide_by_zero(self):
        r = build_team_report("A", _stats(points_per_game=5),
                              _quartiles(points_per_game={"q1": 0, "q2": 0, "q3": 1}), None)
        assert "points_per_game" not in _keys(r["differentials"])


class TestConsistency:
    @staticmethod
    def _cons(**cv):
        return {k: {"cv": v, "n": 20} for k, v in cv.items()}

    def test_high_cv_is_inconsistent_low_cv_is_consistent(self):
        r = build_team_report("A", _stats(), _quartiles(), self._cons(fg3_percentage=40, points_per_game=8))
        c = {x["key"]: x["status"] for x in r["consistency"]}
        assert c == {"fg3_percentage": "inconsistent", "points_per_game": "consistent"}

    def test_mid_cv_is_not_reported(self):
        r = build_team_report("A", _stats(), _quartiles(), self._cons(fg3_percentage=20))
        assert r["consistency"] == []

    def test_cv_from_two_games_is_reported_but_flagged_unreliable(self):
        """Early season (issue #144): no minimum number of games, just a reliability flag."""
        r = build_team_report("A", _stats(), _quartiles(), {"fg3_percentage": {"cv": 50, "n": 2}})
        assert r["consistency"][0]["key"] == "fg3_percentage"
        assert r["consistency"][0]["low_sample"] is True

    def test_cv_with_enough_games_is_reliable(self):
        r = build_team_report("A", _stats(), _quartiles(), {"fg3_percentage": {"cv": 50, "n": 20}})
        assert r["consistency"][0]["low_sample"] is False

    def test_single_game_has_no_variability_so_no_cv_finding(self):
        r = build_team_report("A", _stats(), _quartiles(), {"fg3_percentage": {"cv": 0.0, "n": 1}})
        assert r["consistency"] == []

    def test_missing_consistency_data_is_fine(self):
        assert build_team_report("A", _stats(), _quartiles(), None)["consistency"] == []


class TestModes:
    def test_rival_mode_reframes_the_same_findings(self):
        own = build_team_report("A", _stats(points_per_game=90), _quartiles(), None, mode="own")
        riv = build_team_report("A", _stats(points_per_game=90), _quartiles(), None, mode="rival")
        assert _keys(own["strengths"]) == _keys(riv["strengths"])
        assert own["strengths"][0]["text"] != riv["strengths"][0]["text"]
        assert riv["mode"] == "rival"

    def test_rival_inconsistency_is_an_opportunity(self):
        cons = {"fg3_percentage": {"cv": 45, "n": 20}}
        own = build_team_report("A", _stats(), _quartiles(), cons, mode="own")
        riv = build_team_report("A", _stats(), _quartiles(), cons, mode="rival")
        assert own["consistency"][0]["text"] != riv["consistency"][0]["text"]

    def test_unknown_mode_is_rejected(self):
        with pytest.raises(ValueError):
            build_team_report("A", _stats(), _quartiles(), None, mode="other")


class TestProfileTacticsTraining:
    def test_profile_describes_tempo_and_shot_selection(self):
        r = build_team_report("A", _stats(possessions_per_game=80, three_point_rate=45), _quartiles(), None)
        text = " ".join(r["profile"]).lower()
        assert "ritmo" in text and "triple" in text

    def test_own_training_priorities_come_from_weaknesses(self):
        r = build_team_report("A", _stats(turnovers_per_game=18, fg3_percentage=25), _quartiles(), None)
        keys = [t["key"] for t in r["training"]]
        assert set(keys) == {"turnovers_per_game", "fg3_percentage"}
        assert [t["priority"] for t in r["training"]] == [1, 2]

    def test_training_is_capped(self):
        cfg = ReportConfig(max_training_items=1)
        r = build_team_report("A", _stats(turnovers_per_game=18, fg3_percentage=25), _quartiles(), None, config=cfg)
        assert len(r["training"]) == 1

    def test_tactics_split_offense_and_defense(self):
        r = build_team_report("A", _stats(points_per_game=90, points_against_per_game=65), _quartiles(), None)
        assert {t["area"] for t in r["tactics"]} == {"ofensiva", "defensiva"}

    def test_rival_game_plan_neutralizes_strengths_and_exploits_weaknesses(self):
        r = build_team_report("A", _stats(points_per_game=90, turnovers_per_game=18), _quartiles(), None, mode="rival")
        assert {t["kind"] for t in r["training"]} == {"neutralize", "exploit"}


class TestReportShape:
    def test_header_fields(self):
        r = build_team_report("Equipo X", _stats(), _quartiles(), None)
        assert r["team"] == "Equipo X" and r["games_played"] == 20 and r["mode"] == "own"
        assert set(r) >= {"strengths", "weaknesses", "differentials", "consistency",
                          "profile", "tactics", "training"}

    def test_games_played_reads_total_games_from_real_team_rows_regression(self):
        """Real aggregation rows expose ``total_games`` (not ``games_played``)."""
        stats = {k: v for k, v in _stats().items() if k != "games_played"}
        assert build_team_report("A", {**stats, "total_games": 7}, _quartiles(), None)["games_played"] == 7

    @pytest.mark.parametrize("games, low", [(0, True), (1, True), (4, True), (5, False), (30, False)])
    def test_low_sample_flag_depends_on_games_played(self, games, low):
        r = build_team_report("A", _stats(games_played=games), _quartiles(), None)
        assert r["low_sample"] is low

    def test_report_is_generated_with_a_single_game(self):
        r = build_team_report("A", _stats(games_played=1, points_per_game=95), _quartiles(), None)
        assert r["games_played"] == 1 and r["low_sample"] is True
        assert "points_per_game" in [f["key"] for f in r["strengths"]]

    def test_empty_stats_do_not_crash(self):
        r = build_team_report("A", {}, {}, None)
        assert r["games_played"] == 0


def _zone(zone, rating, delta=10.0, fga=40, points=2, low=False):
    return {"zone": zone, "zone_label": zone.replace("_", " ").title(), "points": points, "fga": fga,
            "fgm": 20, "fg_pct": 50.0, "league_pct": 40.0, "delta_pp": delta, "rating": rating, "low_sample": low}


class TestZones:
    ZONES = [
        _zone("paint", "above", 12.0),
        _zone("mid_left", "below", -9.0),
        _zone("top_three", "above", 4.0, points=3),
        _zone("wing_left", "average", 1.0),
        _zone("corner_left", "none", None, fga=0),
        _zone("corner_right", "unknown", None),
    ]

    def _report(self, mode="own", **kw):
        return build_team_report("A", _stats(), _quartiles(), None, mode=mode, zones=self.ZONES, **kw)

    def test_only_hot_and_cold_zones_are_reported_ordered_by_gap(self):
        z = self._report()["zones"]
        assert [(x["zone"], x["kind"]) for x in z] == [("paint", "hot"), ("mid_left", "cold"), ("top_three", "hot")]

    def test_zone_items_carry_values_and_low_sample_flag(self):
        z = build_team_report("A", _stats(), _quartiles(), None, zones=[_zone("paint", "above", low=True)])["zones"][0]
        assert z["label"] == "Paint" and z["fg_pct"] == 50.0 and z["league_pct"] == 40.0
        assert z["delta_pp"] == 10.0 and z["fga"] == 40 and z["low_sample"] is True

    def test_rival_mode_reframes_zone_text(self):
        own = self._report("own")["zones"][0]["text"]
        riv = self._report("rival")["zones"][0]["text"]
        assert own != riv

    def test_no_zone_data_gives_empty_section(self):
        assert build_team_report("A", _stats(), _quartiles(), None)["zones"] == []
        assert build_team_report("A", _stats(), _quartiles(), None, zones=[])["zones"] == []
