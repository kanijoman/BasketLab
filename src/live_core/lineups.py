"""Lineups and plus/minus of the live game (issue #248), standard library only.

``LiveGame`` owns a ``LineupTracker`` and calls it as it applies the events: ``tick`` credits the game-seconds that pass to the
quintet each team has on court (only while it has exactly five), ``points`` gives a made basket to the scorer's quintet (for) and
the rival's (against) and to the +/- of every player on court (his team's points minus the rival's), and ``refresh`` notices when the
five on court change and starts the stint of the new quintet.

The snapshot carries, per team, every quintet with its ``seconds``, ``pts_for``, ``pts_against`` and ``stints`` (the most played
first) and the quintet on court now with the same numbers of ITS CURRENT STINT plus ``since`` (the game-second it went on court).
Each player carries ``pm`` (the whole game) and ``stint_pm`` (since he came in). The official box score of a game has each player's
+/- (``pllss``); the numbers agree with it (tested on the sample game).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

QUINTET = 5

Key = Tuple[str, ...]


def _totals() -> Dict[str, int]:
    return {"seconds": 0, "pts_for": 0, "pts_against": 0, "stints": 0}


class LineupTracker:
    def __init__(self, team_ids: Sequence[str]) -> None:
        self._teams = list(team_ids)
        self._lineups: Dict[str, Dict[Key, Dict[str, int]]] = {tid: {} for tid in self._teams}
        self._now: Dict[str, Optional[Dict[str, Any]]] = {tid: None for tid in self._teams}

    def _on_court(self, players: Dict[str, Any], team_id: str) -> Key:
        return tuple(sorted(pid for pid, p in players.items() if p.on_court and p.team_id == team_id))

    def refresh(self, players: Dict[str, Any], at: int) -> None:
        """Start a new stint for every team whose five on court are not the ones it was tracking."""
        for tid in self._teams:
            on_court = self._on_court(players, tid)
            key: Optional[Key] = on_court if len(on_court) == QUINTET else None
            current = self._now[tid]
            if (current["key"] if current else None) == key:
                continue
            if key is None:
                self._now[tid] = None
                continue
            self._now[tid] = {"key": key, "since": at, "seconds": 0, "pts_for": 0, "pts_against": 0}
            self._lineups[tid].setdefault(key, _totals())["stints"] += 1

    def tick(self, seconds: int) -> None:
        """``seconds`` of game time have passed with the quintets as they are."""
        for tid in self._teams:
            current = self._now[tid]
            if current is not None and seconds > 0:
                current["seconds"] += seconds
                self._lineups[tid][current["key"]]["seconds"] += seconds

    def points(self, players: Dict[str, Any], scorer: str, value: int) -> None:
        """A basket of ``value`` points by ``scorer``'s team."""
        for p in players.values():
            if p.on_court and p.team_id in self._teams:
                delta = value if p.team_id == scorer else -value
                p.pm += delta
                p.stint_pm += delta
        for tid in self._teams:
            current = self._now[tid]
            if current is not None:
                field = "pts_for" if tid == scorer else "pts_against"
                current[field] += value
                self._lineups[tid][current["key"]][field] += value

    def snapshot(self) -> Dict[str, Any]:
        lineups = {
            tid: [{"players": list(key), **totals}
                  for key, totals in sorted(table.items(), key=lambda item: (-item[1]["seconds"], item[0]))]
            for tid, table in self._lineups.items()
        }
        now = {tid: ({"players": list(c["key"]), "since": c["since"], "seconds": c["seconds"],
                      "pts_for": c["pts_for"], "pts_against": c["pts_against"]} if c else None)
               for tid, c in self._now.items()}
        return {"lineups": lineups, "lineup_now": now}


def lineup_key(players: Sequence[str]) -> str:
    """The id of a quintet in the package tables: its players' ids, sorted, joined with ``|``."""
    return "|".join(sorted(players))


def season_table(totals: Dict[str, Dict[Key, Dict[str, int]]], team_id: str, limit: int) -> List[Dict[str, Any]]:
    """The most played quintets of a team over a season, as rows for ``tables.lineups``."""
    rows = [{"team_id": team_id, "players": list(key), **t,
             "net40": round((t["pts_for"] - t["pts_against"]) / t["seconds"] * 2400, 1) if t["seconds"] else 0.0}
            for key, t in totals.get(team_id, {}).items() if t["seconds"] > 0]
    rows.sort(key=lambda r: (-r["seconds"], r["players"]))
    return rows[:limit]
