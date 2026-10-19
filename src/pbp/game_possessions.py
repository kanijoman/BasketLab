"""Possessions, rebounds and turnovers of a FEB game per team, from the play-by-play validated against the box score.

Rebounds: the pbp counts players and teams (the official box score does not credit team rebounds); offensive when the
rebounding team is the one that missed. It is valid when it is not fewer than the box score (``ro`` / ``rd``), checked
for offensive and defensive separately; otherwise the box score value is used and flagged (``*_source``).

Possessions: the exact count of the tracker, unless its feed is ``unreliable`` or it disagrees with the estimate
(FGA - ORB + TOV + 0.44 FTA, with the validated rebounds and turnovers) by more than 15 %; then both teams use the
estimate (``possessions_reason``). FEB only: other documents give ``None`` and the caller keeps its own numbers.
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Tuple

from src.live_core.four_factors import FT_POSSESSION_COST
from src.live_core.possessions import track

from .game_events import game_events

RECONCILIATION_MAX_PCT = 15.0
_SHOTS = ("fg2", "fg3")


def estimate_possessions(fga: float, orb: float, tov: float, fta: float) -> float:
    """The classic estimate: FGA - ORB + TOV + 0.44 * FTA (the cost of a free throw is the tracker's)."""
    return fga - orb + tov + FT_POSSESSION_COST * fta


def _int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def rebound_sides(events: List[Any]) -> Iterator[Tuple[Any, str]]:
    """``(event, "orb" | "drb")`` for every rebound that follows a miss: the one who missed rebounds offensively, always."""
    last_miss: Optional[str] = None
    for ev in events:
        if ev.kind in _SHOTS or ev.kind == "ft":
            last_miss = ev.team_id if not ev.made else (last_miss if ev.kind == "ft" else None)
        elif ev.kind == "rebound":
            if last_miss is not None:
                yield ev, ("orb" if last_miss == ev.team_id else "drb")
            last_miss = None


def _pbp_counts(events: List[Any], team_ids: List[str]) -> Dict[str, Dict[str, int]]:
    """Rebounds (player / team, offensive / defensive) and turnovers per team, with the real-game rebound rule."""
    counts = {t: {"orb_player": 0, "orb_team": 0, "drb_player": 0, "drb_team": 0, "tov": 0} for t in team_ids}
    for ev in events:
        if ev.kind == "turnover" and ev.team_id in counts:
            counts[ev.team_id]["tov"] += 1
    for ev, side in rebound_sides([e for e in events if e.team_id in counts]):
        counts[ev.team_id][f"{side}_{'team' if ev.player_id is None else 'player'}"] += 1
    return counts


def _validated(pbp: int, box: int) -> tuple:
    """(value, source): the pbp when it is not fewer than the box score, else the box score."""
    return (pbp, "pbp") if pbp >= box else (box, "boxscore")


class GameAnalysis(NamedTuple):
    """What the tracker found in a game: the per-team figures, the possessions and the quality of the feed."""

    teams: Dict[str, Dict[str, Any]]
    possessions: List[Any]
    quality: Any


def analyse_game(game_doc: Dict[str, Any]) -> Optional[GameAnalysis]:
    """Run the tracker on a FEB game; ``None`` if it has no play-by-play or box score to read."""
    teams = (game_doc.get("BOXSCORE") or {}).get("TEAM") or []
    if len(teams) != 2 or not (game_doc.get("PLAYBYPLAY") or {}).get("LINES"):
        return None
    ids = [str(t.get("id")) for t in teams]
    events = sorted(game_events(game_doc, False), key=lambda e: (e.elapsed, e.num))
    if not events:
        return None
    pbp = _pbp_counts(events, ids)
    possessions, quality = track(events, ids)
    last_period = max(e.period for e in events)
    minutes = 40 + 5 * max(0, last_period - 4)

    out: Dict[str, Dict[str, Any]] = {}
    for team, tid in zip(teams, ids):
        box, counts = team.get("TOTAL") or {}, pbp[tid]
        orb, orb_source = _validated(counts["orb_player"] + counts["orb_team"], _int(box.get("ro")))
        drb, drb_source = _validated(counts["drb_player"] + counts["drb_team"], _int(box.get("rd")))
        tov, tov_source = _validated(counts["tov"], _int(box.get("to")))
        fga, fta = _int(box.get("p2a")) + _int(box.get("p3a")), _int(box.get("p1a"))
        out[tid] = {
            "team_id": tid, "pts": _int(box.get("pts")), "fga": fga, "fta": fta,
            "orb": orb, "orb_source": orb_source, "team_orb": counts["orb_team"],
            "drb": drb, "drb_source": drb_source, "team_drb": counts["drb_team"],
            "tov": tov, "tov_source": tov_source,
            "possessions_pbp": quality.counted.get(tid, 0),
            "possessions_estimate": estimate_possessions(fga, orb, tov, fta),
            "quality_level": quality.level, "breaks_raw": quality.breaks_raw, "game_minutes": minutes,
        }
    _choose_possessions(out, quality.level)
    return GameAnalysis(out, possessions, quality)


def team_game_possessions(game_doc: Dict[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
    """Per team id: possessions (with source, reason and quality), rebounds and turnovers; None if the game cannot be read."""
    analysis = analyse_game(game_doc)
    return None if analysis is None else analysis.teams


def _choose_possessions(teams: Dict[str, Dict[str, Any]], level: str) -> None:
    """Both teams use the same source: the alternation of one team's possessions depends on the other's."""
    reason = "quality" if level == "unreliable" else None
    if reason is None:
        worst = max(abs(t["possessions_pbp"] - t["possessions_estimate"]) / max(t["possessions_estimate"], 1.0) * 100
                    for t in teams.values())
        reason = "reconciliation" if worst > RECONCILIATION_MAX_PCT else None
    for t in teams.values():
        if reason:
            t.update(possessions=t["possessions_estimate"], possessions_source="estimate", possessions_reason=reason)
        else:
            t.update(possessions=t["possessions_pbp"], possessions_source="pbp", possessions_reason=None)
