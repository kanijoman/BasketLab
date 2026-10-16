"""Regression tests for FEB play-by-play events sharing the same clock tick."""
from __future__ import annotations

from src.pbp.possession_core import extract_possession_rows

_TEAM_INFO = {
    "T1": {"name": "Local", "home_away": "Local"},
    "T2": {"name": "Visitante", "home_away": "Visitante"},
}


def _move(number, team_id, text, action, clock):
    return {
        "num": str(number),
        "idTeam": team_id,
        "text": text,
        "action": action,
        "quarter": "1",
        "time": clock,
    }


def test_same_timestamp_feb_miss_precedes_rebound_when_json_is_reverse_stored():
    """A rebound stored before its same-clock miss must not merge possessions.

    The trailing T2 possession (its rebound at 5:32) has no event after it, so the tracker
    does not emit it.
    """
    game = {
        "HEADER": {"TEAM": [
            {"id": "T1", "name": "Local"},
            {"id": "T2", "name": "Visitante"},
        ]},
        "PLAYBYPLAY": {"LINES": [
            _move(45, "T2", "REBOTE", "rebound", "05:32"),
            _move(44, "T1", "TIRO DE 3 FALLADO", "shoot", "05:32"),
            _move(43, "T2", "TIRO DE 2 FALLADO", "shoot", "05:51"),
            _move(42, "T2", "REBOTE", "rebound", "06:03"),
            _move(41, "T1", "TIRO DE 3 FALLADO", "shoot", "06:03"),
        ]},
    }

    rows = extract_possession_rows(game_data=game, is_fbcyl=False, game_id="TEST", team_info=_TEAM_INFO)

    t2_at_603 = [row for row in rows if row["Equipo_ID"] == "T2" and row["Tiempo_de_juego"] == "06:03"]
    t1_at_551 = [row for row in rows if row["Equipo_ID"] == "T1" and row["Tiempo_de_juego"] == "05:51"]

    assert len(t2_at_603) == 1
    assert t2_at_603[0]["Duracion_posesion"] == 12
    assert len(t1_at_551) == 1
    assert t1_at_551[0]["Duracion_posesion"] == 19
    assert not any(row["Duracion_posesion"] == 45 for row in rows)
