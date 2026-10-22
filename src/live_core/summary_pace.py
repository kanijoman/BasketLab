"""The pace of a quarter, as data of its summary (issue #419).

The summary used to ask to "keep the pace" without measuring it. Here the pace of the summarised window is computed from the event
log (possessions = FGA - ORB + TOV + 0.44 FTA, the mean of both teams, per 40 minutes, as ``pace.py`` does for the whole game) and put
next to the quarters before it and the usual pace of both teams (package baselines). A recommendation about the pace only comes when
the numbers back it. Standard library only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from .four_factors import FT_POSSESSION_COST
from .windows import window_stats

GAME_SECONDS = 2400
MIN_POSSESSIONS = 8        # fewer possessions per team in the window say nothing about the pace


def _possessions(stats: Dict[str, Any]) -> float:
    return stats["fg2"][1] + stats["fg3"][1] - stats["orb"] + stats["tov"] + FT_POSSESSION_COST * stats["ft"][1]


def window_pace(log: Sequence[Sequence[Any]], own: str, rival: str, start: int, end: int) -> Optional[float]:
    """Possessions per 40 minutes (mean of both teams) in ``[start, end]``, or None with too little play to say."""
    if end <= start:
        return None
    mean = (_possessions(window_stats(log, own, start, end)) + _possessions(window_stats(log, rival, start, end))) / 2
    return mean / (end - start) * GAME_SECONDS if mean >= MIN_POSSESSIONS else None


def pace_facts(log: Sequence[Sequence[Any]], own: str, rival: str, start: int, end: int,
               baselines: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Optional[float]]]:
    """The pace of the window, of the game before it and the usual paces of both teams; None when the window has no pace."""
    current = window_pace(log, own, rival, start, end)
    if current is None:
        return None
    before = window_pace(log, own, rival, 0, start) if start > 0 else None
    base = baselines or {}
    rounded = lambda v: None if v is None else round(float(v), 1)  # noqa: E731
    return {"per40": rounded(current), "before40": rounded(before),
            "own_habit40": rounded(base.get("pace_own_per_40")), "rival_habit40": rounded(base.get("pace_rival_per_40"))}


def pace_line(pace: Optional[Dict[str, Optional[float]]]) -> str:
    """``Ritmo: 80 posesiones por 40 min frente a 60 antes (habitual: 70 el nuestro y 64 el rival).`` or an empty text."""
    if not pace:
        return ""
    text = f"Ritmo: {pace['per40']:.0f} posesiones por 40 min"
    if pace["before40"] is not None:
        text += f" frente a {pace['before40']:.0f} antes"
    if pace["own_habit40"] is not None and pace["rival_habit40"] is not None:
        text += f" (habitual: {pace['own_habit40']:.0f} el nuestro y {pace['rival_habit40']:.0f} el rival)"
    return text + "."


def pace_key(pace: Optional[Dict[str, Optional[float]]], net: int, delta: float, min_net: int) -> Optional[Tuple[str, str]]:
    """A key when the pace changed and the result of the quarter says who it favoured (#488): faster and won, or slower and won, keeps that regime;
    faster and lost, or slower and lost, leaves it (competitive advantage, not the score alone)."""
    if not pace or pace["before40"] is None:
        return None
    change = pace["per40"] - pace["before40"]
    if abs(change) < delta or abs(net) < min_net:
        return None
    word, result = ("alto", "ganó") if change > 0 and net > 0 else ("alto", "perdió") if change > 0 else ("bajo", "ganó") if net > 0 else ("bajo", "perdió")
    key = f"Ritmo más {word} que antes ({change:+.0f}) y el cuarto se {result} ({net:+d})"
    if change > 0:
        return key, ("Mantener el ritmo alto que nos ha favorecido" if net > 0 else "Bajar el ritmo: el cuarto más rápido nos ha perjudicado, atacar más tiempo cada posesión")
    return key, ("Mantener el ritmo bajo que nos ha favorecido" if net > 0 else "Subir el ritmo: el cuarto ha sido más lento que los anteriores")
