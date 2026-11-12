"""The Talent row (B2, #878): the games of a player summed per competition, season and TEAM.

The team is part of the statistics (the context of the minutes changes), so a transfer inside a competition is two rows, never one blended row; the phases and groups of the same
competition are one row that lists them. Input is what ``local_data.export.export_collection`` already makes of a collection (FEB and FBCYL player rows, one per player and game), so the
two formats go through the same pipelines the web reads and nothing is computed twice. Minutes are SECONDS for both: FEB's ``min`` is, FBCYL's ``timePlayed`` is whole minutes (measured on
the archive: a team adds up to 12,000 in FEB and to 200 in FBCYL for 5 x 40 minutes), so it is multiplied by 60 here and nowhere else.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Tuple

COUNTS = ("pts", "p1m", "p1a", "p2m", "p2a", "p3m", "p3a", "assist", "ro", "rd", "rt", "st", "to", "bs", "pf", "rf", "val", "pllss")
FBCYL_SECONDS_PER_MINUTE = 60


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _whole(value: float) -> Any:
    return int(value) if float(value).is_integer() else value


def _person(row: Mapping[str, Any], league: str) -> str:
    return f"fbcyl:{row['player_uuid']}" if league == "fbcyl" else f"feb:{row['player_id']}"


def season_player_rows(parts: Iterable[Tuple[str, Mapping[str, Any]]]) -> List[Dict[str, Any]]:
    """``[{person_id, name, team_id, team_name, league, groups, games, minutes, <counts>}]`` of one competition and season, sorted by person and team.

    ``parts`` is ``(group label, export payload)`` for each collection of the competition. A row without minutes is not a game."""
    totals: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for group, payload in parts:
        league = payload.get("league", "feb")
        scale = FBCYL_SECONDS_PER_MINUTE if league == "fbcyl" else 1
        for row in payload["player_rows"]:
            minutes = _number(row.get("minutes")) * scale
            if minutes <= 0:
                continue
            key = (_person(row, league), str(row["team_id"]))
            entry = totals.setdefault(key, {"league": league, "groups": set(), "names": Counter(), "teams": Counter(), "games": 0, "minutes": 0.0, **{c: 0.0 for c in COUNTS}})
            entry["groups"].add(group)
            entry["names"][str(row.get("player_name") or "")] += 1
            entry["teams"][str(row.get("team_name") or "")] += 1
            entry["games"] += 1
            entry["minutes"] += minutes
            for field in COUNTS:
                entry[field] += _number(row.get(field))
    out = []
    for (person, team), e in sorted(totals.items()):
        out.append({"person_id": person, "name": min(e["names"].items(), key=lambda kv: (-kv[1], kv[0]))[0], "team_id": team,
                    "team_name": min(e["teams"].items(), key=lambda kv: (-kv[1], kv[0]))[0], "league": e["league"], "groups": sorted(e["groups"]),
                    "games": e["games"], "minutes": _whole(e["minutes"]), **{c: _whole(e[c]) for c in COUNTS}})
    return out
