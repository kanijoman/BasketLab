"""Kinds of proposal an alert can carry besides substitutions (``type: "sub"``, built by the recommender).

* ``timeout``: call a timeout; ``left`` is how many the own team still has (the engine fills it in).
* ``tactic``: a tactical instruction, optionally aimed at one player (``player_id`` / ``player_name``).

Plain dicts, like the substitutions, so they travel as JSON to the app.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def timeout_message(left: int) -> str:
    if left <= 0:
        return "Tiempo muerto · no quedan"
    return "Tiempo muerto · queda 1" if left == 1 else f"Tiempo muerto · quedan {left}"


def timeout_proposal(left: int) -> Dict[str, Any]:
    return {"type": "timeout", "left": left, "message": timeout_message(left)}


def tactic_proposal(message: str, player_id: Optional[str] = None, player_name: Optional[str] = None) -> Dict[str, Any]:
    proposal: Dict[str, Any] = {"type": "tactic", "message": message}
    if player_id is not None:
        proposal["player_id"] = player_id
    if player_name is not None:
        proposal["player_name"] = player_name
    return proposal
