"""Rival-adjusted statistics service (descriptive analytics).

For each team, adjusts observed per-game stats by the seasonal quality of
each opponent using a **proportional** formula so that the context metric
matches the stat being evaluated:

    adj_game = raw_game * (league_avg_context / rival_seasonal_context)

Examples
--------
* OER 100 vs a rival with DER=86 (great defence)  -> adj OER ~116 (inflated).
* OER 100 vs a rival with DER=103 (poor defence)  -> adj OER ~97  (deflated).
* DER uses rival own OER as context (tougher offence -> deflate DER = looks better).
* eFG% uses rival allowed eFG% (tougher FG defence -> inflate eFG%).
* TOV rate uses rival forced-TOV rate (more pressure -> deflate TOV).
* ORB rate uses rival allowed ORB% (better DRB team -> inflate ORB).

For ``net_rtg`` (signed, can be negative) an additive form is used:

    adj_game = raw_game + (rival_seasonal_net_rtg - league_avg_net_rtg)

Results expose raw_avg, adj_avg, adj (delta), sos (strength-of-schedule
context value for this stat), and n (games with valid adjustment).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.collection_utils import is_fbcyl as _is_fbcyl

# ---------------------------------------------------------------------------
# Field maps — per-game pipeline row field names
# ---------------------------------------------------------------------------

# Team's own stat field in a per-game row
_OWN_FIELDS: Dict[str, str] = {
    "ortg":      "oer_game",
    "drtg":      "der_game",
    "efg_pct":   "efg_pct_game",
    "tov_rate":  "tov_pct_game",
    "oreb_rate": "oreb_rate_game",
    "pts":       "points",
    "net_rtg":   "net_game",
    "pace":      "possessions",
}

# What the TEAM allowed opponents to achieve in each per-game row
_ALLOWED_FIELDS: Dict[str, str] = {
    "ortg":      "opp_oer_game",
    "drtg":      "opp_der_game",
    "efg_pct":   "opp_efg_pct_game",
    "tov_rate":  "opp_tov_pct_game",
    "oreb_rate": "opp_orb_rate_game",
    "pts":       "opponent_points",
    "net_rtg":   "opp_net_game",
}

# Adjustment specs: (stat_key, ctx_dict, ctx_stat, mode)
#   ctx_dict : "own"     -> rival's own seasonal average for ctx_stat
#              "allowed" -> what rival allowed opponents (rival's defensive quality)
#   mode     : "mult" -> adj = raw * (league_ctx / rival_ctx)   [positive-only stats]
#              "add"  -> adj = raw + (rival_ctx - league_ctx)   [signed stats]
_ADJ_SPECS: List[Tuple[str, str, str, str]] = [
    # OER: rival defensive quality = what they allow opponents to score (= rival DER)
    ("ortg",      "allowed", "ortg",      "mult"),
    # DER: rival offensive quality = what they score themselves (= rival OER)
    ("drtg",      "own",     "ortg",      "mult"),
    # eFG%: rival FG defence = eFG% they allow
    ("efg_pct",   "allowed", "efg_pct",   "mult"),
    # TOV rate: rival pressure = TOV% they force on opponents
    ("tov_rate",  "allowed", "tov_rate",  "mult"),
    # ORB rate: rival DRB quality = ORB% they allow opponents
    ("oreb_rate", "allowed", "oreb_rate", "mult"),
    # Raw pts: rival scoring defence = pts they allow per game
    ("pts",       "allowed", "pts",       "mult"),
    # Net rating: rival overall strength (signed -> additive form)
    ("net_rtg",   "own",     "net_rtg",   "add"),
    # Pace: rival's natural tempo — 80 poss vs a 70-poss team is worth more
    ("pace",      "own",     "pace",      "mult"),
]

# Minimum paired games required for a statistically meaningful adjustment.
# With fewer games the rival's seasonal average is dominated by games against
# the evaluated team itself (circular dependency), making adj_avg converge
# artificially to the league mean for every team.
_MIN_ADJ_GAMES: int = 5


class RivalAdjustedService:
    """Compute rival-adjusted descriptive stats for all teams in a collection."""

    def __init__(self, db_handler) -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_rival_adjusted_stats(
        self, collection_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """Return rival-adjusted stats for all teams.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            {team_name: {stat_key: {raw_avg, adj_avg, adj, sos, n}}}
            where *sos* is the mean rival context value (strength of schedule).
            Returns empty dict on error or empty collection.
        """
        fbcyl = _is_fbcyl(collection_name)
        rows = self._fetch_rows(collection_name, fbcyl)
        if not rows:
            return {}
        return self._compute(rows)

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _fetch_rows(self, collection_name: str, fbcyl: bool) -> List[Dict]:
        """Fetch per-game rows from the appropriate aggregation pipeline."""
        try:
            col = self._db.connection.get_collection(collection_name)
            if fbcyl:
                from src.database.aggregation.fbcyl_per_game_pipeline import (
                    build_fbcyl_team_per_game_pipeline,
                    enrich_fbcyl_team_row,
                )
                pipeline = build_fbcyl_team_per_game_pipeline()
                return [enrich_fbcyl_team_row(r) for r in col.aggregate(pipeline)]
            from src.database.aggregation.pipeline_builder import (
                AggregationPipelineBuilder,
            )
            pipeline = AggregationPipelineBuilder.build_per_game_raw_pipeline()
            return list(col.aggregate(pipeline))
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Season sums (used for leave-one-out adjustment)
    # ------------------------------------------------------------------

    def _build_season_sums(
        self, rows: List[Dict]
    ) -> Tuple[
        Dict[str, Dict[str, Tuple[float, int]]],
        Dict[str, Dict[str, Tuple[float, int]]],
    ]:
        """Compute per-team season (sum, count) for own and allowed stats.

        Storing raw sums and counts (rather than averages) lets
        ``_accumulate_adjustments`` produce a leave-one-out context average
        by subtracting the current game's value before dividing:

            LOO_avg = (season_sum - game_val) / (season_count - 1)
        """
        own_acc: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        allowed_acc: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for row in rows:
            team = row.get("team_name")
            if not team:
                continue
            for sk, field in _OWN_FIELDS.items():
                v = row.get(field)
                if v is not None:
                    try:
                        own_acc[team][sk].append(float(v))
                    except (TypeError, ValueError):
                        pass
            for sk, field in _ALLOWED_FIELDS.items():
                v = row.get(field)
                if v is not None:
                    try:
                        allowed_acc[team][sk].append(float(v))
                    except (TypeError, ValueError):
                        pass

        def _to_sums(
            acc: Dict[str, Dict[str, List[float]]]
        ) -> Dict[str, Dict[str, Tuple[float, int]]]:
            return {
                t: {sk: (float(sum(vs)), len(vs)) for sk, vs in sm.items() if vs}
                for t, sm in acc.items()
            }

        return _to_sums(own_acc), _to_sums(allowed_acc)

    def _build_league_averages(
        self,
        sums_own: Dict[str, Dict[str, Tuple[float, int]]],
        sums_allowed: Dict[str, Dict[str, Tuple[float, int]]],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """League-wide averages by pooling each team's per-game mean."""
        def _pool(
            by_team: Dict[str, Dict[str, Tuple[float, int]]]
        ) -> Dict[str, float]:
            acc: Dict[str, List[float]] = defaultdict(list)
            for sm in by_team.values():
                for sk, (total, count) in sm.items():
                    if count > 0:
                        acc[sk].append(total / count)
            return {sk: float(np.mean(vs)) for sk, vs in acc.items() if vs}

        return _pool(sums_own), _pool(sums_allowed)

    # ------------------------------------------------------------------
    # Game-pair matching
    # ------------------------------------------------------------------

    def _pair_rows(self, rows: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """Match game rows by swapped (pts, opp_pts) score pairing.

        Each game produces exactly two rows.  Team A's row has
        (pts=X, opponent_points=Y) and team B's has (pts=Y, opponent_points=X).
        Pairs are consumed so repeated scorelines are handled correctly.
        """
        by_score: Dict[tuple, List[Tuple[int, Dict]]] = defaultdict(list)
        for idx, row in enumerate(rows):
            key = (int(row.get("points") or 0), int(row.get("opponent_points") or 0))
            by_score[key].append((idx, row))

        matched: set = set()
        pairs: List[Tuple[Dict, Dict]] = []

        for idx_a, row_a in enumerate(rows):
            if idx_a in matched:
                continue
            pts_a = int(row_a.get("points") or 0)
            opp_a = int(row_a.get("opponent_points") or 0)
            team_a = row_a.get("team_name")
            for idx_b, row_b in by_score.get((opp_a, pts_a), []):
                if idx_b not in matched and row_b.get("team_name") != team_a:
                    pairs.append((row_a, row_b))
                    matched.add(idx_a)
                    matched.add(idx_b)
                    break

        return pairs

    # ------------------------------------------------------------------
    # Adjustment computation
    # ------------------------------------------------------------------

    def _apply_adjustment(
        self, raw: float, rival_ctx: float, league_ctx: float, mode: str
    ) -> Optional[float]:
        """Compute adjusted value for one stat in one game."""
        if mode == "add":
            return raw + (rival_ctx - league_ctx)
        if rival_ctx == 0:
            return None
        return raw * (league_ctx / rival_ctx)

    def _accumulate_adjustments(
        self,
        pairs: List[Tuple[Dict, Dict]],
        sums_own: Dict[str, Dict[str, Tuple[float, int]]],
        sums_allowed: Dict[str, Dict[str, Tuple[float, int]]],
        league_own: Dict[str, float],
        league_allowed: Dict[str, float],
    ) -> Tuple[
        Dict[str, Dict[str, List[float]]],
        Dict[str, Dict[str, List[float]]],
    ]:
        """Accumulate per-game adjusted values using leave-one-out (LOO) context.

        For each paired game (A vs B), the rival B's contextual stat is the
        **leave-one-out** average: the rival's season sum minus the value they
        recorded in *this specific game*, divided by (count - 1).  This
        eliminates the circular dependency that arises when the rival's seasonal
        average includes the very game being adjusted.

        For ``ctx_dict == "own"``:  rival's game value = ``row_opp[own_field]``
        For ``ctx_dict == "allowed"``: rival's game value = ``row_opp[allowed_field]``
        """
        adj_acc: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        sos_acc: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        def _loo(
            sums: Dict[str, Dict[str, Tuple[float, int]]],
            team: str,
            sk: str,
            game_val: Optional[float],
        ) -> Optional[float]:
            """Leave-one-out average: subtract game_val from team's season sum."""
            entry = sums.get(team, {}).get(sk)
            if not entry:
                return None
            total, count = entry
            if count <= 0:
                return None
            if count == 1 or game_val is None:
                return total / count
            return (total - game_val) / (count - 1)

        def _process(
            team: str, opponent: str, row_team: Dict, row_opp: Dict
        ) -> None:
            for stat_key, ctx_dict, ctx_stat, mode in _ADJ_SPECS:
                raw_v = row_team.get(_OWN_FIELDS.get(stat_key, ""))
                if raw_v is None:
                    continue
                try:
                    raw_v = float(raw_v)
                except (TypeError, ValueError):
                    continue

                # Rival's game value to exclude from LOO (from opponent's row)
                if ctx_dict == "own":
                    opp_game_raw = row_opp.get(_OWN_FIELDS.get(ctx_stat, ""))
                    rival_ctx = _loo(
                        sums_own, opponent, ctx_stat,
                        float(opp_game_raw) if opp_game_raw is not None else None,
                    )
                    league_ctx = league_own.get(ctx_stat)
                else:  # "allowed"
                    opp_game_raw = row_opp.get(_ALLOWED_FIELDS.get(ctx_stat, ""))
                    rival_ctx = _loo(
                        sums_allowed, opponent, ctx_stat,
                        float(opp_game_raw) if opp_game_raw is not None else None,
                    )
                    league_ctx = league_allowed.get(ctx_stat)

                if rival_ctx is None or league_ctx is None:
                    continue
                adj_v = self._apply_adjustment(raw_v, rival_ctx, league_ctx, mode)
                if adj_v is None:
                    continue
                adj_acc[team][stat_key].append(adj_v)
                sos_acc[team][stat_key].append(rival_ctx)

        for row_a, row_b in pairs:
            team_a = row_a.get("team_name")
            team_b = row_b.get("team_name")
            if team_a:
                _process(team_a, team_b or "", row_a, row_b)
            if team_b:
                _process(team_b, team_a or "", row_b, row_a)

        return adj_acc, sos_acc

    def _compute(self, rows: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Full rival-adjustment pipeline."""
        sums_own, sums_allowed = self._build_season_sums(rows)
        if not sums_own:
            return {}
        league_own, league_allowed = self._build_league_averages(
            sums_own, sums_allowed
        )
        pairs = self._pair_rows(rows)
        adj_acc, sos_acc = self._accumulate_adjustments(
            pairs, sums_own, sums_allowed, league_own, league_allowed
        )
        return self._build_result(sums_own, adj_acc, sos_acc)

    def _build_result(
        self,
        sums_own: Dict[str, Dict[str, Tuple[float, int]]],
        adj_acc: Dict[str, Dict[str, List[float]]],
        sos_acc: Dict[str, Dict[str, List[float]]],
    ) -> Dict[str, Dict[str, Any]]:
        """Assemble the final result dict.

        Adjustments are only reported when the team accumulated at least
        ``_MIN_ADJ_GAMES`` paired games.  With leave-one-out this threshold
        mainly guards against tiny round-robin groups where rivals have only
        1 other game to sample from.
        """
        result: Dict[str, Dict[str, Any]] = {}
        for team, stat_sums in sums_own.items():
            result[team] = {}
            for stat_key, (total, count) in stat_sums.items():
                raw_avg = total / count if count > 0 else 0.0
                adj_list = adj_acc[team].get(stat_key, [])
                sos_list = sos_acc[team].get(stat_key, [])
                valid = len(adj_list) >= _MIN_ADJ_GAMES
                adj_avg = round(float(np.mean(adj_list)), 2) if valid else None
                sos = round(float(np.mean(sos_list)), 2) if valid else None
                adj = (
                    round(adj_avg - round(raw_avg, 2), 2)
                    if adj_avg is not None
                    else None
                )
                result[team][stat_key] = {
                    "raw_avg": round(raw_avg, 2),
                    "adj_avg": adj_avg,
                    "adj":     adj,
                    "sos":     sos,
                    "n":       len(adj_list),
                }
        return result
