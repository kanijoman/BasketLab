"""Player statistics service.

Encapsulates player stats loading, IN/OUT analysis, and pair analysis,
decoupled from the PyQt6 UI layer.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import numpy as np

from utils.collection_utils import is_fbcyl as _is_fbcyl

if TYPE_CHECKING:
    from database import MongoDBHandler


class PlayerStatsService:
    """High-level service for player statistics.

    Responsibilities
    ----------------
    - Load raw player stats from the database (with optional filters).
    - Orchestrate IN/OUT analysis requests (delegates to repository).
    - Orchestrate two-player together-on-court analysis.
    - Expose individual stat retrieval with a teammate context.

    This class contains no PyQt6 imports.

    Example
    -------
    ::

        from database import MongoDBHandler
        from services import PlayerStatsService

        handler = MongoDBHandler()
        svc = PlayerStatsService(handler)
        players = svc.load_season_data("FEB_LF2_2025_A")
    """

    def __init__(self, db_handler: "MongoDBHandler") -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_quartiles(self, collection_name: str) -> Dict[str, Dict[str, float]]:
        """Compute quartile thresholds for all tracked player statistics.

        Mirrors ``TeamStatsService.get_quartiles`` so the front-end can apply
        IQRBar and quartile colouring using a backend endpoint rather than
        client-side computation.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            Dict mapping stat field names to ``{"min", "q1", "q2", "q3",
            "max", "count"}`` dicts.  Returns an empty dict on failure.
        """
        stat_fields = [
            'points_per_game', 'rebounds_per_game', 'offensive_rebounds_per_game',
            'defensive_rebounds_per_game', 'assists_per_game', 'steals_per_game',
            'turnovers_per_game', 'blocks_per_game', 'fouls_per_game',
            'valoracion_per_game', 'pllss_per_game', 'minutes_per_game',
            'fg1_percentage', 'fg2_percentage', 'fg3_percentage',
        ]
        try:
            players = self.load_season_data(collection_name)
            if not players:
                return {}
            result: Dict[str, Dict[str, float]] = {}
            for field in stat_fields:
                values = [
                    float(p[field]) for p in players
                    if p.get(field) is not None and p.get('games_played', 0) >= 3
                ]
                if len(values) >= 4:
                    values.sort()
                    result[field] = {
                        'min':   float(values[0]),
                        'q1':    float(np.percentile(values, 25)),
                        'q2':    float(np.percentile(values, 50)),
                        'q3':    float(np.percentile(values, 75)),
                        'max':   float(values[-1]),
                        'count': len(values),
                    }
            return result
        except Exception:
            return {}

    def load_season_data(
        self,
        collection_name: str,
        date_filter: Optional[Dict] = None,
        venue_filter: Optional[bool] = None,
        result_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Load aggregated player stats for a collection.

        Args:
            collection_name: MongoDB collection name.
            date_filter: Optional MongoDB date range dict.
            venue_filter: ``True`` = home only, ``False`` = away only.
            result_filter: ``"won"``, ``"lost"``, or ``None``.

        Returns:
            List of player stat dicts (may be empty).
        """
        players = self._db.get_player_stats(
            collection_name, date_filter, venue_filter, result_filter
        ) or []
        if players:
            self._enrich_with_advanced_stats(collection_name, players)
        return players

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enrich_with_advanced_stats(
        self, collection_name: str, players: List[Dict]
    ) -> List[Dict]:
        """Add advanced per-player metrics (ORtg, DRtg, Usg%, etc.) in-place.

        Fetches season-wide team and opponent stats once per unique team, then
        runs AdvancedStatsCalculator for every player.  Failures for individual
        players are silently ignored — they receive zero defaults instead.

        Args:
            collection_name: MongoDB collection name.
            players: List of player stat dicts (modified in-place).

        Returns:
            The same list with advanced stats merged in.
        """
        try:
            from stats.advanced_stats_calculator import AdvancedStatsCalculator
        except ImportError:
            return players

        # Collect unique team names
        unique_teams = {p.get('team_name') for p in players if p.get('team_name')}

        # Fetch team/opponent context once per team
        team_context: Dict[str, Dict] = {}
        for team_name in unique_teams:
            try:
                ts = self._db.get_aggregated_team_stats(collection_name, team_name)
                os_ = self._db.get_aggregated_opponent_stats(collection_name, team_name)
                if ts and os_:
                    team_context[team_name] = {'team_stats': ts, 'opp_stats': os_}
            except Exception:
                pass

        _default_adv = {
            'usage': 0.0, 'orating': 0.0, 'drating': 0.0, 'net_rtg': 0.0,
            'ftr_adv': 0.0, 'three_pr_adv': 0.0, 'efg_adv': 0.0, 'ts_adv': 0.0,
            'ast_pct': 0.0, 'tov_pct': 0.0, 'stl_pct': 0.0, 'blk_pct': 0.0,
            'drb_pct': 0.0, 'orb_pct': 0.0, 'pie': 0.0,
        }

        for player in players:
            team_name = player.get('team_name', '')
            ctx = team_context.get(team_name)
            if not ctx:
                player.update(_default_adv)
                continue
            try:
                adv = AdvancedStatsCalculator.calculate_all_advanced_stats(
                    player, ctx['team_stats'], ctx['opp_stats']
                )
                # Expose under API-friendly keys (avoid shadowing basic fields)
                player['usage_pct']  = round(adv.get('usage', 0.0), 1)
                player['orating']    = round(adv.get('orating', 0.0), 1)
                player['drating']    = round(adv.get('drating', 0.0), 1)
                player['net_rtg']    = round(adv.get('net_rtg', 0.0), 1)
                player['ast_pct']    = round(adv.get('ast_pct', 0.0), 1)
                player['tov_pct_adv'] = round(adv.get('tov_pct', 0.0), 1)
                player['stl_pct']    = round(adv.get('stl_pct', 0.0), 1)
                player['blk_pct']    = round(adv.get('blk_pct', 0.0), 1)
                player['drb_pct']    = round(adv.get('drb_pct', 0.0), 1)
                player['orb_pct']    = round(adv.get('orb_pct', 0.0), 1)
                player['pie']        = round(adv.get('pie', 0.0), 2)
            except Exception:
                player.update(_default_adv)

        return players

    def get_consistency(self, collection_name: str) -> Dict[str, Dict[str, Any]]:
        """Compute intra-player per-game variability (std dev + CV) for key stats.

        For each player, queries raw per-game counting stats and computes the
        standard deviation (\u03c3) and CV across all games they played.

        Only available for FEB collections.  Returns {} for FBCYL or on error.
        Requires \u22653 games for a meaningful result.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            ``{player_id: {stat_key: {"mean": float, "std": float, "cv": float, "n": int}}}``
        """
        if _is_fbcyl(collection_name):
            return self._get_consistency_fbcyl(collection_name)

        from src.database.aggregation.pipeline_builder import AggregationPipelineBuilder

        try:
            collection = self._db.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_per_player_per_game_pipeline()
            rows = list(collection.aggregate(pipeline))
        except Exception:
            return {}

        if not rows:
            return {}

        FIELD_MAP = {
            "points_per_game":             "pts",
            "rebounds_per_game":           "rt",
            "offensive_rebounds_per_game": "ro",
            "defensive_rebounds_per_game": "rd",
            "assists_per_game":            "assist",
            "steals_per_game":             "st",
            "turnovers_per_game":          "to",
            "blocks_per_game":             "bs",
            "fouls_per_game":              "pf",
            "valoracion_per_game":         "val",
            "pllss_per_game":              "pllss_game",
            "minutes_per_game":            "minutes",
            "fg1_percentage":              "fg1_pct_game",
            "fg2_percentage":              "fg2_pct_game",
            "fg3_percentage":              "fg3_pct_game",
            "efg_percentage":              "efg_pct_game",
            "true_shooting":               "ts_pct_game",
            "free_throw_rate":             "ftr_game",
            "three_point_rate":            "three_pr_game",
            "turnover_rate":               "tov_pct_game",
            # Advanced per-game team-share proxies (added to per-game pipeline)
            "usage_pct":                   "usg_pct_game",
            "ast_pct":                     "ast_pct_game",
            "orb_pct":                     "orb_pct_game",
            "drb_pct":                     "drb_pct_game",
            "stl_pct":                     "stl_pct_game",
            "blk_pct":                     "blk_pct_game",
        }

        by_player: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            pid = row.get("player_id")
            if not pid:
                continue
            for stat_key, raw_field in FIELD_MAP.items():
                val = row.get(raw_field)
                if val is not None:
                    try:
                        by_player[pid][stat_key].append(float(val))
                    except (TypeError, ValueError):
                        pass

        result: Dict[str, Dict[str, Any]] = {}
        for pid, stats in by_player.items():
            result[pid] = {}
            for stat_key, values in stats.items():
                if len(values) < 3:
                    continue
                arr = np.array(values)
                mean = float(np.mean(arr))
                std = float(np.std(arr))
                cv = (std / mean * 100) if mean > 0 else 0.0
                result[pid][stat_key] = {
                    "mean": round(mean, 2),
                    "std":  round(std, 2),
                    "cv":   round(cv, 1),
                    "n":    len(values),
                }

        return result

    def _get_consistency_fbcyl(self, collection_name: str) -> Dict[str, Any]:
        """FBCYL per-game player consistency using the FBCYL player per-game pipeline."""
        from src.database.aggregation.fbcyl_per_game_pipeline import (
            build_fbcyl_player_per_game_pipeline, enrich_fbcyl_player_row,
        )
        from collections import defaultdict

        try:
            collection = self._db.connection.get_collection(collection_name)
            pipeline   = build_fbcyl_player_per_game_pipeline()
            raw_rows   = list(collection.aggregate(pipeline))
        except Exception:
            return {}

        if not raw_rows:
            return {}

        rows = [enrich_fbcyl_player_row(r) for r in raw_rows]

        FBCYL_FIELD_MAP = {
            "points_per_game":             "pts",
            "rebounds_per_game":           "rt",
            "offensive_rebounds_per_game": "ro",
            "defensive_rebounds_per_game": "rd",
            "assists_per_game":            "assist",
            "steals_per_game":             "st",
            "turnovers_per_game":          "to",
            "blocks_per_game":             "bs",
            "fouls_per_game":              "pf",
            "valoracion_per_game":         "val",
            "minutes_per_game":            "minutes",
            "fg2_percentage":              "fg2_pct_game",
            "fg3_percentage":              "fg3_pct_game",
            "efg_percentage":              "efg_pct_game",
            "true_shooting":               "ts_pct_game",
            "free_throw_rate":             "ftr_game",
            "three_point_rate":            "three_pr_game",
            "turnover_rate":               "tov_pct_game",
        }

        by_player: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            pid = row.get("player_id")
            if not pid:
                continue
            for stat_key, raw_field in FBCYL_FIELD_MAP.items():
                val = row.get(raw_field)
                if val is not None:
                    try:
                        by_player[pid][stat_key].append(float(val))
                    except (TypeError, ValueError):
                        pass

        result: Dict[str, Any] = {}
        for pid, stats in by_player.items():
            result[pid] = {}
            for stat_key, values in stats.items():
                if len(values) < 3:
                    continue
                arr  = np.array(values)
                mean = float(np.mean(arr))
                std  = float(np.std(arr))
                cv   = (std / mean * 100) if mean > 0 else 0.0
                result[pid][stat_key] = {
                    "mean": round(mean, 2),
                    "std":  round(std, 2),
                    "cv":   round(cv, 1),
                    "n":    len(values),
                }

        return result

    def get_in_out_analysis(
        self,
        collection_name: str,
        player_id: str,
        date_filter: Optional[Dict] = None,
        debug: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """Return IN/OUT on-court impact analysis for a player.

        Args:
            collection_name: MongoDB collection name.
            player_id: Player identifier (FEB int-string or FBCYL UUID).
            date_filter: Optional date range filter.
            debug: If ``True``, saves per-game raw outputs.
            progress_callback: Optional ``(current, total) -> None`` callback.

        Returns:
            Dict with in/out stats, or empty dict on failure.
        """
        return self._db.get_player_in_out_stats(
            collection_name, player_id, date_filter,
            debug=debug, progress_callback=progress_callback
        ) or {}

    def get_players_together(
        self,
        collection_name: str,
        player1_id: str,
        player2_id: str,
        date_filter: Optional[Dict] = None,
        debug: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """Return stats when two players are simultaneously on court.

        Args:
            collection_name: MongoDB collection name.
            player1_id: First player identifier.
            player2_id: Second player identifier.
            date_filter: Optional date range filter.
            debug: If ``True``, saves per-game raw outputs.
            progress_callback: Optional progress callback.

        Returns:
            Dict with combined stats, or empty dict on failure.
        """
        return self._db.get_two_players_together_stats(
            collection_name, player1_id, player2_id, date_filter,
            debug=debug, progress_callback=progress_callback
        ) or {}

    def get_player_with_teammate(
        self,
        collection_name: str,
        main_player_id: str,
        teammate_id: str,
        date_filter: Optional[Dict] = None,
        debug: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """Return individual stats of ``main_player`` when playing with ``teammate``.

        Args:
            collection_name: MongoDB collection name.
            main_player_id: The player whose stats are returned.
            teammate_id: The teammate who must also be on court.
            date_filter: Optional date range filter.
            debug: Debug mode flag.
            progress_callback: Optional progress callback.

        Returns:
            Dict of individual stats, or empty dict on failure.
        """
        return self._db.get_player_individual_stats_with_teammate(
            collection_name, main_player_id, teammate_id, date_filter,
            debug=debug, progress_callback=progress_callback
        ) or {}
