"""Assist → basket → zone links of one stored game, FEB and FBCYL (issue #773).

An assist is a play of its own that follows the basket it created with the same clock, so the link is read from the play-by-play. Only made field goals are
baskets (a miss never has an assist: its passer is unknown, so no accuracy is computed). The zone comes from the shot of the basket: FEB's SHOTCHART shot with the
same quarter, clock, team, player and result; FBCYL's shot with the same ``eventUuid``. Every made field goal is returned, assisted or not, so the same pass
over the game gives both sides of the comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.shotcharts.feb_zones import build_dorsal_to_id_map, classify_zone, feb_to_fiba

_FBCYL_LOOKBACK = 2          # moves between a basket and its assist (a rebound or sub logged in between is rare)


@dataclass
class GameLinks:
    """``baskets``: ``{team_id, scorer, passer | None, zone | None}`` per made field goal; ``unlinked_team_ids``: the team of each assist tied to no basket; ``names``: player id → name."""
    baskets: List[Dict[str, Any]] = field(default_factory=list)
    unlinked_team_ids: List[str] = field(default_factory=list)
    names: Dict[str, str] = field(default_factory=dict)

    @property
    def unlinked_assists(self) -> int:
        return len(self.unlinked_team_ids)


def extract_links(doc: Dict[str, Any], fbcyl: bool) -> GameLinks:
    return _fbcyl_links(doc) if fbcyl else _feb_links(doc)


def _basket(team_id: str, scorer: Optional[str], zone: Optional[str], points: int) -> Dict[str, Any]:
    return {"team_id": team_id, "scorer": scorer, "passer": None, "zone": zone, "points": points}


def _feb_points(text: str) -> int:
    """3 for ``TIRO DE 3`` / ``MATE DE 3`` (a dunk of 3 is an anomaly of the source), else 2."""
    return 3 if "DE 3" in text.upper() else 2


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
        try:
            slot = int(s.get("team"))
            x, y = feb_to_fiba(float(s.get("x", 0)), float(s.get("y", 0)), slot)
        except (TypeError, ValueError):
            continue
        key = (str(s.get("quarter")), str(s.get("t")), slot, dorsals.get((slot, str(s.get("player", "")))), int(s.get("m", 0)) == 1)
        zones.setdefault(key, []).append(classify_zone(x, y))
    return zones


def _feb_is_made_basket(line: Dict[str, Any]) -> bool:
    return line.get("action") == "shoot" and "ANOTADO" in str(line.get("text", ""))


def _feb_links(doc: Dict[str, Any]) -> GameLinks:
    links = GameLinks(names=_feb_names(doc))
    lines = sorted(((doc.get("PLAYBYPLAY") or {}).get("LINES") or []), key=lambda l: int(l.get("num", 0)))
    team_ids = [str((t or {}).get("id", "")) for t in (doc.get("HEADER") or {}).get("TEAM") or []]
    zones = _feb_zones(doc)
    previous: Optional[Dict[str, Any]] = None          # the line before, when it is a made basket that still has no passer
    for line in lines:
        if line.get("deleted"):
            continue
        action = line.get("action")
        if _feb_is_made_basket(line):
            slot = int(line.get("team", 0)) - 1
            pool = zones.get((str(line.get("quarter")), str(line.get("time")), slot, str(line.get("idPlayer")), True)) or []
            basket = _basket(team_ids[slot] if 0 <= slot < len(team_ids) else "", str(line.get("idPlayer")), pool.pop(0) if pool else None,
                             _feb_points(str(line.get("text", ""))))
            links.baskets.append(basket)
            previous = {"line": line, "basket": basket}
            continue
        if action == "assist":
            if not _feb_tie(previous, line):
                slot = int(line.get("team", 0)) - 1
                links.unlinked_team_ids.append(team_ids[slot] if 0 <= slot < len(team_ids) else "")
            else:
                previous["basket"]["passer"] = str(line.get("idPlayer"))
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
                        x, y = feb_to_fiba(float(p["xnormalize"]), float(p["ynormalize"]), 0)      # FBCYL folds every team into one half court
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
            pid = str(p.get("uuid") or p.get("actorId"))
            player_id[p.get("actorId")] = pid
            links.names[pid] = str(p.get("name") or "")
    zones = _fbcyl_shot_zones(doc)
    recent: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []          # the last moves as (move, basket | None)
    for move in doc.get("moves") or []:
        text = str(move.get("move", ""))
        if _fbcyl_is_made_basket(text):
            scorer = player_id.get(move.get("actorId"), str(move.get("actorId")))
            basket = _basket(team_ext.get(move.get("idTeam"), ""), scorer, zones.get(str(move.get("eventUuid"))),
                             3 if text.lower().startswith("canasta de 3") else 2)
            links.baskets.append(basket)
            recent.append((move, basket))
        elif text.lower().startswith("asistencia"):
            if not _fbcyl_tie(recent, move, player_id):
                links.unlinked_team_ids.append(team_ext.get(move.get("idTeam"), ""))
            recent.append((move, None))
        else:
            recent.append((move, None))
        del recent[:-(_FBCYL_LOOKBACK + 1)]
    return links


def _fbcyl_tie(recent: Iterable[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]], assist: Dict[str, Any], player_id: Dict[Any, str]) -> bool:
    passer = player_id.get(assist.get("actorId"), str(assist.get("actorId")))
    for move, basket in reversed(list(recent)):
        if basket is None or basket["passer"] is not None or basket["scorer"] == passer:
            continue
        if all(move.get(k) == assist.get(k) for k in ("idTeam", "period", "min", "sec")):
            basket["passer"] = passer
            return True
    return False
