"""Reconciliation of the play-by-play of a game with its official box (#884, D0 of epic #872): the common acceptance criterion of every external source.

No source (ACB, FIBA, NCAA, FBCYL youth...) is published without it. The play-by-play engine of FEB and FBCYL took a long time to reach its precision, so a new source is not assumed to reconcile:

* the NINE **core** statistics must match the official box exactly (``CORE_STATS``: points, field goals made and attempted, threes made and attempted, free throws made and attempted, offensive and defensive
  rebounds). One difference and the game is **not reliable**: it stays out of rates, percentiles and ``eligible``, and it is never corrected by eye (the ``reliable`` of ``DERIVED`` in FEB works the same way);
* the **information** statistics (``INFO_STATS``: assists, steals, blocks, turnovers and fouls) are measured and reported by source but do not discard a game (FEB itself has known assist differences, #378);
* what cannot be counted from the play-by-play (``UNCHECKED``: the minutes, that need the lineups) is said in the report.

The play-by-play is counted with the same events as the rest of the pipelines (``game_events``, without the lines the table deleted) and the same rebound rule as the possession tracker (``count_quality_events``); the official box is the FEB
document's (``BOXSCORE.TEAM[].TOTAL``, points from ``HEADER.TEAM``). Pure functions, no I/O: they do not change the game and give the same answer whatever the order of its lines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.pbp.game_events import game_events
from src.pbp.possession_quality import count_quality_events

CORE_STATS = ("PTS", "FGM", "FGA", "3PM", "3PA", "FTM", "FTA", "ORB", "DRB")
INFO_STATS = ("AST", "STL", "BLK", "TOV", "PF")
UNCHECKED = ("MIN",)
_EVENT_STATS = {"assist": "AST", "steal": "STL", "block": "BLK", "foul": "PF"}
# official statistic -> its key in ``BOXSCORE.TEAM[].TOTAL`` (the box writes numbers as texts)
_BOX_KEYS = {"AST": "assist", "STL": "st", "BLK": "bs", "TOV": "to", "PF": "pf", "ORB": "ro", "DRB": "rd", "FTM": "p1m", "FTA": "p1a"}


@dataclass(frozen=True)
class Check:
    """One statistic of one team: what the play-by-play counts and what the official box says."""
    team_id: str
    stat: str
    pbp: int
    official: int

    @property
    def ok(self) -> bool:
        return self.pbp == self.official


@dataclass(frozen=True)
class GameReconciliation:
    game_id: str
    checks: Tuple[Check, ...]

    @property
    def reliable(self) -> bool:
        """All nine core statistics of both teams match the official box."""
        return all(c.ok for c in self.checks if c.stat in CORE_STATS)

    def mismatches(self, stats: Optional[Iterable[str]] = None) -> List[Check]:
        """The checks that do not match, of ``stats`` (all of them by default)."""
        wanted = set(stats) if stats is not None else None
        return [c for c in self.checks if not c.ok and (wanted is None or c.stat in wanted)]


def _number(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _official(team: Dict[str, Any], points: int) -> Dict[str, int]:
    """The official statistics of a team: its box totals and its score."""
    total = team.get("TOTAL") or {}
    box = {stat: _number(total.get(key)) for stat, key in _BOX_KEYS.items()}
    box["FGM"] = _number(total.get("p2m")) + _number(total.get("p3m"))
    box["FGA"] = _number(total.get("p2a")) + _number(total.get("p3a"))
    box["3PM"], box["3PA"], box["PTS"] = _number(total.get("p3m")), _number(total.get("p3a")), points
    return box


def _counted(doc: Dict[str, Any], team_ids: List[str]) -> Dict[str, Dict[str, int]]:
    """What the play-by-play says, per team: shots and rebounds by the rule of the possession tracker, and the information statistics by event."""
    events = [e for e in game_events(doc, False) if not e.deleted]            # a line the table deleted is a correction: the official box does not have it either
    shots = count_quality_events(events, False, team_ids, use_labels=True)          # a source that labels its rebounds is counted by its labels, one that does not by the rule of the tracker
    counted = {}
    for team_id, c in shots.items():
        counted[team_id] = {"PTS": 2 * c["T2M"] + 3 * c["T3M"] + c["T1M"], "FGM": c["T2M"] + c["T3M"], "FGA": c["T2A"] + c["T3A"], "3PM": c["T3M"], "3PA": c["T3A"],
                            "FTM": c["T1M"], "FTA": c["T1A"], "ORB": c["RebO"], "DRB": c["RebD"], "TOV": c["TOV"], **{stat: 0 for stat in _EVENT_STATS.values()}}
    for event in events:
        stat = _EVENT_STATS.get(event.kind)
        if stat and event.team_id in counted:
            counted[event.team_id][stat] += 1
    return counted


def reconcile_game(doc: Dict[str, Any]) -> GameReconciliation:
    """The checks of a game in the FEB document shape (the canonical one of the external sources too). ``ValueError`` if it has no official box to compare with."""
    box = (doc.get("BOXSCORE") or {}).get("TEAM") or []
    if len(box) < 2:
        raise ValueError("the game has no official box (BOXSCORE.TEAM) to reconcile with")
    header = {str(t.get("id")): _number(t.get("pts")) for t in (doc.get("HEADER") or {}).get("TEAM") or []}
    team_ids = [str(t.get("id")) for t in box[:2]]
    counted = _counted(doc, team_ids)
    checks = []
    for team in box[:2]:
        team_id = str(team.get("id"))
        official = _official(team, header.get(team_id, 0))
        checks.extend(Check(team_id, stat, counted[team_id][stat], official[stat]) for stat in (*CORE_STATS, *INFO_STATS))
    return GameReconciliation(str(doc.get("_id")), tuple(checks))


def summarize(results: Iterable[GameReconciliation]) -> Dict[str, Any]:
    """The report of a source: how many team-games match by statistic and the list of those that do not, the unreliable games and what was not checked."""
    results = list(results)
    stats: Dict[str, Dict[str, Any]] = {stat: {"checked": 0, "match": 0, "mismatches": []} for stat in (*CORE_STATS, *INFO_STATS)}
    for result in results:
        for check in result.checks:
            entry = stats[check.stat]
            entry["checked"] += 1
            entry["match"] += check.ok
            if not check.ok:
                entry["mismatches"].append({"game": result.game_id, "team": check.team_id, "pbp": check.pbp, "official": check.official})
    return {"games": len(results), "reliable": sum(r.reliable for r in results), "unreliable": [r.game_id for r in results if not r.reliable],
            "stats": stats, "unchecked": list(UNCHECKED)}
