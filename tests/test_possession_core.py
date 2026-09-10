"""Contract tests for the shared possession core module."""
from __future__ import annotations

import sys
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.possession_core import extract_possession_rows, order_possession_moves


def _move(number, team_id, text, action, clock):
    return {
        "num": str(number),
        "idTeam": team_id,
        "text": text,
        "action": action,
        "quarter": "1",
        "time": clock,
    }


def test_order_possession_moves_sorts_feb_same_timestamp_by_event_number():
    moves = [
        _move(45, "T2", "REBOTE", "rebound", "5:32"),
        _move(44, "T1", "TIRO DE 3 FALLADO", "shoot", "5:32"),
    ]

    ordered = order_possession_moves(moves, is_fbcyl=False)

    assert [m["num"] for m in ordered] == ["44", "45"]


def test_tracker_correction_still_produces_otro_row_at_core_level():
    """The unfiltered core must still emit the 'otro' correction row — only the
    CSV exporter (PossessionExportService) filters it out for end users."""
    game = {
        "HEADER": {"TEAM": [
            {"id": "T1", "name": "Local"},
            {"id": "T2", "name": "Visitante"},
        ]},
        "PLAYBYPLAY": {"LINES": [
            _move(1, "T1", "REBOTE DEFENSIVO", "rebound", "9:00"),
            _move(2, "T2", "TIRO DE 2 ANOTADO", "shoot", "8:30"),
        ]},
    }
    team_info = {
        "T1": {"name": "Local", "home_away": "Local"},
        "T2": {"name": "Visitante", "home_away": "Visitante"},
    }

    rows = extract_possession_rows(
        game_data=game, is_fbcyl=False, game_id="TEST", team_info=team_info,
    )

    forced_close = [r for r in rows if r["Tipo_finalizacion"] == "otro" and r["Puntos_obtenidos"] == 0]
    assert forced_close, "Core extraction must still produce the 'otro' correction row"


def test_extract_possession_rows_returns_export_columns_contract():
    game = {
        "HEADER": {"TEAM": [
            {"id": "T1", "name": "Local"},
            {"id": "T2", "name": "Visitante"},
        ]},
        "PLAYBYPLAY": {"LINES": [
            _move(2, "T1", "TIRO DE 2 ANOTADO", "shoot", "9:00"),
            _move(1, "T2", "PÉRDIDA", "turnover", "9:00"),
        ]},
    }
    team_info = {
        "T1": {"name": "Local", "home_away": "Local"},
        "T2": {"name": "Visitante", "home_away": "Visitante"},
    }

    rows = extract_possession_rows(
        game_data=game,
        is_fbcyl=False,
        game_id="TEST",
        team_info=team_info,
    )

    assert rows
    first = rows[0]
    assert "ID_Partido" in first
    assert "Equipo_ID" in first
    assert "Tiempo_de_juego" in first
    assert "Duracion_posesion" in first
    assert "Controversial_Possession" in first
