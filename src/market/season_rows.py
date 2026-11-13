"""The Talent row (B2, #878): the games of a player summed per competition, season and TEAM.

The team is part of the statistics (the context of the minutes changes), so a transfer inside a competition is two rows, never one blended row; the phases and groups of the same
competition are one row that lists them. Input is what ``local_data.export.export_collection`` already makes of a collection (FEB and FBCYL player rows, one per player and game), so the
two formats go through the same pipelines the web reads and nothing is computed twice. Minutes are SECONDS for both: FEB's ``min`` is, FBCYL's ``timePlayed`` is whole minutes (measured on
the archive: a team adds up to 12,000 in FEB and to 200 in FBCYL for 5 x 40 minutes), so it is multiplied by 60 here and nowhere else.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from src.market.bio import canonical_position, normalize_height, position_group

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


def _year(season: Any) -> int:
    try:
        return int(str(season))
    except ValueError:
        return 0


def _closeness(r: Mapping[str, Any], season: str, team: str) -> Tuple[int, int, int, str]:
    """Order of the roster rows of a person for a row of ``season`` and ``team``: that team and season, another team of the season, then the nearest seasons (a tie goes to the later one)."""
    if str(r.get("season")) == season:
        return (0 if str(r["team_id"]) == team else 1, 0, 0, str(r["team_id"]))
    gap = _year(r.get("season")) - _year(season)
    return (2, abs(gap), -gap, str(r["team_id"]))


def _first(candidates: List[Mapping[str, Any]], read: Any) -> Tuple[Any, Optional[Mapping[str, Any]]]:
    """The first value ``read`` finds in the candidates (None where nobody says it) and the roster row it came from."""
    for r in candidates:
        value = read(r)
        if value is not None:
            return value, r
    return None, None


def _bio_of(row: Mapping[str, Any], mine: List[Mapping[str, Any]], season: str) -> Dict[str, Any]:
    """The bio of one row, FIELD BY FIELD (#910): FEB leaves height and position empty for most players, so an empty field takes the same person's value from another team of the
    season or from the nearest season; ``bio_from`` says where each of those came from (``season:team``), and is empty when the roster of the row said it all. Formation and shirt number
    belong to the team and the season: they come from that roster, or (a transfer without roster of its own) from another team of the season, never from another season."""
    team = str(row["team_id"])
    ordered = sorted(mine, key=lambda r: _closeness(r, season, team))
    same_season = [r for r in ordered if str(r.get("season")) == season]
    fields: Dict[str, Any] = {}
    origin: Dict[str, str] = {}
    reads = {"full_name": lambda r: r.get("name") or None, "birth": lambda r: r.get("birth") or None, "nationality": lambda r: r.get("nationality") or None,
             "height": lambda r: normalize_height(r.get("height")), "position": lambda r: canonical_position(r.get("position"))}
    for field, read in reads.items():
        fields[field], found = _first(ordered, read)
        if found is not None and (str(found.get("season")), str(found["team_id"])) != (season, team) and field != "full_name":
            origin[field] = f"{found.get('season')}:{found['team_id']}"
    fields["position_group"], _ = _first(ordered, lambda r: position_group(r.get("position")))
    fields["formacion"], _ = _first(same_season, lambda r: r.get("formacion"))
    fields["dorsal"], _ = _first(same_season, lambda r: r.get("dorsal"))
    return {**fields, "bio_from": origin}


def attach_bio(rows: Iterable[Mapping[str, Any]], roster: Iterable[Mapping[str, Any]], season: str) -> List[Dict[str, Any]]:
    """The rows with ``full_name`` and the bio of the FEB rosters (``roster_sweep``, every season): birth date, height (cm), position, nationality, formacion and shirt number.

    Each field is resolved on its own (``_bio_of``); what nobody says is None, never a guess (FBCYL has no roster). ``position_group`` (G/F/C) is the coarse position every source can say."""
    by_person: Dict[str, List[Mapping[str, Any]]] = {}
    for r in roster:
        by_person.setdefault(r["person_id"], []).append(r)
    return [{**row, **_bio_of(row, by_person.get(row["person_id"], []), str(season))} for row in rows]
