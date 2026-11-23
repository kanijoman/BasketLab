"""The reconciliation of the play by play of ESPN with its official box (#888, D4 of epic #872; criterion of #884).

Before a game is published what the plays say each team did is compared, statistic by statistic, with the box, and a game that does not match is KEPT but marked as not reliable (``_reliable: false``): the
archive does not discard anything and the people who read it can see what to trust. What is compared with what (measured on real games, 23/11/2026):

* points, field goals, threes and free throws: the plays against the SUM of the players of the box (and the points of the box against the score of the game);
* rebounds, turnovers, steals, blocks and fouls: the plays against the TOTALS of the team, which include what the team itself did (a team rebound or turnover has no player in the box). A technical foul
  of a player counts as a foul of the team; one of the bench (no player) does not.

A game whose play by play came empty (one of the real ones, with a complete box) cannot be checked and is not reliable. Pure function; nothing of the game is changed.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

_FROM_PLAYERS = ("fgm", "fga", "tpm", "tpa", "ftm", "fta")
_FROM_TOTALS = {"orb": "offensiveRebounds", "drb": "defensiveRebounds", "tov": "totalTurnovers", "stl": "steals", "blk": "blocks", "pf": "fouls"}


def _plays_say(plays: List[Dict[str, Any]]) -> Dict[str, Counter]:
    """What the plays say each team did."""
    said: Dict[str, Counter] = {}
    for play in plays:
        team, kind = play["team_id"], play["type"]
        if not team:
            continue
        count = said.setdefault(team, Counter())
        if play["shooting"]:
            free_throw = play["points_attempted"] == 1 or kind.endswith("FreeThrow")
            made = int(play["scoring"])
            count["pts"] += play["points"]
            if free_throw:
                count["fta"] += 1
                count["ftm"] += made
            else:
                count["fga"] += 1
                count["fgm"] += made
                if play["points_attempted"] == 3:
                    count["tpa"] += 1
                    count["tpm"] += made
        elif kind == "Offensive Rebound":
            count["orb"] += 1
        elif kind == "Defensive Rebound":
            count["drb"] += 1
        elif "Turnover" in kind:
            count["tov"] += 1
        elif kind == "Steal":
            count["stl"] += 1
        elif kind == "Block Shot":
            count["blk"] += 1
        elif kind == "PersonalFoul" or (kind == "Technical Foul" and play["athlete_id"]):
            count["pf"] += 1
    return said


def reconcile(game: Dict[str, Any]) -> Dict[str, Any]:
    """``{"reliable": bool, "problems": [...]}`` for a game as ``ncaa_page.parse_summary`` read it: each problem names the team, the statistic and the two figures."""
    problems: List[str] = []
    score = {t["id"]: t["score"] for t in game["teams"]}
    box = {team: Counter() for team in game["players"]}
    for team, players in game["players"].items():
        for player in players:
            if player["stats"]:
                box[team].update({k: v for k, v in player["stats"].items() if k in (*_FROM_PLAYERS, "pts")})
        if box[team]["pts"] != score.get(team):
            problems.append(f"team {team} box: the players add {box[team]['pts']} points, the game says {score.get(team)}")
    if not game["plays"]:
        return {"reliable": False, "problems": [*problems, "the play by play is empty: it cannot be checked"]}
    said = _plays_say(game["plays"])
    for team in game["players"]:
        mine = said.get(team, Counter())
        if mine["pts"] != score.get(team):
            problems.append(f"team {team} pts: the plays say {mine['pts']}, the box {score.get(team)}")
        for key in _FROM_PLAYERS:
            if mine[key] != box[team][key]:
                problems.append(f"team {team} {key}: the plays say {mine[key]}, the box {box[team][key]}")
        totals = game["totals"].get(team, {})
        for key, name in _FROM_TOTALS.items():
            if name not in totals or str(mine[key]) != str(totals[name]):
                problems.append(f"team {team} {key}: the plays say {mine[key]}, the box {totals.get(name)}")
    return {"reliable": not problems, "problems": problems}
