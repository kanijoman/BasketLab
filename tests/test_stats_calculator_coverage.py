"""Extended coverage tests for StatsCalculator.calculate_stat_value and create_comparative_stat.

Missing lines targeted: stats_calculator.py 305-392 (calculate_stat_value dispatch),
plus create_comparative_stat delta logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from stats.stats_calculator import StatsCalculator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _team():
    """Typical FEB boxscore team dict."""
    return {
        "name": "TeamA",
        "pts": 80,
        "p2m": 25, "p2a": 45,
        "p3m": 7,  "p3a": 20,
        "p1m": 9,  "p1a": 12,
        "ro": 10,  "rd": 25,
        "assist": 16,
        "st": 8,
        "to": 12,
        "bs": 4,
    }


def _opp():
    """Typical FEB boxscore opponent dict."""
    return {
        "name": "TeamB",
        "pts": 72,
        "p2m": 22, "p2a": 40,
        "p3m": 5,  "p3a": 18,
        "p1m": 8,  "p1a": 10,
        "ro": 8,   "rd": 22,
        "assist": 14,
        "st": 6,
        "to": 14,
        "bs": 3,
    }


def _calc():
    return StatsCalculator()


# ---------------------------------------------------------------------------
# calculate_stat_value — basic stats
# ---------------------------------------------------------------------------

class TestCalculateStatValueBasic:
    def test_points_per_game(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "points_per_game") == 80.0

    def test_points_allowed_per_game(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "points_allowed_per_game") == 72.0

    def test_fg2_percentage(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "fg2_percentage")
        assert pytest.approx(result, rel=1e-3) == 25 / 45 * 100

    def test_fg3_percentage(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "fg3_percentage")
        assert pytest.approx(result, rel=1e-3) == 7 / 20 * 100

    def test_ft_percentage(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "ft_percentage")
        assert pytest.approx(result, rel=1e-3) == 9 / 12 * 100

    def test_rebounds_per_game(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "rebounds_per_game") == 35.0

    def test_def_rebounds(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "def_rebounds_per_game") == 25.0

    def test_off_rebounds(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "off_rebounds_per_game") == 10.0

    def test_assists_per_game(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "assists_per_game") == 16.0

    def test_steals_per_game(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "steals_per_game") == 8.0

    def test_turnovers_per_game(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "turnovers_per_game") == 12.0

    def test_blocks_per_game(self):
        assert _calc().calculate_stat_value(_team(), _opp(), "blocks_per_game") == 4.0


# ---------------------------------------------------------------------------
# calculate_stat_value — advanced stats
# ---------------------------------------------------------------------------

class TestCalculateStatValueAdvanced:
    def test_possessions_per_game_positive(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "possessions_per_game")
        assert result > 0

    def test_offensive_rating_positive(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "offensive_rating")
        assert result > 0

    def test_defensive_rating_positive(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "defensive_rating")
        assert result > 0

    def test_net_rating_sign(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "net_rating")
        ortg = _calc().calculate_stat_value(_team(), _opp(), "offensive_rating")
        drtg = _calc().calculate_stat_value(_team(), _opp(), "defensive_rating")
        assert pytest.approx(result, rel=1e-6) == ortg - drtg

    def test_efg_percentage_range(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "efg_percentage")
        assert 0 <= result <= 100

    def test_true_shooting_range(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "true_shooting")
        assert 0 <= result <= 100

    def test_three_point_rate_range(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "three_point_rate")
        assert 0 <= result <= 100

    def test_free_throw_rate_range(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "free_throw_rate")
        assert 0 <= result <= 100

    def test_assist_fg_rate(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "assist_fg_rate")
        assert result > 0

    def test_assist_rate(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "assist_rate")
        assert result > 0

    def test_turnover_rate(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "turnover_rate")
        assert result > 0

    def test_steal_rate(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "steal_rate")
        assert result > 0

    def test_block_rate(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "block_rate")
        assert result > 0

    def test_offensive_rebound_rate_range(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "offensive_rebound_rate")
        assert 0 <= result <= 100

    def test_defensive_rebound_rate_range(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "defensive_rebound_rate")
        assert 0 <= result <= 100

    def test_unknown_stat_returns_none(self):
        result = _calc().calculate_stat_value(_team(), _opp(), "no_such_stat")
        assert result is None


# ---------------------------------------------------------------------------
# calculate_stat_value — zero-division guards
# ---------------------------------------------------------------------------

class TestCalculateStatValueZeroDivision:
    def _empty(self):
        return {"name": "Empty", "pts": 0, "p2m": 0, "p2a": 0, "p3m": 0, "p3a": 0,
                "p1m": 0, "p1a": 0, "ro": 0, "rd": 0, "assist": 0, "st": 0, "to": 0, "bs": 0}

    def test_fg2_pct_zero_attempts_returns_zero(self):
        assert _calc().calculate_stat_value(self._empty(), self._empty(), "fg2_percentage") == 0

    def test_fg3_pct_zero_attempts_returns_zero(self):
        assert _calc().calculate_stat_value(self._empty(), self._empty(), "fg3_percentage") == 0

    def test_ft_pct_zero_attempts_returns_zero(self):
        assert _calc().calculate_stat_value(self._empty(), self._empty(), "ft_percentage") == 0

    def test_efg_zero_attempts_returns_zero(self):
        assert _calc().calculate_stat_value(self._empty(), self._empty(), "efg_percentage") == 0

    def test_true_shooting_zero_returns_zero(self):
        assert _calc().calculate_stat_value(self._empty(), self._empty(), "true_shooting") == 0

    def test_three_point_rate_zero_returns_zero(self):
        assert _calc().calculate_stat_value(self._empty(), self._empty(), "three_point_rate") == 0

    def test_assist_fg_rate_zero_fgm_returns_zero(self):
        assert _calc().calculate_stat_value(self._empty(), self._empty(), "assist_fg_rate") == 0


# ---------------------------------------------------------------------------
# calculate_stat_value — FBCYL format passthrough
# ---------------------------------------------------------------------------

class TestCalculateStatValueFBCYL:
    def _fbcyl_team(self):
        return {
            "score": 78,
            "shotsOfTwoSuccessful": 24, "shotsOfTwoAttempted": 44,
            "shotsOfThreeSuccessful": 6, "shotsOfThreeAttempted": 18,
            "shotsOfOneSuccessful": 6,  "shotsOfOneAttempted": 8,
            "offensiveRebound": 9, "defensiveRebound": 24,
            "assists": 15,
            "steals": 7,
            "lost": 11,
            "block": 3,
        }

    def test_fbcyl_points_per_game(self):
        result = _calc().calculate_stat_value(self._fbcyl_team(), self._fbcyl_team(), "points_per_game")
        assert result == 78.0

    def test_fbcyl_fg2_percentage(self):
        result = _calc().calculate_stat_value(self._fbcyl_team(), self._fbcyl_team(), "fg2_percentage")
        assert pytest.approx(result, rel=1e-3) == 24 / 44 * 100


# ---------------------------------------------------------------------------
# create_comparative_stat
# ---------------------------------------------------------------------------

class TestCreateComparativeStat:
    def _monthly(self):
        return {
            "_id": "m1",
            "team_name": "Alpha",
            "points_per_game": 80.0,
            "assists_per_game": 18.0,
            "turnovers_per_game": 10.0,
        }

    def _rest(self):
        return {
            "_id": "r1",
            "team_name": "Alpha",
            "points_per_game": 75.0,
            "assists_per_game": 15.0,
            "turnovers_per_game": 12.0,
        }

    def test_returns_dict_with_keys(self):
        result = _calc().create_comparative_stat(self._monthly(), self._rest())
        for k in ("_id", "team_name", "monthly", "rest", "deltas"):
            assert k in result

    def test_team_name_copied(self):
        result = _calc().create_comparative_stat(self._monthly(), self._rest())
        assert result["team_name"] == "Alpha"

    def test_delta_positive_when_monthly_higher(self):
        result = _calc().create_comparative_stat(self._monthly(), self._rest())
        assert result["deltas"]["points_per_game"] > 0

    def test_delta_negative_when_monthly_lower(self):
        result = _calc().create_comparative_stat(self._monthly(), self._rest())
        assert result["deltas"]["turnovers_per_game"] < 0

    def test_delta_zero_when_rest_is_zero(self):
        monthly = dict(self._monthly())
        rest = dict(self._rest())
        rest["assists_per_game"] = 0
        result = _calc().create_comparative_stat(monthly, rest)
        assert result["deltas"]["assists_per_game"] == 0
