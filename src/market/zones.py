"""The shots by zone of a Talent row (#994): per player AND team (the granularity of the row) the made and attempted shots of each of the 10 zones of the engine, and the same for the whole competition.

The shots are the ones the web reads (``shotcharts.owned_shots``: FEB's player is the dorsal resolved to the player id of its game, FBCYL's is the uuid), so the zones of the profile are the ones of the
shot chart. A shot whose dorsal matches nobody counts for the competition and for no player. Each count is ``[made, attempted]`` per zone flattened in ``ZONE_ORDER`` (20 numbers), the compact form
that keeps the file small; the keys are ``<person_id>|<team_id>``, those of the rows. Pure functions except ``competition_zones``, which reads the games one at a time.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from src.live_core.zones import ZONES
from src.shotcharts.owned_shots import OwnedShot, iter_owned_shots
from src.utils.collection_utils import is_fbcyl

ZONE_ORDER = tuple(ZONES)
_INDEX = {zone: i for i, zone in enumerate(ZONE_ORDER)}
WIDTH = 2 * len(ZONE_ORDER)


def _add(counts: List[int], shot: OwnedShot) -> None:
    i = _INDEX.get(shot[5])
    if i is None:
        return
    counts[2 * i + 1] += 1
    if shot[4]:
        counts[2 * i] += 1


def zone_table(shots: Iterable[OwnedShot], fbcyl: bool) -> Dict[str, Any]:
    """``{league: [20], players: {person_id|team_id: [20]}}`` of the shots (a zone the engine does not know is left out, never guessed)."""
    league = [0] * WIDTH
    players: Dict[str, List[int]] = {}
    for shot in shots:
        _add(league, shot)
        if shot[1] is not None and shot[5] in _INDEX:
            person = f"fbcyl:{shot[1]}" if fbcyl else f"feb:{shot[1]}"
            _add(players.setdefault(f"{person}|{shot[0]}", [0] * WIDTH), shot)
    return {"league": league, "players": {k: players[k] for k in sorted(players)}}


def merge_tables(tables: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The sum of several tables (the groups and phases of one competition)."""
    league = [0] * WIDTH
    players: Dict[str, List[int]] = {}
    for table in tables:
        league = [a + b for a, b in zip(league, table["league"])]
        for key, counts in table["players"].items():
            have = players.setdefault(key, [0] * WIDTH)
            players[key] = [a + b for a, b in zip(have, counts)]
    return {"league": league, "players": {k: players[k] for k in sorted(players)}}


def competition_zones(connection: Any, collections: Iterable[str]) -> Dict[str, Any]:
    """The table of a competition and season: its collections (groups and phases) added up."""
    return merge_tables([zone_table(iter_owned_shots(connection.get_collection(name), is_fbcyl(name)), is_fbcyl(name)) for name in collections])
