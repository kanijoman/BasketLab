"""Roster sweep of Mercado (#874): birth date, height, position, nationality and full name of every FEB team of a season.

The live packages only read the roster of the next rivals (``live_prep.publisher``); Mercado needs all of them, so the sweep walks
every team that appears in the games of a season. It reuses the parser of ``live_prep.roster_fetcher`` (the page has no contract, the
columns are found by class or header) and adds only what a sweep needs: one request per team and season, a pause between requests
("the website is somebody else's") and a list of the teams that could not be read, so a night with FEB down is visible and the next
run asks for them again. Output rows are sorted and carry no timestamp, so a repeated sweep changes no byte.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.live_prep.roster_fetcher import fetch_team_roster
from src.market.identity import PREFIX

logger = logging.getLogger(__name__)

DELAY_S = 1.0


def season_team_ids(games: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
    """``{season: [team id]}`` of the FEB games with a box score; the ids are those of the roster pages."""
    seasons: Dict[str, set] = {}
    for game in games:
        season = str(game.get("_season") or "")
        for team in (game.get("BOXSCORE") or {}).get("TEAM", []) or []:
            if season and team.get("id"):
                seasons.setdefault(season, set()).add(str(team["id"]))
    return {season: sorted(ids) for season, ids in sorted(seasons.items())}


def sweep_rosters(
    teams_by_season: Dict[str, Iterable[str]],
    get: Optional[Callable[..., Any]] = None,
    sleep: Callable[[float], None] = time.sleep,
    delay: float = DELAY_S,
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """``(rows, missing)``: one row per player and team of each season, and the ``(season, team)`` pairs whose page could not be read."""
    rows: List[Dict[str, Any]] = []
    missing: List[Tuple[str, str]] = []
    first = True
    for season, team_ids in sorted(teams_by_season.items()):
        for team_id in dict.fromkeys(str(t) for t in team_ids):
            if not first:
                sleep(delay)
            first = False
            roster = fetch_team_roster(team_id, get=get)
            if roster is None:
                missing.append((season, team_id))
                continue
            rows.extend({"person_id": PREFIX + pid, "season": season, **data} for pid, data in roster.items())
    rows.sort(key=lambda r: (r["season"], r["team_id"], r["person_id"]))
    return rows, missing
