"""Normalised events from FBCYL moves, the same ``Event`` the FEB parser produces.

FBCYL reports the time REMAINING in the period (``min``/``sec`` count down from 10:00 to 0:00, like FEB; checked on
the sample and on 6 real games: the first move is at 10:00 and the last at 0:00, and the capture ``timestamp`` grows
while ``min:sec`` falls) and has no line numbers: the position in the list is the order. Matching is
accent-insensitive (the stored data has mojibake). Notes on the real feed:

* "Mate" / "Mate fuera" are lines of a dunk made / missed, written after its own offensive rebound.
* A foul is written twice: "Falta, 3a falta" for who commits it and "Falta recibida" for who suffers it; only the
  first is a foul here. Technical and unsportsmanlike fouls carry their name when the feed gives it.
* Offensive fouls ("Falta en ataque") are followed by their own "Pérdida".
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .clock import period_length, period_start
from .events import Event

_SHOT = re.compile(r"^(canasta|intento fallado) de ([123])$")


def _foul_type(low: str) -> str:
    if "antideportiva" in low:
        return "unsportsmanlike"
    if "cnica" in low:
        return "technical"
    if low.startswith("falta en ataque"):
        return "other"
    return "personal"


def _classify(text: str) -> Dict[str, Any]:
    low = text.lower().strip()
    shot = _SHOT.match(low)
    if shot:
        value, made = int(shot.group(2)), shot.group(1) == "canasta"
        return {"kind": "ft" if value == 1 else f"fg{value}", "made": made, "points": value if made else 0}
    if low in ("mate", "mate fuera"):
        made = low == "mate"
        return {"kind": "fg2", "made": made, "points": 2 if made else 0}
    if low.startswith("rebote"):
        return {"kind": "rebound"}
    if low.startswith("p") and "rdida" in low:
        return {"kind": "turnover"}
    if low.startswith("recuperaci"):
        return {"kind": "steal"}
    if low.startswith("asistencia"):
        return {"kind": "assist"}
    if low.startswith("tap"):
        return {"kind": "block"}
    if low.startswith("entra al campo"):
        return {"kind": "sub_in"}
    if low.startswith("sale del campo"):
        return {"kind": "sub_out"}
    if low.startswith("tiempo muerto"):
        return {"kind": "timeout"}
    if low.startswith("fin de"):
        return {"kind": "period_end"}
    if low.startswith(("comienzo", "inicio")):
        return {"kind": "period_start"}
    if low.startswith(("falta,", "personal", "antideportiva", "técnica", "tecnica", "t�cnica", "descalificante",
                       "falta en ataque")):
        return {"kind": "foul", "foul_type": _foul_type(low)}
    return {"kind": "other"}


def parse_move(move: Dict[str, Any], index: int) -> Optional[Event]:
    """One FBCYL move -> ``Event``; None when it lacks a usable period or clock. ``index`` is its position in the game."""
    try:
        period, remaining = int(move["period"]), int(move["min"]) * 60 + int(move["sec"])
    except (KeyError, TypeError, ValueError):
        return None
    team = move.get("idTeam")
    actor = move.get("actorId")
    return Event(
        num=index + 1, period=period, remaining=remaining,
        elapsed=period_start(period) + period_length(period) - remaining, team_id=str(team) if team else None,
        player_id=str(actor) if actor else None, name=move.get("actorName"), text=str(move.get("move") or ""),
        **_classify(str(move.get("move") or "")))


def parse_moves(moves: List[Dict[str, Any]]) -> List[Event]:
    return [e for e in (parse_move(m, i) for i, m in enumerate(moves)) if e is not None]
