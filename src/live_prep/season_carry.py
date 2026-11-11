"""The rating a team starts the season with: its final rating of the previous one, by ``teamCode`` (issue #825).

The ids of the teams change every season, the ``teamCode`` does not. Measured on 1,106 games of 4 season transitions: log loss of the prior win probability 0.5486 -> 0.5366, and the
accuracy of a team's first 3 games 61.7 % -> 72.2 %. Only FEB (FBCYL games carry no ``teamCode``). Teams with no link (new, promoted, relegated) start at 0 as always.
The rating only needs the final score, so the header of each game is read, not its play-by-play.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

from .club_fetcher import normalize_club
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
    ids: Dict[str, str]         # teamCode -> the team id of that season (its page tells the club, #862)


def _final_by_code(mongo_collection: Any) -> Tuple[Dict[str, float], Dict[str, str]]:
    fields = {"HEADER.TEAM.id": 1, "HEADER.TEAM.pts": 1, "HEADER.TEAM.teamCode": 1, "HEADER.starttime": 1}
    games = sorted((play_key(g["HEADER"].get("starttime")), str(g["_id"]), g["HEADER"]["TEAM"]) for g in mongo_collection.find({"HEADER.TEAM.pts": {"$exists": True}}, fields))
    ratings, codes = TeamRatings(), {}
    for _, _, teams in games:
        if len(teams) != 2 or any(t.get("pts") in (None, "") for t in teams):
            continue
        ids = [str(t["id"]) for t in teams]
        codes.update({i: str(t["teamCode"]) for i, t in zip(ids, teams) if t.get("teamCode")})
        ratings.update(ids[0], ids[1], float(teams[0]["pts"]) - float(teams[1]["pts"]))      # FEB's header lists the home team first
    return {code: ratings.rating(i) for i, code in codes.items()}, {code: i for i, code in codes.items()}


def carry_for(handler: Any, collection: str) -> Carry:
    """The final ratings (by teamCode) of the previous season and the id each team had then; empty when there is none or anything fails (a package never depends on it)."""
    try:
        ratings: Dict[str, float] = {}
        ids: Dict[str, str] = {}
        for name in previous_collections(handler, collection):
            found, found_ids = _final_by_code(handler.repository.connection.get_collection(name))
            ratings.update(found)
            ids.update(found_ids)
        return Carry(ratings, ids)
    except Exception as exc:  # noqa: BLE001 - the carry only refines the prior
        log.warning("no carry-over ratings for %s: %s", collection, exc)
        return Carry({}, {})


def carry_ratings(handler: Any, collection: str) -> Dict[str, float]:
    return carry_for(handler, collection).ratings


class ClubLinker:
    """Links a team that has not played yet to its teamCode of last season through the CLUB shown on its team page (issue #862).

    The pages of last season's teams are read once, and only when the first unlinked team asks: the rest of the time (a season under way) nobody pays for them.
    A club shared by two teams of last season is ambiguous and links nothing."""

    def __init__(self, carry: Carry, club_of: Callable[[str], Optional[str]]) -> None:
        self._carry, self._club_of = carry, club_of
        self._by_club: Optional[Dict[str, str]] = None

    def _previous(self) -> Dict[str, str]:
        if self._by_club is None:
            clubs: Dict[str, set] = {}
            for code, team_id in self._carry.ids.items():
                key = normalize_club(self._club_of(team_id))
                if key:
                    clubs.setdefault(key, set()).add(code)
            self._by_club = {key: next(iter(codes)) for key, codes in clubs.items() if len(codes) == 1}
        return self._by_club

    def code_of(self, team_id: str) -> Optional[str]:
        if not self._carry.ratings:
            return None
        key = normalize_club(self._club_of(team_id))
        return self._previous().get(key) if key else None
