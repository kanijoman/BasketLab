"""Tests for the configurable lineup minimums (min_minutes / min_games).

Previously the repository hard-coded 15 minutes / 5 games, so users could not
see rarer combinations. The thresholds are now parameters (0 disables a filter).
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.database.repository import BasketballRepository
from src.services.lineup_service import LineupService

V1 = "/api/v1"
LINEUP = frozenset(["P1", "P2", "P3", "P4", "P5"])


def _single_game_stats(minutes: float) -> dict:
    return {
        'minutes': minutes, 'games_played': 1, 'segments_count': 1,
        'points_for': 10, 'points_against': 8, 'possessions': 12,
        'ortg': 80.0, 'drtg': 60.0, 'net_rating': 20.0, 'plus_minus': 2,
        'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0, 'ftm': 0, 'fta': 0,
        'orb': 0, 'drb': 0, 'trb': 0, 'ast': 0, 'stl': 0, 'blk': 0,
        'tov': 0, 'pf': 0,
    }


@pytest.fixture()
def repo():
    conn = Mock()
    conn.is_connected.return_value = True
    r = BasketballRepository(conn)
    r.get_games_for_team = Mock(return_value=[
        {'_id': 'g1', 'HEADER': {'starttime': '2024-01-01 - 18:00'}},
        {'_id': 'g2', 'HEADER': {'starttime': '2024-01-02 - 18:00'}},
    ])  # 2 games x 3 min = 6 min total, 2 games
    r._bulk_load_player_names = Mock(return_value={})
    return r


def _run(repo, **kwargs):
    with patch('src.database.lineup_stats_calculator.LineupStatsCalculator') as calc, \
         patch('src.database.lineup_extractor.LineupExtractor') as extractor, \
         patch('src.database.playbyplay_analyzer.PlayByPlayAnalyzer'):
        extractor.return_value.get_lineup_combinations.return_value = {LINEUP: 180}
        calc.return_value.calculate_lineup_stats_single_game.side_effect = (
            lambda *a, **k: _single_game_stats(3.0)
        )
        return repo.get_lineup_analysis(
            'col', 'T1', 'Team', combination_size=5, is_fbcyl=False, **kwargs
        )


class TestRepositoryMinimums:
    def test_default_minimums_still_exclude_small_samples(self, repo):
        assert _run(repo) == []

    def test_lineup_minimums_configurable_regression(self, repo):
        """0/0 must return lineups that the old hard-coded 15 min / 5 games hid."""
        assert len(_run(repo, min_minutes=0, min_games=0)) == 1

    def test_custom_thresholds_are_respected(self, repo):
        assert len(_run(repo, min_minutes=6, min_games=2)) == 1
        assert _run(repo, min_minutes=7, min_games=2) == []
        assert _run(repo, min_minutes=6, min_games=3) == []


class TestFebProjectionRegression:
    """FEB lineup extraction needs BOXSCORE.TEAM[].PLAYER[].id to know the roster.

    Bug: the projection only loaded PLAYBYPLAY + HEADER, so
    ``LineupExtractor._get_team_players`` returned an empty set and every FEB
    team produced zero lineups (FBCYL was unaffected).
    """

    def test_feb_projection_includes_boxscore_roster_regression(self, repo):
        _run(repo)
        projection = repo.get_games_for_team.call_args.kwargs['projection']
        keys = set(projection)
        assert any(k == 'BOXSCORE' or k.startswith('BOXSCORE.TEAM') for k in keys), (
            f"FEB projection must include the BOXSCORE roster, got {sorted(keys)}"
        )
        assert 'PLAYBYPLAY' in keys

    def test_fbcyl_projection_unchanged(self, repo):
        with patch('src.database.lineup_stats_calculator.LineupStatsCalculator'), \
             patch('src.database.lineup_extractor.LineupExtractor'), \
             patch('src.database.playbyplay_analyzer.PlayByPlayAnalyzer'):
            repo.get_lineup_analysis('FBCYL_x', 'T1', 'Team', is_fbcyl=True)
        projection = repo.get_games_for_team.call_args.kwargs['projection']
        assert 'moves' in projection and not any(k.startswith('BOXSCORE') for k in projection)


class TestServiceForwardsMinimums:
    def test_service_forwards_thresholds_to_handler(self):
        db = MagicMock()
        db.get_lineup_analysis.return_value = []
        LineupService(db).get_lineup_analysis("col", "1", "T", min_minutes=2.5, min_games=1)
        kwargs = db.get_lineup_analysis.call_args.kwargs
        assert kwargs["min_minutes"] == 2.5
        assert kwargs["min_games"] == 1

    def test_service_defaults_are_15_and_5(self):
        db = MagicMock()
        db.get_lineup_analysis.return_value = []
        LineupService(db).get_lineup_analysis("col", "1", "T")
        kwargs = db.get_lineup_analysis.call_args.kwargs
        assert kwargs["min_minutes"] == 15
        assert kwargs["min_games"] == 5


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestEndpointsForwardMinimums:
    @pytest.mark.parametrize("suffix", ["", "/stream"])
    def test_params_forwarded(self, client, suffix):
        with patch("src.api.routers.lineups.LineupService") as svc_cls:
            svc_cls.return_value.get_lineup_analysis.return_value = []
            r = client.get(
                f"{V1}/lineups/COL/T1{suffix}",
                params={"team_name": "T", "min_minutes": 0, "min_games": 2},
            )
            assert r.status_code == 200
            kwargs = svc_cls.return_value.get_lineup_analysis.call_args.kwargs
            assert kwargs["min_minutes"] == 0
            assert kwargs["min_games"] == 2

    @pytest.mark.parametrize("suffix", ["", "/stream"])
    def test_defaults(self, client, suffix):
        with patch("src.api.routers.lineups.LineupService") as svc_cls:
            svc_cls.return_value.get_lineup_analysis.return_value = []
            client.get(f"{V1}/lineups/COL/T1{suffix}", params={"team_name": "T"})
            kwargs = svc_cls.return_value.get_lineup_analysis.call_args.kwargs
            assert kwargs["min_minutes"] == 15
            assert kwargs["min_games"] == 5

    @pytest.mark.parametrize("param", ["min_minutes", "min_games"])
    def test_negative_values_rejected(self, client, param):
        r = client.get(f"{V1}/lineups/COL/T1", params={"team_name": "T", param: -1})
        assert r.status_code == 422
