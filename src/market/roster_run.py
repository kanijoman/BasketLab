"""The daily roster sweep (A5, #905): which teams to ask FEB for and what is kept between runs.

The current season (the latest of the games) is swept WHOLE every day: signings and departures happen all season long. The closed seasons only once: their rosters do not change, so a team is
asked for when its season has no record of it. Newest first, so the data that matters most arrives first, and a ``budget`` (closed-season teams per run) cuts the BACKLOG where it is: a first load of several
seasons is thousands of requests, more than one run should hold, and the next run goes on where this one stopped without asking twice for anything. The budget never counts the current season:
it is re-swept every day, and if it counted the backlog would never get past it. A team FEB did not answer is not marked as swept:
the next run asks for it again.

The pure part is ``plan_sweep``; ``sweep_into`` runs the plan with ``roster_sweep`` (one request per team, a pause between requests) and merges the result into the files of
``roster_store`` (``rosters/<season>.json`` of ``basketlab-archive-ext``). A player who left a roster disappears with the next sweep of it, because the rows of a swept team are replaced.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from src.market.competitions import competitions_of
from src.market.roster_store import merge_season, read_swept
from src.market.roster_sweep import DELAY_S, sweep_rosters

Plan = List[Tuple[str, str]]


def plan_sweep(teams_by_season: Mapping[str, Iterable[str]], swept: Mapping[str, Set[str]], seasons: Optional[Iterable[str]] = None, budget: Optional[int] = None) -> Plan:
    """``[(season, team)]`` to ask FEB for: the whole current season, and of the closed ones only the teams not swept yet, at most ``budget`` of them; current first, then newest first.

    The current season is the latest of the GAMES, not of ``seasons``: asking for 2025 alone must not turn it into the season that is swept every time."""
    current = max(teams_by_season) if teams_by_season else None
    wanted = {str(s) for s in seasons} if seasons else None
    now: Plan = []
    backlog: Plan = []
    for season in sorted(teams_by_season, reverse=True):
        if wanted is not None and season not in wanted:
            continue
        teams = sorted({str(t) for t in teams_by_season[season]})
        if season == current:
            now += [(season, t) for t in teams]
        else:
            backlog += [(season, t) for t in teams if t not in swept.get(season, set())]
    return now + (backlog if budget is None else backlog[:max(budget, 0)])


def sweep_into(folder: Any, teams_by_season: Mapping[str, Iterable[str]], get: Optional[Callable[..., Any]] = None, sleep: Callable[[float], None] = time.sleep, delay: float = DELAY_S,
               seasons: Optional[Iterable[str]] = None, budget: Optional[int] = None) -> Dict[str, Any]:
    """Run the plan and merge what FEB answered into ``folder``. Returns ``{planned, swept, left, missing, changed}``: the teams asked for, those that answered, the closed-season teams the budget left for
    the next run, the ``(season, team)`` that did not answer and the seasons whose file changed."""
    swept_before = read_swept(folder)
    full = plan_sweep(teams_by_season, swept_before, seasons)
    plan = plan_sweep(teams_by_season, swept_before, seasons, budget)
    asked: Dict[str, List[str]] = defaultdict(list)
    for season, team in plan:
        asked[season].append(team)
    rows, missing = sweep_rosters(dict(asked), get=get, sleep=sleep, delay=delay) if plan else ([], [])
    failed = defaultdict(set)
    for season, team in missing:
        failed[season].add(team)
    changed = []
    for season, teams in sorted(asked.items(), reverse=True):
        answered = [t for t in teams if t not in failed[season]]
        if merge_season(folder, season, [r for r in rows if r["season"] == season], swept=answered):
            changed.append(season)
    return {"planned": len(plan), "swept": len(plan) - len(missing), "left": len(full) - len(plan), "missing": sorted(missing), "changed": changed}


def teams_by_season(connection: Any, names: Iterable[str], catalogue: Iterable[Mapping[str, Any]]) -> Dict[str, List[str]]:
    """``{season: [team id]}`` of the FEB games of ``names``, sorted. The season is the one ``competitions_of`` gives (the same key the Talent rows use to join the roster); FBCYL has no roster
    page and a collection that says nothing is left out. Only the ids are read, in Mongo: a game weighs about 1 MB in memory."""
    names = list(names)
    metas = {d["_id"]: d for d in connection.get_collection("COLLECTION_META").find({"_id": {"$in": names}})}
    found, _unknown = competitions_of(names, metas, list(catalogue))
    out: Dict[str, Set[str]] = defaultdict(set)
    for competition, members in found.items():
        if competition.league != "feb":
            continue
        for member in members:
            pipeline = [{"$unwind": "$BOXSCORE.TEAM"}, {"$group": {"_id": "$BOXSCORE.TEAM.id"}}]
            out[competition.season].update(str(d["_id"]) for d in connection.get_collection(member.collection).aggregate(pipeline) if d["_id"])
    return {season: sorted(teams) for season, teams in sorted(out.items()) if teams}
