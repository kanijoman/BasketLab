"""Tests for src.services — TeamStatsService, PlayerStatsService, LineupService, CollectionService.

These tests use lightweight mocks (MagicMock / mongomock) so they run
without a live MongoDB connection and without PyQt6.
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared Mock helper
# ---------------------------------------------------------------------------

def _make_db_handler(
    team_stats=None, opponent_stats=None, player_stats=None, all_teams=None
):
    """Return a mock MongoDBHandler pre-configured with sensible return values."""
    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.get_team_stats.return_value = team_stats or []
    handler.get_opponent_stats.return_value = opponent_stats or []
    handler.get_player_stats.return_value = player_stats or []
    handler.get_all_teams.return_value = all_teams or []
    handler.get_aggregated_team_stats.return_value = {}
    handler.get_aggregated_opponent_stats.return_value = {}
    handler.get_league_stats.return_value = {}
    handler.get_player_in_out_stats.return_value = {}
    handler.get_two_players_together_stats.return_value = {}
    handler.get_player_individual_stats_with_teammate.return_value = {}
    handler.get_lineup_analysis.return_value = []
    return handler


# ---------------------------------------------------------------------------
# TeamStatsService
# ---------------------------------------------------------------------------

class TestTeamStatsServiceLoadSeasonData:
    def test_returns_dict_with_two_keys(self):
        from src.services import TeamStatsService
        svc = TeamStatsService(_make_db_handler())
        result = svc.load_season_data("FEB_LF2_2025_A")
        assert "team_stats" in result
        assert "opponent_stats" in result

    def test_passes_collection_name_to_db(self):
        from src.services import TeamStatsService
        handler = _make_db_handler()
        svc = TeamStatsService(handler)
        svc.load_season_data("FEB_LF2_2025_A")
        handler.get_team_stats.assert_called_once()
        args = handler.get_team_stats.call_args[0]
        assert args[0] == "FEB_LF2_2025_A"

    def test_passes_filters_to_db(self):
        from src.services import TeamStatsService
        handler = _make_db_handler()
        svc = TeamStatsService(handler)
        svc.load_season_data("COL", date_filter={"$gte": 1}, venue_filter=True, result_filter="won")
        handler.get_team_stats.assert_called_once_with("COL", {"$gte": 1}, True, "won")

    def test_none_db_return_yields_empty_lists(self):
        from src.services import TeamStatsService
        handler = _make_db_handler()
        handler.get_team_stats.return_value = None
        handler.get_opponent_stats.return_value = None
        svc = TeamStatsService(handler)
        result = svc.load_season_data("X")
        assert result["team_stats"] == []
        assert result["opponent_stats"] == []

    def test_team_stats_returned_unchanged(self):
        from src.services import TeamStatsService
        data = [{"team_name": "Alpha", "points_per_game": 80.0}]
        svc = TeamStatsService(_make_db_handler(team_stats=data))
        result = svc.load_season_data("COL")
        assert result["team_stats"] is data


class TestTeamStatsServiceGetAllTeams:
    def test_returns_list(self):
        from src.services import TeamStatsService
        svc = TeamStatsService(_make_db_handler(all_teams=["A", "B", "C"]))
        teams = svc.get_all_teams("COL")
        assert teams == ["A", "B", "C"]

    def test_none_return_yields_empty(self):
        from src.services import TeamStatsService
        handler = _make_db_handler()
        handler.get_all_teams.return_value = None
        svc = TeamStatsService(handler)
        assert svc.get_all_teams("X") == []


class TestTeamStatsServiceGetQuartiles:
    def test_returns_dict_on_success(self):
        from src.services import TeamStatsService
        with patch("src.services.team_stats_service.TeamStatsAggregator") as MockAgg:
            mock_instance = MockAgg.return_value
            mock_instance.calculate_league_quartiles.return_value = {"points": {"q1": 60}}
            svc = TeamStatsService(_make_db_handler())
            result = svc.get_quartiles("COL")
        assert isinstance(result, dict)

    def test_returns_empty_dict_on_exception(self):
        from src.services import TeamStatsService
        with patch("src.services.team_stats_service.TeamStatsAggregator") as MockAgg:
            mock_instance = MockAgg.return_value
            mock_instance.calculate_league_quartiles.side_effect = RuntimeError("db error")
            svc = TeamStatsService(_make_db_handler())
            result = svc.get_quartiles("COL")
        assert result == {}


# ---------------------------------------------------------------------------
# PlayerStatsService
# ---------------------------------------------------------------------------

class TestPlayerStatsServiceLoadSeasonData:
    def test_returns_list(self):
        from src.services import PlayerStatsService
        data = [{"player_name": "Doe", "points_per_game": 15}]
        svc = PlayerStatsService(_make_db_handler(player_stats=data))
        result = svc.load_season_data("COL")
        assert result is data

    def test_passes_collection_name(self):
        from src.services import PlayerStatsService
        handler = _make_db_handler()
        svc = PlayerStatsService(handler)
        svc.load_season_data("FEB_LF2_2025_A")
        handler.get_player_stats.assert_called_once()
        assert handler.get_player_stats.call_args[0][0] == "FEB_LF2_2025_A"

    def test_none_return_yields_empty_list(self):
        from src.services import PlayerStatsService
        handler = _make_db_handler()
        handler.get_player_stats.return_value = None
        svc = PlayerStatsService(handler)
        assert svc.load_season_data("X") == []


class TestPlayerStatsServiceInOut:
    def test_get_in_out_analysis_called_with_correct_args(self):
        from src.services import PlayerStatsService
        handler = _make_db_handler()
        svc = PlayerStatsService(handler)
        svc.get_in_out_analysis("COL", "player1")
        handler.get_player_in_out_stats.assert_called_once()
        call_args = handler.get_player_in_out_stats.call_args
        assert call_args[0][0] == "COL"
        assert call_args[0][1] == "player1"

    def test_none_return_yields_empty_dict(self):
        from src.services import PlayerStatsService
        handler = _make_db_handler()
        handler.get_player_in_out_stats.return_value = None
        svc = PlayerStatsService(handler)
        assert svc.get_in_out_analysis("X", "p1") == {}


class TestPlayerStatsServiceTogether:
    def test_get_players_together_called(self):
        from src.services import PlayerStatsService
        handler = _make_db_handler()
        svc = PlayerStatsService(handler)
        svc.get_players_together("COL", "p1", "p2")
        handler.get_two_players_together_stats.assert_called_once()

    def test_none_return_yields_empty_dict(self):
        from src.services import PlayerStatsService
        handler = _make_db_handler()
        handler.get_two_players_together_stats.return_value = None
        svc = PlayerStatsService(handler)
        assert svc.get_players_together("X", "p1", "p2") == {}


# ---------------------------------------------------------------------------
# LineupService
# ---------------------------------------------------------------------------

class TestLineupService:
    def test_get_lineup_analysis_delegates_to_db(self):
        from src.services import LineupService
        handler = _make_db_handler()
        svc = LineupService(handler)
        svc.get_lineup_analysis("FEB_LF2_2025_A", "123", "Alpha")
        handler.get_lineup_analysis.assert_called_once()

    def test_fbcyl_flag_set_for_fbcyl_collection(self):
        from src.services import LineupService
        handler = _make_db_handler()
        svc = LineupService(handler)
        svc.get_lineup_analysis("FBCYL_SE_2025_A", "uuid", "Beta")
        call_kwargs = handler.get_lineup_analysis.call_args[1]
        assert call_kwargs.get("is_fbcyl") is True

    def test_fbcyl_flag_false_for_feb_collection(self):
        from src.services import LineupService
        handler = _make_db_handler()
        svc = LineupService(handler)
        svc.get_lineup_analysis("FEB_LF2_2025_A", "123", "Alpha")
        call_kwargs = handler.get_lineup_analysis.call_args[1]
        assert call_kwargs.get("is_fbcyl") is False

    def test_none_return_yields_empty_list(self):
        from src.services import LineupService
        handler = _make_db_handler()
        handler.get_lineup_analysis.return_value = None
        svc = LineupService(handler)
        assert svc.get_lineup_analysis("COL", "123", "Team") == []


# ---------------------------------------------------------------------------
# CollectionService
# ---------------------------------------------------------------------------

class TestCollectionServiceResolve:
    def test_resolve_name_basic(self):
        from src.services import CollectionService
        result = CollectionService.resolve_name("FEB", "LF2_2025", "A")
        assert result == "FEB_LF2_2025_A"

    def test_resolve_name_removes_spaces(self):
        from src.services import CollectionService
        result = CollectionService.resolve_name("FEB", "LF2 2025", "A")
        assert " " not in result

    def test_format_is_fbcyl_true(self):
        from src.services import CollectionService
        assert CollectionService.format_is_fbcyl("FBCYL_SE_2025_A") is True

    def test_format_is_fbcyl_false(self):
        from src.services import CollectionService
        assert CollectionService.format_is_fbcyl("FEB_LF2_2025_A") is False


class TestCollectionServiceGetTeams:
    def test_returns_list(self):
        from src.services import CollectionService
        handler = _make_db_handler(all_teams=["A", "B"])
        svc = CollectionService(handler)
        assert svc.get_teams("COL") == ["A", "B"]

    def test_none_return_handled(self):
        from src.services import CollectionService
        handler = _make_db_handler()
        handler.get_all_teams.return_value = None
        svc = CollectionService(handler)
        assert svc.get_teams("COL") == []


class TestCollectionServiceHasData:
    def test_returns_false_when_disconnected(self):
        from src.services import CollectionService
        handler = _make_db_handler()
        handler.is_connected.return_value = False
        svc = CollectionService(handler)
        assert svc.collection_has_data("COL") is False

    def test_returns_true_when_documents_exist(self):
        from src.services import CollectionService
        handler = _make_db_handler()
        mock_collection = MagicMock()
        mock_collection.count_documents.return_value = 1
        handler.connection.get_collection.return_value = mock_collection
        svc = CollectionService(handler)
        assert svc.collection_has_data("COL") is True

    def test_returns_false_on_exception(self):
        from src.services import CollectionService
        handler = _make_db_handler()
        handler.connection.get_collection.side_effect = RuntimeError("err")
        svc = CollectionService(handler)
        assert svc.collection_has_data("COL") is False
