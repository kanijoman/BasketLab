"""How coaches behave, read from the finished games: the evidence the alert rules are built on.

``game_behaviour`` extracts, for one game, the timeouts and what preceded them, the voluntary stint lengths, how
personal fouls were handled and the scoring droughts of each team. ``summarize_coach`` aggregates many games and
``simulate_run_rule`` replays the "rival run" rule with other thresholds to see how many alerts it would give and how
often a timeout followed. Replaces the provisional analysis scripts.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.live_core.events import Event

from .eval_labels import Actions

DROUGHT_S = 240
FOLLOW_S = 120
LONG_STINT_S = 420
_SCORING = ("fg2", "fg3", "ft")
_FOUL_OUT = 5


def _points(events: Iterable[Event], team: str, start: float, end: float) -> int:
    return sum(e.points for e in events if e.kind in _SCORING and e.points and e.team_id == team and start < e.elapsed <= end)


def _percentile(values: Sequence[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _at_boundary(e: Event) -> bool:
    """A change at the end or the opening of a period is a routine rotation, not a decision of the bench."""
    return e.remaining in (0, 600) or (e.period > 4 and e.remaining == 300)


def _timeouts(actions: Actions, teams: Tuple[str, str]) -> List[Dict[str, Any]]:
    out = []
    for e in actions.events:
        if e.kind != "timeout" or e.team_id not in teams:
            continue
        opp = teams[1] if e.team_id == teams[0] else teams[0]
        out.append({
            "team": e.team_id, "elapsed": e.elapsed,
            "opp_150": _points(actions.events, opp, e.elapsed - 150, e.elapsed),
            "own_150": _points(actions.events, e.team_id, e.elapsed - 150, e.elapsed),
            "own_tov_300": sum(1 for x in actions.events
                               if x.kind == "turnover" and x.team_id == e.team_id and e.elapsed - 300 < x.elapsed <= e.elapsed),
        })
    return out


def _stints(actions: Actions) -> List[Dict[str, Any]]:
    on: Dict[str, int] = {}
    out = []
    for e in actions.events:
        if e.kind == "sub_in" and e.player_id:
            on[e.player_id] = e.elapsed
        elif e.kind == "sub_out" and e.player_id in on:
            start = on.pop(e.player_id)
            voluntary = not _at_boundary(e) and e.elapsed in actions.voluntary_sub_outs(e.player_id)
            if voluntary:
                out.append({"team": e.team_id, "stint_s": e.elapsed - start, "period": e.period})
    return out


def _foul_cases(actions: Actions) -> List[Dict[str, Any]]:
    out = []
    for e in actions.events:
        if e.kind == "foul" and e.player_id and e.foul_type == "personal" and e.pf_count in (2, 3, 4):
            subbed = any(x.kind == "sub_out" and x.player_id == e.player_id and e.elapsed <= x.elapsed <= e.elapsed + FOLLOW_S
                         for x in actions.events)
            out.append({"pf": e.pf_count, "period": e.period, "subbed_120": subbed})
    return out


def _droughts(actions: Actions, teams: Tuple[str, str]) -> List[Dict[str, Any]]:
    end = max((e.elapsed for e in actions.events), default=0)
    out = []
    for team in teams:
        scored = sorted(e.elapsed for e in actions.events if e.kind in _SCORING and e.points and e.team_id == team)
        timeouts = actions.timeouts(team)
        previous = 0
        for t in scored + [end]:
            if t - previous >= DROUGHT_S:
                out.append({"team": team, "start": previous, "length": t - previous,
                            "timeout": any(previous < x <= t for x in timeouts)})
            previous = t
    return out


def game_behaviour(actions: Actions, teams: Tuple[str, str]) -> Dict[str, List[Dict[str, Any]]]:
    return {"timeouts": _timeouts(actions, teams), "stints": _stints(actions),
            "foul_cases": _foul_cases(actions), "droughts": _droughts(actions, teams)}


# --- aggregation -------------------------------------------------------------------------

def _share(count: int, total: int) -> Optional[float]:
    return count / total if total else None


def _period_group(period: int) -> str:
    return "H1" if period <= 2 else "Q3" if period == 3 else "Q4" if period == 4 else "OT"


def summarize_coach(games: Sequence[Dict[str, Any]], team_games: int) -> Dict[str, Any]:
    """Numbers over many ``game_behaviour`` results; ``team_games`` = team-games they come from (two per game)."""
    timeouts = [t for g in games for t in g["timeouts"]]
    stints = [s["stint_s"] for g in games for s in g["stints"]]
    droughts = [d for g in games for d in g["droughts"]]
    net = lambda t: t["opp_150"] - t["own_150"]  # noqa: E731
    fouls: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for g in games:
        for c in g["foul_cases"]:
            cell = fouls.setdefault(str(c["pf"]), {}).setdefault(_period_group(c["period"]), {"n": 0, "subbed": 0})
            cell["n"] += 1
            cell["subbed"] += bool(c["subbed_120"])
    return {
        "games": len(games),
        "timeouts": {
            "total": len(timeouts),
            "per_team_game": len(timeouts) / team_games if team_games else 0,
            "after_rival_unanswered_8": _share(sum(1 for t in timeouts if t["opp_150"] >= 8 and t["own_150"] == 0), len(timeouts)),
            "after_rival_net_run_6": _share(sum(1 for t in timeouts if net(t) >= 6), len(timeouts)),
            "after_four_turnovers": _share(sum(1 for t in timeouts if t["own_tov_300"] >= 4), len(timeouts)),
        },
        "stints": {
            "n": len(stints), "median_s": _percentile(stints, 0.5), "p75_s": _percentile(stints, 0.75),
            "p90_s": _percentile(stints, 0.9),
            "share_over_420": _share(sum(1 for s in stints if s > LONG_STINT_S), len(stints)),
        },
        "fouls": {pf: {grp: {"n": c["n"], "subbed_120": c["subbed"] / c["n"]} for grp, c in sorted(groups.items())}
                  for pf, groups in sorted(fouls.items())},
        "droughts": {
            "n": len(droughts), "per_team_game": len(droughts) / team_games if team_games else 0,
            "with_timeout": _share(sum(1 for d in droughts if d["timeout"]), len(droughts)),
        },
    }


# --- the run rule with other thresholds --------------------------------------------------

def _spec_label(threshold: int, window: int, mode: str) -> str:
    return f"{threshold} {'sin respuesta' if mode == 'unanswered' else 'netos'} en {window} s"


def _fires(events: List[Event], team: str, opp: str, threshold: int, window: int, mode: str) -> List[int]:
    fired: List[int] = []
    last = float("-inf")
    for e in events:
        if e.team_id != opp or e.kind not in _SCORING or not e.points or e.elapsed - last < window:
            continue
        against = _points(events, opp, e.elapsed - window, e.elapsed)
        for_us = _points(events, team, e.elapsed - window, e.elapsed)
        if (against >= threshold and for_us == 0) if mode == "unanswered" else (against - for_us >= threshold):
            fired.append(e.elapsed)
            last = e.elapsed
    return fired


def simulate_run_rule(actions_list: Sequence[Actions], pairs: Sequence[Tuple[str, str]],
                      specs: Sequence[Tuple[int, int, str]], follow_s: int = FOLLOW_S) -> List[Dict[str, Any]]:
    """For each ``(points, window_s, mode)`` (mode ``unanswered`` or ``net``): alerts per team-game, the share followed
    by an own timeout within ``follow_s`` and the share of all own timeouts that had one of those alerts before."""
    table = []
    for threshold, window, mode in specs:
        fires = followed = timeouts_total = covered = 0
        for actions, (a, b) in zip(actions_list, pairs):
            for team, opp in ((a, b), (b, a)):
                own = actions.timeouts(team)
                fired = _fires(actions.events, team, opp, threshold, window, mode)
                fires += len(fired)
                followed += sum(1 for f in fired if any(f <= t <= f + follow_s for t in own))
                timeouts_total += len(own)
                covered += sum(1 for t in own if any(f <= t <= f + follow_s for f in fired))
        table.append({"spec": _spec_label(threshold, window, mode), "fires": fires,
                      "per_team_game": fires / (2 * len(actions_list)) if actions_list else 0,
                      "followed": _share(followed, fires), "covered": _share(covered, timeouts_total)})
    return table
