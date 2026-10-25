"""How a score is written in the alerts (feedback 0.4.0, #560): like the scoreboard, the local team first.

The engine thinks from OUR side, but the staff reads the scoreboard: ``24-22`` there must be ``24-22`` in the notice, whoever we are. When the local team is the rival the
points of the rival go first and the difference says whose it is. Standard library only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

# the header's score is the one on the scoreboard; it can be used for a period end only while it is still that end (a late poll has the next period's points in it)
HEADER_FRESH_S = 10


def own_first(snap: Dict[str, Any], own_id: str) -> bool:
    """Our points go first unless the snapshot says the local team is the other one (an old snapshot without ``home_id`` keeps our team first)."""
    home = snap.get("home_id")
    return home is None or home == own_id


def score_text(snap: Dict[str, Any], own_id: str, own_pts: int, rival_pts: int) -> str:
    """``24-22 (+2)``; with the rival as the local team ``22-24 (+2 para nosotros)``: the sign is always ours."""
    net = own_pts - rival_pts
    if own_first(snap, own_id):
        return f"{own_pts}-{rival_pts} ({net:+d})"
    return f"{rival_pts}-{own_pts} ({net:+d} para nosotros)"


def plain_score(snap: Dict[str, Any], own_id: str, own_pts: int, rival_pts: int) -> str:
    """``24-22`` in the order of the scoreboard, without the difference."""
    return f"{own_pts}-{rival_pts}" if own_first(snap, own_id) else f"{rival_pts}-{own_pts}"


def header_score(snap: Dict[str, Any], own_id: str, rival_id: str, end: int) -> Optional[Tuple[int, int]]:
    """``(own, rival)`` of FEB's header when it can stand for the score at ``end`` (it has points and the snapshot is within ``HEADER_FRESH_S`` of that moment)."""
    header = snap.get("score") or {}
    if own_id not in header or rival_id not in header or sum(header.values()) <= 0 or snap["elapsed"] - end > HEADER_FRESH_S:
        return None
    return int(header[own_id]), int(header[rival_id])
