"""Normalised play-by-play events parsed from FEB ``PLAYBYPLAY.LINES``.

Matching relies on the ``action`` field plus accent-insensitive keywords of the Spanish
text: the stored sample contains mojibake in accented words, so accented letters are
never required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .clock import elapsed_seconds, parse_clock

_NAME_RE = re.compile(r"^\([^)]*\)\s*([^:]+):")
_SHOT_RE = re.compile(r"TIRO DE (\d) (ANOTADO|FALLADO)", re.IGNORECASE)
_PF_RE = re.compile(r"Faltas:\s*(\d+)\.")

_SIMPLE_KINDS = {
    "rebound": "rebound",
    "lose": "turnover",
    "recovery": "steal",
    "assist": "assist",
    "blockshot": "block",
    "timeout": "timeout",
}

_NOT_DELETED = (None, "", "0", "false", "False", 0, False)


@dataclass(frozen=True)
class Event:
    num: int
    period: int
    remaining: int
    elapsed: int
    kind: str
    team_id: Optional[str] = None
    player_id: Optional[str] = None
    name: Optional[str] = None
    made: Optional[bool] = None
    points: int = 0
    foul_type: Optional[str] = None
    pf_count: Optional[int] = None
    deleted: bool = False
    text: str = ""


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _foul_type(text: str) -> str:
    upper = text.upper()
    if "ANTIDEPORTIVA" in upper:
        return "unsportsmanlike"
    if "PERSONAL" in upper:
        return "personal"
    if "CNICA" in upper:  # "Técnica" (accent may be broken)
        return "technical"
    return "other"


def _classify(action: str, text: str) -> Dict[str, Any]:
    lower = text.lower()
    if action == "subst":
        if "entra a pista" in lower:
            return {"kind": "sub_in"}
        if "sale de pista" in lower:
            return {"kind": "sub_out"}
        return {"kind": "other"}
    if action in ("shoot", "fthrow"):
        match = _SHOT_RE.search(text)
        if not match:
            return {"kind": "other"}
        value, made = int(match.group(1)), match.group(2).upper() == "ANOTADO"
        kind = "ft" if action == "fthrow" or value == 1 else f"fg{value}"
        return {"kind": kind, "made": made, "points": (1 if kind == "ft" else value) if made else 0}
    if action == "foul":
        pf = _PF_RE.search(text)
        return {"kind": "foul", "foul_type": _foul_type(text), "pf_count": int(pf.group(1)) if pf else None}
    if action == "period":
        if lower.lstrip().startswith("comienzo"):
            return {"kind": "period_start"}
        if lower.lstrip().startswith("fin"):
            return {"kind": "period_end"}
        return {"kind": "other"}
    return {"kind": _SIMPLE_KINDS.get(action, "other")}


def parse_line(line: Dict[str, Any]) -> Optional[Event]:
    """Parse one FEB PBP line; None when it lacks a usable number/period/clock."""
    num = _to_int(line.get("num"))
    period = _to_int(line.get("quarter"))
    remaining = parse_clock(line.get("time"))
    if num is None or period is None or remaining is None:
        return None

    text = line.get("text") or ""
    name = _NAME_RE.match(text)
    return Event(
        num=num,
        period=period,
        remaining=remaining,
        elapsed=elapsed_seconds(period, remaining),
        team_id=line.get("idTeam"),
        player_id=line.get("idPlayer"),
        name=name.group(1).strip() if name else None,
        deleted=line.get("deleted") not in _NOT_DELETED,
        text=text,
        **_classify(line.get("action") or "", text),
    )
