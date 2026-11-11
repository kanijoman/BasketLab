"""What a competition has for each of its sections besides the rows (#676, #684, #685): the payload of an exporter, or ``None`` when there is nothing to publish.

Split from ``web_data`` (#842) to keep that module under the size limit. The rules here (when a section has nothing to publish) are NOT seen by the version of a section's code
(``build_cache.section_versions``): changing one needs ``build_cache.EPOCH`` raised.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.local_data.assist_connections_export import export_assist_connections
from src.local_data.consistency_export import export_consistency
from src.local_data.export import export_derived
from src.local_data.inout_export import export_inout
from src.local_data.lineups_export import export_lineups
from src.local_data.matches_export import export_matches
from src.local_data.possessions_export import export_possession_csv, export_possessions
from src.local_data.rival_adjusted_export import export_rival_adjusted
from src.local_data.rotations_export import export_rotations
from src.local_data.shots_export import export_shots


def section_payload(section: str, handler: Any, db: Any, collection: str) -> Optional[Dict[str, Any]]:
    """What a competition has for ``section``, or ``None`` when it has nothing to publish: no game with ``DERIVED`` or with shots, or no play-by-play to analyse the rotations or the lineups."""
    if section == "derived":
        payload = export_derived(db[collection], collection)
        return payload if payload["rows"] else None
    if section == "shots":
        payload = export_shots(db[collection], collection)
        return payload if payload["shots"] else None
    if section == "possessions":
        payload = export_possessions(handler, collection)
        return payload if payload["table"] else None
    if section == "possession_csv":
        payload = export_possession_csv(handler, collection)
        return payload if payload["csv"] else None
    if section == "matches":
        payload = export_matches(handler, collection)
        return payload if payload["matches"] else None
    if section == "inout":
        payload = export_inout(handler, collection)
        return payload if payload["players"] else None
    if section == "consistency":
        payload = export_consistency(handler, collection)
        return payload if payload["players"] else None
    if section == "rival_adjusted":
        payload = export_rival_adjusted(handler, collection)
        return payload if payload["teams"] else None
    if section == "assist_connections":
        payload = export_assist_connections(handler, collection)
        return payload if payload["teams"] else None
    if section == "lineups":
        payload = export_lineups(handler, collection)
        return payload if payload["teams"] else None
    payload = export_rotations(handler, collection)
    return payload if any(t["analysis"].get("games_with_playbyplay") for t in payload["teams"]) else None
