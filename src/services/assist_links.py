"""Assist → basket → zone links of one stored game, FEB and FBCYL (issue #773).

An assist is a play of its own that follows the basket it created with the same clock, so the link is read from the play-by-play. Only made field goals are
baskets (a miss never has an assist: its passer is unknown, so no accuracy is computed). The zone comes from the shot of the basket: FEB's SHOTCHART shot with the
same quarter, clock, team, player and result; FBCYL's shot with the same ``eventUuid``. Every made field goal is returned, assisted or not, so the same pass
over the game gives both sides of the comparison.

The archive holds what FEB and the clubs typed: a play with no team, no player or no number exists (it stopped a whole web-data publication once). Such a play is
never attributed to anybody (no «None» player) and never raises; an assist that cannot be tied to a basket is counted apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.shotcharts.feb_zones import build_dorsal_to_id_map, classify_zone, feb_to_fiba

_FBCYL_LOOKBACK = 2          # moves between a basket and its assist (a rebound or sub logged in between is rare)


@dataclass
class GameLinks:
    """``baskets``: ``{team_id, scorer, passer | None, zone | None, points}`` per made field goal; ``unlinked_team_ids``: the team of each assist tied to no basket; ``names``: player id → name."""
    baskets: List[Dict[str, Any]] = field(default_factory=list)
    unlinked_team_ids: List[str] = field(default_factory=list)
    names: Dict[str, str] = field(default_factory=dict)

    @property
    def unlinked_assists(self) -> int:
        return len(self.unlinked_team_ids)


def extract_links(doc: Dict[str, Any], fbcyl: bool) -> GameLinks:
    return _fbcyl_links(doc) if fbcyl else _feb_links(doc)


def _basket(team_id: str, scorer: str, zone: Optional[str], points: int) -> Dict[str, Any]:
    return {"team_id": team_id, "scorer": scorer, "passer": None, "zone": zone, "points": points}


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------------------------ FEB
def _feb_names(doc: Dict[str, Any]) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for team in (doc.get("BOXSCORE") or {}).get("TEAM") or []:
        for player in team.get("PLAYER") or []:
            if player.get("id"):
                names[str(player["id"])] = str(player.get("name") or "")
    return names


def _feb_zones(doc: Dict[str, Any]) -> Dict[Tuple[str, str, int, Optional[str], bool], List[str]]:
    """The zones of the SHOTCHART shots by ``(quarter, clock, slot, player id, made)`` (equal keys keep their order and are used once each)."""
    shotchart = doc.get("SHOTCHART") or {}
    dorsals = build_dorsal_to_id_map(shotchart)
    zones: Dict[Tuple[str, str, int, Optional[str], bool], List[str]] = {}
    for s in shotchart.get("SHOTS") or []:
        slot, made = _int(s.get("team")), _int(s.get("m"))
        if slot not in (0, 1) or made is None:
            continue                                                  # a shot with no team or no result cannot be matched to a basket
        try:
            x, y = feb_to_fiba(float(s.get("x", 0)), float(s.get("y", 0)), slot)
        except (TypeError, ValueError):
            continue
        key = (str(s.get("quarter")), str(s.get("t")), slot, dorsals.get((slot, str(s.get("player", "")))), made == 1)
        zones.setdefault(key, []).append(classify_zone(x, y))
    return zones


def _feb_is_made_basket(line: Dict[str, Any]) -> bool:
    return line.get("action") == "shoot" and "ANOTADO" in str(line.get("text") or "")


def _feb_slot(line: Dict[str, Any], teams: int) -> Optional[int]:
    """0 or 1 for the team of the line (FEB writes ``'1'`` / ``'2'``), ``None`` when it has none."""
    slot = _int(line.get("team"))
    return slot - 1 if slot is not None and 1 <= slot <= teams else None


def _feb_points(text: str) -> int:
    """3 for ``TIRO DE 3`` / ``MATE DE 3`` (a dunk of 3 is an anomaly of the source), else 2."""
    return 3 if "DE 3" in text.upper() else 2


def _feb_links(doc: Dict[str, Any]) -> GameLinks:
    links = GameLinks(names=_feb_names(doc))
    lines = sorted(((doc.get("PLAYBYPLAY") or {}).get("LINES") or []), key=lambda l: _int(l.get("num")) or 0)
    team_ids = [str((t or {}).get("id", "")) for t in (doc.get("HEADER") or {}).get("TEAM") or []]
    zones = _feb_zones(doc)
    previous: Optional[Dict[str, Any]] = None          # the line before, when it is a made basket that still has no passer
    for line in lines:
        if line.get("deleted"):
            continue
        slot = _feb_slot(line, len(team_ids))
        player = line.get("idPlayer")
        if _feb_is_made_basket(line):
            previous = None
            if slot is None or not player:
                continue                                                  # nobody to credit: not a basket of anybody
            pool = zones.get((str(line.get("quarter")), str(line.get("time")), slot, str(player), True)) or []
            basket = _basket(team_ids[slot], str(player), pool.pop(0) if pool else None, _feb_points(str(line.get("text") or "")))
            links.baskets.append(basket)
            previous = {"line": line, "basket": basket}
            continue
        if line.get("action") == "assist":
            if player and _feb_tie(previous, line):
                previous["basket"]["passer"] = str(player)
            else:
                links.unlinked_team_ids.append(team_ids[slot] if slot is not None else "")
        previous = None
    return links


def _feb_tie(previous: Optional[Dict[str, Any]], assist: Dict[str, Any]) -> bool:
    if previous is None or previous["basket"]["passer"] is not None:
        return False
    line = previous["line"]
    same_play = all(line.get(k) == assist.get(k) for k in ("team", "quarter", "time"))
    return same_play and str(line.get("idPlayer")) != str(assist.get("idPlayer"))


# ---------------------------------------------------------------------------------------------------------------- FBCYL
def _fbcyl_shot_zones(doc: Dict[str, Any]) -> Dict[str, str]:
    zones: Dict[str, str] = {}
    for team in (doc.get("stats") or {}).get("teams") or []:
        for player in team.get("players") or []:
            for points in (player.get("data") or {}).values():
                if not isinstance(points, list):
                    continue
                for p in points:
                    if isinstance(p, dict) and p.get("eventUuid") and "xnormalize" in p and "ynormalize" in p:
                        try:
                            x, y = feb_to_fiba(float(p["xnormalize"]), float(p["ynormalize"]), 0)      # FBCYL folds every team into one half court
                        except (TypeError, ValueError):
                            continue
                        zones[str(p["eventUuid"])] = classify_zone(x, y)
    return zones


def _fbcyl_is_made_basket(move: str) -> bool:
    low = move.lower()
    return low.startswith("canasta de 2") or low.startswith("canasta de 3") or low == "mate"


def _fbcyl_links(doc: Dict[str, Any]) -> GameLinks:
    links = GameLinks()
    team_ext: Dict[Any, str] = {}
    player_id: Dict[Any, str] = {}
    for team in (doc.get("stats") or {}).get("teams") or []:
        team_ext[team.get("teamIdIntern")] = str(team.get("teamIdExtern", ""))
        for p in team.get("players") or []:
            pid = p.get("uuid") or p.get("actorId")
            if pid is None:
                continue
            player_id[p.get("actorId")] = str(pid)
            links.names[str(pid)] = str(p.get("name") or "")
    zones = _fbcyl_shot_zones(doc)
    recent: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []          # the last moves as (move, basket | None)
    for move in doc.get("moves") or []:
        text = str(move.get("move") or "")
        actor = _actor(move, player_id)
        team = team_ext.get(move.get("idTeam"), "")
        if _fbcyl_is_made_basket(text) and actor and team:
            basket = _basket(team, actor, zones.get(str(move.get("eventUuid"))), 3 if text.lower().startswith("canasta de 3") else 2)
            links.baskets.append(basket)
            recent.append((move, basket))
        elif text.lower().startswith("asistencia"):
            if not (actor and _fbcyl_tie(recent, move, actor)):
                links.unlinked_team_ids.append(team)
            recent.append((move, None))
        else:
            recent.append((move, None))
        del recent[:-(_FBCYL_LOOKBACK + 1)]
    return links


def _actor(move: Dict[str, Any], player_id: Dict[Any, str]) -> Optional[str]:
    """The id of the player of a move, ``None`` when the move has none (never the text «None»)."""
    raw = move.get("actorId")
    return None if raw is None else player_id.get(raw, str(raw))


def _fbcyl_tie(recent: Iterable[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]], assist: Dict[str, Any], passer: str) -> bool:
    for move, basket in reversed(list(recent)):
        if basket is None or basket["passer"] is not None or basket["scorer"] == passer:
            continue
        if all(move.get(k) == assist.get(k) for k in ("idTeam", "period", "min", "sec")):
            basket["passer"] = passer
            return True
    return False
