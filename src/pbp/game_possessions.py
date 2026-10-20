"""Possessions, rebounds and turnovers of a FEB game per team, from the play-by-play validated against the box score.

Rebounds: the pbp counts players and teams (the official box score does not credit team rebounds); offensive when the
rebounding team is the one that missed. It is valid when it is not fewer than the box score (``ro`` / ``rd``), checked
for offensive and defensive separately; otherwise the box score value is used and flagged (``*_source``).

Possessions: the exact count of the tracker, unless the game is not ``reliable`` by its impact (#390): more than
``UNKNOWN_ORIGIN_MAX_PCT`` of the points scored in possessions of unknown origin (the feed lacks the event that ended the rival's
possession), or a count that differs from the estimate (FGA - ORB + TOV + 0.44 FTA, with the validated rebounds and turnovers) by
more than ``RECONCILIATION_MAX_PCT``; then both teams use the estimate (``possessions_reason``) and the figures that depend on the
possessions leave the game out. The alternation breaks (``quality_level``) are only informative: they come from annotation errors of
the feed that cannot be rebuilt without video, and most of them hardly change the figures. Documents that are not a FEB or FBCYL game
give ``None`` and the caller keeps its own numbers.

FBCYL (issue #373): the same figures from the moves (``events_fbcyl``) and the team box (``stats.teams[].data``). That box INCLUDES the team
rebounds and turnovers and the moves have almost none of them, so the pbp is below the box nearly always (23 of 34 team-games for the
offensive rebounds) and the box value wins: the rule "pbp unless it is fewer than the box" is the same, it just chooses the box more often.
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Tuple

from src.live_core.four_factors import FT_POSSESSION_COST
from src.live_core.possessions import track

from .game_events import game_events

RECONCILIATION_MAX_PCT = 10.0
UNKNOWN_ORIGIN_MAX_PCT = 10.0
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


def _fbcyl_total(team: Dict[str, Any]) -> Dict[str, Any]:
    """The box totals of an FBCYL team with the names of the FEB ones (``ro``, ``rd``, ``to``, ``p1a``...)."""
    data = team.get("data") or {}
    return {"ro": data.get("offensiveRebound"), "rd": data.get("defensiveRebound"), "to": data.get("lost"), "pts": data.get("score"),
            "p2a": data.get("shotsOfTwoAttempted"), "p3a": data.get("shotsOfThreeAttempted"), "p1a": data.get("shotsOfOneAttempted")}


def game_teams(game_doc: Dict[str, Any]) -> Optional[Tuple[bool, List[str], List[Dict[str, Any]]]]:
    """``(is_fbcyl, ids, totals)`` of a game with two teams and play-by-play; ``None`` otherwise. The ids are those of the events (FEB team id,
    FBCYL ``teamIdIntern``) and the totals are the box ones with the FEB names."""
    teams = (game_doc.get("BOXSCORE") or {}).get("TEAM") or []
    if len(teams) == 2 and (game_doc.get("PLAYBYPLAY") or {}).get("LINES"):
        return False, [str(t.get("id")) for t in teams], [t.get("TOTAL") or {} for t in teams]
    fbcyl = (game_doc.get("stats") or {}).get("teams") or []
    if len(fbcyl) == 2 and game_doc.get("moves"):
        return True, [str(t.get("teamIdIntern")) for t in fbcyl], [_fbcyl_total(t) for t in fbcyl]
    return None


def game_minutes(game_doc: Dict[str, Any], is_fbcyl: bool, last_period: int) -> int:
    """Minutes of the game: its regulation (the sum of the FBCYL periods; 40 for FEB) and 5 per overtime."""
    regulation = 40
    if is_fbcyl:
        durations = [d for d in ((game_doc.get("stats") or {}).get("periodDurationList") or [])[:4] if isinstance(d, (int, float)) and d > 0]
        regulation = int(sum(durations)) if len(durations) == 4 else 40
    return regulation + 5 * max(0, last_period - 4)


def analyse_game(game_doc: Dict[str, Any]) -> Optional[GameAnalysis]:
    """Run the tracker on a FEB or FBCYL game; ``None`` if it has no play-by-play or box score to read."""
    view = game_teams(game_doc)
    if view is None:
        return None
    is_fbcyl, ids, totals = view
    events = sorted(game_events(game_doc, is_fbcyl), key=lambda e: (e.elapsed, e.num))
    if not events:
        return None
    pbp = _pbp_counts(events, ids)
    possessions, quality = track(events, ids)
    last_period = max(e.period for e in events)
    minutes = game_minutes(game_doc, is_fbcyl, last_period)

    out: Dict[str, Dict[str, Any]] = {}
    for box, tid in zip(totals, ids):
        counts = pbp[tid]
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
    _choose_possessions(out, _unknown_points_pct(possessions))
    return GameAnalysis(out, possessions, quality)


def team_game_possessions(game_doc: Dict[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
    """Per team id: possessions (with source, reason and quality), rebounds and turnovers; None if the game cannot be read."""
    analysis = analyse_game(game_doc)
    return None if analysis is None else analysis.teams


def _unknown_points_pct(possessions: List[Any]) -> float:
    """Share of the points scored in possessions whose origin the feed does not allow to know."""
    total = sum(p.points for p in possessions)
    return sum(p.points for p in possessions if p.origin == "unknown") / total * 100 if total else 0.0


def _choose_possessions(teams: Dict[str, Dict[str, Any]], unknown_pct: float) -> None:
    """Both teams use the same source: the alternation of one team's possessions depends on the other's."""
    reason = "quality" if unknown_pct > UNKNOWN_ORIGIN_MAX_PCT else None
    if reason is None:
        worst = max(abs(t["possessions_pbp"] - t["possessions_estimate"]) / max(t["possessions_estimate"], 1.0) * 100
                    for t in teams.values())
        reason = "reconciliation" if worst > RECONCILIATION_MAX_PCT else None
    for t in teams.values():
        t["unknown_pts_pct"], t["reliable"] = unknown_pct, reason is None
        if reason:
            t.update(possessions=t["possessions_estimate"], possessions_source="estimate", possessions_reason=reason)
        else:
            t.update(possessions=t["possessions_pbp"], possessions_source="pbp", possessions_reason=None)
