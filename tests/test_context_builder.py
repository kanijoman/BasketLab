"""Tests for ContextBuilder and TeamAnalyzer — FASE B quality coverage.

Covers:
- ContextBuilder.build_team_context(): returns str, contains team name, FEB+FBCYL
- ContextBuilder.build_player_context(): returns str, contains player name
- TeamAnalyzer: no API key → raises ValueError (no live API calls)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ai.context_builder import ContextBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_team_stats():
    return {
        'games_played': 10,
        'wins': 6, 'losses': 4,
        'points_per_game': 78.0,
        'points_allowed_per_game': 72.0,
        'rebounds_per_game': 35.0,
        'assists_per_game': 18.0,
        'steals_per_game': 7.0,
        'blocks_per_game': 3.0,
        'turnovers_per_game': 12.0,
        'fg2_percentage': 50.0,
        'fg3_percentage': 35.0,
        'ft_percentage': 75.0,
        'three_point_rate': 30.0,
        'effective_fg_percentage': 52.0,
        'turnover_rate': 13.0,
        'offensive_rebound_rate': 25.0,
        'free_throw_rate': 0.25,
        'true_shooting_percentage': 56.0,
        'assist_rate': 55.0,
        'assist_fg_rate': 60.0,
        'steal_rate': 8.0,
        'block_rate': 4.0,
        'offensive_rebounds_per_game': 8.0,
        'defensive_rebounds_per_game': 27.0,
        'net_rating': 6.0,
        'offensive_rating': 110.0,
        'defensive_rating': 104.0,
        'pace': 90.0,
    }


def _minimal_league_stats():
    return {
        'points_per_game': {'q1': 65, 'q2': 72, 'q3': 78},
        'points_allowed_per_game': {'q1': 70, 'q2': 76, 'q3': 83},
        'rebounds_per_game': {'q1': 30, 'q2': 34, 'q3': 38},
        'assists_per_game': {'q1': 14, 'q2': 18, 'q3': 22},
        'steals_per_game': {'q1': 5, 'q2': 7, 'q3': 9},
        'blocks_per_game': {'q1': 2, 'q2': 3, 'q3': 5},
        'turnovers_per_game': {'q1': 10, 'q2': 13, 'q3': 16},
        'fg3_percentage': {'q1': 30, 'q2': 35, 'q3': 38},
    }


def _minimal_player_stats():
    return {
        'team_name': 'Alpha FC',
        'dorsal': '7',
        'games_played': 10,
        'mpg': 28.5,
        'ppg': 14.2,
        'rpg': 5.3,
        'apg': 3.1,
        'topg': 1.5,
        'fg2_pct': 52.0,
        'fg3_pct': 36.0,
        'ft_pct': 78.0,
        'ts': 56.0,
        'efg': 54.0,
        'fpg': 2.5,
    }


# ---------------------------------------------------------------------------
# ContextBuilder.build_team_context
# ---------------------------------------------------------------------------

class TestBuildTeamContext:
    def _cb(self):
        return ContextBuilder()

    def test_returns_string(self):
        stats = {'team_stats': _minimal_team_stats(), 'league_stats': _minimal_league_stats()}
        result = self._cb().build_team_context('Equipo A', stats, include_recommendations=False)
        assert isinstance(result, str)

    def test_contains_team_name(self):
        stats = {'team_stats': _minimal_team_stats(), 'league_stats': _minimal_league_stats()}
        result = self._cb().build_team_context('Equipo Prueba', stats, include_recommendations=False)
        assert 'Equipo Prueba' in result

    def test_empty_stats_does_not_raise(self):
        """Empty stats dict must not crash — returns a graceful string."""
        result = self._cb().build_team_context('Vacío', {}, include_recommendations=False)
        assert isinstance(result, str)

    def test_with_recommendations_own(self):
        """include_recommendations=True with own analysis type adds recommendation sections."""
        stats = {'team_stats': _minimal_team_stats(), 'league_stats': _minimal_league_stats()}
        result = self._cb().build_team_context('Equipo A', stats,
                                                include_recommendations=True, analysis_type='own')
        assert 'PETICION DE ANALISIS' in result
        assert 'SCOUTING PROPIO' in result

    def test_with_recommendations_scouting(self):
        """analysis_type='scouting' adds rival scouting sections."""
        stats = {'team_stats': _minimal_team_stats(), 'league_stats': _minimal_league_stats()}
        result = self._cb().build_team_context('Rival', stats,
                                                include_recommendations=True, analysis_type='scouting')
        assert 'SCOUTING RIVAL' in result

    def test_no_recommendations_omits_scouting_sections(self):
        """include_recommendations=False → no scouting section (PROPIO/RIVAL) appended."""
        stats = {'team_stats': _minimal_team_stats(), 'league_stats': _minimal_league_stats()}
        result = self._cb().build_team_context('Equipo A', stats, include_recommendations=False)
        # The scouting type labels must not appear when recommendations are off
        assert 'SCOUTING PROPIO' not in result
        assert 'SCOUTING RIVAL' not in result

    def test_consistency_data_included_when_present(self):
        """Consistency dict is formatted and appears in the context."""
        stats = {
            'team_stats': _minimal_team_stats(),
            'league_stats': _minimal_league_stats(),
            'consistency': {
                'points_per_game': {'mean': 78.0, 'std': 8.0, 'cv': 10.3, 'n': 10},
            },
        }
        result = self._cb().build_team_context('Equipo A', stats, include_recommendations=False)
        assert 'Consistencia' in result

    def test_shot_zones_section_when_present(self):
        """shot_zones data triggers shot zone section in context."""
        stats = {
            'team_stats': _minimal_team_stats(),
            'league_stats': _minimal_league_stats(),
            'shot_zones': {'paint': {'made': 100, 'attempted': 200}},
        }
        result = self._cb().build_team_context('Equipo A', stats, include_recommendations=False)
        assert isinstance(result, str)  # must not raise


# ---------------------------------------------------------------------------
# ContextBuilder.build_player_context
# ---------------------------------------------------------------------------

class TestBuildPlayerContext:
    def _cb(self):
        return ContextBuilder()

    def test_returns_string(self):
        result = self._cb().build_player_context('Juan García', _minimal_player_stats())
        assert isinstance(result, str)

    def test_contains_player_name(self):
        result = self._cb().build_player_context('María López', _minimal_player_stats())
        assert 'María López' in result

    def test_contains_team_name(self):
        result = self._cb().build_player_context('Player X', _minimal_player_stats())
        assert 'Alpha FC' in result

    def test_zero_games_does_not_raise(self):
        stats = dict(_minimal_player_stats())
        stats['games_played'] = 0
        result = self._cb().build_player_context('Sin datos', stats)
        assert isinstance(result, str)

    def test_with_league_stats_does_not_raise(self):
        league = {'ft_pct': {'q1': 70, 'q2': 75, 'q3': 80}}
        result = self._cb().build_player_context('Juan García', _minimal_player_stats(),
                                                   league_stats=league)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TeamAnalyzer — validation without live API
# ---------------------------------------------------------------------------

class TestTeamAnalyzerValidation:
    """These tests verify that TeamAnalyzer raises ValueError when no API key
    is configured, without making any network requests.  They do NOT test
    actual AI responses (that requires real keys and is excluded from CI).
    """

    def test_raises_when_no_gemini_key(self):
        """Instantiating without a Gemini key must raise ValueError."""
        from ai.config import AnalysisConfig
        from ai.team_analyzer import TeamAnalyzer
        import unittest.mock as mock

        original = AnalysisConfig.GEMINI_API_KEY
        try:
            AnalysisConfig.GEMINI_API_KEY = None
            with mock.patch.object(AnalysisConfig, 'has_api_key', return_value=False):
                with pytest.raises(ValueError, match="No API key"):
                    TeamAnalyzer(provider='gemini')
        finally:
            AnalysisConfig.GEMINI_API_KEY = original

    def test_raises_for_unsupported_provider(self):
        """Unknown provider raises ValueError."""
        from ai.config import AnalysisConfig
        from ai.team_analyzer import TeamAnalyzer
        import unittest.mock as mock

        with mock.patch.object(AnalysisConfig, 'has_api_key', return_value=True):
            with pytest.raises(ValueError, match="Unsupported provider"):
                TeamAnalyzer(provider='unknown_llm')
