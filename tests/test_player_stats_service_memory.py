"""Regression tests — FASE A: N+1 fix in _enrich_with_advanced_stats.

Before fix: get_team_stats and get_opponent_stats called N times (once per
unique team).
After fix:  both called exactly once regardless of how many teams are present.

Also covers FASE B pipeline team_filter:
- FEB  pipeline produces a $match on BOXSCORE.TEAM.TOTAL.name when team_filter given.
- FBCYL pipeline produces a $match on team_name when team_filter given.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.player_stats_service import PlayerStatsService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player(player_id: str, team_name: str) -> dict:
    return {
        "player_id": player_id,
        "player_name": f"Player {player_id}",
        "team_name": team_name,
        "games_played": 5,
        "points_per_game": 10.0,
    }


def _team_row(team_name: str) -> dict:
    """Minimal team stats row returned by get_team_stats / get_opponent_stats."""
    return {
        "team_name": team_name,
        "offensive_rating": 100.0,
        "defensive_rating": 98.0,
        "points_scored": 500,
        "games_played": 10,
        "total_possessions": 200,
        "points_received": 490,
    }


# ---------------------------------------------------------------------------
# FASE A — N+1 regression
# ---------------------------------------------------------------------------

class TestEnrichAdvancedStatsN1:
    """_enrich_with_advanced_stats must call get_team_stats exactly once."""

    def _db_with_three_teams(self) -> MagicMock:
        db = MagicMock()
        db.get_team_stats.return_value = [
            _team_row("Team A"),
            _team_row("Team B"),
            _team_row("Team C"),
        ]
        db.get_opponent_stats.return_value = [
            _team_row("Team A"),
            _team_row("Team B"),
            _team_row("Team C"),
        ]
        return db

    def test_get_team_stats_called_once_with_three_teams(self):
        """N+1 regression: 4 players across 3 teams must trigger exactly 1 call."""
        db = self._db_with_three_teams()
        svc = PlayerStatsService(db)
        players = [
            _player("1", "Team A"),
            _player("2", "Team A"),
            _player("3", "Team B"),
            _player("4", "Team C"),
        ]
        svc._enrich_with_advanced_stats("col", players)

        db.get_team_stats.assert_called_once_with("col")
        db.get_opponent_stats.assert_called_once_with("col")

    def test_get_aggregated_helpers_not_called(self):
        """Per-team helper get_aggregated_team_stats must not be invoked."""
        db = self._db_with_three_teams()
        svc = PlayerStatsService(db)
        svc._enrich_with_advanced_stats("col", [_player("p1", "Team A")])

        db.get_aggregated_team_stats.assert_not_called()
        db.get_aggregated_opponent_stats.assert_not_called()

    def test_single_team_still_one_call(self):
        db = MagicMock()
        db.get_team_stats.return_value = [_team_row("Solo")]
        db.get_opponent_stats.return_value = [_team_row("Solo")]
        svc = PlayerStatsService(db)
        svc._enrich_with_advanced_stats("col", [_player("p1", "Solo"), _player("p2", "Solo")])

        assert db.get_team_stats.call_count == 1
        assert db.get_opponent_stats.call_count == 1

    def test_empty_players_no_db_calls(self):
        """No players → no DB call should be made."""
        db = MagicMock()
        svc = PlayerStatsService(db)
        svc._enrich_with_advanced_stats("col", [])

        db.get_team_stats.assert_not_called()
        db.get_opponent_stats.assert_not_called()

    def test_db_error_does_not_propagate(self):
        """Failures in bulk fetch must be swallowed, players returned intact."""
        db = MagicMock()
        db.get_team_stats.side_effect = Exception("DB down")
        db.get_opponent_stats.side_effect = Exception("DB down")
        svc = PlayerStatsService(db)
        players = [_player("p1", "TeamX")]
        # Must not raise
        result = svc._enrich_with_advanced_stats("col", players)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# FASE B — pipeline team_filter
# ---------------------------------------------------------------------------

class TestFEBPipelineTeamFilter:
    """FEB build_player_stats_pipeline: team_filter adds $match on team name."""

    def _stages(self, team_filter=None):
        from database.aggregation.pipeline_builder import AggregationPipelineBuilder
        return AggregationPipelineBuilder.build_player_stats_pipeline(
            team_filter=team_filter
        )

    def test_team_filter_adds_match_stage(self):
        pipeline = self._stages(team_filter="Río Breogán")
        match_stages = [s["$match"] for s in pipeline if "$match" in s]
        assert any(
            s.get("BOXSCORE.TEAM.TOTAL.name") == "Río Breogán"
            for s in match_stages
        ), "Expected $match on BOXSCORE.TEAM.TOTAL.name"

    def test_no_team_filter_no_team_match(self):
        pipeline = self._stages()
        match_stages = [s["$match"] for s in pipeline if "$match" in s]
        assert not any(
            "BOXSCORE.TEAM.TOTAL.name" in s for s in match_stages
        )

    def test_team_filter_match_placed_before_player_unwind(self):
        """Team match must appear before $unwind of BOXSCORE.TEAM.PLAYER."""
        pipeline = self._stages(team_filter="TeamX")
        team_match_idx = None
        player_unwind_idx = None
        for i, stage in enumerate(pipeline):
            if "$match" in stage and stage["$match"].get("BOXSCORE.TEAM.TOTAL.name"):
                team_match_idx = i
            if "$unwind" in stage and "PLAYER" in str(stage["$unwind"]):
                player_unwind_idx = i
        assert team_match_idx is not None, "$match on team not found"
        assert player_unwind_idx is not None, "$unwind on PLAYER not found"
        assert team_match_idx < player_unwind_idx, (
            "Team $match must come before player $unwind for efficiency"
        )


class TestFBCYLPipelineTeamFilter:
    """FBCYL build_player_stats_pipeline: team_filter adds $match on team_name."""

    def _stages(self, team_filter=None):
        from database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder
        return FBCYLPipelineBuilder.build_player_stats_pipeline(
            team_filter=team_filter
        )

    def test_team_filter_adds_match_stage(self):
        pipeline = self._stages(team_filter="Baloncesto Segovia")
        match_stages = [s["$match"] for s in pipeline if "$match" in s]
        assert any(
            s.get("team_name") == "Baloncesto Segovia"
            for s in match_stages
        ), "Expected $match on team_name"

    def test_no_team_filter_no_team_name_match(self):
        pipeline = self._stages()
        match_stages = [s["$match"] for s in pipeline if "$match" in s]
        assert not any("team_name" in s for s in match_stages)

    def test_team_filter_match_placed_before_player_unwind(self):
        """Team match must appear before $unwind of players."""
        pipeline = self._stages(team_filter="TeamX")
        team_match_idx = None
        player_unwind_idx = None
        for i, stage in enumerate(pipeline):
            if "$match" in stage and "team_name" in stage["$match"]:
                team_match_idx = i
            if "$unwind" in stage:
                path = stage["$unwind"] if isinstance(stage["$unwind"], str) else stage["$unwind"].get("path", "")
                if "players" in path:
                    player_unwind_idx = i
        assert team_match_idx is not None, "$match on team_name not found"
        assert player_unwind_idx is not None, "$unwind on players not found"
        assert team_match_idx < player_unwind_idx


# ---------------------------------------------------------------------------
# Rankings — games_played contract (regression guard for min-games filter)
# ---------------------------------------------------------------------------

class TestLoadSeasonDataGamesPlayedContract:
    """load_season_data must always return 'games_played' in every player row.

    This guards the frontend min-games filter in RankingsPage which relies on
    this field to exclude phantom players (e.g. M. BETCH, M. MUKENDI) that
    played only 1-2 games and produce unrealistic per-game averages.

    The backend intentionally returns ALL players including low-sample ones;
    the frontend is responsible for applying min_games >= N filtering.
    """

    def _make_db(self, players: list) -> MagicMock:
        db = MagicMock()
        db.get_player_stats.return_value = players
        db.get_team_stats.return_value = []
        db.get_opponent_stats.return_value = []
        return db

    def test_games_played_present_for_all_players(self):
        """Every player row must contain a numeric games_played field."""
        players = [
            {**_player("p1", "Team A"), "games_played": 20},
            {**_player("p2", "Team A"), "games_played": 1},   # phantom player
        ]
        db = self._make_db(players)
        svc = PlayerStatsService(db)
        result = svc.load_season_data("COL")
        assert all("games_played" in p for p in result), (
            "games_played must be present in every player row for frontend filtering"
        )

    def test_single_game_player_not_filtered_by_backend(self):
        """Backend must NOT remove players with games_played=1.
        The frontend (RankingsPage minGames filter) is solely responsible."""
        phantom = {**_player("phantom", "Team A"), "games_played": 1, "points_per_game": 40.0}
        db = self._make_db([phantom])
        svc = PlayerStatsService(db)
        result = svc.load_season_data("COL")
        ids = [p.get("player_id") for p in result]
        assert "phantom" in ids, (
            "Backend must not silently discard low-games-played players; "
            "frontend is responsible for min_games filtering"
        )

    def test_games_played_value_preserved_unchanged(self):
        """games_played value must not be mutated by enrichment."""
        players = [
            {**_player("p1", "Team A"), "games_played": 3},
            {**_player("p2", "Team A"), "games_played": 17},
        ]
        db = self._make_db(players)
        svc = PlayerStatsService(db)
        result = svc.load_season_data("COL2")
        by_id = {p["player_id"]: p for p in result}
        assert by_id["p1"]["games_played"] == 3
        assert by_id["p2"]["games_played"] == 17
