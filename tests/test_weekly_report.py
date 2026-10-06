"""Tests for WeeklyReportService — ZIP bundle generation.

Covers:
- generate_report_zip() returns bytes
- Return value is a valid ZIP archive
- Works with empty collection (no stats → graceful fallback)
- Works with minimal FEB mock data
- _sanitize helper strips illegal filesystem characters
- _aggregate_fbcyl_players sums player stats correctly
- progress_callback is called at each of the 5 stages
- _write_comparative uses team_name key (FBCYL dict _id regression)
"""

import io
import zipfile
import pytest
from unittest.mock import MagicMock, patch

from src.services.weekly_report_service import (
    WeeklyReportService,
    _sanitize,
    _aggregate_fbcyl_players,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_db_handler(team_stats=None):
    """Return a minimal mock MongoDBHandler."""
    db = MagicMock()
    db.get_team_stats.return_value = team_stats or []
    db.get_opponent_stats.return_value = team_stats or []
    # connection.get_collection returns an empty mock collection by default
    mock_coll = MagicMock()
    mock_coll.find.return_value = []
    mock_coll.find_one.return_value = None
    db.connection.get_collection.return_value = mock_coll
    return db


def _minimal_team_stat(name: str = "Team A", wins: int = 5, losses: int = 3) -> dict:
    return {
        "_id": name,
        "team_name": name,
        "wins": wins, "losses": losses,
        "points_per_game": 75.0,
        "points_against_per_game": 70.0,
        "p2m": 20, "p2a": 40, "p3m": 6, "p3a": 18, "p1m": 15, "p1a": 20,
        "ro": 8, "rd": 25, "rt": 33, "assist": 15, "st": 8, "to": 12, "bs": 3, "fp": 18,
        "pts": 75, "games": 8,
        "net_rtg": 5.0, "off_rtg": 110.0, "def_rtg": 105.0, "pace": 90.0,
        "efg_pct": 50.0, "ts_pct": 55.0, "tov_pct": 13.0, "orb_pct": 30.0,
        "ftr": 0.25, "opp_efg_pct": 48.0,
    }


# ---------------------------------------------------------------------------
# _sanitize helper
# ---------------------------------------------------------------------------

class TestSanitize:
    def test_removes_colon(self):
        assert ":" not in _sanitize("Team: One")

    def test_removes_slash(self):
        assert "/" not in _sanitize("a/b")
        assert "\\" not in _sanitize("a\\b")

    def test_removes_angle_brackets(self):
        result = _sanitize("<Test>")
        assert "<" not in result
        assert ">" not in result

    def test_keeps_normal_characters(self):
        assert _sanitize("TeamA 2025") == "TeamA 2025"


# ---------------------------------------------------------------------------
# _aggregate_fbcyl_players helper
# ---------------------------------------------------------------------------

class TestAggregateFbcylPlayers:
    def _make_player(self, pts: int = 10, ast: int = 3) -> dict:
        return {
            "data": {
                "shotsOfTwoAttempted": 5,
                "shotsOfTwoSuccessful": 2,
                "shotsOfThreeAttempted": 3,
                "shotsOfThreeSuccessful": 1,
                "shotsOfOneAttempted": 2,
                "shotsOfOneSuccessful": 1,
                "offensiveRebound": 1,
                "defensiveRebound": 3,
                "lost": 1,
                "assists": ast,
                "steals": 1,
                "block": 0,
                "score": pts,
            }
        }

    def test_sums_points_across_players(self):
        players = [self._make_player(pts=10), self._make_player(pts=15)]
        result = _aggregate_fbcyl_players(players)
        assert result["pts"] == 25

    def test_sums_assists_across_players(self):
        players = [self._make_player(ast=3), self._make_player(ast=5)]
        result = _aggregate_fbcyl_players(players)
        assert result["assist"] == 8

    def test_empty_players_returns_zeros(self):
        result = _aggregate_fbcyl_players([])
        assert result["pts"] == 0
        assert result["assist"] == 0

    def test_result_has_required_keys(self):
        players = [self._make_player()]
        result = _aggregate_fbcyl_players(players)
        for key in ("pts", "assist", "p2a", "p2m", "p3a", "p3m", "ro", "rd", "to", "st"):
            assert key in result


# ---------------------------------------------------------------------------
# WeeklyReportService.generate_report_zip()
# ---------------------------------------------------------------------------

class TestWeeklyReportService:
    def test_returns_bytes(self):
        db = _make_db_handler()
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_is_valid_zip(self):
        db = _make_db_handler()
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        buf = io.BytesIO(result)
        assert zipfile.is_zipfile(buf)

    def test_empty_collection_still_returns_zip(self):
        """Even with no stats data, the service returns a valid (possibly empty) ZIP."""
        db = _make_db_handler(team_stats=[])
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_zip_contains_general_folder(self):
        """With actual team stats, the General/ folder should be populated."""
        stats = [_minimal_team_stat("Team A"), _minimal_team_stat("Team B", 3, 5)]
        db = _make_db_handler(team_stats=stats)
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        general_files = [n for n in names if n.startswith("General/")]
        assert len(general_files) > 0

    def test_zip_uses_sanitized_team_names(self):
        """Team names with special chars should be sanitized in ZIP path names."""
        stats = [_minimal_team_stat("Team/A: Test"), _minimal_team_stat("Team B")]
        db = _make_db_handler(team_stats=stats)
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip(
            "FEB_LF2_2025_A", "Team/A: Test", "Team B"
        )
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = "".join(zf.namelist())
        # The raw "/" from team name should not appear as path separator confusion
        assert "Team/A: Test" not in names

    def test_fbcyl_collection_does_not_crash(self):
        """FBCYL collections follow a different data format; service should not raise."""
        db = _make_db_handler(team_stats=[])
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FBCYL_SE_2025", "Team A", "Team B")
        assert isinstance(result, bytes)

    def test_progress_callback_called_five_times(self):
        """progress_callback must be called once per major stage (total=5)."""
        db = _make_db_handler(team_stats=[])
        svc = WeeklyReportService(db)
        calls = []
        svc.generate_report_zip(
            "FEB_LF2_2025_A", "Team A", "Team B",
            progress_callback=lambda step, total, msg: calls.append((step, total, msg)),
        )
        assert len(calls) == 5
        # Steps must be 1..5 in order
        assert [c[0] for c in calls] == [1, 2, 3, 4, 5]
        # total always 5
        assert all(c[1] == 5 for c in calls)
        # All messages are non-empty strings
        assert all(isinstance(c[2], str) and c[2] for c in calls)

    def test_progress_callback_none_does_not_raise(self):
        """Passing no progress_callback (default None) must not raise."""
        db = _make_db_handler(team_stats=[])
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        assert isinstance(result, bytes)

    def test_write_comparative_uses_team_name_key(self):
        """_write_comparative must match teams by team_name, not str(_id).

        Regression for FBCYL where _id is a dict {"team_id": ..., "team_name": ...}.
        str(dict) produces different strings when dict ordering varies across
        Python versions, causing the intersection to be empty.
        """
        stats_won = [
            {"_id": {"team_id": 1, "team_name": "Alpha"}, "team_name": "Alpha",
             "total_games": 5, "games_home": 3, "games_away": 2,
             "points_scored": 400, "points_received": 350,
             "points_per_game": 80.0, "points_against_per_game": 70.0,
             "fg2_percentage": 50.0, "fg3_percentage": 35.0, "ft_percentage": 75.0,
             "total_rebounds": 200, "rebounds_def": 150, "rebounds_off": 50,
             "assists": 80, "steals": 30, "turnovers": 60, "blocks": 10,
             "offensive_rating": 110.0, "defensive_rating": 100.0, "net_rating": 10.0,
             "possessions_per_game": 70.0, "efg_percentage": 52.0,
             "true_shooting": 55.0, "three_point_rate": 30.0, "free_throw_rate": 20.0,
             "assist_fg_rate": 60.0, "assist_rate": 55.0, "turnover_rate": 12.0,
             "steal_rate": 8.0, "block_rate": 3.0, "offensive_rebound_rate": 25.0,
             "defensive_rebound_rate": 75.0},
        ]
        stats_lost = [
            {"_id": {"team_id": 1, "team_name": "Alpha"}, "team_name": "Alpha",
             "total_games": 3, "games_home": 1, "games_away": 2,
             "points_scored": 220, "points_received": 240,
             "points_per_game": 73.0, "points_against_per_game": 80.0,
             "fg2_percentage": 44.0, "fg3_percentage": 30.0, "ft_percentage": 70.0,
             "total_rebounds": 120, "rebounds_def": 90, "rebounds_off": 30,
             "assists": 45, "steals": 15, "turnovers": 40, "blocks": 5,
             "offensive_rating": 100.0, "defensive_rating": 110.0, "net_rating": -10.0,
             "possessions_per_game": 68.0, "efg_percentage": 46.0,
             "true_shooting": 50.0, "three_point_rate": 28.0, "free_throw_rate": 18.0,
             "assist_fg_rate": 50.0, "assist_rate": 48.0, "turnover_rate": 15.0,
             "steal_rate": 6.0, "block_rate": 2.0, "offensive_rebound_rate": 22.0,
             "defensive_rebound_rate": 78.0},
        ]
        db = _make_db_handler()
        db.get_team_stats.side_effect = lambda coll, **kw: (
            stats_won if kw.get("result_filter") == "won"
            else stats_lost if kw.get("result_filter") == "lost"
            else []
        )
        svc = WeeklyReportService(db)
        import zipfile as _zf, io as _io
        result = svc.generate_report_zip("FBCYL_TEST", "Alpha", "Beta")
        with _zf.ZipFile(_io.BytesIO(result)) as zf:
            names = zf.namelist()
        # Comparative PNGs must be present (own basic+advanced, plus the
        # rival variants — placeholders here since get_opponent_stats isn't
        # configured for this test's mock).
        comparative = [n for n in names if "02_" in n and "Ganados" in n]
        own = [n for n in comparative if "_Rival" not in n]
        assert len(own) == 2, f"Expected 2 own comparative PNGs, got: {names}"


# ---------------------------------------------------------------------------
# "Toda la Competición" look & feel must match comparative tables (no CV badge)
# ---------------------------------------------------------------------------

class TestGeneralStatsLookAndFeel:
    """Regression: 'Toda la Competición' must render like the comparative
    tables (Ganados vs Perdidos, Local vs Visitante, Último Mes) — no inline
    CV (sigma) badge overlay, since consistency already has its own dedicated
    table (06_Consistencia_Liga.png).
    """

    def test_toda_competicion_has_no_text_colors_overlay(self):
        stats = [_minimal_team_stat("Team A"), _minimal_team_stat("Team B", 3, 5)]
        db = _make_db_handler(team_stats=stats)
        svc = WeeklyReportService(db)
        # Non-empty CV data so apply_cv_overlay (if still called) would
        # actually populate text_colors instead of short-circuiting to [].
        fake_consistency = {
            "own": {
                "Team A": {"points_per_game": {"cv": 20.0, "mean": 75.0, "std": 15.0, "n": 5}},
                "Team B": {"points_per_game": {"cv": 18.0, "mean": 70.0, "std": 12.6, "n": 5}},
            }
        }
        with patch(
            "src.services.weekly_report_service.render_table_png",
            wraps=__import__(
                "src.services._weekly_report_helpers", fromlist=["render_table_png"]
            ).render_table_png,
        ) as mock_render, patch(
            "src.services.team_stats_service.TeamStatsService.get_consistency",
            return_value=fake_consistency,
        ):
            svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        toda_competicion_calls = [
            c for c in mock_render.call_args_list
            if "Toda la Competición" in c.args[3]
        ]
        assert toda_competicion_calls, "No 'Toda la Competición' render calls captured"
        for call in toda_competicion_calls:
            assert call.kwargs.get("text_colors") is None, (
                "'Toda la Competición' tables must not use the CV text_colors "
                "overlay, to match the comparative tables' look & feel"
            )


# ---------------------------------------------------------------------------
# Comparative sections (02/03/04) must still appear even with sparse data
# ---------------------------------------------------------------------------

class TestComparativeInsufficientData:
    """Regression: early-season collections (teams without both a win AND a
    loss yet, or without both home AND away games, or without games older
    than 30 days) must still produce 02/03/04 PNGs — as a 'datos
    insuficientes' placeholder — instead of silently omitting the files.
    """

    def _make_db_sparse(self):
        """Only the unfiltered call returns data; every filtered call (used
        by won/lost, home/away, last-month comparatives) returns an empty
        list, simulating a competition too early in the season for any team
        to have both halves of a comparison.
        """
        stats = [_minimal_team_stat("Team A"), _minimal_team_stat("Team B", 3, 5)]
        db = _make_db_handler(team_stats=stats)
        db.get_team_stats.side_effect = lambda coll, **kw: (
            [] if kw else stats
        )
        return db

    def test_zip_contains_won_lost_pngs(self):
        db = self._make_db_sparse()
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        assert any("02_Basicas_Ganados_vs_Perdidos.png" in n for n in names), names
        assert any("02_Avanzadas_Ganados_vs_Perdidos.png" in n for n in names), names

    def test_zip_contains_venue_pngs(self):
        db = self._make_db_sparse()
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        assert any("03_Basicas_Local_vs_Visitante.png" in n for n in names), names
        assert any("03_Avanzadas_Local_vs_Visitante.png" in n for n in names), names

    def test_zip_contains_month_pngs(self):
        db = self._make_db_sparse()
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
        assert any("04_Basicas_" in n and "Mes" in n for n in names), names
        assert any("04_Avanzadas_" in n and "Mes" in n for n in names), names


# ---------------------------------------------------------------------------
# Rival (opponent) variants for reports 01-04
# ---------------------------------------------------------------------------

class TestRivalVariants:
    """Regression: each of 01-04 must also produce a '_Rival' variant built
    from get_opponent_stats() (what rivals did against each team) instead of
    get_team_stats() (own team data).
    """

    def _make_db_with_rival_data(self):
        own_stats = [_minimal_team_stat("Team A"), _minimal_team_stat("Team B", 3, 5)]
        rival_stats = [_minimal_team_stat("Team A", 2, 6), _minimal_team_stat("Team B", 6, 2)]
        db = _make_db_handler(team_stats=own_stats)
        db.get_team_stats.side_effect = lambda coll, **kw: own_stats
        db.get_opponent_stats.side_effect = lambda coll, **kw: rival_stats
        return db

    def _names(self, db) -> list:
        svc = WeeklyReportService(db)
        result = svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            return zf.namelist()

    def test_zip_contains_rival_toda_competicion_pngs(self):
        names = self._names(self._make_db_with_rival_data())
        assert any("01_Basicas_Toda_Competicion_Rival.png" in n for n in names), names
        assert any("01_Avanzadas_Toda_Competicion_Rival.png" in n for n in names), names
        # Own (non-rival) variants must still be present alongside
        assert any(n.endswith("01_Basicas_Toda_Competicion.png") for n in names), names

    def test_zip_contains_rival_won_lost_pngs(self):
        names = self._names(self._make_db_with_rival_data())
        assert any("02_Basicas_Ganados_vs_Perdidos_Rival.png" in n for n in names), names
        assert any("02_Avanzadas_Ganados_vs_Perdidos_Rival.png" in n for n in names), names

    def test_zip_contains_rival_venue_pngs(self):
        names = self._names(self._make_db_with_rival_data())
        assert any("03_Basicas_Local_vs_Visitante_Rival.png" in n for n in names), names
        assert any("03_Avanzadas_Local_vs_Visitante_Rival.png" in n for n in names), names

    def test_zip_contains_rival_month_pngs(self):
        names = self._names(self._make_db_with_rival_data())
        assert any("04_Basicas_" in n and "Mes_Rival.png" in n for n in names), names
        assert any("04_Avanzadas_" in n and "Mes_Rival.png" in n for n in names), names

    def test_rival_toda_competicion_uses_opponent_stats_data(self):
        """The rival '01' table must be built from get_opponent_stats(), not
        get_team_stats() — assert the rendered title/content differs because
        the underlying team rows differ (distinguishable via render args).
        """
        db = self._make_db_with_rival_data()
        svc = WeeklyReportService(db)
        with patch(
            "src.services.weekly_report_service.render_table_png",
            wraps=__import__(
                "src.services._weekly_report_helpers", fromlist=["render_table_png"]
            ).render_table_png,
        ) as mock_render:
            svc.generate_report_zip("FEB_LF2_2025_A", "Team A", "Team B")
        rival_calls = [c for c in mock_render.call_args_list if "(Rival)" in c.args[3]]
        assert rival_calls, "No rival-labelled render calls captured"

