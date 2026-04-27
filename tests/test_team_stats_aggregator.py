"""Unit tests for TeamStatsAggregator — covers 15% → ~80%.

Tests:
- __init__: stores db_handler and collection_name
- get_team_season_stats: happy path FEB, team not found, empty list, exception
- calculate_league_quartiles: happy path, empty, <4 teams, exception, field extraction
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.team_stats_aggregator import TeamStatsAggregator


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_team_row(**kwargs):
    """Return a minimal team stat row matching DB schema."""
    base = {
        "team_name": "Alpha FC",
        "total_games": 20,
        "points_per_game": 75.0,
        "points_allowed_per_game": 70.0,
        "rebounds_per_game": 35.0,
        "assists_per_game": 18.0,
        "steals_per_game": 8.0,
        "turnovers_per_game": 14.0,
        "blocks_per_game": 3.0,
        "possessions_per_game": 72.0,
        "fg2_percentage": 0.48,
        "fg3_percentage": 0.35,
        "ft_percentage": 0.75,
        "efg_percentage": 0.51,
        "true_shooting": 0.54,
        "turnover_rate": 0.13,
        "offensive_rebound_rate": 0.30,
        "free_throw_rate": 0.25,
        "three_point_rate": 0.38,
        "assist_rate": 0.55,
        "assist_fg_rate": 0.60,
        "steal_rate": 0.09,
        "block_rate": 0.05,
        "defensive_rebound_rate": 0.72,
        "offensive_rating": 108.5,
        "defensive_rating": 103.2,
        "net_rating": 5.3,
        "points_scored": 1500,
        "total_rebounds": 700,
        "rebounds_off": 200,
        "rebounds_def": 500,
    }
    base.update(kwargs)
    return base


def _make_handler(team_rows: list) -> MagicMock:
    handler = MagicMock()
    handler.get_team_stats.return_value = team_rows
    return handler


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_stores_db_handler(self):
        handler = MagicMock()
        agg = TeamStatsAggregator(handler, "FEB_test")
        assert agg.db_handler is handler

    def test_stores_collection_name(self):
        agg = TeamStatsAggregator(MagicMock(), "FEB_test")
        assert agg.collection_name == "FEB_test"


# ---------------------------------------------------------------------------
# get_team_season_stats
# ---------------------------------------------------------------------------

class TestGetTeamSeasonStats:
    def test_returns_dict_for_known_team(self):
        handler = _make_handler([_make_team_row()])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        assert isinstance(result, dict)

    def test_games_played_correct(self):
        handler = _make_handler([_make_team_row(total_games=20)])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        assert result["games_played"] == 20.0

    def test_points_per_game_correct(self):
        handler = _make_handler([_make_team_row(points_per_game=75.5)])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        assert result["points_per_game"] == 75.5

    def test_offensive_rating_correct(self):
        handler = _make_handler([_make_team_row(offensive_rating=110.0)])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        assert result["offensive_rating"] == 110.0

    def test_team_not_found_returns_empty_dict(self):
        handler = _make_handler([_make_team_row(team_name="Other Team")])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Unknown Team")
        assert result == {}

    def test_empty_list_returns_empty_dict(self):
        handler = _make_handler([])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        assert result == {}

    def test_exception_returns_empty_dict(self):
        handler = MagicMock()
        handler.get_team_stats.side_effect = RuntimeError("DB error")
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        assert result == {}

    def test_net_rating_derived(self):
        handler = _make_handler([_make_team_row(net_rating=7.5)])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        assert result["net_rating"] == 7.5

    def test_multiple_teams_selects_correct_one(self):
        rows = [
            _make_team_row(team_name="Alpha FC", points_per_game=70.0),
            _make_team_row(team_name="Beta BC", points_per_game=85.0),
        ]
        handler = _make_handler(rows)
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Beta BC")
        assert result["points_per_game"] == 85.0

    def test_returns_all_expected_keys(self):
        handler = _make_handler([_make_team_row()])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.get_team_season_stats("Alpha FC")
        for key in ("games_played", "points_per_game", "offensive_rating",
                    "defensive_rating", "net_rating", "fg2_percentage",
                    "fg3_percentage", "ft_percentage", "assists_per_game"):
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# calculate_league_quartiles
# ---------------------------------------------------------------------------

def _make_12_teams() -> list:
    """12 teams with varied stats for quartile calculation."""
    return [
        _make_team_row(team_name=f"Team{i}", points_per_game=60.0 + i * 2.5,
                       offensive_rating=95.0 + i * 1.5,
                       defensive_rating=90.0 + i * 1.2,
                       net_rating=(95.0 + i * 1.5) - (90.0 + i * 1.2),
                       efg_percentage=0.42 + i * 0.01,
                       true_shooting=0.50 + i * 0.01,
                       turnover_rate=0.10 + i * 0.005,
                       offensive_rebound_rate=0.25 + i * 0.01)
        for i in range(12)
    ]


class TestCalculateLeagueQuartiles:
    def test_returns_dict(self):
        handler = _make_handler(_make_12_teams())
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        assert isinstance(result, dict)

    def test_points_per_game_quartile_exists(self):
        handler = _make_handler(_make_12_teams())
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        assert "points_per_game" in result

    def test_quartile_has_required_keys(self):
        handler = _make_handler(_make_12_teams())
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        q = result["points_per_game"]
        for key in ("q1", "q2", "q3", "min", "max", "count"):
            assert key in q, f"Quartile missing key: {key}"

    def test_q1_less_than_q2_less_than_q3(self):
        handler = _make_handler(_make_12_teams())
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        q = result["points_per_game"]
        assert q["q1"] <= q["q2"] <= q["q3"]

    def test_min_max_bounds(self):
        handler = _make_handler(_make_12_teams())
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        q = result["points_per_game"]
        assert q["min"] <= q["q1"]
        assert q["q3"] <= q["max"]

    def test_count_equals_team_count(self):
        teams = _make_12_teams()
        handler = _make_handler(teams)
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        assert result["points_per_game"]["count"] == 12

    def test_fewer_than_4_teams_excluded(self):
        """Quartiles need ≥4 data points; with 3 teams no quartile returned."""
        rows = [_make_team_row(team_name=f"T{i}", points_per_game=60.0 + i)
                for i in range(3)]
        handler = _make_handler(rows)
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        assert "points_per_game" not in result

    def test_empty_list_returns_empty_dict(self):
        handler = _make_handler([])
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        assert result == {}

    def test_exception_returns_empty_dict(self):
        handler = MagicMock()
        handler.get_team_stats.side_effect = RuntimeError("DB error")
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        assert result == {}

    def test_offensive_rating_quartile_values_reasonable(self):
        """ORtg values for 12 teams should produce q2 near midpoint."""
        handler = _make_handler(_make_12_teams())
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        q = result["offensive_rating"]
        # Teams go 95, 96.5, ..., 111.5 → median ≈ 103.25
        assert 100 <= q["q2"] <= 106

    def test_net_rating_quartile_present(self):
        handler = _make_handler(_make_12_teams())
        agg = TeamStatsAggregator(handler, "FEB_test")
        result = agg.calculate_league_quartiles()
        assert "net_rating" in result
