"""Multi-phase service — combine statistics across several collections.

Supports two views:
- ``get_combined_team_stats``   — one merged row per team (all phases summed)
- ``get_combined_player_stats`` — one merged row per player (all phases summed)
- ``get_team_stats_breakdown``  — raw per-collection stats keyed by collection name
- ``get_player_stats_breakdown``— raw per-collection player stats keyed by collection name

Counting stats (games_played, points_scored, …) are summed.
Per-game averages are recomputed from the summed totals.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

# Fields that are simple totals (sum across phases)
_SUM_FIELDS = (
    "games_played", "games_won", "games_lost",
    "points_scored", "points_received",
    "fg2_made", "fg2_attempts",
    "fg3_made", "fg3_attempts",
    "ft_made", "ft_attempts",
    "rebounds_off", "rebounds_def", "total_rebounds",
    "assists", "steals", "turnovers", "blocks", "personal_fouls",
    "total_possessions", "total_minutes",
    "total_points",  # player-level alias
    "valoracion",    # player valoración (PIR)
)

# Per-game fields and their (total_field, games_field) source pair
_PG_FIELDS: Dict[str, tuple] = {
    "points_per_game":     ("points_scored",   "games_played"),
    "points_against_per_game": ("points_received", "games_played"),
    "possessions_per_game": ("total_possessions", "games_played"),
    "rebounds_per_game":   ("total_rebounds",  "games_played"),
    "assists_per_game":    ("assists",          "games_played"),
    "steals_per_game":     ("steals",           "games_played"),
    "turnovers_per_game":  ("turnovers",        "games_played"),
    "blocks_per_game":     ("blocks",           "games_played"),
    # player-level
    "total_points_per_game": ("total_points",  "games_played"),
    "minutes_per_game":      ("total_minutes",  "games_played"),
    "valoracion_per_game":   ("valoracion",     "games_played"),
}

# Percentage fields and their (made, attempts) pair
_PCT_FIELDS: Dict[str, tuple] = {
    "fg2_percentage": ("fg2_made", "fg2_attempts"),
    "fg3_percentage": ("fg3_made", "fg3_attempts"),
    "ft_percentage":  ("ft_made",  "ft_attempts"),
}

# FEB MongoDB aggregation pipelines use slightly different field names than
# the canonical names expected by _SUM_FIELDS / _PG_FIELDS / _PCT_FIELDS.
# This mapping is applied to each row before merging.
_FEB_FIELD_ALIASES: Dict[str, str] = {
    # Team pipeline aliases
    "total_games":   "games_played",
    "fg2_attempted": "fg2_attempts",
    "fg3_attempted": "fg3_attempts",
    "ft_attempted":  "ft_attempts",
    # Player pipeline aliases (FEB player aggregation uses short field names)
    "total_pts":    "total_points",
    "total_p2m":   "fg2_made",
    "total_p2a":   "fg2_attempts",
    "total_p3m":   "fg3_made",
    "total_p3a":   "fg3_attempts",
    "total_p1m":   "ft_made",
    "total_p1a":   "ft_attempts",
    "total_ro":    "rebounds_off",
    "total_rd":    "rebounds_def",
    "total_rt":    "total_rebounds",
    "total_assist": "assists",
    "total_st":    "steals",
    "total_to":    "turnovers",
    "total_bs":    "blocks",
    "total_pf":    "personal_fouls",
    "total_val":   "valoracion",
}


def _normalize_row(row: Dict) -> Dict:
    """Rename FEB pipeline field names to canonical names in-place."""
    for src, dst in _FEB_FIELD_ALIASES.items():
        if src in row and dst not in row:
            row[dst] = row.pop(src)
    return row


class MultiPhaseService:
    """Merge basketball stats across multiple collections (seasons / phases)."""

    def __init__(self, db: Any, collections: List[str]) -> None:
        self._db = db
        self._collections = collections

    # ------------------------------------------------------------------
    # Public API — combined views
    # ------------------------------------------------------------------

    def get_combined_team_stats(self, is_fbcyl: bool) -> List[Dict]:
        """Return one merged stats row per team, summing all phases."""
        rows_by_coll = self._load_team_stats(is_fbcyl)
        return _merge_by_key(rows_by_coll, key="team_name")

    def get_combined_player_stats(self, is_fbcyl: bool) -> List[Dict]:
        """Return one merged stats row per player, summing all phases."""
        rows_by_coll = self._load_player_stats(is_fbcyl)
        return _merge_by_key(rows_by_coll, key="player_name")

    # ------------------------------------------------------------------
    # Public API — breakdown views
    # ------------------------------------------------------------------

    def get_team_stats_breakdown(self, is_fbcyl: bool) -> Dict[str, List[Dict]]:
        """Return raw per-collection team stats keyed by collection name."""
        return self._load_team_stats(is_fbcyl)

    def get_player_stats_breakdown(self, is_fbcyl: bool) -> Dict[str, List[Dict]]:
        """Return raw per-collection player stats keyed by collection name."""
        return self._load_player_stats(is_fbcyl)

    # ------------------------------------------------------------------
    # Private loaders
    # ------------------------------------------------------------------

    def _load_team_stats(self, is_fbcyl: bool) -> Dict[str, List[Dict]]:
        result: Dict[str, List[Dict]] = {}
        for coll in self._collections:
            rows = self._db.get_team_stats(coll) or []
            result[coll] = rows
        return result

    def _load_player_stats(self, is_fbcyl: bool) -> Dict[str, List[Dict]]:
        result: Dict[str, List[Dict]] = {}
        for coll in self._collections:
            rows = self._db.get_player_stats(coll) or []
            result[coll] = rows
        return result


# ---------------------------------------------------------------------------
# Module-level merge helpers
# ---------------------------------------------------------------------------

def _merge_by_key(
    rows_by_coll: Dict[str, List[Dict]],
    key: str,
) -> List[Dict]:
    """Merge rows from multiple collections, summing counting stats.

    Rows with the same *key* value are collapsed into one row.
    After summing, per-game and percentage fields are recomputed.
    """
    accumulated: Dict[str, Dict] = {}

    for coll_rows in rows_by_coll.values():
        for row in coll_rows:
            _normalize_row(row)
            entity_key = row.get(key, "")
            if not entity_key:
                continue
            if entity_key not in accumulated:
                # Seed with a copy — use the raw data as starting point
                accumulated[entity_key] = {
                    k: (v if not isinstance(v, (int, float)) else 0)
                    for k, v in row.items()
                }
                accumulated[entity_key][key] = entity_key

            acc = accumulated[entity_key]
            for field in _SUM_FIELDS:
                if field in row:
                    acc[field] = acc.get(field, 0) + (row[field] or 0)

    if not accumulated:
        return []

    result = []
    for entity_key, acc in accumulated.items():
        _recompute_derived(acc)
        result.append(acc)
    return result


def _recompute_derived(row: Dict) -> None:
    """Recompute per-game and percentage fields from summed counting stats."""
    games = row.get("games_played") or 0

    for pg_field, (total_f, games_f) in _PG_FIELDS.items():
        total = row.get(total_f)
        g = row.get(games_f) or games
        if total is not None and g:
            row[pg_field] = round(total / g, 2)

    # Player rows use total_points instead of points_scored
    if "total_points" in row and "points_per_game" not in row:
        total = row.get("total_points", 0) or 0
        if games and total:
            row["points_per_game"] = round(total / games, 2)
    elif "total_points" in row and games:
        # Recompute to override the seeded initial value
        total = row.get("total_points", 0) or 0
        row["points_per_game"] = round(total / games, 2) if games else 0.0

    # Aliases
    if "points_per_game" in row:
        row["points_allowed_per_game"] = row.get("points_against_per_game", 0)

    for pct_field, (made_f, att_f) in _PCT_FIELDS.items():
        made = row.get(made_f, 0) or 0
        att  = row.get(att_f,  0) or 0
        row[pct_field] = round(made / att * 100, 2) if att else 0.0

    # Win percentage
    gp = row.get("games_played") or 0
    gw = row.get("games_won") or 0
    row["win_percentage"] = round(gw / gp * 100, 2) if gp else 0.0

    # Alias games_played → total_games (matches TeamStat interface used by frontend)
    row["total_games"] = games

    # ORB / DRB per game
    orb = row.get("rebounds_off", 0) or 0
    drb = row.get("rebounds_def", 0) or 0
    if games:
        row["offensive_rebounds_per_game"] = round(orb / games, 2)
        row["defensive_rebounds_per_game"] = round(drb / games, 2)

    # Collect shooting totals for advanced stats
    fg2m = row.get("fg2_made", 0) or 0
    fg2a = row.get("fg2_attempts", 0) or 0
    fg3m = row.get("fg3_made", 0) or 0
    fg3a = row.get("fg3_attempts", 0) or 0
    fta  = row.get("ft_attempts", 0) or 0
    fgm  = fg2m + fg3m
    fga  = fg2a + fg3a
    tov  = row.get("turnovers", 0) or 0
    ast  = row.get("assists", 0) or 0
    stl  = row.get("steals", 0) or 0
    blk  = row.get("blocks", 0) or 0
    # Use total_points (player rows) or points_scored (team rows)
    pts  = row.get("points_scored") or row.get("total_points", 0) or 0
    poss = row.get("total_possessions", 0) or 0
    opp_pts = row.get("points_received", 0) or 0

    # Offensive / Defensive / Net rating (per 100 possessions)
    if poss:
        row["offensive_rating"] = round(pts / poss * 100, 2)
        row["defensive_rating"] = round(opp_pts / poss * 100, 2)
        row["net_rating"] = round((pts - opp_pts) / poss * 100, 2)

    # eFG%
    if fga:
        row["efg_percentage"] = round((fg2m + 1.5 * fg3m) / fga * 100, 2)
        row["three_point_rate"] = round(fg3a / fga * 100, 2)

    # TOV% (four-factors formula)
    tov_denom = fga + 0.44 * fta + tov
    if tov_denom:
        row["turnover_rate"] = round(tov / tov_denom * 100, 2)

    # Free-throw rate
    if fga:
        row["free_throw_rate"] = round(fta / fga * 100, 2)

    # True shooting %
    ts_denom = 2 * (fga + 0.44 * fta)
    if ts_denom and pts:
        row["true_shooting"] = round(pts / ts_denom * 100, 2)

    # Assist / field-goal rate
    if fgm:
        row["assist_fg_rate"] = round(ast / fgm * 100, 2)

    # Rates per 100 possessions
    if poss:
        row["assist_rate"] = round(ast / poss * 100, 2)
        row["steal_rate"]  = round(stl / poss * 100, 2)
        row["block_rate"]  = round(blk / poss * 100, 2)

    # Rebound share rates (within own team totals — opponent data not available)
    reb_total = orb + drb
    if reb_total:
        row["offensive_rebound_rate"] = round(orb / reb_total * 100, 2)
        row["defensive_rebound_rate"] = round(drb / reb_total * 100, 2)
