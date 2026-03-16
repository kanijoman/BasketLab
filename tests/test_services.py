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


# ---------------------------------------------------------------------------
# Helpers for list_available / drop_collection tests
# ---------------------------------------------------------------------------

def _make_db_handler_with_collections(names: list) -> MagicMock:
    """Return a mock whose connection returns the given collection names."""
    handler = MagicMock()
    handler.is_connected.return_value = True

    mock_db = MagicMock()
    mock_db.list_collection_names.return_value = names
    handler.connection.get_database.return_value = mock_db
    handler.connection.is_connected.return_value = True

    mock_col = MagicMock()
    mock_col.count_documents.return_value = 10
    handler.connection.get_collection.return_value = mock_col
    return handler


# ---------------------------------------------------------------------------
# CollectionService.list_available — regression for FEB name filter bug
# ---------------------------------------------------------------------------

class TestCollectionServiceListAvailable:
    """Regression tests for the list_available() filtering bug.

    Bug: ``_COLLECTION_PATTERN = re.compile(r'^(FEB|FBCYL)_')`` silently
    excluded every FEB collection whose sanitised name does NOT start with
    ``FEB_`` (e.g. ``L_F_-2_2025_2026_Liga_Regular_A`` from the real DB).
    """

    def test_feb_collection_without_feb_prefix_is_included_regression(self):
        """Regression: L_F_-2_2025_2026_Liga_Regular_A must appear in results."""
        from src.services import CollectionService
        handler = _make_db_handler_with_collections(["L_F_-2_2025_2026_Liga_Regular_A"])
        svc = CollectionService(handler)
        results = svc.list_available()
        names = [r["name"] for r in results]
        assert "L_F_-2_2025_2026_Liga_Regular_A" in names, (
            "FEB collection without FEB_ prefix was incorrectly excluded"
        )

    def test_feb_collection_tagged_as_feb_regression(self):
        """Regression: collections not starting with FBCYL_ must be tagged FEB."""
        from src.services import CollectionService
        handler = _make_db_handler_with_collections(["L_F_-2_2025_2026_Liga_Regular_A"])
        svc = CollectionService(handler)
        results = svc.list_available()
        assert results[0]["league"] == "FEB"

    def test_group_parsed_from_feb_collection_name(self):
        """Group suffix (last token matching [A-Z0-9]{1,2}) is extracted."""
        from src.services import CollectionService
        handler = _make_db_handler_with_collections(["L_F_-2_2025_2026_Liga_Regular_A"])
        svc = CollectionService(handler)
        results = svc.list_available()
        assert results[0]["group"] == "A"

    def test_fbcyl_collection_tagged_as_fbcyl(self):
        from src.services import CollectionService
        handler = _make_db_handler_with_collections(
            ["FBCYL_Femenino_FBCYL_1a_DIVISION_FEMENINA_Temporada_20252026"]
        )
        svc = CollectionService(handler)
        results = svc.list_available()
        assert results[0]["league"] == "FBCYL"

    def test_test_collection_is_excluded(self):
        """The literal 'test' collection must never appear in results."""
        from src.services import CollectionService
        handler = _make_db_handler_with_collections(["test"])
        svc = CollectionService(handler)
        results = svc.list_available()
        assert results == []

    def test_system_collection_is_excluded(self):
        """'system.*' collections are MongoDB internals and must be skipped."""
        from src.services import CollectionService
        handler = _make_db_handler_with_collections(["system.version", "system.users"])
        svc = CollectionService(handler)
        results = svc.list_available()
        assert results == []

    def test_returns_empty_when_disconnected(self):
        from src.services import CollectionService
        handler = _make_db_handler_with_collections([])
        handler.is_connected.return_value = False
        svc = CollectionService(handler)
        assert svc.list_available() == []

    def test_game_count_populated_from_db(self):
        from src.services import CollectionService
        handler = _make_db_handler_with_collections(["L_F_-2_2025_2026_Liga_Regular_B"])
        handler.connection.get_collection.return_value.count_documents.return_value = 42
        svc = CollectionService(handler)
        results = svc.list_available()
        assert results[0]["game_count"] == 42

    def test_multiple_collections_all_returned(self):
        """Both FEB groups and the FBCYL collection must all be present."""
        from src.services import CollectionService
        real_names = [
            "L_F_-2_2025_2026_Liga_Regular_A",
            "L_F_-2_2025_2026_Liga_Regular_B",
            "FBCYL_Femenino_FBCYL_1a_DIVISION_2026",
            "test",
        ]
        handler = _make_db_handler_with_collections(real_names)
        svc = CollectionService(handler)
        results = svc.list_available()
        result_names = {r["name"] for r in results}
        assert "L_F_-2_2025_2026_Liga_Regular_A" in result_names
        assert "L_F_-2_2025_2026_Liga_Regular_B" in result_names
        assert "FBCYL_Femenino_FBCYL_1a_DIVISION_2026" in result_names
        assert "test" not in result_names

    def test_returns_empty_list_on_db_exception(self):
        from src.services import CollectionService
        handler = _make_db_handler_with_collections([])
        handler.connection.get_database.side_effect = RuntimeError("db error")
        svc = CollectionService(handler)
        assert svc.list_available() == []


# ---------------------------------------------------------------------------
# CollectionService.drop_collection — regression for updated guard
# ---------------------------------------------------------------------------

class TestCollectionServiceDropCollection:
    """Regression tests for the drop_collection() guard.

    The old guard required ``^(FEB|FBCYL)_`` and therefore would refuse to
    drop legitimate FEB collections like ``L_F_-2_2025_2026_Liga_Regular_A``.
    The new guard blocks ``system.*`` and reserved names instead.
    """

    def _make_connected_handler(self):
        handler = MagicMock()
        handler.is_connected.return_value = True
        mock_db = MagicMock()
        handler.connection.get_database.return_value = mock_db
        return handler

    def test_drops_feb_slug_collection_regression(self):
        """Regression: L_F_-2_... style names must be droppable."""
        from src.services import CollectionService
        handler = self._make_connected_handler()
        svc = CollectionService(handler)
        svc.drop_collection("L_F_-2_2025_2026_Liga_Regular_A")  # must not raise
        handler.connection.get_database().drop_collection.assert_called_once_with(
            "L_F_-2_2025_2026_Liga_Regular_A"
        )

    def test_drops_fbcyl_collection(self):
        from src.services import CollectionService
        handler = self._make_connected_handler()
        svc = CollectionService(handler)
        svc.drop_collection("FBCYL_Femenino_2026")  # must not raise
        handler.connection.get_database().drop_collection.assert_called_once()

    def test_refuses_to_drop_test_collection(self):
        from src.services import CollectionService
        handler = self._make_connected_handler()
        svc = CollectionService(handler)
        with pytest.raises(ValueError, match="reserved or system"):
            svc.drop_collection("test")

    def test_refuses_to_drop_system_collection(self):
        from src.services import CollectionService
        handler = self._make_connected_handler()
        svc = CollectionService(handler)
        with pytest.raises(ValueError):
            svc.drop_collection("system.version")

    def test_raises_runtime_error_when_disconnected(self):
        from src.services import CollectionService
        handler = self._make_connected_handler()
        handler.is_connected.return_value = False
        svc = CollectionService(handler)
        with pytest.raises(RuntimeError, match="not connected"):
            svc.drop_collection("L_F_-2_2025_2026_Liga_Regular_A")
