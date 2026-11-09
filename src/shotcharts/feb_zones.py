"""FEB shot-zone helpers: zone classification and per-zone counting.

Extracted from the shots router so services (team report, scouting) can reuse them.

The zones are the ones of the engine, ``live_core.zones`` (issue #452, block 2): restricted_area, key_area, short_mid_range, medium_mid_range, long_mid_range, left_corner_three,
left_wing_three, center_three, right_wing_three, right_corner_three. The web used to have its own geometry (paint, mid_left/center/right, wing_left, top_three...) and the same shot fell in
a different zone in the web and in the app; there is ONE geometry now and this module only keeps the API the router, the services and the exporters call.
FBCYL carries its coordinates in the players' stats (``fbcyl_zones``).
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from src.live_core.zones import ZONES, classify_fiba, feb_to_fiba  # noqa: F401  (feb_to_fiba is re-exported: the services and the exporters import it from here)

# Zone metadata, in the order of the engine: (label, points)
ZONE_META: Dict[str, Dict[str, Any]] = {key: {"label": zone["name"], "points": zone["points"]} for key, zone in ZONES.items()}


def classify_zone(x: float, y: float) -> str:
    """Return the zone key for a FIBA-coordinate shot at (x, y) (metres on the half court)."""
    return classify_fiba(x, y)["zone"]


# ---------------------------------------------------------------------------
# MongoDB extraction helpers
# ---------------------------------------------------------------------------

def build_dorsal_to_id_map(shotchart: dict) -> dict:
    """Build a (team_idx, dorsal_str) → player_id lookup from SHOTCHART.TEAM.

    SHOTCHART.SHOTS[].player stores the dorsal number, not the player ID.
    SHOTCHART.TEAM[n].PLAYER[].id holds the actual player identifier that
    matches PlayerStat.player_id from the stats aggregation pipeline.
    """
    mapping: dict = {}
    # SHOTCHART.TEAM is a list ordered by team slot (0 = local, 1 = away)
    for t_idx, team_entry in enumerate(shotchart.get("TEAM", [])):
        for player in team_entry.get("PLAYER", []):
            raw_no = str(player.get("no", ""))
            stripped = raw_no.lstrip("0") or raw_no  # "05" → "5", but "0" → "0"
            pid = str(player.get("id", ""))
            if pid:
                mapping[(t_idx, raw_no)] = pid
                mapping[(t_idx, stripped)] = pid
    return mapping


def iter_shots_feb(coll, team_id: Optional[str], player_filter: Optional[str]) -> Iterator[Dict]:
    """Lazily yield the classified FEB shots of a collection (O(1) memory per game).

    Filters by ``HEADER.TEAM.id`` (indexed, sponsor-change safe) when
    ``team_id`` is provided, avoiding a full-collection scan.
    """
    # Include SHOTCHART.TEAM so we can resolve dorsal → player_id per game
    projection = {
        "SHOTCHART.SHOTS": 1,
        "SHOTCHART.TEAM": 1,
        "HEADER.TEAM": 1,
    }
    query: dict = {"SHOTCHART.SHOTS": {"$exists": True}}
    if team_id:
        query["HEADER.TEAM.id"] = team_id
    cursor = coll.find(query, projection)

    for doc in cursor:
        header_teams = doc.get("HEADER", {}).get("TEAM", [])

        # Determine which team slot (0 or 1) belongs to our team_id
        team_idx_filter: Optional[int] = None
        if team_id:
            for idx, t in enumerate(header_teams):
                if str(t.get("id", "")) == str(team_id):
                    team_idx_filter = idx
                    break
            if team_idx_filter is None:
                continue  # doc matched the index but id not found in array — skip

        shotchart = doc.get("SHOTCHART", {})
        # Build dorsal→player_id map for this game (needed for player filter)
        dorsal_map = build_dorsal_to_id_map(shotchart) if player_filter else {}

        shots_raw = shotchart.get("SHOTS", [])
        for s in shots_raw:
            # FEB scraper stores team as a string ("0" / "1") in MongoDB — cast to int
            try:
                t_idx = int(s.get("team"))
            except (TypeError, ValueError):
                continue
            if t_idx not in (0, 1):
                continue

            # Apply team filter: only include our team's shots
            if team_idx_filter is not None and t_idx != team_idx_filter:
                continue

            # Apply player filter: resolve dorsal to actual player ID before comparing
            if player_filter:
                dorsal = str(s.get("player", ""))
                resolved_id = dorsal_map.get((t_idx, dorsal), "")
                if resolved_id != player_filter:
                    continue

            x_pct = float(s.get("x", 0))
            y_pct = float(s.get("y", 0))
            made   = int(s.get("m", 0)) == 1
            x_fiba, y_fiba = feb_to_fiba(x_pct, y_pct, t_idx)
            zone = classify_zone(x_fiba, y_fiba)

            yield {
                "zone": zone,
                "made": made,
                "x":    x_fiba,
                "y":    y_fiba,
            }


def extract_shots_feb(coll, team_id: Optional[str], player_filter: Optional[str]) -> List[Dict]:
    """All classified FEB shots as a list (use ``iter_shots_feb`` for league-wide scans)."""
    return list(iter_shots_feb(coll, team_id, player_filter))


def stream_zone_counts_feb(
    coll, team_id: Optional[str], player_filter: Optional[str]
) -> Dict[str, Dict[str, int]]:
    """Count FEB shots per zone using O(1) memory (no ``all_shots`` list).

    Streams the cursor and accumulates zone counters in-place.  The
    zones endpoint uses this instead of building an intermediate list.

    Returns:
        Dict mapping zone key → ``{"fga": int, "fgm": int}``.
    """
    accum: Dict[str, Dict[str, int]] = {z: {"fga": 0, "fgm": 0} for z in ZONE_META}

    # Projection: skip SHOTCHART.TEAM unless we need the dorsal map
    projection: Dict[str, int] = {"SHOTCHART.SHOTS": 1, "HEADER.TEAM": 1}
    if player_filter:
        projection["SHOTCHART.TEAM"] = 1

    query: dict = {"SHOTCHART.SHOTS": {"$exists": True}}
    if team_id:
        query["HEADER.TEAM.id"] = team_id
    cursor = coll.find(query, projection)

    for doc in cursor:
        header_teams = doc.get("HEADER", {}).get("TEAM", [])

        team_idx_filter: Optional[int] = None
        if team_id:
            for idx, t in enumerate(header_teams):
                if str(t.get("id", "")) == str(team_id):
                    team_idx_filter = idx
                    break
            if team_idx_filter is None:
                continue

        shotchart = doc.get("SHOTCHART", {})
        dorsal_map = build_dorsal_to_id_map(shotchart) if player_filter else {}

        for s in shotchart.get("SHOTS", []):
            try:
                t_idx = int(s.get("team"))
            except (TypeError, ValueError):
                continue
            if t_idx not in (0, 1):
                continue
            if team_idx_filter is not None and t_idx != team_idx_filter:
                continue
            if player_filter:
                dorsal = str(s.get("player", ""))
                if dorsal_map.get((t_idx, dorsal), "") != player_filter:
                    continue

            x_pct = float(s.get("x", 0))
            y_pct = float(s.get("y", 0))
            made   = int(s.get("m", 0)) == 1
            x_fiba, y_fiba = feb_to_fiba(x_pct, y_pct, t_idx)
            zone = classify_zone(x_fiba, y_fiba)
            if zone in accum:
                accum[zone]["fga"] += 1
                if made:
                    accum[zone]["fgm"] += 1

    return accum


def aggregate_zones(accum: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    """Build the zone-stats response list from a ``{zone: {fga, fgm}}`` accumulator."""
    result = []
    for zone_key, meta in ZONE_META.items():
        fga = accum.get(zone_key, {}).get("fga", 0)
        fgm = accum.get(zone_key, {}).get("fgm", 0)
        result.append({
            "zone":       zone_key,
            "zone_label": meta["label"],
            "points":     meta["points"],
            "fga":        fga,
            "fgm":        fgm,
            "fg_pct":     round(fgm / fga * 100, 1) if fga > 0 else 0.0,
        })
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
