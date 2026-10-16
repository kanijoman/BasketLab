"""Classification helpers of the possession reconstruction: how a possession ends and starts."""
from __future__ import annotations

from typing import Dict, Optional

from .event_helpers import (
    is_ft_event,
    is_missed_fg,
    is_missed_ft,
    is_rebound,
    is_steal,
    is_turnover,
    points_from_move,
)


def is_controversial_possession(duration: int, points: int) -> bool:
    """Flag possessions that should be reviewed in quality workflows."""
    if duration == 0 and points > 0:
        return True
    if duration > 90:
        return True
    if duration > 40:
        return True
    return False


def _is_shot_attempt(move: Dict, is_fbcyl: bool) -> bool:
    text = str(move.get("move") or "") if is_fbcyl else str(move.get("text") or "")
    text_u = text.upper()
    return (
        is_ft_event(move, is_fbcyl)
        or is_missed_fg(move, is_fbcyl)
        or (not is_fbcyl and ("TIRO DE 2" in text_u or "TIRO DE 3" in text_u or "TRIPLE" in text_u)
            and "FALLADO" not in text_u and "FALLA" not in text_u)
        or (is_fbcyl and ("Canasta de 2" in text or "Canasta de 3" in text))
    )


def _period_changed(curr: Dict, prev: Dict, is_fbcyl: bool) -> bool:
    if is_fbcyl:
        return curr.get("period") != prev.get("period")
    return str(curr.get("quarter") or "") != str(prev.get("quarter") or "")


def _classify_ending(move: Dict, points: int, idx: int, steal_tovs: frozenset, is_fbcyl: bool) -> str:
    text = str(move.get("move") or "") if is_fbcyl else str(move.get("text") or "")
    text_u = text.upper()
    if is_turnover(move, is_fbcyl):
        return "recuperacion" if idx in steal_tovs else "violacion"
    if is_missed_fg(move, is_fbcyl):
        return "tiro_fallado"
    if is_ft_event(move, is_fbcyl) or is_missed_ft(move, is_fbcyl):
        return "tiros_libres"
    effective_pts = points if points > 0 else points_from_move(move, is_fbcyl)
    if effective_pts == 3:
        return "triple"
    if effective_pts == 2:
        if "BANDEJA" in text_u or "LAYUP" in text_u or "bandeja" in text.lower():
            return "bandeja"
        if "MATE" in text_u or "SLAM" in text_u or "mate" in text.lower():
            return "mate"
        return "tiro_2"
    if effective_pts >= 1:
        return "tiros_libres"
    if is_rebound(move, is_fbcyl):
        return "rebote_defensivo"
    if is_steal(move, is_fbcyl):
        return "recuperacion"
    return "otro"


def _classify_origin(prev_ending: Optional[str], start_move: Optional[Dict], is_period_start: bool) -> str:
    del start_move
    if is_period_start:
        return "saque_inicial_periodo"
    if prev_ending is None:
        return "inicio_partido"
    if prev_ending in ("rebote_defensivo", "tiro_fallado"):
        return "rebote_defensivo"
    if prev_ending == "recuperacion":
        return "recuperacion"
    if prev_ending == "violacion":
        return "violacion"
    return "saque_fondo"


def _quarter_clock(move: Optional[Dict], is_fbcyl: bool) -> str:
    if move is None:
        return "10:00"
    if is_fbcyl:
        period = int(move.get("period") or 1)
        quarter_secs = 300 if period > 4 else 600
        elapsed = int(move.get("min") or 0) * 60 + int(move.get("sec") or 0)
        remaining = max(0, quarter_secs - elapsed)
        mins, secs = divmod(remaining, 60)
        return f"{mins:02d}:{secs:02d}"
    raw = str(move.get("time") or "10:00")
    return raw if ":" in raw else "10:00"


def _period_start_timestamp(move: Dict, is_fbcyl: bool) -> int:
    period = int(move.get("period" if is_fbcyl else "quarter") or 1)
    if period > 4:
        return 4 * 600 + (period - 5) * 300
    return (period - 1) * 600
