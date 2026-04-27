"""Tests for IndividualScoutingDocxBuilder.

Covers:
- Constructor initializes attributes correctly (FEB + FBCYL)
- build() returns b'' when no players for the requested team
- build() returns valid DOCX bytes when players exist
- Module-level helpers: _safe, _fmt_min, _quartile_fill
"""

import io
import zipfile
import pytest
from unittest.mock import MagicMock, patch

from src.services.individual_scouting_service import (
    IndividualScoutingDocxBuilder,
    _safe,
    _fmt_min,
    _quartile_fill,
)


# ---------------------------------------------------------------------------
# Minimal player dict matching PlayerStatsService output keys
# ---------------------------------------------------------------------------

def _make_player(name: str = "Player One", team: str = "Team A") -> dict:
    return {
        "player_name": name,
        "team_name": team,
        "player_id": "p001",
        "games_played": 5,
        "points_per_game": 10.2,
        "rebounds_per_game": 4.0,
        "offensive_rebounds_per_game": 1.2,
        "defensive_rebounds_per_game": 2.8,
        "assists_per_game": 3.5,
        "steals_per_game": 1.0,
        "turnovers_per_game": 1.5,
        "blocks_per_game": 0.5,
        "fouls_per_game": 2.2,
        "valoracion_per_game": 12.0,
        "pllss_per_game": 8.5,
        "minutes_per_game": 25.5,
        "fg1_percentage": 75.0,
        "fg2_percentage": 48.0,
        "fg3_percentage": 33.0,
        "true_shooting": 52.0,
        "usage_pct": 18.0,
        "tov_pct_adv": 12.0,
        "total_pts": 51,
        "total_p1m": 15, "total_p1a": 20,
        "total_p2m": 12, "total_p2a": 25,
        "total_p3m": 4, "total_p3a": 12,
        "total_ro": 6, "total_rd": 14, "total_rt": 20,
        "total_assist": 17, "total_st": 5, "total_to": 7,
        "total_bs": 2, "total_fp": 11,
        "total_minutes": 127.5,
        "dorsal": "7",
        "license": "LIC001",
        "projection_30_pts": 12.0,
        "projection_30_reb": 4.7,
        "projection_30_ast": 4.1,
        "projection_30_stl": 1.2,
        "projection_30_tov": 1.8,
        "projection_30_blk": 0.6,
        "projection_30_val": 14.1,
        "projection_30_p2a": 10.0, "projection_30_p2m": 4.8,
        "projection_30_p3a": 5.6, "projection_30_p3m": 1.9,
        "projection_30_p1a": 2.4, "projection_30_p1m": 1.8,
        "projection_30_ro": 1.4, "projection_30_rd": 3.3,
    }


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestIndividualScoutingDocxBuilderInit:
    def test_feb_collection_sets_is_fbcyl_false(self):
        db = MagicMock()
        b = IndividualScoutingDocxBuilder("FEB_LF2_2025_A", "Team A", db)
        assert b.is_fbcyl is False

    def test_fbcyl_collection_sets_is_fbcyl_true(self):
        db = MagicMock()
        b = IndividualScoutingDocxBuilder("FBCYL_SE_2025", "Team A", db)
        assert b.is_fbcyl is True

    def test_stores_include_ai_notes_flag(self):
        db = MagicMock()
        b = IndividualScoutingDocxBuilder("FEB_LF2_2025_A", "T", db, include_ai_notes=False)
        assert b.include_ai_notes is False

    def test_default_provider_is_groq(self):
        db = MagicMock()
        b = IndividualScoutingDocxBuilder("FEB_LF2_2025_A", "T", db)
        assert b.provider == "groq"


# ---------------------------------------------------------------------------
# build() — empty collection
# ---------------------------------------------------------------------------

class TestBuildEmptyCollection:
    def test_returns_empty_bytes_when_no_players_in_team(self):
        db = MagicMock()
        builder = IndividualScoutingDocxBuilder("FEB_LF2_2025_A", "NonExistentTeam", db)

        with patch("src.services.player_stats_service.PlayerStatsService") as MockSvc:
            MockSvc.return_value.load_season_data.return_value = []
            result = builder.build()

        assert result == b""

    def test_returns_empty_bytes_when_players_exist_but_wrong_team(self):
        db = MagicMock()
        builder = IndividualScoutingDocxBuilder("FEB_LF2_2025_A", "Different Team", db)
        players = [_make_player(team="Team A"), _make_player("P2", "Team B")]

        with patch("src.services.player_stats_service.PlayerStatsService") as MockSvc:
            MockSvc.return_value.load_season_data.return_value = players
            result = builder.build()

        assert result == b""


# ---------------------------------------------------------------------------
# build() — with players (DOCX output)
# ---------------------------------------------------------------------------

