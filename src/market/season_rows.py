"""The Talent row (B2, #878): the games of a player summed per competition, season and TEAM.

The team is part of the statistics (the context of the minutes changes), so a transfer inside a competition is two rows, never one blended row; the phases and groups of the same
competition are one row that lists them. Input is what ``local_data.export.export_collection`` already makes of a collection (FEB and FBCYL player rows, one per player and game), so the
two formats go through the same pipelines the web reads and nothing is computed twice. Minutes are SECONDS for both: FEB's ``min`` is, FBCYL's ``timePlayed`` is whole minutes (measured on
the archive: a team adds up to 12,000 in FEB and to 200 in FBCYL for 5 x 40 minutes), so it is multiplied by 60 here and nowhere else.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from src.market.bio import canonical_position, normalize_height, position_group, source_rank
from src.market.countries import country, nationalities

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


def _candidates(mine: List[Mapping[str, Any]], external: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """What the sources say of one person, all alike: the FEB roster rows (source ``feb``, with their team) and the external candidates (``external_bio``, one per season, no team)."""
    out = [{"source": "feb", "season": str(r.get("season")), "team": str(r["team_id"]), "row": r} for r in mine]
    out += [{"source": str(c.get("source") or ""), "season": str(c["season"]) if c.get("season") else None, "team": None, "row": c} for c in external]
    return out


def _order(c: Mapping[str, Any], season: str, team: str) -> Tuple[int, int, int, int, str, str]:
    """Closest season first (how far does not matter, an unknown season is the farthest); a tie goes to the same team, then the source of higher priority, then the later season."""
    gap = _year(c["season"]) - _year(season) if c["season"] else None
    return (10 ** 6 if gap is None else abs(gap), 0 if c["team"] == team else 1, source_rank(c["source"]), -(gap or 0), c["source"], str(c["team"]))


def _label(c: Mapping[str, Any]) -> str:
    """Where a value came from: ``season:team`` for a FEB roster, ``source:season`` for an external source (``source`` alone if it does not say the season)."""
    return f"{c['season']}:{c['team']}" if c["source"] == "feb" else f"{c['source']}:{c['season']}" if c["season"] else c["source"]


def _first(candidates: List[Dict[str, Any]], read: Any) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """The first value ``read`` finds in the candidates (None where nobody says it) and the candidate it came from."""
    for c in candidates:
        value = read(c["row"])
        if value is not None:
            return value, c
    return None, None


def _bio_of(row: Mapping[str, Any], mine: List[Mapping[str, Any]], season: str, external: List[Mapping[str, Any]], borrowed: bool = False) -> Dict[str, Any]:
    """The bio of one row, FIELD BY FIELD (#910, #996): every source says it (FEB rosters of any season and team, linked external players) and the CLOSEST season wins (``_order``), because
    height, position and nationality change with the years; ``bio_from`` says where a value came from when it is not the roster of the row. The date of birth does not change: a different one
    is in ``bio_conflict``. ``nationalities`` lists every different passport (closest first), ``nationality`` is the first. Formation and shirt number belong to the team and the season:
    they come from that roster, or from another team of the season, never from another season, and never from the FEB club of a ``borrowed`` bio (a FBCYL player linked to a FEB person)."""
    team = str(row["team_id"])
    ordered = sorted(_candidates(mine, external), key=lambda c: _order(c, season, team))
    fields: Dict[str, Any] = {}
    origin: Dict[str, str] = {}
    reads = {"full_name": lambda r: r.get("name") or None, "birth": lambda r: r.get("birth") or None, "nationality": lambda r: country(r.get("nationality")),
             "height": lambda r: normalize_height(r.get("height")), "position": lambda r: canonical_position(r.get("position"))}
    for field, read in reads.items():
        fields[field], found = _first(ordered, read)
        if found is not None and field != "full_name" and (found["season"], found["team"]) != (season, team):
            origin[field] = _label(found)
    fields["position_group"], _ = _first(ordered, lambda r: position_group(r.get("position")))
    fields["nationalities"] = nationalities(c["row"].get("nationality") for c in ordered)
    fields["bio_conflict"] = ["birth"] if len({c["row"].get("birth") for c in ordered if c["row"].get("birth")}) > 1 else []
    same_season = [] if borrowed else [c for c in ordered if c["source"] == "feb" and c["season"] == season]
    fields["formacion"], _ = _first(same_season, lambda r: r.get("formacion"))
    fields["dorsal"], _ = _first(same_season, lambda r: r.get("dorsal"))
    return {**fields, "bio_from": origin}


def attach_bio(rows: Iterable[Mapping[str, Any]], roster: Iterable[Mapping[str, Any]], season: str, external: Optional[Mapping[str, List[Mapping[str, Any]]]] = None,
               linked: Optional[Mapping[str, str]] = None) -> List[Dict[str, Any]]:
    """The rows with ``full_name`` and the bio of the FEB rosters (``roster_sweep``, every season) and of the linked external players (``external``, #979): birth date, height (cm), position, nationality(ies), formacion and shirt number.

    Each field is resolved on its own, by the closest season (``_bio_of``); what nobody says is None, never a guess (FBCYL has no roster). ``position_group`` (G/F/C) is the coarse position every source can say.
    ``linked`` is ``{person id: FEB person id}`` of the ``linked`` identity links (#996): such a row says ``linked_to`` (its own ``person_id`` is not rewritten) and takes the bio of the FEB person."""
    by_person: Dict[str, List[Mapping[str, Any]]] = {}
    for r in roster:
        by_person.setdefault(r["person_id"], []).append(r)
    external, linked = external or {}, linked or {}
    out = []
    for row in rows:
        feb = linked.get(row["person_id"])
        who = feb or row["person_id"]
        out.append({**row, **_bio_of(row, by_person.get(who, []), str(season), list(external.get(who, [])), borrowed=feb is not None), "linked_to": feb})
    return out
