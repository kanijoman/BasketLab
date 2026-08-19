"""Event-classification helpers shared by PossessionAnalyzer and PossessionExportService."""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

_NEUTRAL = frozenset(("subst", "foul", "timeout", "assist"))


def _text(move: Dict, is_fbcyl: bool) -> str:
    return str(move.get("move") or "") if is_fbcyl else str(move.get("text") or "")


def _action(move: Dict) -> str:
    return str(move.get("action") or "").lower()


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------

def get_timestamp(move: Dict, is_fbcyl: bool) -> int:
    if is_fbcyl:
        period = int(move.get("period") or 1)
        return (period - 1) * 600 + int(move.get("min") or 0) * 60 + int(move.get("sec") or 0)
    try:
        q = int(move.get("quarter") or 1)
        parts = str(move.get("time") or "10:00").split(":")
        m, s = int(parts[0]), int(parts[1])
        return (q - 1) * 600 + max(0, 600 - (m * 60 + s))
    except (ValueError, TypeError, IndexError):
        return 0


def get_opponent_team(team_id: str, moves: List[Dict]) -> str:
    ids = {str(m.get("idTeam") or "") for m in moves if m.get("idTeam")} - {team_id, ""}
    return ids.pop() if ids else team_id


# ---------------------------------------------------------------------------
# Event classification
# ---------------------------------------------------------------------------

def is_missed_fg(move: Dict, is_fbcyl: bool) -> bool:
    t = _text(move, is_fbcyl)
    u = t.upper()
    act = _action(move)
    if is_fbcyl:
        return ("Intento fallado" in t or "fallado" in t.lower()) and "de 1" not in t.lower()
    if ("FALLADO" in u or "FALLA" in u) and ("TIRO DE 2" in u or "TIRO DE 3" in u or "TRIPLE" in u):
        return True
    if act == "shoot" and ("FALLADO" in u or "FALLA" in u) and "TIRO DE 1" not in u:
        return True
    return False


def is_missed_ft(move: Dict, is_fbcyl: bool) -> bool:
    t = _text(move, is_fbcyl)
    u = t.upper()
    act = _action(move)
    if is_fbcyl:
        return "Intento fallado de 1" in t or ("fallado" in t.lower() and "de 1" in t.lower())
    if ("TIRO DE 1" in u or "TIRO LIBRE" in u) and ("FALLADO" in u or "FALLA" in u):
        return True
    if act == "fthrow" and ("FALLADO" in u or "FALLA" in u):
        return True
    return False


def is_ft_event(move: Dict, is_fbcyl: bool) -> bool:
    """True for any free throw event, whether made or missed."""
    t = _text(move, is_fbcyl)
    u = t.upper()
    act = _action(move)
    if act == "fthrow":
        return True
    if is_fbcyl:
        tl = t.lower()
        return (
            "Canasta de 1" in t
            or "Intento fallado de 1" in t
            or ("de 1" in tl and ("fallado" in tl or "Canasta" in t))
        )
    return "TIRO DE 1" in u or "TIRO LIBRE" in u


def points_from_move(move: Dict, is_fbcyl: bool) -> int:
    t = _text(move, is_fbcyl)
    u = t.upper()
    act = _action(move)
    if is_fbcyl:
        if "Canasta de 2" in t:
            return 2
        if "Canasta de 3" in t:
            return 3
        if "Canasta de 1" in t or "Tiro libre anotado" in t:
            return 1
        return 0
    if "FALLADO" in u or "FALLA" in u:
        return 0
    if "ANOTADO" in u or act in ("shoot", "fthrow"):
        if "TIRO DE 3" in u or "TRIPLE" in u or "CANASTA DE 3" in u:
            return 3
        if "TIRO DE 2" in u or "CANASTA DE 2" in u:
            return 2
        if "TIRO DE 1" in u or "TIRO LIBRE" in u:
            return 1
    return 0


def is_turnover(move: Dict, is_fbcyl: bool) -> bool:
    u = _text(move, is_fbcyl).upper()
    return "PÉRDIDA" in u or "PERDIDA" in u or _action(move) in ("turnover", "lose")


def is_rebound(move: Dict, is_fbcyl: bool) -> bool:
    return _action(move) == "rebound" or "REBOTE" in _text(move, is_fbcyl).upper()


def is_steal(move: Dict, is_fbcyl: bool) -> bool:
    u = _text(move, is_fbcyl).upper()
    return _action(move) == "steal" or "ROBO" in u or "RECUPERA" in u


# ---------------------------------------------------------------------------
# Sequence helpers
# ---------------------------------------------------------------------------

def is_last_free_throw(idx: int, moves: List[Dict], is_fbcyl: bool) -> bool:
    """True if no FT from same team follows within the next few moves (skips neutral events)."""
    if idx >= len(moves) - 1:
        return True
    curr_team = str(moves[idx].get("idTeam") or "")
    for j in range(idx + 1, min(idx + 6, len(moves))):
        m = moves[j]
        if _action(m) in _NEUTRAL:
            continue
        if str(m.get("idTeam") or "") != curr_team:
            return True
        return not is_ft_event(m, is_fbcyl)
    return True


def ft_sequence_info(idx: int, moves: List[Dict], is_fbcyl: bool) -> Tuple[bool, int]:
    """Return (is_last_in_sequence, total_made_points_in_sequence).

    Scans backward and forward through consecutive FT events from the same team,
    skipping neutral events (subst/foul/timeout/assist) in between.
    """
    team = str(moves[idx].get("idTeam") or "")
    start = idx
    for j in range(idx - 1, -1, -1):
        m = moves[j]
        if _action(m) in _NEUTRAL:
            continue
        if str(m.get("idTeam") or "") == team and is_ft_event(m, is_fbcyl):
            start = j
        else:
            break
    end = idx
    for j in range(idx + 1, len(moves)):
        m = moves[j]
        if _action(m) in _NEUTRAL:
            continue
        if str(m.get("idTeam") or "") == team and is_ft_event(m, is_fbcyl):
            end = j
        else:
            break
    made_pts = sum(
        1 for j in range(start, end + 1)
        if is_ft_event(moves[j], is_fbcyl) and not is_missed_ft(moves[j], is_fbcyl)
    )
    return idx == end, made_pts


