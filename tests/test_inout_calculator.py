"""Tests for InOutStatsCalculator — FASE B quality coverage.

Covers:
- _extract_points_from_action(): FEB + FBCYL format, misses, free throws
- _process_fbcyl_move(): stats accumulation from FBCYL move text
- _process_feb_action(): stats accumulation from FEB action text
- calculate_in_out_stats(): integration — IN vs OUT buckets populated
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.inout_calculator import InOutStatsCalculator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_analyzer(lines: list = None, is_fbcyl: bool = False,
                   team_mapping: dict = None, player_segments: dict = None):
    """Return a minimal mock PlayByPlayAnalyzer."""
    analyzer = MagicMock()
    analyzer.is_fbcyl = is_fbcyl
    # lines/moves list used by calculate_in_out_stats
    if is_fbcyl:
        analyzer.moves = lines or []
    else:
        analyzer.lines = lines or []
    analyzer.team_mapping = team_mapping or {}
    # get_player_court_segments returns list of {start, end} dicts
    analyzer.get_player_court_segments.return_value = player_segments or []
    return analyzer


def _calc(lines=None, is_fbcyl=False, player_segments=None, team_mapping=None):
    a = _make_analyzer(lines, is_fbcyl, team_mapping, player_segments)
    return InOutStatsCalculator(a)


# ---------------------------------------------------------------------------
# _extract_points_from_action — FEB format
# ---------------------------------------------------------------------------

class TestExtractPointsFEB:
    def _calc(self):
        return _calc()

    def test_feb_2pt_made_via_text(self):
        action = {'text': 'TIRO DE 2 ANOTADO', 'idTeam': 'T1'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 2
        assert team == 'T1'

    def test_feb_2pt_missed_returns_zero(self):
        action = {'text': 'TIRO DE 2 FALLADO', 'idTeam': 'T1'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 0

    def test_feb_3pt_made_via_text(self):
        action = {'text': 'TRIPLE ANOTADO', 'idTeam': 'T2'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 3
        assert team == 'T2'

    def test_feb_3pt_missed_via_text(self):
        action = {'text': 'TRIPLE FALLADO', 'idTeam': 'T2'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 0

    def test_feb_ft_made_via_text(self):
        action = {'text': 'TIRO LIBRE ANOTADO', 'idTeam': 'T1'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 1
        assert team == 'T1'

    def test_feb_shoot_action_made_2pt(self):
        action = {'action': 'shoot', 'logParam4': '1', 'logParam6': '2', 'idTeam': 'T1', 'text': ''}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 2

    def test_feb_shoot_action_missed_returns_zero(self):
        action = {'action': 'shoot', 'logParam4': '0', 'logParam6': '2', 'idTeam': 'T1', 'text': ''}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 0

    def test_feb_fthrow_made(self):
        action = {'action': 'fthrow', 'logParam4': '1', 'idTeam': 'T1', 'text': ''}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 1

    def test_feb_fthrow_missed(self):
        action = {'action': 'fthrow', 'logParam4': '0', 'idTeam': 'T1', 'text': ''}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 0

    def test_non_scoring_action_returns_zero_team_none(self):
        action = {'action': 'rebound', 'idTeam': 'T1', 'text': 'REBOTE'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 0
        assert team is None


# ---------------------------------------------------------------------------
# _extract_points_from_action — FBCYL format
# ---------------------------------------------------------------------------

class TestExtractPointsFBCYL:
    def _calc(self):
        return _calc(is_fbcyl=True)

    def test_fbcyl_2pt_made(self):
        action = {'move': 'Canasta de 2', 'idTeam': 'T1'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 2
        assert team == 'T1'

    def test_fbcyl_3pt_made(self):
        action = {'move': 'Canasta de 3', 'idTeam': 'T1'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 3

    def test_fbcyl_free_throw_made(self):
        action = {'move': 'Canasta de 1', 'idTeam': 'T2'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 1

    def test_fbcyl_missed_2pt_returns_zero(self):
        action = {'move': 'Intento fallado de 2', 'idTeam': 'T1'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 0

    def test_fbcyl_non_scoring_move(self):
        action = {'move': 'Pérdida de balón', 'idTeam': 'T1'}
        pts, team = self._calc()._extract_points_from_action(action)
        assert pts == 0


# ---------------------------------------------------------------------------
# _process_fbcyl_move — shot stats accumulation
# ---------------------------------------------------------------------------

class TestProcessFBCYLMove:
    def _target(self):
        return {
            'points_for': 0, 'points_against': 0,
            'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
            'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
            'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0,
        }

    def _calc(self):
        return _calc(is_fbcyl=True)

    def test_team_2pt_made_increments_fgm2_fga2(self):
        target = self._target()
        line = {'idTeam': 'T1'}
        self._calc()._process_fbcyl_move(line, 'Canasta de 2', 'T1', 'T1', target, 0, [line])
        assert target['fgm_2'] == 1
        assert target['fga_2'] == 1

    def test_opponent_2pt_made_increments_opp_fgm2(self):
        target = self._target()
        line = {'idTeam': 'T2'}
        self._calc()._process_fbcyl_move(line, 'Canasta de 2', 'T2', 'T1', target, 0, [line])
        assert target['opp_fgm_2'] == 1
        assert target['opp_fga_2'] == 1

    def test_team_missed_2pt(self):
        target = self._target()
        line = {'idTeam': 'T1'}
        self._calc()._process_fbcyl_move(line, 'Intento fallado de 2', 'T1', 'T1', target, 0, [line])
        assert target['fga_2'] == 1
        assert target['fgm_2'] == 0

    def test_team_3pt_made(self):
        target = self._target()
        line = {'idTeam': 'T1'}
        self._calc()._process_fbcyl_move(line, 'Canasta de 3', 'T1', 'T1', target, 0, [line])
        assert target['fgm_3'] == 1
        assert target['fga_3'] == 1

    def test_team_turnover(self):
        target = self._target()
        line = {'idTeam': 'T1'}
        self._calc()._process_fbcyl_move(line, 'Pérdida de balón', 'T1', 'T1', target, 0, [line])
        assert target['tov'] == 1

    def test_opponent_turnover(self):
        target = self._target()
        line = {'idTeam': 'T2'}
        self._calc()._process_fbcyl_move(line, 'Pérdida', 'T2', 'T1', target, 0, [line])
        assert target['opp_tov'] == 1

    def test_team_foul(self):
        target = self._target()
        line = {'idTeam': 'T1'}
        self._calc()._process_fbcyl_move(line, 'Falta personal', 'T1', 'T1', target, 0, [line])
        assert target['pf'] == 1

    def test_team_points_for_updated(self):
        """points_for is incremented by points scored for the team."""
        target = self._target()
        line = {'idTeam': 'T1', 'move': 'Canasta de 2'}
        self._calc()._process_fbcyl_move(line, 'Canasta de 2', 'T1', 'T1', target, 0, [line])
        assert target['points_for'] == 2

    def test_opponent_points_update_points_against(self):
        """Opponent scoring increments points_against."""
        target = self._target()
        line = {'idTeam': 'T2', 'move': 'Canasta de 3'}
        self._calc()._process_fbcyl_move(line, 'Canasta de 3', 'T2', 'T1', target, 0, [line])
        assert target['points_against'] == 3


# ---------------------------------------------------------------------------
# _process_feb_action — stats accumulation
# ---------------------------------------------------------------------------

class TestProcessFEBAction:
    def _target(self):
        return {
            'points_for': 0, 'points_against': 0,
            'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
            'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
            'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0,
        }

    def _calc(self):
        return _calc()

    def test_team_2pt_made(self):
        target = self._target()
        line = {'text': 'TIRO DE 2 ANOTADO', 'idTeam': 'T1', 'action': 'shoot', 'logParam4': '1', 'logParam6': '2'}
        self._calc()._process_feb_action(line, 'TIRO DE 2 ANOTADO', 'shoot', 'T1', 'T1', target, 0, [line], None)
        assert target['fgm_2'] == 1
        assert target['fga_2'] == 1

    def test_team_2pt_missed(self):
        target = self._target()
        line = {'text': 'TIRO DE 2 FALLADO', 'idTeam': 'T1', 'action': 'shoot', 'logParam4': '0', 'logParam6': '2'}
        self._calc()._process_feb_action(line, 'TIRO DE 2 FALLADO', 'shoot', 'T1', 'T1', target, 0, [line], None)
        assert target['fga_2'] == 1
        assert target['fgm_2'] == 0

    def test_team_3pt_made_via_triple(self):
        target = self._target()
        line = {'text': 'TRIPLE ANOTADO', 'idTeam': 'T1', 'action': 'shoot', 'logParam4': '1', 'logParam6': '3'}
        self._calc()._process_feb_action(line, 'TRIPLE ANOTADO', 'shoot', 'T1', 'T1', target, 0, [line], None)
        assert target['fgm_3'] == 1
        assert target['fga_3'] == 1

    def test_team_assist(self):
        target = self._target()
        line = {'text': 'ASISTENCIA DE...', 'idTeam': 'T1', 'action': 'assist'}
        self._calc()._process_feb_action(line, 'ASISTENCIA DE...', 'assist', 'T1', 'T1', target, 0, [line], None)
        assert target['ast'] == 1

    def test_team_steal(self):
        target = self._target()
        line = {'text': 'ROBO DE BALÓN', 'idTeam': 'T1', 'action': 'steal'}
        self._calc()._process_feb_action(line, 'ROBO DE BALÓN', 'steal', 'T1', 'T1', target, 0, [line], None)
        assert target['stl'] == 1

    def test_team_turnover(self):
        target = self._target()
        line = {'text': 'PÉRDIDA', 'idTeam': 'T1', 'action': 'turnover'}
        self._calc()._process_feb_action(line, 'PÉRDIDA', 'turnover', 'T1', 'T1', target, 0, [line], None)
        assert target['tov'] == 1

    def test_team_foul(self):
        target = self._target()
        line = {'text': 'FALTA PERSONAL', 'idTeam': 'T1', 'action': 'foul'}
        self._calc()._process_feb_action(line, 'FALTA PERSONAL', 'foul', 'T1', 'T1', target, 0, [line], None)
        assert target['pf'] == 1

    def test_opponent_action_goes_to_opp_keys(self):
        target = self._target()
        line = {'text': 'TRIPLE ANOTADO', 'idTeam': 'T2', 'action': 'shoot', 'logParam4': '1', 'logParam6': '3'}
        self._calc()._process_feb_action(line, 'TRIPLE ANOTADO', 'shoot', 'T2', 'T1', target, 0, [line], None)
        assert target['opp_fgm_3'] == 1
        assert target['opp_fga_3'] == 1

    def test_returns_last_shot_team_for_rebound_tracking(self):
        target = self._target()
        line = {'text': 'TIRO DE 2 FALLADO', 'idTeam': 'T1', 'action': 'shoot', 'logParam4': '0', 'logParam6': '2'}
        result = self._calc()._process_feb_action(line, 'TIRO DE 2 FALLADO', 'shoot', 'T1', 'T1', target, 0, [line], None)
        # After a missed shot, last_shot_team is tracked
        assert result == 'T1'


# ---------------------------------------------------------------------------
# calculate_in_out_stats — integration with mock analyzer
# ---------------------------------------------------------------------------

class TestCalculateInOutStats:
    """Smoke tests for calculate_in_out_stats using a mock analyzer with
    pre-built court segment data."""

    def _feb_lines(self):
        """Three simple FEB play-by-play lines."""
        return [
            {'action': 'shoot', 'text': 'TIRO DE 2 ANOTADO', 'idTeam': 'T1',
             'logParam4': '1', 'logParam6': '2', 'idPlayer': 'P1', 'tActual': '0:00'},
            {'action': 'shoot', 'text': 'TRIPLE FALLADO', 'idTeam': 'T2',
             'logParam4': '0', 'logParam6': '3', 'idPlayer': 'P2', 'tActual': '0:30'},
            {'action': 'turnover', 'text': 'PÉRDIDA', 'idTeam': 'T2',
             'idPlayer': 'P3', 'tActual': '1:00'},
        ]

    def test_returns_in_and_out_keys(self):
        calc = _calc(lines=self._feb_lines(), is_fbcyl=False)
        # Give the player segments covering the full game
        calc.analyzer.get_player_court_segments.return_value = [{'start': 0, 'end': 600}]
        result = calc.calculate_in_out_stats('P1', 'T1')
        assert 'in' in result
        assert 'out' in result

    def test_in_stats_has_required_keys(self):
        calc = _calc(lines=self._feb_lines(), is_fbcyl=False)
        calc.analyzer.get_player_court_segments.return_value = [{'start': 0, 'end': 600}]
        result = calc.calculate_in_out_stats('P1', 'T1')
        for key in ('points_for', 'points_against', 'fgm_2', 'fga_2', 'tov', 'pf'):
            assert key in result['in'], f"Key '{key}' missing from 'in' stats"

    def test_out_stats_has_required_keys(self):
        calc = _calc(lines=self._feb_lines(), is_fbcyl=False)
        calc.analyzer.get_player_court_segments.return_value = []
        result = calc.calculate_in_out_stats('P1', 'T1')
        for key in ('points_for', 'points_against', 'fgm_2', 'fga_2', 'tov', 'pf'):
            assert key in result['out'], f"Key '{key}' missing from 'out' stats"

    def test_empty_lines_returns_zero_stats(self):
        calc = _calc(lines=[], is_fbcyl=False)
        calc.analyzer.get_player_court_segments.return_value = []
        result = calc.calculate_in_out_stats('P1', 'T1')
        assert result['in']['points_for'] == 0
        assert result['out']['points_for'] == 0
