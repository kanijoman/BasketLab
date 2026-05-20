"""Team evolution service — game-by-game temporal statistics analysis.

Extracted from ``team_stats_service`` to keep file size under 500 lines.
Provides per-team and competition-wide rolling/cumulative averages for any
supported stat key across all games in a collection, ordered chronologically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Any

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.database.aggregation.pipeline_team_stats import TeamStatsPipelineMixin
from utils.collection_utils import is_fbcyl as _is_fbcyl

# ---------------------------------------------------------------------------
# All stat keys supported by the evolution endpoints
# ---------------------------------------------------------------------------
EVOLUTION_STAT_KEYS: frozenset = frozenset({
    # Basic — counting
    "points", "points_allowed",
    "fg2_made", "fg2_attempts", "fg3_made", "fg3_attempts",
    "ft_made", "ft_attempts",
    "rebounds", "def_rebounds", "off_rebounds",
    "assists", "steals", "turnovers", "blocks",
    # Basic — percentages
    "fg2_percentage", "fg3_percentage", "ft_percentage",
    # Advanced
    "possessions", "offensive_rating", "defensive_rating", "net_rating",
    "efg_percentage", "true_shooting",
    "three_point_rate", "free_throw_rate",
    "assist_fg_rate", "assist_rate", "turnover_rate",
    "steal_rate", "block_rate",
    "off_rebound_rate", "def_rebound_rate",
})


class EvolutionService:
    """Service for game-by-game stat evolution.

    Exposes:
    - ``get_team_evolution`` — rolling + cumulative per-team series.
    - ``get_competition_evolution`` — competition-wide rolling + cumulative
      averages aligned by game index (P1, P2, …).
    """

    def __init__(self, db_handler: "MongoDBHandler") -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_team_evolution(
        self,
        collection_name: str,
        team_id: str,
        stat: str = "points",
        rolling_window: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return chronological game-by-game values with rolling and cumulative averages.

        Args:
            collection_name: MongoDB collection name.
            team_id: Stable team ID (``HEADER.TEAM.id`` for FEB,
                ``stats.teams.teamIdExtern`` for FBCYL).
            stat: One of the keys in ``EVOLUTION_STAT_KEYS``.
            rolling_window: Window size in games for the rolling average.

        Returns:
            List of dicts with ``game_number``, ``game_date``, ``opponent``,
            ``value``, ``rolling_avg``, ``cumulative_avg``, ``won``.
        """
        is_fbcyl = _is_fbcyl(collection_name)
        try:
            coll = self._db.connection.get_collection(collection_name)
            rows = self._evolution_fbcyl(coll, team_id) if is_fbcyl else self._evolution_feb(coll, team_id)
        except Exception:
            return []

        result: List[Dict[str, Any]] = []
        running_sum = 0.0
        count = 0

        for i, row in enumerate(rows):
            value = self._compute_stat(row, stat)
            # Rolling average over last N games
            window = rows[max(0, i - rolling_window + 1): i + 1]
            window_vals = [v for r in window if (v := self._compute_stat(r, stat)) is not None]
            rolling = round(sum(window_vals) / len(window_vals), 2) if window_vals else None
            # Cumulative season average
            if value is not None:
                running_sum += value
                count += 1
            cumulative = round(running_sum / count, 2) if count else None

            result.append({
                "game_number":    i + 1,
                "game_date":      row.get("game_date", ""),
                "opponent":       row.get("opponent", ""),
                "value":          round(value, 2) if value is not None else None,
                "rolling_avg":    rolling,
                "cumulative_avg": cumulative,
                "won":            bool(row.get("won", False)),
            })
        return result

    def get_competition_evolution(
        self,
        collection_name: str,
        stat: str = "points",
        rolling_window: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return competition-wide rolling and cumulative averages by game index.

        For each game position P_i, computes:
        - ``competition_rolling`` — average of each team's rolling avg at game i.
        - ``competition_cumulative`` — average of each team's cumulative avg at game i.

        Teams with fewer games than i simply don't contribute at position i.
        Alignment is by game index (P1, P2, …), matching the frontend x-axis.

        Args:
            collection_name: MongoDB collection name.
            stat: Stat key from ``EVOLUTION_STAT_KEYS``.
            rolling_window: Window size for the competition rolling average.

        Returns:
            List of dicts with ``game_number``, ``competition_rolling``,
            ``competition_cumulative``.
        """
        is_fbcyl = _is_fbcyl(collection_name)
        try:
            all_teams = self._db.get_teams_with_ids(collection_name) or []
            if not all_teams:
                return []
            coll = self._db.connection.get_collection(collection_name)
            if is_fbcyl:
                team_rows = [self._evolution_fbcyl(coll, t["id"]) for t in all_teams]
            else:
                team_rows = [self._evolution_feb(coll, t["id"]) for t in all_teams]
        except Exception:
            return []

        # Pre-compute per-game stat values for every team
        team_values: List[List[Optional[float]]] = [
            [self._compute_stat(r, stat) for r in rows]
            for rows in team_rows
        ]

        max_games = max((len(v) for v in team_values), default=0)
        if max_games == 0:
            return []

        result: List[Dict[str, Any]] = []
        # Track running sums per team for cumulative averages
        team_running_sums = [0.0] * len(team_values)
        team_counts = [0] * len(team_values)

        for i in range(max_games):
            # Update each team's running sum with their game-i value
            for t_idx, vals in enumerate(team_values):
                if i < len(vals) and vals[i] is not None:
                    team_running_sums[t_idx] += vals[i]
                    team_counts[t_idx] += 1

            # Competition rolling: average of each team's rolling avg at game i
            rolling_vals: List[float] = []
            for t_idx, vals in enumerate(team_values):
                if i >= len(vals):
                    continue
                window = vals[max(0, i - rolling_window + 1): i + 1]
                w_vals = [v for v in window if v is not None]
                if w_vals:
                    rolling_vals.append(sum(w_vals) / len(w_vals))

            # Competition cumulative: average of team cumulative means at game i
            cum_vals = [
                team_running_sums[t_idx] / team_counts[t_idx]
                for t_idx in range(len(team_values))
                if team_counts[t_idx] > 0 and i < len(team_values[t_idx])
            ]

            result.append({
                "game_number":            i + 1,
                "competition_rolling":    round(sum(rolling_vals) / len(rolling_vals), 2) if rolling_vals else None,
                "competition_cumulative": round(sum(cum_vals) / len(cum_vals), 2) if cum_vals else None,
            })
        return result

    # ------------------------------------------------------------------
    # FEB pipeline — all raw counting fields projected per game
    # ------------------------------------------------------------------

    def _evolution_feb(self, coll, team_id: str) -> List[Dict]:
        """Return per-game raw stat rows for a FEB team.

        Each row contains all counting fields needed to compute any supported
        stat in Python via ``_compute_stat``.
        """
        mixin = TeamStatsPipelineMixin
        opp = mixin._opponent_conditional_field  # teamIndex=0 → pick team_1_field

        pipeline = [
            # Parse match date from string
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$HEADER.starttime",
                            "format": "%d-%m-%Y - %H:%M",
                            "onError": None,
                            "onNull": None,
                        }
                    }
                }
            },
            # Early filter: only games involving this team (indexed)
            {"$match": {"HEADER.TEAM.id": team_id}},
            # Pre-capture all team_0_* / team_1_* counting stats + localPoints/awayPoints
            mixin._add_match_level_fields(),
            # Capture opponent team name for display
            {
                "$addFields": {
                    "localTeamName": {"$arrayElemAt": ["$HEADER.TEAM.name", 0]},
                    "awayTeamName":  {"$arrayElemAt": ["$HEADER.TEAM.name", 1]},
                }
            },
            mixin._unwind_teams(),
            {"$match": {"BOXSCORE.TEAM.TOTAL.id": team_id}},
            {
                "$project": {
                    "game_date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$parsedDate",
                            "onNull": "unknown",
                        }
                    },
                    "won": {
                        "$cond": [
                            {"$eq": ["$teamIndex", 0]},
                            {"$gt": ["$localPoints", "$awayPoints"]},
                            {"$gt": ["$awayPoints", "$localPoints"]},
                        ]
                    },
                    "opponent": {
                        "$cond": [
                            {"$eq": ["$teamIndex", 0]},
                            "$awayTeamName",
                            "$localTeamName",
                        ]
                    },
                    # Own counting stats
                    "pts":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"},
                    "fg2m": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2m"},
                    "fg2a": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2a"},
                    "fg3m": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3m"},
                    "fg3a": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3a"},
                    "ftm":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1m"},
                    "fta":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1a"},
                    "drb":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.rd"},
                    "orb":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"},
                    "ast":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.assist"},
                    "stl":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.st"},
                    "tov":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.to"},
                    "blk":  {"$toInt": "$BOXSCORE.TEAM.TOTAL.bs"},
                    # Opponent points (from pre-captured localPoints/awayPoints)
                    "opp_pts": {
                        "$cond": [
                            {"$eq": ["$teamIndex", 0]},
                            "$awayPoints",
                            "$localPoints",
                        ]
                    },
                    # Opponent counting stats (from pre-captured team_0_* / team_1_*)
                    "opp_fg2m": opp("team_0_fg2_made",  "team_1_fg2_made"),
                    "opp_fg2a": opp("team_0_fg2_att",   "team_1_fg2_att"),
                    "opp_fg3m": opp("team_0_fg3_made",  "team_1_fg3_made"),
                    "opp_fg3a": opp("team_0_fg3_att",   "team_1_fg3_att"),
                    "opp_ftm":  opp("team_0_ft_made",   "team_1_ft_made"),
                    "opp_fta":  opp("team_0_ft_att",    "team_1_ft_att"),
                    "opp_drb":  opp("team_0_def_reb",   "team_1_def_reb"),
                    "opp_orb":  opp("team_0_off_reb",   "team_1_off_reb"),
                    "opp_ast":  opp("team_0_assists",   "team_1_assists"),
                    "opp_stl":  opp("team_0_steals",    "team_1_steals"),
                    "opp_tov":  opp("team_0_turnovers", "team_1_turnovers"),
                    "opp_blk":  opp("team_0_blocks",    "team_1_blocks"),
                },
            },
            {"$sort": {"game_date": 1}},
        ]
        docs = list(coll.aggregate(pipeline))
        return [self._feb_doc_to_row(d) for d in docs]

    @staticmethod
    def _feb_doc_to_row(d: Dict) -> Dict:
        """Convert a FEB aggregation output doc to a normalised raw row."""
        si = EvolutionService._safe_int
        return {
            "game_date": d.get("game_date", ""),
            "opponent":  d.get("opponent", ""),
            "won":       bool(d.get("won", False)),
            "pts":   si(d.get("pts")),   "fg2m": si(d.get("fg2m")), "fg2a": si(d.get("fg2a")),
            "fg3m":  si(d.get("fg3m")),  "fg3a": si(d.get("fg3a")),
            "ftm":   si(d.get("ftm")),   "fta":  si(d.get("fta")),
            "drb":   si(d.get("drb")),   "orb":  si(d.get("orb")),
            "ast":   si(d.get("ast")),   "stl":  si(d.get("stl")),
            "tov":   si(d.get("tov")),   "blk":  si(d.get("blk")),
            "opp_pts":  si(d.get("opp_pts")),
            "opp_fg2m": si(d.get("opp_fg2m")), "opp_fg2a": si(d.get("opp_fg2a")),
            "opp_fg3m": si(d.get("opp_fg3m")), "opp_fg3a": si(d.get("opp_fg3a")),
            "opp_ftm":  si(d.get("opp_ftm")),  "opp_fta":  si(d.get("opp_fta")),
            "opp_drb":  si(d.get("opp_drb")),  "opp_orb":  si(d.get("opp_orb")),
            "opp_ast":  si(d.get("opp_ast")),  "opp_stl":  si(d.get("opp_stl")),
            "opp_tov":  si(d.get("opp_tov")),  "opp_blk":  si(d.get("opp_blk")),
        }

    # ------------------------------------------------------------------
    # FBCYL pipeline — raw fields from stats.teams.data.*
    # ------------------------------------------------------------------

    def _evolution_fbcyl(self, coll, team_id: str) -> List[Dict]:
        """Return per-game raw stat rows for a FBCYL team."""
        tid = int(team_id) if isinstance(team_id, str) and team_id.isdigit() else team_id
        pipeline = [
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$stats.startDate",
                            "format": "%Y-%m-%dT%H:%M:%S.%LZ",
                            "onError": None,
                            "onNull": None,
                        }
                    },
                    # Pre-capture both team entries before unwind
                    "t0_entry": {"$arrayElemAt": ["$stats.teams", 0]},
                    "t1_entry": {"$arrayElemAt": ["$stats.teams", 1]},
                }
            },
            {"$match": {"stats.teams.teamIdExtern": tid}},
            {"$unwind": {"path": "$stats.teams", "includeArrayIndex": "teamIndex"}},
            {"$match": {"stats.teams.teamIdExtern": tid}},
            {
                "$project": {
                    "game_date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$parsedDate",
                            "onNull": "unknown",
                        }
                    },
                    "won":     {"$ifNull": ["$stats.teams.isWinner", False]},
                    "opponent": {
                        "$cond": [
                            {"$eq": ["$teamIndex", 0]},
                            {"$ifNull": ["$t1_entry.name", {"$ifNull": ["$t1_entry.teamName", "?"]}]},
                            {"$ifNull": ["$t0_entry.name", {"$ifNull": ["$t0_entry.teamName", "?"]}]},
                        ]
                    },
                    # Own stats — data.* format (primary), direct field fallback
                    "pts":  {"$ifNull": ["$stats.teams.data.score", "$stats.teams.PTS"]},
                    "fg2m": {"$ifNull": ["$stats.teams.data.shotsOfTwoSuccessful", None]},
                    "fg2a": {"$ifNull": ["$stats.teams.data.shotsOfTwoAttempted", None]},
                    "fg3m": {"$ifNull": ["$stats.teams.data.shotsOfThreeSuccessful", None]},
                    "fg3a": {"$ifNull": ["$stats.teams.data.shotsOfThreeAttempted", None]},
                    "ftm":  {"$ifNull": ["$stats.teams.data.shotsOfOneSuccessful", None]},
                    "fta":  {"$ifNull": ["$stats.teams.data.shotsOfOneAttempted", None]},
                    "orb":  {"$ifNull": ["$stats.teams.data.offensiveRebound", None]},
                    "drb":  {"$ifNull": ["$stats.teams.data.defensiveRebound", None]},
                    "ast":  {"$ifNull": ["$stats.teams.data.assists", "$stats.teams.AST"]},
                    "stl":  {"$ifNull": ["$stats.teams.data.steals", "$stats.teams.ST"]},
                    "tov":  {"$ifNull": ["$stats.teams.data.lost", "$stats.teams.TO"]},
                    "blk":  {"$ifNull": ["$stats.teams.data.block", "$stats.teams.BS"]},
                    # Opponent stats from pre-captured entries
                    "opp_pts": {
                        "$cond": [
                            {"$eq": ["$teamIndex", 0]},
                            {"$ifNull": ["$t1_entry.data.score", None]},
                            {"$ifNull": ["$t0_entry.data.score", None]},
                        ]
                    },
                    "opp_fg2m": {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.shotsOfTwoSuccessful",    "$t0_entry.data.shotsOfTwoSuccessful"]},
                    "opp_fg2a": {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.shotsOfTwoAttempted",     "$t0_entry.data.shotsOfTwoAttempted"]},
                    "opp_fg3m": {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.shotsOfThreeSuccessful",  "$t0_entry.data.shotsOfThreeSuccessful"]},
                    "opp_fg3a": {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.shotsOfThreeAttempted",   "$t0_entry.data.shotsOfThreeAttempted"]},
                    "opp_ftm":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.shotsOfOneSuccessful",    "$t0_entry.data.shotsOfOneSuccessful"]},
                    "opp_fta":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.shotsOfOneAttempted",     "$t0_entry.data.shotsOfOneAttempted"]},
                    "opp_orb":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.offensiveRebound",        "$t0_entry.data.offensiveRebound"]},
                    "opp_drb":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.defensiveRebound",        "$t0_entry.data.defensiveRebound"]},
                    "opp_ast":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.assists",                 "$t0_entry.data.assists"]},
                    "opp_stl":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.steals",                  "$t0_entry.data.steals"]},
                    "opp_tov":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.lost",                    "$t0_entry.data.lost"]},
                    "opp_blk":  {"$cond": [{"$eq": ["$teamIndex", 0]}, "$t1_entry.data.block",                   "$t0_entry.data.block"]},
                }
            },
            {"$sort": {"game_date": 1}},
        ]
        docs = list(coll.aggregate(pipeline))
        return [self._feb_doc_to_row(d) for d in docs]  # Same normalisation

    # ------------------------------------------------------------------
    # Stat computation from a raw row
    # ------------------------------------------------------------------

    def _compute_stat(self, row: Dict, stat: str) -> Optional[float]:
        """Compute a stat value from a raw row's counting fields.

        All inputs fall back to 0 so division-by-zero is handled. Returns None
        for ratio stats when the denominator is zero (e.g. no field-goal attempts).
        """
        si = self._safe_int
        pts  = si(row.get("pts"));    fg2m = si(row.get("fg2m")); fg2a = si(row.get("fg2a"))
        fg3m = si(row.get("fg3m"));   fg3a = si(row.get("fg3a"))
        ftm  = si(row.get("ftm"));    fta  = si(row.get("fta"))
        drb  = si(row.get("drb"));    orb  = si(row.get("orb"))
        ast  = si(row.get("ast"));    stl  = si(row.get("stl"))
        tov  = si(row.get("tov"));    blk  = si(row.get("blk"))
        opp_pts  = si(row.get("opp_pts"))
        opp_fg2a = si(row.get("opp_fg2a")); opp_fg3a = si(row.get("opp_fg3a"))
        opp_fta  = si(row.get("opp_fta"))
        opp_drb  = si(row.get("opp_drb"));  opp_orb  = si(row.get("opp_orb"))
        opp_tov  = si(row.get("opp_tov"))

        fga = fg2a + fg3a
        fgm = fg2m + fg3m
        opp_fga = opp_fg2a + opp_fg3a
        poss     = max(fga     + 0.44 * fta     + tov     - orb,     1.0)
        opp_poss = max(opp_fga + 0.44 * opp_fta + opp_tov - opp_orb, 1.0)

        lookup: Dict[str, Any] = {
            # Basic — counting
            "points":            float(pts),
            "points_allowed":    float(opp_pts),
            "fg2_made":          float(fg2m),
            "fg2_attempts":      float(fg2a),
            "fg3_made":          float(fg3m),
            "fg3_attempts":      float(fg3a),
            "ft_made":           float(ftm),
            "ft_attempts":       float(fta),
            "rebounds":          float(orb + drb),
            "def_rebounds":      float(drb),
            "off_rebounds":      float(orb),
            "assists":           float(ast),
            "steals":            float(stl),
            "turnovers":         float(tov),
            "blocks":            float(blk),
            # Basic — percentages
            "fg2_percentage":    (fg2m / fg2a * 100) if fg2a > 0 else None,
            "fg3_percentage":    (fg3m / fg3a * 100) if fg3a > 0 else None,
            "ft_percentage":     (ftm  / fta  * 100) if fta  > 0 else None,
            # Advanced
            "possessions":       float(poss),
            "offensive_rating":  pts     / poss     * 100,
            "defensive_rating":  opp_pts / opp_poss * 100,
            "net_rating":        (pts / poss * 100) - (opp_pts / opp_poss * 100),
            "efg_percentage":    ((fgm + 0.5 * fg3m) / fga * 100)       if fga > 0 else None,
            "true_shooting":     (pts / (2 * (fga + 0.44 * fta)) * 100) if (fga + 0.44 * fta) > 0 else None,
            "three_point_rate":  (fg3a / fga * 100)  if fga  > 0 else None,
            "free_throw_rate":   (fta  / fga * 100)  if fga  > 0 else None,
            "assist_fg_rate":    (ast  / fgm * 100)  if fgm  > 0 else None,
            "assist_rate":       ast  / poss * 100,
            "turnover_rate":     tov  / poss * 100,
            "steal_rate":        stl  / opp_poss * 100,
            "block_rate":        blk  / opp_poss * 100,
            "off_rebound_rate":  (orb / (orb + opp_drb) * 100) if (orb + opp_drb) > 0 else None,
            "def_rebound_rate":  (drb / (drb + opp_orb) * 100) if (drb + opp_orb) > 0 else None,
        }
        val = lookup.get(stat)
        return self._safe_num(val)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_int(val) -> int:
        """Convert raw DB value to int, defaulting to 0."""
        try:
            return int(val) if val is not None else 0
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_num(val) -> Optional[float]:
        """Convert value to float, returning None on failure."""
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
