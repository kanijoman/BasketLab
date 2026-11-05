"""The reference of the server charts' zone colours (issues #139, #760, #765): how every team, or every player, of a competition shot in each zone of the analyzer."""
from typing import Any, Dict, List, Literal, Optional

from src.shotcharts.owned_shots import iter_owned_shots

Entity = Dict[str, Dict[str, int]]


def league_zone_distribution(analyzer, coll: Any, fbcyl: bool = False, by: Literal["team", "player"] = "team") -> Optional[List[Entity]]:
    """One ``{zone_key: {"made", "total"}}`` per team (or per player with ``by="player"``) of the competition held in ``coll`` (FEB or FBCYL), in the zones of ``analyzer``.

    The shots are streamed and only the counts of each entity stay in memory (a league has tens of thousands of shots and the server 512 MB). A shot of a player nobody can name counts
    for his team and for no player. ``None`` when there is nothing to compare with or the database fails: the caller then keeps the legacy fixed colouring.
    """
    try:
        tables: Dict[str, Entity] = {}
        for team_id, player_id, x, y, made, _zone in iter_owned_shots(coll, fbcyl):
            owner = team_id if by == "team" else player_id
            zone_key = analyzer.zone_key_for_shot(x, y) if owner else None
            if zone_key is None:
                continue
            table = tables.setdefault(owner, {key: {"made": 0, "total": 0} for key in analyzer.zones.zones})
            table[zone_key]["total"] += 1
            table[zone_key]["made"] += int(made)
        return list(tables.values()) or None
    except Exception:  # noqa: BLE001 - callers fall back to the legacy colouring
        return None
