"""Rival-adjusted statistics service (FASE 2).

For each team and each stat, adjusts for opponent quality:

    adj_stat = actual_stat - (opp_avg_allowed - league_avg_allowed)

A positive adj value means the team performed *above* what you'd expect given
opponent quality; a negative value means underperformance.

Supports both FEB and FBCYL collections using the respective per-game
pipelines.  Results include raw mean, adjustment, adjusted mean and number of
games (n), so callers can decide how to present the uncertainty.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

from utils.collection_utils import is_fbcyl as _is_fbcyl


# Stats we adjust — key → own field → (opp defensive field)
# "own field" is what the team produced; "opp field" is what the OPPONENT allowed
# (i.e. the stat from the OPPONENT'S perspective in the per-game pipeline)
_STAT_PAIRS: Dict[str, tuple] = {
    "net_rtg":    ("net_game",       "opp_net_game"),
    "ortg":       ("oer_game",       "opp_oer_game"),
    "drtg":       ("der_game",       "opp_der_game"),
    "efg_pct":    ("efg_pct_game",   "opp_efg_pct_game"),
    "tov_rate":   ("tov_pct_game",   "opp_tov_pct_game"),
    "oreb_rate":  ("oreb_rate_game", "opp_orb_rate_game"),
    "pts":        ("points",         "opponent_points"),
}


class RivalAdjustedService:
    """Compute rival-adjusted per-game statistics for all teams in a collection.

    Algorithm
    ---------
    1. Run the per-game raw pipeline to get one row per (team, game).
    2. From those rows, compute each team's *defensive average*:
       ``opp_quality[T][stat]`` = mean value that opponents achieved against T.
    3. Compute the league average allowed per stat.
    4. For each team T, iterate over their games.  For each game against
       opponent O, compute the adjustment:
       ``adj_i = own_stat_i - (opp_quality[O][stat] - league_avg_allowed[stat])``
    5. Return the mean adjusted value across all games.

    The pipeline does not include opponent_name directly in the per-game
    projection.  We reconstruct it from the fact that every match produces
    exactly two rows (one per team).  We group rows by a synthetic game
    identifier: ``(team_name, opponent_points, points)`` which is unique per
    game when using counting stats.

    For FBCYL, the same logic applies using the FBCYL per-game pipeline.
    """

    def __init__(self, db_handler) -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_rival_adjusted_stats(
        self,
        collection_name: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Return rival-adjusted stats for all teams.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            ``{team_name: {stat_key: {raw_avg, adj, adj_avg, n, sos}}}``
            where *sos* (strength of schedule) is the mean opponent quality
            expressed as the average *allowed* value of each stat.

            Returns empty dict on error or empty collection.
        """
        fbcyl = _is_fbcyl(collection_name)
        rows = self._fetch_rows(collection_name, fbcyl)
        if not rows:
            return {}

        # Build per-team raw averages and per-stat defensive quality
        # Also build a way to link each team's game to the opponent
        return self._compute(rows)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_rows(self, collection_name: str, fbcyl: bool) -> List[Dict]:
        """Fetch per-game rows from the appropriate pipeline."""
        try:
            col = self._db.connection.get_collection(collection_name)
            if fbcyl:
                from src.database.aggregation.fbcyl_per_game_pipeline import (
                    build_fbcyl_team_per_game_pipeline,
                    enrich_fbcyl_team_row,
                )
                pipeline = build_fbcyl_team_per_game_pipeline()
                raw = list(col.aggregate(pipeline))
                return [enrich_fbcyl_team_row(r) for r in raw]
            else:
                from src.database.aggregation.pipeline_builder import (
                    AggregationPipelineBuilder,
                )
                pipeline = AggregationPipelineBuilder.build_per_game_raw_pipeline()
                return list(col.aggregate(pipeline))
        except Exception:
            return []

    def _compute(self, rows: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Core rival-adjustment computation.

        Strategy: pair each game's two rows (same game produces rows for both
        teams) using the fact that team A row has:
          - points = A's score
          - opponent_points = B's score
        and team B row has:
          - points = B's score
          - opponent_points = A's score
        We build a lookup: game_signature → {team_name: row} where
        game_signature = frozenset({(A_name, A_pts, B_pts)}).

        This allows us to retrieve the opponent's defensive quality for
        each game without adding opponent_name to the pipeline.
        """
        # Step 1: compute defensive quality per team (what they ALLOW per game)
        # From each row for team T, the opp_* fields = what T allowed
        allowed: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        own_vals: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

        for row in rows:
            team = row.get("team_name")
            if not team:
                continue
            for stat_key, (own_f, opp_f) in _STAT_PAIRS.items():
                own_v = row.get(own_f)
                opp_v = row.get(opp_f)
                if own_v is not None:
                    try:
                        own_vals[team][stat_key].append(float(own_v))
                    except (TypeError, ValueError):
                        pass
                if opp_v is not None:
                    try:
                        # opp_f = what opponent produced (= what T allowed)
                        # For net_rtg we want "opp's net_rtg" = how good opp performed
                        # which is -T's net_rtg from T's perspective... Actually
                        # opp_net_game is already computed as opp's net_rtg.
                        # For "pts allowed by T", we use opponent_points (pts BY opp).
                        # For clarity we track allowed[T][stat] = opp's achievement vs T
                        allowed[team][stat_key].append(float(opp_v))
                    except (TypeError, ValueError):
                        pass

        # Step 2: compute mean allowed per team and league averages
        mean_allowed: Dict[str, Dict[str, float]] = {}
        all_allowed_by_stat: Dict[str, List[float]] = defaultdict(list)
        for team, stat_map in allowed.items():
            mean_allowed[team] = {}
            for stat_key, vals in stat_map.items():
                if vals:
                    m = float(np.mean(vals))
                    mean_allowed[team][stat_key] = m
                    all_allowed_by_stat[stat_key].extend(vals)

        league_avg_allowed: Dict[str, float] = {
            stat_key: float(np.mean(vals))
            for stat_key, vals in all_allowed_by_stat.items()
            if vals
        }

        # Step 3: pair rows to find opponents.
        # Build: (pts_A, pts_B) → {team_name: row} mapping within each game.
        # Use a running game index based on seeing (pts, opp_pts) pairs sequentially.
        # Groups of rows that share the same (pts_a, pts_b) match key.
        game_buckets: Dict[frozenset, List[Dict]] = defaultdict(list)
        for row in rows:
            team = row.get("team_name")
            pts = row.get("points") or 0
            opp_pts = row.get("opponent_points") or 0
            # Signature: a frozenset of both score tuples so it's symmetric
            sig = frozenset([(team, int(pts), int(opp_pts))])
            # Extend with unique hint: we pair A-B by matching their swapped scores
            # Instead, bucket by the unordered pair of scores
            score_key = frozenset([int(pts), int(opp_pts)])
            game_buckets[score_key].append(row)

        # Step 4: now compute per-team adjustments.
        # For each team, we need their games and the opponent's defensive quality.
        # We iterate all rows: for team T in game with score (p, opp_p),
        # find team O with score (opp_p, p) → O's mean_allowed is the adjustment base.
        result: Dict[str, Dict[str, Any]] = {}

        # Reorganise: list of (team, own_vals_per_stat, opp_quality_per_stat)
        # For each row, find opponent by score reversal
        team_game_adj: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        team_game_sos: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

        for row in rows:
            team = row.get("team_name")
            if not team:
                continue
            pts = int(row.get("points") or 0)
            opp_pts = int(row.get("opponent_points") or 0)

            # Find the opponent team in this game: they have pts=opp_pts, opp_pts=pts
            # Scan the same score bucket
            score_key = frozenset([pts, opp_pts])
            opponent_name: Optional[str] = None
            for candidate in game_buckets[score_key]:
                cname = candidate.get("team_name")
                cpts = int(candidate.get("points") or 0)
                if cname != team and cpts == opp_pts:
                    opponent_name = cname
                    break

            for stat_key, (own_f, _) in _STAT_PAIRS.items():
                own_v = row.get(own_f)
                if own_v is None:
                    continue
                try:
                    own_v = float(own_v)
                except (TypeError, ValueError):
                    continue

                if opponent_name and opponent_name in mean_allowed:
                    opp_quality = mean_allowed[opponent_name].get(stat_key)
                    league_avg = league_avg_allowed.get(stat_key)
                    if opp_quality is not None and league_avg is not None:
                        adj = own_v - (opp_quality - league_avg)
                        team_game_adj[team][stat_key].append(adj)
                        team_game_sos[team][stat_key].append(opp_quality)

        # Build final result
        for team in own_vals:
            result[team] = {}
            for stat_key in _STAT_PAIRS:
                raw_list = own_vals[team].get(stat_key, [])
                adj_list = team_game_adj[team].get(stat_key, [])
                sos_list = team_game_sos[team].get(stat_key, [])
                if not raw_list:
                    continue
                raw_avg = round(float(np.mean(raw_list)), 2)
                adj_avg_val = round(float(np.mean(adj_list)), 2) if adj_list else None
                sos = round(float(np.mean(sos_list)), 2) if sos_list else None
                adj = (round(adj_avg_val - raw_avg, 2)
                       if adj_avg_val is not None else None)
                result[team][stat_key] = {
                    "raw_avg":  raw_avg,
                    "adj_avg":  adj_avg_val,
                    "adj":      adj,
                    "sos":      sos,
                    "n":        len(raw_list),
                }

        return result
