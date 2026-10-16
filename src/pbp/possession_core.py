"""Possession rows (one per possession) for exports and analyzers, built with the shared possession tracker.

The state machine lives in ``src.live_core.possessions`` (one for live, scouting and statistics); this module turns
its possessions into the row format the CSV export and ``PossessionAnalyzer`` use, for FEB and FBCYL.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

from src.live_core.clock import period_length, period_start
from src.live_core.events import Event, parse_line
from src.live_core.events_fbcyl import parse_moves
from src.live_core.possessions import Possession, track

from .possession_quality import QUALITY_METRICS, count_quality_pbp_metrics, previous_missed_shot_index

__all__ = [
    "QUALITY_METRICS", "count_quality_pbp_metrics", "extract_possession_rows", "is_controversial_possession",
    "is_tab_evaluated_possession", "previous_missed_shot_index",
]

_ZERO_DURATION_VALID_ENDINGS = frozenset(("violacion", "recuperacion"))
_ORIGIN = {"period_start": "saque_inicial_periodo", "def_rebound": "rebote_defensivo", "team_def_rebound": "rebote_defensivo",
           "steal": "recuperacion", "turnover": "violacion"}
_FG_ENDING = {"fg3": "triple", "dunk": "mate"}


def is_controversial_possession(duration: int, points: int) -> bool:
    """Flag possessions that should be reviewed in quality workflows."""
    if duration == 0 and points > 0:
        return True
    return duration > 40


def is_tab_evaluated_possession(row: Dict) -> bool:
    """Return True if the possessions tab includes this row in its OER/pace stats.

    Drops the possessions the tracker had to infer (``otro`` with 0 points) and those with an implausible duration,
    unless they scored or ended in a way that is inherently duration-independent (violación/recuperación).
    """
    duration = int(row.get("Duracion_posesion") or 0)
    points = int(row.get("Puntos_obtenidos") or 0)
    ending_type = str(row.get("Tipo_finalizacion") or "")
    if ending_type == "otro" and points == 0:
        return False
    if 0 < duration <= 90:
        return True
    return duration == 0 and (points > 0 or ending_type in _ZERO_DURATION_VALID_ENDINGS)


def extract_possession_rows(game_data: Dict, is_fbcyl: bool, game_id: str, team_info: Dict[str, Dict]) -> List[Dict]:
    """Return canonical possession rows used by exporter and analyzer."""
    events = _events(game_data, is_fbcyl)
    team_ids = _team_ids(team_info, events)
    if len(team_ids) != 2:
        return []
    possessions, _ = track(events, team_ids)
    score = {tid: 0 for tid in team_ids}
    rows = []
    for poss in possessions:
        rival = team_ids[1] if poss.team_id == team_ids[0] else team_ids[0]
        rows.append(_row(poss, rival, score[poss.team_id] - score[rival], game_id, team_info))
        score[poss.team_id] += poss.points
    return rows


def _events(game_data: Dict, is_fbcyl: bool) -> List[Event]:
    if is_fbcyl:
        return parse_moves(game_data.get("moves") or [])
    lines = (game_data.get("PLAYBYPLAY") or {}).get("LINES") or []
    # the real feed always has a line number; without one the position in the list is the order
    numbered = [line if line.get("num") not in (None, "") else {**line, "num": str(i + 1)} for i, line in enumerate(lines)]
    return [e for e in (parse_line(line) for line in numbered) if e is not None]


def _team_ids(team_info: Dict[str, Dict], events: Sequence[Event]) -> List[str]:
    ids = [str(t) for t in team_info]
    if len(ids) == 2:
        return ids
    seen = sorted({e.team_id for e in events if e.team_id and e.kind in ("fg2", "fg3", "ft", "turnover", "rebound")})
    return seen if len(seen) == 2 else []


def _clock(poss: Possession) -> str:
    remaining = max(0, period_start(poss.period) + period_length(poss.period) - poss.start_elapsed)
    return f"{remaining // 60:02d}:{remaining % 60:02d}"


def _ending(poss: Possession) -> str:
    if poss.outcome == "made_fg":
        return _FG_ENDING.get(poss.shot_kind, "tiro_2")
    if poss.outcome in ("ft_made", "trip"):
        return "tiros_libres"
    if poss.outcome == "missed_shot":
        return "tiros_libres" if poss.shot_kind == "ft" else "tiro_fallado"
    if poss.outcome == "turnover":
        return "recuperacion" if poss.steal else "violacion"
    return "otro"


def _row(poss: Possession, rival: str, margin: int, game_id: str, team_info: Dict[str, Dict]) -> Dict:
    info, rival_info = team_info.get(poss.team_id, {}), team_info.get(rival, {})
    return {
        "ID_Partido": game_id,
        "Equipo": info.get("name", poss.team_id),
        "Equipo_ID": poss.team_id,
        "Rival": rival_info.get("name", rival),
        "Rival_ID": rival,
        "Local_Visitante": info.get("home_away", ""),
        "Cuarto": str(poss.period),
        "Tiempo_de_juego": _clock(poss),
        "Diferencia_marcador": margin,
        "Origen_posesion": _ORIGIN.get(poss.origin, "saque_fondo"),
        "Duracion_posesion": poss.duration,
        "Tipo_finalizacion": _ending(poss),
        "Puntos_obtenidos": poss.points,
        "Tiene_rebote_ofensivo": 1 if poss.orebs or poss.repaired_orebs else 0,
        "Controversial_Possession": is_controversial_possession(poss.duration, poss.points),
        # data quality of the source: a feed error can make a possession inferred or repaired
        "Posesion_contada": 1 if poss.counted else 0,
        "Posesion_reparada": 1 if poss.repaired else 0,
        "Hueco_previo": 1 if poss.gap_before else 0,
        "Puntos_segunda_oportunidad": poss.second_chance_points,
    }
