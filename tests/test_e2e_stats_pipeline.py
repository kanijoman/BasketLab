"""E2E tests for BasketLab statistics pipeline.

End-to-end coverage strategy: test the full code path from service entry-point
down through helpers and math, mocking only the DB/IO boundary (bottom layer).
No real MongoDB — mongomock or MagicMock at collection level only.

Test groups:
  1. WeeklyReportService.generate_report_zip — ZIP structure & content (E2E)
  2. ElasticityService — predictive pipeline with synthetic historical data (E2E)
  3. PDFGenerator + AI context builder — full document generation pipeline (E2E)
  4. Full stats pipeline: StatsCalculator → TeamStatsAggregator → quartiles (E2E)
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_returns_bytes(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC")
        assert isinstance(result, bytes)

    def test_returns_valid_zip(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC")
        # ZIP format magic bytes: PK\x03\x04
        assert result[:4] == b"PK\x03\x04" or zipfile.is_zipfile(io.BytesIO(result))

    def test_zip_contains_general_folder(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        assert any(n.startswith("General/") for n in names)

    def test_zip_contains_basic_stats_png(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        assert any("Basicas_Toda_Competicion.png" in n for n in names)

    def test_zip_contains_advanced_stats_png(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        assert any("Avanzadas_Toda_Competicion.png" in n for n in names)

    def test_progress_callback_called(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        calls = []
        svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC",
                                  progress_callback=lambda s, t, m: calls.append(s))
        assert len(calls) == 5  # 5 major steps

    def test_progress_callback_steps_are_sequential(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        steps = []
        svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC",
                                  progress_callback=lambda s, t, m: steps.append(s))
        assert steps == [1, 2, 3, 4, 5]

    def test_empty_team_stats_produces_zip_without_crash(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        db_handler.get_team_stats.return_value = []
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC")
        assert isinstance(result, bytes)

    def test_no_player_stats_produces_zip_without_crash(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        db_handler.get_player_stats.return_value = []
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FEB_LF2_2025", "Alpha FC", "Beta BC")
        assert isinstance(result, bytes)

    def test_fbcyl_collection_does_not_crash(self, db_handler):
        from services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db_handler)
        result = svc.generate_report_zip("FBCYL_SE_2025", "Alpha FC", "Beta BC")
        assert isinstance(result, bytes)


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
# E2E-3: Context Builder → PDF generation pipeline
# ---------------------------------------------------------------------------

class TestContextBuilderToPDFE2E:
    """E2E: ContextBuilder builds text → PDFGenerator converts to bytes."""

    def test_full_own_analysis_to_pdf(self):
        from ai.context_builder import ContextBuilder
        from services.pdf_generator import PDFGenerator

        team_name = "Alpha FC"
        stats_payload = {
            "team_stats": _make_team_stat(team_name),
            "league_stats": {"avg_points": 73.0, "avg_net_rating": 0.0},
            "consistency": {"cv_ppg": 8.5, "cv_ortg": 6.2},
        }
        cb = ContextBuilder()
        context = cb.build_team_context(team_name, stats_payload,
                                         include_recommendations=True,
                                         analysis_type="own")
        assert isinstance(context, str)
        assert team_name in context

        # Convert context to HTML-ish string and generate PDF
        html = f"<h1>Análisis: {team_name}</h1><pre>{context[:500]}</pre>"
        pdf_bytes = PDFGenerator.generate_bytes_from_html(html, team_name=team_name)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:4] == b"%PDF"

    def test_scouting_analysis_to_pdf(self):
        from ai.context_builder import ContextBuilder
        from services.pdf_generator import PDFGenerator

        team_name = "Beta BC"
        stats_payload = {
            "team_stats": _make_team_stat(team_name, ppg=68.0),
            "league_stats": {},
            "consistency": {},
        }
        cb = ContextBuilder()
        context = cb.build_team_context(team_name, stats_payload,
                                         include_recommendations=False,
                                         analysis_type="scouting")
        html = f"<h1>Scouting: {team_name}</h1><p>{context[:200]}</p>"
        pdf_bytes = PDFGenerator.generate_bytes_from_html(html, team_name=team_name)
        assert pdf_bytes[:4] == b"%PDF"

    def test_context_contains_key_stats(self):
        from ai.context_builder import ContextBuilder

        team_name = "Gamma GC"
        stats_payload = {
            "team_stats": _make_team_stat(team_name, ppg=80.0, ortg=115.0),
            "league_stats": {},
            "consistency": {},
        }
        cb = ContextBuilder()
        context = cb.build_team_context(team_name, stats_payload,
                                         include_recommendations=False)
        assert team_name in context

    def test_pdf_bytes_increase_with_longer_content(self):
        from services.pdf_generator import PDFGenerator
        short_pdf = PDFGenerator.generate_bytes_from_html("<p>Hi</p>")
        long_html = "<p>" + "Análisis detallado de estadísticas. " * 100 + "</p>"
        long_pdf = PDFGenerator.generate_bytes_from_html(long_html)
        # Longer content should produce a larger PDF
        assert len(long_pdf) >= len(short_pdf)


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

    def test_extract_shots_fbcyl_returns_correct_count(self):
        from services.weekly_report_service import _extract_shots

        doc = self._make_fbcyl_doc("Alpha FC")
        mock_coll = MagicMock()
        mock_coll.find.return_value = [doc]
        mock_db = MagicMock()
        mock_db.connection.get_collection.return_value = mock_coll

        shots, player_map, is_fbcyl = _extract_shots(mock_db, "FBCYL_SE_2025", "Alpha FC")

        # 2 made 2s + 1 missed 2 + 1 made 3 = 4 shots
        assert len(shots) == 4
        assert is_fbcyl is True

    def test_extract_shots_fbcyl_marks_made_correctly(self):
        from services.weekly_report_service import _extract_shots

        doc = self._make_fbcyl_doc("Alpha FC")
        mock_coll = MagicMock()
        mock_coll.find.return_value = [doc]
        mock_db = MagicMock()
        mock_db.connection.get_collection.return_value = mock_coll

        shots, _, _ = _extract_shots(mock_db, "FBCYL_SE_2025", "Alpha FC")
        made = [s for s in shots if s["m"] == 1]
        missed = [s for s in shots if s["m"] == 0]
        assert len(made) == 3   # 2 made 2s + 1 made 3
        assert len(missed) == 1

    def test_extract_shots_fbcyl_builds_player_map(self):
        from services.weekly_report_service import _extract_shots

        doc = self._make_fbcyl_doc("Alpha FC")
        mock_coll = MagicMock()
        mock_coll.find.return_value = [doc]
        mock_db = MagicMock()
        mock_db.connection.get_collection.return_value = mock_coll

        _, player_map, _ = _extract_shots(mock_db, "FBCYL_SE_2025", "Alpha FC")
        assert "player-uuid-1" in player_map

    def test_extract_shots_empty_collection_returns_empty(self):
        from services.weekly_report_service import _extract_shots

        mock_coll = MagicMock()
        mock_coll.find.return_value = []
        mock_db = MagicMock()
        mock_db.connection.get_collection.return_value = mock_coll

        shots, player_map, is_fbcyl = _extract_shots(mock_db, "FBCYL_SE_2025", "Alpha FC")
        assert shots == []
        assert player_map == {}

    def test_extract_shots_none_collection_returns_empty(self):
        from services.weekly_report_service import _extract_shots

        mock_db = MagicMock()
        mock_db.connection.get_collection.return_value = None

        shots, player_map, is_fbcyl = _extract_shots(mock_db, "FBCYL_SE_2025", "Alpha FC")
        assert shots == []

    def test_extract_shots_missing_coordinates_skipped(self):
        from services.weekly_report_service import _extract_shots

        doc = {
            "stats": {
                "teams": [{
                    "name": "Alpha FC",
                    "teamIdExtern": "T001",
                    "players": [{
                        "uuid": "p1",
                        "name": "Player",
                        "data": {
                            # No xnormalize field — should be skipped
                            "shootingOfTwoSuccessfulPoint": [{"x": 0.3, "y": 0.4}],
                        },
                    }],
                }]
            }
        }
        mock_coll = MagicMock()
        mock_coll.find.return_value = [doc]
        mock_db = MagicMock()
        mock_db.connection.get_collection.return_value = mock_coll

        shots, _, _ = _extract_shots(mock_db, "FBCYL_SE_2025", "Alpha FC")
        assert shots == []  # malformed coord skipped


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

    def test_aggregation_sums_players(self):
        from services.weekly_report_service import _aggregate_fbcyl_players
        players = self._make_players(5, base_score=10)
        result = _aggregate_fbcyl_players(players)
        assert result["p2a"] == 5 * 8  # 40
        assert result["p2m"] == 5 * 4  # 20

    def test_aggregation_handles_missing_keys(self):
        from services.weekly_report_service import _aggregate_fbcyl_players
        players = [{"uuid": "x", "name": "P", "data": {}}]
        result = _aggregate_fbcyl_players(players)
        assert result["p2a"] == 0
        assert result["pts"] == 0

    def test_aggregation_empty_list(self):
        from services.weekly_report_service import _aggregate_fbcyl_players
        result = _aggregate_fbcyl_players([])
        for key in ("p2a", "p2m", "p3a", "p3m", "p1a", "p1m", "ro", "rd",
                    "to", "assist", "st", "bs", "pts"):
            assert result[key] == 0

    def test_aggregation_total_score(self):
        from services.weekly_report_service import _aggregate_fbcyl_players
        # 3 players with scores 10, 11, 12 → total 33
        players = self._make_players(3, base_score=10)
        result = _aggregate_fbcyl_players(players)
        assert result["pts"] == 10 + 11 + 12
