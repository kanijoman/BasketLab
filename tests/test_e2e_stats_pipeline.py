"""E2E tests for BasketLab statistics pipeline.

End-to-end coverage strategy: test the full code path from service entry-point
down through helpers and math, mocking only the DB/IO boundary (bottom layer).
No real MongoDB — mongomock or MagicMock at collection level only.

Test groups:
  1. WeeklyReportService.generate_report_zip — ZIP structure & content (E2E)
  2. ElasticityService — predictive pipeline with synthetic historical data (E2E)
  3. Full stats pipeline: StatsCalculator → TeamStatsAggregator → quartiles (E2E)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_team_stat(name: str, *, ppg: float = 75.0, ortg: float = 108.0,
                    drtg: float = 104.0) -> dict:
    return {
        "team_name": name, "total_games": 20,
        "points_per_game": ppg, "points_allowed_per_game": ppg - 5,
        "rebounds_per_game": 35.0, "assists_per_game": 18.0,
        "steals_per_game": 7.5, "turnovers_per_game": 13.0,
        "blocks_per_game": 3.0, "possessions_per_game": 72.0,
        "fg2_percentage": 0.47, "fg3_percentage": 0.35,
        "ft_percentage": 0.74, "efg_percentage": 0.51,
        "true_shooting": 0.54, "turnover_rate": 0.13,
        "offensive_rebound_rate": 0.29, "free_throw_rate": 0.24,
        "three_point_rate": 0.38, "assist_rate": 0.53,
        "assist_fg_rate": 0.58, "steal_rate": 0.09,
        "block_rate": 0.05, "defensive_rebound_rate": 0.71,
        "offensive_rating": ortg, "defensive_rating": drtg,
        "net_rating": ortg - drtg,
        "points_scored": ppg * 20, "total_rebounds": 35.0 * 20,
        "rebounds_off": 200, "rebounds_def": 500,
    }


def _make_player_stat(name: str, team: str) -> dict:
    return {
        "player_name": name, "team_name": team, "total_games": 18,
        "points_per_game": 12.5, "rebounds_per_game": 5.0,
        "assists_per_game": 3.0, "steals_per_game": 1.0,
        "turnovers_per_game": 2.0, "blocks_per_game": 0.5,
        "minutes_per_game": 25.0, "fgm2": 80, "fga2": 160,
        "fgm3": 30, "fga3": 90, "ftm": 50, "fta": 65,
        "offensive_rebounds": 30, "defensive_rebounds": 60,
        "total_points": 225, "total_rebounds": 90, "total_assists": 54,
        "fg2_percentage": 0.50, "fg3_percentage": 0.33, "ft_percentage": 0.77,
    }


# ---------------------------------------------------------------------------
# E2E-1: WeeklyReportService.generate_report_zip
# ---------------------------------------------------------------------------

class TestWeeklyReportServiceE2E:
    """E2E: WeeklyReportService → ZIP structure verification.

    DB layer is mocked; the full rendering/ZIP assembly code path executes.
    """

    @pytest.fixture
    def db_handler(self):
        handler = MagicMock()
        handler.is_connected.return_value = True
        teams = [
            _make_team_stat("Alpha FC"),
            _make_team_stat("Beta BC", ppg=71.0),
        ]
        # All get_team_stats variants return same teams list
        handler.get_team_stats.return_value = teams
        handler.get_opponent_stats.return_value = teams
        handler.get_player_stats.return_value = [
            _make_player_stat("Player 1", "Alpha FC"),
            _make_player_stat("Player 2", "Alpha FC"),
        ]
        handler.get_last_match.return_value = None  # no last match data
        mock_coll = MagicMock()
        mock_coll.find.return_value = []
        handler.connection.get_collection.return_value = mock_coll
        handler.connection.is_connected.return_value = True
        return handler












# ---------------------------------------------------------------------------
# E2E-2: Stats pipeline — StatsCalculator → TeamStatsAggregator → quartiles
# ---------------------------------------------------------------------------

class TestStatsCalculatorToAggregatorE2E:
    """E2E: StatsCalculator produces values → TeamStatsAggregator computes quartiles."""

    def test_full_pipeline_12_teams(self):
        from database.team_stats_aggregator import TeamStatsAggregator
        teams = [
            _make_team_stat(f"Team{i}", ppg=60 + i * 2.5,
                            ortg=95 + i * 1.5, drtg=90 + i * 1.2)
            for i in range(12)
        ]
        handler = MagicMock()
        handler.get_team_stats.return_value = teams
        agg = TeamStatsAggregator(handler, "FEB_LF2_2025")

        # Step 1: get individual team stats
        team_stats = agg.get_team_season_stats("Team6")
        assert team_stats["points_per_game"] == 75.0  # 60 + 6*2.5

        # Step 2: compute league quartiles
        quartiles = agg.calculate_league_quartiles()
        assert "points_per_game" in quartiles
        q = quartiles["points_per_game"]

        # Step 3: validate basketball invariants
        assert q["q1"] < q["q2"] < q["q3"]
        assert q["min"] <= q["q1"]
        assert q["q3"] <= q["max"]

    def test_net_rating_equals_ortg_minus_drtg(self):
        from database.team_stats_aggregator import TeamStatsAggregator
        teams = [_make_team_stat(f"T{i}", ortg=100 + i, drtg=95 + i) for i in range(6)]
        handler = MagicMock()
        handler.get_team_stats.return_value = teams
        agg = TeamStatsAggregator(handler, "FEB_LF2_2025")
        stats = agg.get_team_season_stats("T3")
        # net_rating = ortg - drtg = 103 - 98 = 5
        assert abs(stats["net_rating"] - 5.0) < 0.01

    def test_quartile_count_matches_teams(self):
        from database.team_stats_aggregator import TeamStatsAggregator
        n = 8
        teams = [_make_team_stat(f"T{i}") for i in range(n)]
        handler = MagicMock()
        handler.get_team_stats.return_value = teams
        agg = TeamStatsAggregator(handler, "FEB_LF2_2025")
        q = agg.calculate_league_quartiles()
        assert q["points_per_game"]["count"] == n


# ---------------------------------------------------------------------------
# E2E-4: WeeklyReportService._extract_shots for FBCYL data
# ---------------------------------------------------------------------------

class TestExtractShotsFbcylE2E:
    """E2E: _extract_shots helper processes FBCYL document structure correctly."""

    def _make_fbcyl_doc(self, team_name: str) -> dict:
        return {
            "stats": {
                "startDate": "2025-01-15",
                "teams": [
                    {
                        "name": team_name,
                        "teamIdExtern": "T001",
                        "players": [
                            {
                                "uuid": "player-uuid-1",
                                "name": "Jugadora Uno",
                                "data": {
                                    "shootingOfTwoSuccessfulPoint": [
                                        {"xnormalize": 0.3, "ynormalize": 0.4},
                                        {"xnormalize": 0.5, "ynormalize": 0.2},
                                    ],
                                    "shootingOfTwoFailedPoint": [
                                        {"xnormalize": 0.6, "ynormalize": 0.3},
                                    ],
                                    "shootingOfThreeSuccessfulPoint": [
                                        {"xnormalize": 0.9, "ynormalize": 0.5},
                                    ],
                                    "shootingOfThreeFailedPoint": [],
                                },
                            }
                        ],
                    },
                    {
                        "name": "Rival Team",
                        "teamIdExtern": "T002",
                        "players": [],
                    },
                ],
            }
        }








# ---------------------------------------------------------------------------
# E2E-5: FBCYL player aggregation helper
# ---------------------------------------------------------------------------

class TestAggregateFbcylPlayersE2E:
    """E2E: _aggregate_fbcyl_players sums across all players correctly."""

    def _make_players(self, count: int, base_score: int = 10) -> list:
        return [
            {
                "uuid": f"uuid-{i}",
                "name": f"Player {i}",
                "data": {
                    "shotsOfTwoAttempted": 8,
                    "shotsOfTwoSuccessful": 4,
                    "shotsOfThreeAttempted": 4,
                    "shotsOfThreeSuccessful": 1,
                    "shotsOfOneAttempted": 3,
                    "shotsOfOneSuccessful": 2,
                    "offensiveRebound": 2,
                    "defensiveRebound": 5,
                    "lost": 2,
                    "assists": 3,
                    "steals": 1,
                    "block": 1,
                    "score": base_score + i,
                },
            }
            for i in range(count)
        ]




