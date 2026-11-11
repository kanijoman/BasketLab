"""The rating a team starts the season with: its final rating of the previous one, by ``teamCode`` (issue #825).

The ids of the teams change every season, the ``teamCode`` does not. Measured on 1,106 games of 4 season transitions: log loss of the prior win probability 0.5486 -> 0.5366, and the
accuracy of a team's first 3 games 61.7 % -> 72.2 %. Only FEB (FBCYL games carry no ``teamCode``). Teams with no link (new, promoted, relegated) start at 0 as always.
The rating only needs the final score, so the header of each game is read, not its play-by-play.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, NamedTuple, Tuple

from .game_sources import is_knockout, is_fbcyl, play_key
from .team_rating import TeamRatings

log = logging.getLogger(__name__)
_YEARS = re.compile(r"(?<!\d)(20\d\d)_(20\d\d)(?!\d)")


def _previous_season(name: str) -> str:
    """``X_2026_2027_Liga_Regular_A`` -> ``X_2025_2026_``: the prefix every league of the previous season starts with ('' when the name has no season)."""
    match = _YEARS.search(name)
    if not match or int(match.group(2)) != int(match.group(1)) + 1:
        return ""
    return f"{name[:match.start()]}{int(match.group(1)) - 1}_{int(match.group(2)) - 1}_"


def previous_collections(handler: Any, collection: str) -> List[str]:
    """The regular-league collections (every group) of the same competition one season before."""
    prefix = _previous_season(collection)
    if not prefix or is_fbcyl(collection):
        return []
    names = handler.repository.connection.get_database().list_collection_names()
    return sorted(n for n in names if n.startswith(prefix) and "Liga_Regular" in n and not is_knockout(n))


class Carry(NamedTuple):
    ratings: Dict[str, float]   # teamCode -> final rating of the previous season
    names: Dict[str, str]       # normalised team name -> teamCode, for the teams that have not played yet (issue #862); ambiguous names are left out


def normalize_name(name: str) -> str:
    """``" Peñas  Huesca "`` -> ``"PENAS HUESCA"``: the exact name of a team without case, accents or extra spaces."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c))
    return " ".join(plain.upper().split())


def _final_by_code(mongo_collection: Any) -> Tuple[Dict[str, float], Dict[str, set]]:
    fields = {"HEADER.TEAM.id": 1, "HEADER.TEAM.pts": 1, "HEADER.TEAM.teamCode": 1, "HEADER.TEAM.name": 1, "HEADER.starttime": 1}
    games = sorted((play_key(g["HEADER"].get("starttime")), str(g["_id"]), g["HEADER"]["TEAM"]) for g in mongo_collection.find({"HEADER.TEAM.pts": {"$exists": True}}, fields))
    ratings, codes, names = TeamRatings(), {}, {}
    for _, _, teams in games:
        if len(teams) != 2 or any(t.get("pts") in (None, "") for t in teams):
            continue
        ids = [str(t["id"]) for t in teams]
        codes.update({i: str(t["teamCode"]) for i, t in zip(ids, teams) if t.get("teamCode")})
        for t in teams:
            if t.get("teamCode") and normalize_name(t.get("name")):
                names.setdefault(normalize_name(t["name"]), set()).add(str(t["teamCode"]))
        ratings.update(ids[0], ids[1], float(teams[0]["pts"]) - float(teams[1]["pts"]))      # FEB's header lists the home team first
    return {code: ratings.rating(i) for i, code in codes.items()}, names


def carry_for(handler: Any, collection: str) -> Carry:
    """The ratings (by teamCode) and the names of the previous season; empty when there is none or anything fails (a package never depends on it)."""
    try:
        ratings: Dict[str, float] = {}
        codes_of: Dict[str, set] = {}
        for name in previous_collections(handler, collection):
            found, names = _final_by_code(handler.repository.connection.get_collection(name))
            ratings.update(found)
            for key, codes in names.items():
                codes_of.setdefault(key, set()).update(codes)
        return Carry(ratings, {key: next(iter(codes)) for key, codes in codes_of.items() if len(codes) == 1})
    except Exception as exc:  # noqa: BLE001 - the carry only refines the prior
        log.warning("no carry-over ratings for %s: %s", collection, exc)
        return Carry({}, {})


def carry_ratings(handler: Any, collection: str) -> Dict[str, float]:
    return carry_for(handler, collection).ratings
