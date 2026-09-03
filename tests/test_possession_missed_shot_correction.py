"""Regression coverage for possession ownership mismatches on missed shots."""
from __future__ import annotations

from src.services.possession_export_service import PossessionExportService


def _move(number, team_id, text, action, clock):
    return {
        "num": str(number),
        "idTeam": team_id,
        "text": text,
        "action": action,
        "quarter": "2",
        "time": clock,
    }


def test_missed_shot_by_other_team_closes_the_stale_possession():
    """A missed shot must correct possession ownership before rebound handling."""
    game = {
        "HEADER": {"TEAM": [
            {"id": "T1", "name": "Local"},
            {"id": "T2", "name": "Visitante"},
        ]},
        "PLAYBYPLAY": {"LINES": [
            _move(157, "T2", "REBOTE", "rebound", "7:04"),
            _move(156, "T1", "TIRO DE 2 FALLADO", "shoot", "7:04"),
            _move(150, "T1", "PÉRDIDA", "lose", "7:36"),
            _move(148, "T2", "TIRO DE 2 ANOTADO", "shoot", "7:50"),
        ]},
    }

    rows = PossessionExportService(game, is_fbcyl=False, game_id="TEST").extract_possessions()

    stale_possession = next(row for row in rows if row["Equipo_ID"] == "T2" and row["Tiempo_de_juego"] == "7:36")
    missed_shot = next(row for row in rows if row["Equipo_ID"] == "T1" and row["Tiempo_de_juego"] == "7:04")
    assert stale_possession["Duracion_posesion"] == 32
    assert missed_shot["Tipo_finalizacion"] == "tiro_fallado"
    assert missed_shot["Duracion_posesion"] == 0