# ---------------------------------------------------------------------------
# Pre-scan detectors
# ---------------------------------------------------------------------------

def detect_offensive_rebounds(moves: List[Dict], is_fbcyl: bool) -> Set[int]:
    """Indices of missed shots (FG or FT) that are directly followed by an OReb from the same team."""
    indices: Set[int] = set()
    for i, move in enumerate(moves):
        if not is_rebound(move, is_fbcyl):
            continue
        curr_team = str(move.get("idTeam") or "")
        for lb in range(1, min(5, i + 1)):
            prev = moves[i - lb]
            if _action(prev) in _NEUTRAL:
                continue
            prev_team = str(prev.get("idTeam") or "")
            prev_u = _text(prev, is_fbcyl).upper()
            if is_missed_fg(prev, is_fbcyl) or is_missed_ft(prev, is_fbcyl):
                if prev_team == curr_team:
                    indices.add(i - lb)
                break
            if ("ANOTADO" in prev_u and "FALLADO" not in prev_u) or "PÉRDIDA" in prev_u or "PERDIDA" in prev_u:
                break
            if _action(prev) in ("rebound", "steal") or "REBOTE" in prev_u or "ROBO" in prev_u:
                break
    return indices


def detect_shooting_foul_indices(moves: List[Dict], is_fbcyl: bool) -> Set[int]:
    """Indices of missed FGs that are shooting fouls (same-team FT event follows)."""
    indices: Set[int] = set()
    for i, move in enumerate(moves):
        if not is_missed_fg(move, is_fbcyl):
            continue
        team = str(move.get("idTeam") or "")
        for j in range(i + 1, min(i + 7, len(moves))):
            nxt = moves[j]
            act = _action(nxt)
            if act in _NEUTRAL:
                continue
            nxt_team = str(nxt.get("idTeam") or "")
            nxt_u = _text(nxt, is_fbcyl).upper()
            if nxt_team == team and is_ft_event(nxt, is_fbcyl):
                indices.add(i)
                break
            if act in ("rebound", "steal") or "REBOTE" in nxt_u or "ROBO" in nxt_u:
                break
            if "ANOTADO" in nxt_u and "FALLADO" not in nxt_u:
                break
            if "PÉRDIDA" in nxt_u or "PERDIDA" in nxt_u:
                break
    return indices


def detect_steal_turnover_indices(moves: List[Dict], is_fbcyl: bool) -> Set[int]:
    """Return indices of turnover moves accompanied by an opponent steal.

    Covers combined events, forward two-event pattern (turnover then steal),
    and the FEB reverse pattern (steal stored before turnover at same timestamp).
    """
    steal_tovs: Set[int] = set()
    n = len(moves)
    for i, move in enumerate(moves):
        if not is_turnover(move, is_fbcyl):
            continue
        # Combined single event containing both turnover and steal markers
        if is_steal(move, is_fbcyl):
            steal_tovs.add(i)
            continue
        tid = str(move.get("idTeam") or "")
        # Forward: next non-neutral move from a different team is a steal
        for j in range(i + 1, min(i + 5, n)):
            m = moves[j]
            if _action(m) in _NEUTRAL:
                continue
            if str(m.get("idTeam") or "") != tid and is_steal(m, is_fbcyl):
                steal_tovs.add(i)
            break
        if i in steal_tovs:
            continue
        # Backward: FEB stores the steal event before the turnover at the same timestamp
        ts_i = get_timestamp(move, is_fbcyl)
        for j in range(i - 1, max(i - 5, -1), -1):
            m = moves[j]
            if _action(m) in _NEUTRAL:
                continue
            if get_timestamp(m, is_fbcyl) < ts_i:
                break
            if str(m.get("idTeam") or "") != tid and is_steal(m, is_fbcyl):
                steal_tovs.add(i)
                break
    return steal_tovs


def detect_and1_indices(moves: List[Dict], is_fbcyl: bool) -> Set[int]:
    """Indices of made FGs followed by a same-team FT (and-1 plays)."""
    indices: Set[int] = set()
    for i, move in enumerate(moves):
        pts = points_from_move(move, is_fbcyl)
        if pts not in (2, 3) or is_ft_event(move, is_fbcyl):
            continue
        team = str(move.get("idTeam") or "")
        for j in range(i + 1, min(i + 9, len(moves))):
            nxt = moves[j]
            act = _action(nxt)
            if act in _NEUTRAL:
                continue
            nxt_team = str(nxt.get("idTeam") or "")
            if nxt_team == team and is_ft_event(nxt, is_fbcyl):
                indices.add(i)
                break
            nxt_u = _text(nxt, is_fbcyl).upper()
            if act in ("shoot", "rebound", "lose", "recovery", "period"):
                break
            if is_missed_fg(nxt, is_fbcyl) or is_missed_ft(nxt, is_fbcyl):
                break
            if "ANOTADO" in nxt_u and "FALLADO" not in nxt_u and "TIRO DE 1" not in nxt_u and "TIRO LIBRE" not in nxt_u:
                break
            if "PÉRDIDA" in nxt_u or "PERDIDA" in nxt_u or "REBOTE" in nxt_u or "ROBO" in nxt_u:
                break
    return indices
