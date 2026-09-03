"""Tests for PossessionAnalyzer — FASE B quality coverage.

Covers:
- __init__: FEB and FBCYL initialisation, team mapping
- _get_timestamp(): FEB quarter+time → seconds; FBCYL period+min+sec
- _is_possession_ending_event(): FEB and FBCYL format detection
- _get_points_from_move(): point extraction
- _get_team_mapping(): correct team1/team2 mapping
- calculate_possessions(): integration: returns dict with required keys
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from unittest.mock import patch

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.possession_analyzer import PossessionAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feb_game(team1_id='T1', team2_id='T2', lines=None):
    """Minimal FEB game document."""
    return {
        'HEADER': {
            'TEAM': [
                {'id': team1_id, 'name': 'Team 1'},
                {'id': team2_id, 'name': 'Team 2'},
            ],
        },
        'PLAYBYPLAY': {
            'LINES': lines or [],
        },
    }


def _fbcyl_game(team1_id='T1', team2_id='T2', moves=None):
    """Minimal FBCYL game document."""
    return {
        'stats': {
            'teams': [
                {'teamIdIntern': team1_id, 'name': 'Team 1'},
                {'teamIdIntern': team2_id, 'name': 'Team 2'},
            ],
        },
        'moves': moves or [],
    }


def _feb_move(text, action='shoot', team='T1', quarter='1', time='09:00'):
    return {'text': text, 'action': action, 'idTeam': team,
            'quarter': quarter, 'time': time}


def _fbcyl_move(move_text, team='T1', period=1, min_=1, sec=0):
    return {'move': move_text, 'idTeam': team, 'period': period, 'min': min_, 'sec': sec}


# ---------------------------------------------------------------------------
# __init__ and team mapping
# ---------------------------------------------------------------------------

class TestInit:
    def test_feb_init_loads_lines(self):
        lines = [_feb_move('TIRO DE 2 ANOTADO')]
        analyzer = PossessionAnalyzer(_feb_game(lines=lines), is_fbcyl=False)
        assert analyzer.moves == lines

    def test_fbcyl_init_loads_moves(self):
        moves = [_fbcyl_move('Canasta de 2')]
        analyzer = PossessionAnalyzer(_fbcyl_game(moves=moves), is_fbcyl=True)
        assert analyzer.moves == moves

    def test_feb_team_mapping(self):
        analyzer = PossessionAnalyzer(_feb_game('T1', 'T2'), is_fbcyl=False)
        assert analyzer.team_mapping['T1'] == 'team1'
        assert analyzer.team_mapping['T2'] == 'team2'

    def test_fbcyl_team_mapping(self):
        analyzer = PossessionAnalyzer(_fbcyl_game('F1', 'F2'), is_fbcyl=True)
        assert analyzer.team_mapping['F1'] == 'team1'
        assert analyzer.team_mapping['F2'] == 'team2'


# ---------------------------------------------------------------------------
# _get_timestamp
# ---------------------------------------------------------------------------

class TestGetTimestamp:
    def test_feb_first_quarter_start(self):
        """Quarter 1, time 10:00 → 0 seconds elapsed."""
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        move = _feb_move('', quarter='1', time='10:00')
        assert analyzer._get_timestamp(move) == 0

    def test_feb_first_quarter_midpoint(self):
        """Quarter 1, time 5:00 → 300 seconds elapsed."""
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        move = _feb_move('', quarter='1', time='5:00')
        assert analyzer._get_timestamp(move) == 300

    def test_feb_second_quarter(self):
        """Quarter 2, time 10:00 → 600 seconds (quarter 1 complete)."""
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        move = _feb_move('', quarter='2', time='10:00')
        assert analyzer._get_timestamp(move) == 600

    def test_fbcyl_period1_min1_sec0(self):
        """Period 1, minute 1, second 0 → 60 seconds."""
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        move = _fbcyl_move('', period=1, min_=1, sec=0)
        assert analyzer._get_timestamp(move) == 60

    def test_fbcyl_period2_start(self):
        """Period 2, minute 0, second 0 → 600 seconds (period 1 complete)."""
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        move = _fbcyl_move('', period=2, min_=0, sec=0)
        assert analyzer._get_timestamp(move) == 600


# ---------------------------------------------------------------------------
# _is_possession_ending_event
# ---------------------------------------------------------------------------

class TestIsPossessionEndingEvent:
    def test_feb_made_2pt_ends_possession(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        move = _feb_move('TIRO DE 2 ANOTADO')
        assert analyzer._is_possession_ending_event(move) is True

    def test_feb_missed_2pt_does_not_end_possession(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        move = _feb_move('TIRO DE 2 FALLADO')
        assert analyzer._is_possession_ending_event(move) is False

    def test_feb_3pt_made_ends_possession(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        move = _feb_move('TRIPLE ANOTADO')
        assert analyzer._is_possession_ending_event(move) is True

    def test_feb_turnover_ends_possession(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        move = _feb_move('PÉRDIDA DE BALÓN', action='turnover')
        assert analyzer._is_possession_ending_event(move) is True

    def test_fbcyl_canasta_2_ends_possession(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        move = _fbcyl_move('Canasta de 2')
        assert analyzer._is_possession_ending_event(move) is True

    def test_fbcyl_canasta_3_ends_possession(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        move = _fbcyl_move('Canasta de 3')
        assert analyzer._is_possession_ending_event(move) is True

    def test_fbcyl_perdida_ends_possession(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        move = _fbcyl_move('Pérdida de balón')
        assert analyzer._is_possession_ending_event(move) is True

    def test_fbcyl_missed_2pt_does_not_end_possession(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        move = _fbcyl_move('Intento fallado de 2')
        assert analyzer._is_possession_ending_event(move) is False


# ---------------------------------------------------------------------------
# _get_points_from_move
# ---------------------------------------------------------------------------

class TestGetPointsFromMove:
    def test_feb_2pt_made(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        assert analyzer._get_points_from_move(_feb_move('TIRO DE 2 ANOTADO')) == 2

    def test_feb_2pt_missed_zero(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        assert analyzer._get_points_from_move(_feb_move('TIRO DE 2 FALLADO')) == 0

    def test_feb_3pt_made(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        assert analyzer._get_points_from_move(_feb_move('TRIPLE ANOTADO')) == 3

    def test_feb_free_throw_made(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        assert analyzer._get_points_from_move(_feb_move('TIRO LIBRE ANOTADO', action='fthrow')) == 1

    def test_fbcyl_2pt_made(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        assert analyzer._get_points_from_move(_fbcyl_move('Canasta de 2')) == 2

    def test_fbcyl_3pt_made(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        assert analyzer._get_points_from_move(_fbcyl_move('Canasta de 3')) == 3

    def test_fbcyl_free_throw_made(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        assert analyzer._get_points_from_move(_fbcyl_move('Canasta de 1')) == 1

    def test_fbcyl_non_scoring_move(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        assert analyzer._get_points_from_move(_fbcyl_move('Rebote')) == 0


# ---------------------------------------------------------------------------
# calculate_possessions — integration smoke
# ---------------------------------------------------------------------------

class TestCalculatePossessions:
    def test_feb_empty_game_returns_required_keys(self):
        """Empty game → returns dict with the expected structure."""
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')
        assert 'total_possessions' in result
        assert 'avg_duration' in result
        assert 'possessions_by_duration' in result

    def test_fbcyl_empty_game_returns_required_keys(self):
        analyzer = PossessionAnalyzer(_fbcyl_game(), is_fbcyl=True)
        result = analyzer.calculate_possessions('T1')
        assert 'total_possessions' in result
        assert 'avg_duration' in result

    def test_feb_total_possessions_non_negative(self):
        lines = [
            _feb_move('TIRO DE 2 ANOTADO', team='T1', quarter='1', time='9:00'),
            _feb_move('TIRO DE 3 FALLADO', team='T2', quarter='1', time='8:00'),
            _feb_move('PÉRDIDA DE BALÓN', action='turnover', team='T1', quarter='1', time='7:00'),
        ]
        analyzer = PossessionAnalyzer(_feb_game(lines=lines), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')
        assert result['total_possessions'] >= 0

    def test_fbcyl_total_possessions_non_negative(self):
        moves = [
            _fbcyl_move('Canasta de 2', team='T1', period=1, min_=1, sec=0),
            _fbcyl_move('Pérdida de balón', team='T2', period=1, min_=2, sec=0),
            _fbcyl_move('Canasta de 3', team='T1', period=1, min_=3, sec=0),
        ]
        analyzer = PossessionAnalyzer(_fbcyl_game(moves=moves), is_fbcyl=True)
        result = analyzer.calculate_possessions('T1')
        assert result['total_possessions'] >= 0

    def test_possessions_by_duration_has_three_buckets(self):
        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')
        buckets = result['possessions_by_duration']
        assert len(buckets) == 3

    def test_avg_duration_non_negative(self):
        lines = [
            _feb_move('TIRO DE 2 ANOTADO', team='T1', quarter='1', time='9:30'),
        ]
        analyzer = PossessionAnalyzer(_feb_game(lines=lines), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')
        assert result['avg_duration'] >= 0

    @patch('database.possession_analyzer.extract_possession_rows')
    def test_zero_duration_scoring_possession_is_not_dropped(self, mock_extract_rows):
        """0-second scoring possessions have an unreliable duration label but real points that must be kept."""
        mock_extract_rows.return_value = [
            {"Equipo_ID": "T1", "Tipo_finalizacion": "tiro_2", "Duracion_posesion": 0, "Puntos_obtenidos": 2},
            {"Equipo_ID": "T1", "Tipo_finalizacion": "tiro_2", "Duracion_posesion": 8, "Puntos_obtenidos": 0},
        ]

        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')

        assert result['total_possessions'] == 2
        fast = result['possessions_by_duration']['<=8s']
        assert fast['count'] == 2
        assert fast['total_points'] == 2
        assert fast['oer'] == 100.0

    @patch('database.possession_analyzer.extract_possession_rows')
    def test_zero_duration_without_points_is_excluded(self, mock_extract_rows):
        """0-second rows with no points are transition artifacts and must not dilute OER."""
        mock_extract_rows.return_value = [
            {"Equipo_ID": "T1", "Duracion_posesion": 0, "Puntos_obtenidos": 0},
            {"Equipo_ID": "T1", "Duracion_posesion": 8, "Puntos_obtenidos": 2},
        ]

        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')

        assert result['total_possessions'] == 1
        fast = result['possessions_by_duration']['<=8s']
        assert fast['count'] == 1
        assert fast['total_points'] == 2
        assert fast['oer'] == 200.0

    @patch('database.possession_analyzer.extract_possession_rows')
    def test_non_scoring_otro_rows_are_excluded(self, mock_extract_rows):
        """Correction rows (Tipo_finalizacion='otro') with 0 points must not count."""
        mock_extract_rows.return_value = [
            {"Equipo_ID": "T1", "Tipo_finalizacion": "otro", "Duracion_posesion": 7, "Puntos_obtenidos": 0},
            {"Equipo_ID": "T1", "Tipo_finalizacion": "tiro_2", "Duracion_posesion": 10, "Puntos_obtenidos": 2},
        ]

        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')

        assert result['total_possessions'] == 1
        medium = result['possessions_by_duration']['8-16s']
        assert medium['count'] == 1
        assert medium['total_points'] == 2
        assert medium['oer'] == 200.0

    @patch('database.possession_analyzer.extract_possession_rows')
    def test_zero_duration_turnover_is_included(self, mock_extract_rows):
        """Legitimate 0-second turnovers must count as possessions in fast bucket."""
        mock_extract_rows.return_value = [
            {"Equipo_ID": "T1", "Tipo_finalizacion": "violacion", "Duracion_posesion": 0, "Puntos_obtenidos": 0},
            {"Equipo_ID": "T1", "Tipo_finalizacion": "tiro_2", "Duracion_posesion": 8, "Puntos_obtenidos": 2},
        ]

        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')

        assert result['total_possessions'] == 2
        fast = result['possessions_by_duration']['<=8s']
        assert fast['count'] == 2
        assert fast['total_points'] == 2
        assert fast['oer'] == 100.0

    @patch('database.possession_analyzer.extract_possession_rows')
    def test_zero_duration_steal_is_included(self, mock_extract_rows):
        """Legitimate 0-second steal recoveries must count as possessions."""
        mock_extract_rows.return_value = [
            {"Equipo_ID": "T1", "Tipo_finalizacion": "recuperacion", "Duracion_posesion": 0, "Puntos_obtenidos": 0},
            {"Equipo_ID": "T1", "Tipo_finalizacion": "tiro_2", "Duracion_posesion": 8, "Puntos_obtenidos": 2},
        ]

        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')

        assert result['total_possessions'] == 2
        fast = result['possessions_by_duration']['<=8s']
        assert fast['count'] == 2
        assert fast['total_points'] == 2
        assert fast['oer'] == 100.0

    @patch('database.possession_analyzer.extract_possession_rows')
    def test_zero_duration_non_scoring_non_turnover_is_excluded(self, mock_extract_rows):
        """0-second non-scoring endings other than turnover/steal should not inflate fast possessions."""
        mock_extract_rows.return_value = [
            {"Equipo_ID": "T1", "Tipo_finalizacion": "tiro_fallado", "Duracion_posesion": 0, "Puntos_obtenidos": 0},
            {"Equipo_ID": "T1", "Tipo_finalizacion": "tiro_2", "Duracion_posesion": 8, "Puntos_obtenidos": 2},
        ]

        analyzer = PossessionAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_possessions('T1')

        assert result['total_possessions'] == 1
        fast = result['possessions_by_duration']['<=8s']
        assert fast['count'] == 1
        assert fast['total_points'] == 2
        assert fast['oer'] == 200.0
