"""Lineups ("Combinaciones") time filters.

Bug: with "Últimos 7 días" the page always said there were no matches. The router sent the cutoff as an ISO
*string* ("2026-10-04") but the repository compares it with the parsed game date (a BSON date), and Mongo never
matches a date against a string.
New: a "last game" filter that analyses only the team's most recent game.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.api.routers.lineups import period_date_filter
from src.database.repository import BasketballRepository

V1 = "/api/v1"


# -- bug: the cutoff must be a datetime --------------------------------------------------------------

class TestPeriodDateFilter:
    def test_cutoff_is_a_datetime_not_an_iso_string_regression(self):
        cutoff = period_date_filter(7)["$gte"]
        assert isinstance(cutoff, datetime)
        assert abs((datetime.utcnow() - timedelta(days=7)) - cutoff) < timedelta(seconds=5)

    def test_zero_means_the_full_season(self):
        assert period_date_filter(0) is None


@pytest.fixture()
def service_spy():
    handler = MagicMock()
    handler.is_connected.return_value = True
    app.dependency_overrides[get_db] = lambda: handler
    with patch("src.api.routers.lineups.LineupService") as service:
        service.return_value.get_lineup_analysis.return_value = []
        yield TestClient(app), service.return_value.get_lineup_analysis
    app.dependency_overrides.clear()


class TestRouter:
    def test_period_reaches_the_service_as_a_datetime_cutoff(self, service_spy):
        client, analysis = service_spy
        assert client.get(f"{V1}/lineups/FEB_X/1?team_name=A&period=7").status_code == 200
        assert isinstance(analysis.call_args.kwargs["date_filter"]["$gte"], datetime)
        assert analysis.call_args.kwargs["last_game"] is False

    def test_last_game_is_forwarded_and_needs_no_date_cutoff(self, service_spy):
        client, analysis = service_spy
        assert client.get(f"{V1}/lineups/FEB_X/1?team_name=A&last_game=true&period=7").status_code == 200
        assert analysis.call_args.kwargs["last_game"] is True
        assert analysis.call_args.kwargs["date_filter"] is None


# -- new: the most recent game of a team --------------------------------------------------------------

def _repo(aggregate_result=None, connected=True):
    connection = Mock()
    connection.is_connected.return_value = connected
    collection = MagicMock()
    collection.aggregate.return_value = aggregate_result or []
    connection.get_collection.return_value = collection
    return BasketballRepository(connection), collection


class TestLastGame:
    def test_pipeline_takes_the_newest_parsed_date_and_ignores_unparseable_ones(self):
        repo, collection = _repo([{"_id": 7}])
        assert repo.get_last_game_for_team("LF_X", "1", only_with_playbyplay=True) == [{"_id": 7}]
        pipeline = collection.aggregate.call_args.args[0]
        assert {"$match": {"_parsedDate": {"$ne": None}}} in pipeline
        assert pipeline.index({"$sort": {"_parsedDate": -1}}) < pipeline.index({"$limit": 1})
        assert "$dateFromString" in str(pipeline[1])  # FEB dd-mm-yyyy parsed inside MongoDB (no Python filtering)

    def test_projection_is_applied_after_the_limit(self):
        repo, collection = _repo()
        repo.get_last_game_for_team("LF_X", "1", projection={"HEADER": 1})
        pipeline = collection.aggregate.call_args.args[0]
        assert pipeline[-1] == {"$project": {"HEADER": 1}}

    def test_disconnected_database_returns_no_games(self):
        repo, _ = _repo(connected=False)
        assert repo.get_last_game_for_team("LF_X", "1") == []


class TestAnalysisUsesTheFilters:
    @patch("src.database.lineup_stats_calculator.LineupStatsCalculator")
    @patch("src.database.lineup_extractor.LineupExtractor")
    @patch("src.database.playbyplay_analyzer.PlayByPlayAnalyzer")
    def _run(self, _pbp, extractor, calculator, games, **kwargs):
        repo, _ = _repo()
        repo.get_games_for_team = Mock(return_value=games)
        repo.get_last_game_for_team = Mock(return_value=games)
        extractor.return_value.get_lineup_combinations.return_value = {frozenset("ABCDE"): 1200}
        calculator.return_value.calculate_lineup_stats_single_game.return_value = {
            "minutes": 20.0, "games_played": 1, "segments_count": 3, "points_for": 30, "points_against": 25,
            "possessions": 40, "ortg": 75.0, "drtg": 62.5, "net_rating": 12.5, "plus_minus": 5,
            **{k: 0 for k in ("fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "trb", "ast", "stl", "blk", "tov", "pf")},
        }
        repo._get_player_names_for_lineup = Mock(return_value=(list("ABCDE"), [None] * 5))
        return repo, repo.get_lineup_analysis("LF_X", "1", "Team", combination_size=5, is_fbcyl=False, **kwargs)

    def test_last_game_analyses_only_the_newest_game_and_does_not_load_the_season(self):
        games = [{"_id": "g9", "HEADER": {"starttime": "11-10-2026 - 18:00"}}]
        repo, result = self._run(games=games, last_game=True, min_games=5)
        repo.get_last_game_for_team.assert_called_once()
        repo.get_games_for_team.assert_not_called()
        assert len(result) == 1  # one game cannot reach "5 games together": the minimum is capped to the games available

    def test_minimum_games_is_capped_to_the_games_in_the_period_regression(self):
        games = [{"_id": "g1", "HEADER": {"starttime": "10-10-2026 - 17:00"}},
                 {"_id": "g2", "HEADER": {"starttime": "11-10-2026 - 18:00"}}]
        _, result = self._run(games=games, date_filter={"$gte": datetime(2026, 10, 4)}, min_games=5)
        assert len(result) == 1  # 2 games in the last 7 days with the default minimum of 5 used to leave the page empty

    def test_the_full_season_keeps_its_minimum_of_games(self):
        games = [{"_id": "g1", "HEADER": {"starttime": "10-10-2026 - 17:00"}}]
        _, result = self._run(games=games, min_games=5)
        assert result == []
