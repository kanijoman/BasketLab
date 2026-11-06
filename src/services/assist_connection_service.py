"""Assist connections of a team: who passes, who receives and from which zones the receiver scores (issue #773).

Per game the links come from ``assist_links`` (FEB and FBCYL); this module adds them up for one team. Only made baskets are linked, so there is no accuracy: the
comparison is, per receiver and zone, the baskets scored with an assist against the ones scored without. The ranking has no minimum: every player who scored is
listed (those with no assisted basket have ``received: 0``) and the user chooses the order.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, Iterator, List, Optional

from src.services.assist_links import GameLinks, extract_links
from src.shotcharts.fbcyl_zones import _tid_query as _fbcyl_team_query
from utils.collection_utils import is_fbcyl

_FEB_PROJECTION = {"PLAYBYPLAY.LINES": 1, "SHOTCHART": 1, "HEADER.TEAM.id": 1, "BOXSCORE.TEAM.PLAYER.id": 1, "BOXSCORE.TEAM.PLAYER.name": 1}
_FBCYL_PROJECTION = {"moves": 1, "stats.teams": 1}


def _pct(part: int, whole: int) -> Optional[float]:
    return round(100.0 * part / whole, 1) if whole else None


def _ranked(counter: Counter, names: Dict[str, str]) -> List[Dict[str, Any]]:
    rows = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"player_id": pid, "name": names.get(pid, pid), "count": n} for pid, n in rows]


def _zone_rows(zones: Dict[str, Counter]) -> List[Dict[str, Any]]:
    rows = []
    for zone, c in zones.items():
        total = c["assisted"] + c["unassisted"]
        rows.append({"zone": zone, "assisted": c["assisted"], "unassisted": c["unassisted"], "assisted_pct": _pct(c["assisted"], total)})
    return sorted(rows, key=lambda r: (-(r["assisted"] + r["unassisted"]), r["zone"]))


def aggregate(games: Iterable[GameLinks], team_id: str, player_id: Optional[str] = None) -> Dict[str, Any]:
    """The connections of ``team_id`` over the games (any order gives the same answer)."""
    names: Dict[str, str] = {}
    count = 0
    unlinked = 0
    by_scorer: Dict[str, Dict[str, Any]] = {}
    passes: Dict[str, Counter] = {}
    for links in games:
        names.update(links.names)
        lost = sum(1 for t in links.unlinked_team_ids if t == str(team_id))
        unlinked += lost
        played = lost > 0
        for b in links.baskets:
            if b["team_id"] != str(team_id):
                continue
            played = True
            row = by_scorer.setdefault(b["scorer"], {"from": Counter(), "zones": {}, "assisted": 0, "unassisted": 0, "without_zone": 0,
                                                                                    "points": 0, "assisted_points": 0})
            side = "assisted" if b["passer"] else "unassisted"
            row[side] += 1
            row["points"] += b["points"]
            row["assisted_points"] += b["points"] if b["passer"] else 0
            if b["zone"] is None:
                row["without_zone"] += 1
            else:
                row["zones"].setdefault(b["zone"], Counter())[side] += 1
            if b["passer"]:
                row["from"][b["passer"]] += 1
                passes.setdefault(b["passer"], Counter())[b["scorer"]] += 1
        count += played                         # the games of THIS team: a competition is read once for all of its teams
    assisted_total = sum(r["assisted"] for r in by_scorer.values())
    receivers = [{
        "player_id": pid, "name": names.get(pid, pid), "received": r["assisted"], "unassisted": r["unassisted"], "fgm": r["assisted"] + r["unassisted"],
        "points": r["points"], "assisted_points": r["assisted_points"], "assisted_points_pct": _pct(r["assisted_points"], r["points"]) or 0.0,
        "share_pct": _pct(r["assisted"], assisted_total) or 0.0, "assisted_pct": _pct(r["assisted"], r["assisted"] + r["unassisted"]) or 0.0,
        "zones": _zone_rows(r["zones"]), "without_zone": r["without_zone"], "from": _ranked(r["from"], names),
    } for pid, r in by_scorer.items()]
    receivers.sort(key=lambda r: (-r["received"], -r["fgm"], r["player_id"]))
    passers = [{"player_id": pid, "name": names.get(pid, pid), "assists": sum(c.values()), "share_pct": _pct(sum(c.values()), assisted_total) or 0.0,
                "to": _ranked(c, names)} for pid, c in passes.items()]
    passers.sort(key=lambda p: (-p["assists"], p["player_id"]))
    result: Dict[str, Any] = {
        "team_id": str(team_id), "games": count, "assisted_baskets": assisted_total,
        "total_baskets": sum(r["fgm"] for r in receivers), "assists_total": assisted_total + unlinked, "assists_linked": assisted_total,
        "linked_pct": _pct(assisted_total, assisted_total + unlinked), "receivers": receivers, "passers": passers,
    }
    if player_id is not None:
        result["focus"] = {"as_receiver": next((r for r in receivers if r["player_id"] == str(player_id)), None),
                           "as_passer": next((p for p in passers if p["player_id"] == str(player_id)), None)}
    return result


class AssistConnectionService:
    def __init__(self, handler: Any) -> None:
        self.handler = handler

    def _games(self, collection: str, team_id: Optional[str], fbcyl: bool) -> Iterator[GameLinks]:
        """One game at a time from the cursor (a game document is about 1 MB); ``team_id=None`` reads the whole competition."""
        coll = self.handler.connection.get_collection(collection)
        if coll is None:                                        # not connected: nothing to read
            return
        if fbcyl:
            cursor = coll.find(_fbcyl_team_query(team_id), _FBCYL_PROJECTION)
        else:
            cursor = coll.find({} if team_id is None else {"HEADER.TEAM.id": str(team_id)}, _FEB_PROJECTION)
        for doc in cursor:
            yield extract_links(doc, fbcyl)

    def get_connections(self, collection: str, team_id: str, player_id: Optional[str] = None) -> Dict[str, Any]:
        fbcyl = is_fbcyl(collection)
        result = aggregate(self._games(collection, team_id, fbcyl), team_id, player_id)
        result["format"] = "fbcyl" if fbcyl else "feb"
        result["collection"] = collection
        return result

    def get_all_teams(self, collection: str) -> List[Dict[str, Any]]:
        """The connections of every team of the competition from ONE pass over its games (each game is read once, not once per team)."""
        fbcyl = is_fbcyl(collection)
        links = list(self._games(collection, None, fbcyl))          # the links of a game are a few KB: the 1 MB documents are not kept
        rows = []
        for team in self.handler.get_teams_with_ids(collection) or []:
            result = aggregate(links, str(team["id"]))
            if result["total_baskets"]:
                rows.append({"team_id": str(team["id"]), "team_name": team["name"], "analysis": result})
        return rows
