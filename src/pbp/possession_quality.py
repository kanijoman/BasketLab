"""Per-team quality counts from the play-by-play (T2/T3/T1 made-attempted, rebounds, turnovers)."""
from __future__ import annotations

from typing import Dict, List, Optional

from .event_helpers import (
    detect_offensive_rebounds,
    is_ft_event,
    is_missed_fg,
    is_missed_ft,
    is_rebound,
    is_turnover,
)
from .possession_moves import _NEUTRAL, _get_moves, order_possession_moves


QUALITY_METRICS = ("T2M", "T2A", "T3M", "T3A", "T1M", "T1A", "RebO", "RebD", "TOV")


def count_quality_pbp_metrics(game_data: Dict, is_fbcyl: bool, team_ids: List[str]) -> Dict[str, Dict[str, int]]:
    """Count per-team quality metrics from PBP using shared ordering and rebound lookup."""
    counts = {tid: {metric: 0 for metric in QUALITY_METRICS} for tid in team_ids}
    moves = order_possession_moves(_get_moves(game_data, is_fbcyl), is_fbcyl)
    orebs = detect_offensive_rebounds(moves, is_fbcyl)

    for idx, move in enumerate(moves):
        tid = str(move.get("idTeam") or "")
        if tid not in counts:
            continue
        _update_quality_counts_for_move(counts[tid], moves, idx, orebs, is_fbcyl)
    return counts


def previous_missed_shot_index(moves: List[Dict], rebound_idx: int, is_fbcyl: bool) -> Optional[int]:
    """Return index of the closest preceding missed shot linked to a rebound event."""
    for offset in range(1, min(5, rebound_idx + 1)):
        previous_idx = rebound_idx - offset
        previous = moves[previous_idx]
        action = str(previous.get("action") or "").lower()
        if action in _NEUTRAL:
            continue
        if is_missed_fg(previous, is_fbcyl) or is_missed_ft(previous, is_fbcyl):
            return previous_idx
        text = str(previous.get("move") or "") if is_fbcyl else str(previous.get("text") or "")
        text_upper = text.upper()
        if ("ANOTADO" in text_upper and "FALLADO" not in text_upper) or is_turnover(previous, is_fbcyl):
            break
        if action in ("rebound", "steal") or "REBOTE" in text_upper or "ROBO" in text_upper:
            break
    return None


def _update_quality_counts_for_move(
    team_counts: Dict[str, int],
    moves: List[Dict],
    idx: int,
    orebs: set,
    is_fbcyl: bool,
) -> None:
    move = moves[idx]
    text = str(move.get("move") or "") if is_fbcyl else str(move.get("text") or "")
    if _count_ft_quality_event(team_counts, move, is_fbcyl):
        return
    if _count_fg_quality_event(team_counts, move, text, is_fbcyl):
        return
    if not is_fbcyl and is_rebound(move, is_fbcyl) and not move.get("idPlayer"):
        return  # team rebound (no player) — official boxscore ro/rd totals don't credit these
    if _count_rebound_quality_event(team_counts, moves, idx, orebs, is_fbcyl):
        return
    if is_turnover(move, is_fbcyl):
        team_counts["TOV"] += 1


def _count_ft_quality_event(team_counts: Dict[str, int], move: Dict, is_fbcyl: bool) -> bool:
    if not is_ft_event(move, is_fbcyl):
        return False
    team_counts["T1A"] += 1
    if not is_missed_ft(move, is_fbcyl):
        team_counts["T1M"] += 1
    return True


def _count_fg_quality_event(team_counts: Dict[str, int], move: Dict, text: str, is_fbcyl: bool) -> bool:
    text_u = text.upper()
    if not is_fbcyl:
        if "TIRO DE 3" in text_u or "TRIPLE" in text_u:
            team_counts["T3A"] += 1
            if "FALLADO" not in text_u and "FALLA" not in text_u:
                team_counts["T3M"] += 1
            return True
        if "TIRO DE 2" in text_u:
            team_counts["T2A"] += 1
            if "FALLADO" not in text_u and "FALLA" not in text_u:
                team_counts["T2M"] += 1
            return True
        return False

    text_l = text.lower()
    if "Canasta de 3" in text or "Intento fallado de 3" in text or ("fallado" in text_l and "de 3" in text_l):
        team_counts["T3A"] += 1
        if "Canasta de 3" in text:
            team_counts["T3M"] += 1
        return True
    if "Canasta de 2" in text or "Intento fallado de 2" in text or ("fallado" in text_l and "de 2" in text_l):
        team_counts["T2A"] += 1
        if "Canasta de 2" in text:
            team_counts["T2M"] += 1
        return True
    if is_missed_fg(move, is_fbcyl):
        team_counts["T2A"] += 1
        return True
    return False


def _count_rebound_quality_event(
    team_counts: Dict[str, int],
    moves: List[Dict],
    idx: int,
    orebs: set,
    is_fbcyl: bool,
) -> bool:
    move = moves[idx]
    if not is_rebound(move, is_fbcyl):
        return False
    missed_idx = previous_missed_shot_index(moves, idx, is_fbcyl)
    if missed_idx in orebs:
        team_counts["RebO"] += 1
        return True
    if missed_idx is None:
        return True
    prev_tid = str(moves[missed_idx].get("idTeam") or "")
    curr_tid = str(move.get("idTeam") or "")
    if prev_tid != curr_tid:
        team_counts["RebD"] += 1
    return True