class TestBuildWithPlayers:
    def _mock_fetcher(self):
        fetcher = MagicMock()
        fetcher.get_player_dorsal_and_photo.return_value = ("7", None, None)
        return fetcher

    def _mock_shot_chart(self):
        fig = MagicMock()
        fig.savefig = MagicMock()
        return fig

    def test_returns_bytes(self):
        db = MagicMock()
        builder = IndividualScoutingDocxBuilder(
            "FEB_LF2_2025_A", "Team A", db, include_ai_notes=False
        )
        players = [_make_player("Player One", "Team A")]

        with (
            patch("src.services.player_stats_service.PlayerStatsService") as MockSvc,
            patch("src.services.player_data_fetcher.PlayerDataFetcher") as MockFetch,
            patch("src.services.individual_scouting_service._fetch_bytes", return_value=None),
            patch("src.services.individual_scouting_service._extract_shots", return_value=[]),
            patch("src.shotcharts.shot_visualizer.ShotChartVisualizer") as MockVis,
            patch("src.shotcharts.zone_analysis.ZoneAnalyzer") as MockZones,
        ):
            MockSvc.return_value.load_season_data.return_value = players
            MockFetch.return_value.get_player_dorsal_and_photo.return_value = ("7", None, None)
            MockFetch.return_value.get_player_birth_info.return_value = (None, None, None)
            mock_fig = MagicMock()
            mock_fig.savefig = MagicMock()
            MockVis.return_value.create_shot_chart.return_value = mock_fig
            MockZones.return_value.analyze_zones.return_value = {}
            MockZones.return_value.create_zone_chart.return_value = mock_fig

            result = builder.build()

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_is_valid_docx_zip(self):
        db = MagicMock()
        builder = IndividualScoutingDocxBuilder(
            "FEB_LF2_2025_A", "Team A", db, include_ai_notes=False
        )
        players = [_make_player("Player One", "Team A")]

        with (
            patch("src.services.player_stats_service.PlayerStatsService") as MockSvc,
            patch("src.services.player_data_fetcher.PlayerDataFetcher") as MockFetch,
            patch("src.services.individual_scouting_service._fetch_bytes", return_value=None),
            patch("src.services.individual_scouting_service._extract_shots", return_value=[]),
            patch("src.shotcharts.shot_visualizer.ShotChartVisualizer") as MockVis,
            patch("src.shotcharts.zone_analysis.ZoneAnalyzer") as MockZones,
        ):
            MockSvc.return_value.load_season_data.return_value = players
            MockFetch.return_value.get_player_dorsal_and_photo.return_value = ("7", None, None)
            MockFetch.return_value.get_player_birth_info.return_value = (None, None, None)
            mock_fig = MagicMock()
            mock_fig.savefig = MagicMock()
            MockVis.return_value.create_shot_chart.return_value = mock_fig
            MockZones.return_value.analyze_zones.return_value = {}
            MockZones.return_value.create_zone_chart.return_value = mock_fig

            result = builder.build()

        # DOCX is a ZIP archive — valid bytes start with PK signature
        assert result[:2] == b"PK"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

class TestSafeHelper:
    def test_none_returns_dash(self):
        assert _safe(None) == "-"

    def test_numeric_formats_one_decimal(self):
        assert _safe(10.567) == "10.6"

    def test_zero_decimals(self):
        assert _safe(10.0, decimals=0) == "10"

    def test_suffix_appended(self):
        assert _safe(45.5, suffix="%") == "45.5%"

    def test_non_numeric_returns_string(self):
        assert _safe("N/A") == "N/A"


class TestFmtMinHelper:
    def test_none_returns_dash(self):
        assert _fmt_min(None) == "-"

    def test_whole_minutes(self):
        assert _fmt_min(25.0) == "25:00"

    def test_fractional_minutes(self):
        assert _fmt_min(25.5) == "25:30"

    def test_zero(self):
        assert _fmt_min(0.0) == "0:00"


class TestQuartileFill:
    def test_returns_none_for_none_value(self):
        assert _quartile_fill(None, [1.0, 2.0, 3.0, 4.0]) is None

    def test_returns_none_for_small_sample(self):
        assert _quartile_fill(3.0, [1.0, 2.0]) is None

    def test_top_quartile_returns_green(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        result = _quartile_fill(8.0, vals, reverse=False)
        assert result == "C6EFCE"

    def test_bottom_quartile_returns_red(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        result = _quartile_fill(1.0, vals, reverse=False)
        assert result == "FFC7CE"

    def test_reverse_inverts_colors(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        # With reverse=True, lowest value (1.0) should be green (best)
        result = _quartile_fill(1.0, vals, reverse=True)
        assert result == "C6EFCE"
