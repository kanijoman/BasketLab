"""Per-game raw team pipeline (one document per team per match)."""

from typing import List, Dict
from .basic_stats import get_shooting_percentages, get_per_game_stats  # noqa: F401
from .advanced_stats import get_all_advanced_stats  # noqa: F401
from .pipeline_team_stats import TeamStatsPipelineMixin
from .possession_expr import game_minutes, real_possessions
from src.stats.formulas import mongo_expression


# The per-game fields of the consistency (and the weekly report) for each formula of the registry; the rival's carry ``opp_`` (and ``orb``/``drb`` where the own ones say ``oreb``/``dreb``)
PER_GAME_FIELDS = {"offensive_rating": "oer_game", "defensive_rating": "der_game", "net_rating": "net_game", "efg_percentage": "efg_pct_game", "true_shooting": "ts_pct_game",
                   "turnover_rate": "tov_pct_game", "three_point_rate": "three_point_rate_game", "free_throw_rate": "free_throw_rate_game", "assist_fg_rate": "assist_fg_rate_game",
                   "assist_rate": "assist_rate_game", "steal_rate": "steal_rate_game", "block_rate": "block_rate_game", "offensive_rebound_rate": "oreb_rate_game",
                   "defensive_rebound_rate": "dreb_rate_game"}
_RIVAL_NAMES = {"oreb_rate_game": "opp_orb_rate_game", "dreb_rate_game": "opp_drb_rate_game"}

# the counters of the registry in a per-game document: the team's own, and the same game seen from the rival (points, shots, rebounds and possessions swapped)
OWN_FIELDS = {"points": "$points", "points_against": "$opponent_points", "fg2m": "$fg2_made", "fg2a": "$fg2_attempts", "fg3m": "$fg3_made", "fg3a": "$fg3_attempts", "fta": "$ft_attempts",
              "ast": "$assists", "stl": "$steals", "blk": "$blocks", "tov": "$turnovers", "orb": "$off_rebounds", "drb": "$def_rebounds", "opp_orb": "$opp_off_rebounds",
              "opp_drb": "$opp_def_rebounds", "poss": "$real_poss", "opp_poss": "$opp_real_poss"}
RIVAL_FIELDS = {"points": "$opponent_points", "points_against": "$points", "fg2m": "$opp_fg2_made", "fg2a": "$opp_fg2_attempts", "fg3m": "$opp_fg3_made", "fg3a": "$opp_fg3_attempts",
                "fta": "$opp_ft_attempts", "ast": "$opp_assists", "stl": "$opp_steals", "blk": "$opp_blocks", "tov": "$opp_turnovers", "orb": "$opp_off_rebounds",
                "drb": "$opp_def_rebounds", "opp_orb": "$off_rebounds", "opp_drb": "$def_rebounds", "poss": "$opp_real_poss", "opp_poss": "$real_poss"}


def per_game_rates() -> dict:
    """Every rate of a game, the team's (``oer_game``...) and its rival's (``opp_oer_game``...), each with the formula of ``config/formulas.json`` over the REAL possessions of the game (#1153, #1154)."""
    out = {}
    for name, field in PER_GAME_FIELDS.items():
        out[field] = mongo_expression(name, OWN_FIELDS, empty=None)
        out[_RIVAL_NAMES.get(field, f"opp_{field}")] = mongo_expression(name, RIVAL_FIELDS, empty=None)
    return out


class TeamPerGamePipelineMixin:
    """Per-game raw team pipeline (one document per team per match)."""

    @staticmethod
    def build_season_rows_pipeline() -> List[Dict]:
        """One document per team per match with exactly what the season ``$group`` reads, plus the match date.

        The contract of the local-first data (#327): the client sums these rows (filtering by venue, result or date) and derives the ratios
        itself, so the figures of the team tables no longer need the server. Phases 1-3 of ``build_team_stats_pipeline`` with ``starttime``
        (``dd-mm-yyyy - hh:mm``, as FEB writes it) added.
        """
        project = TeamStatsPipelineMixin._project_match_data()
        project["$project"]["starttime"] = "$HEADER.starttime"
        project["$project"]["game_minutes"] = game_minutes()          # what ``possessions_per_40`` scaled by: the client undoes it for Evolución (#672)
        return [TeamStatsPipelineMixin._add_match_level_fields(), TeamStatsPipelineMixin._unwind_teams(), project]

    @staticmethod
    def build_per_game_raw_pipeline() -> List[Dict]:
        """Return one document per team per game with raw counting stats.

        Reuses phases 1-3 of ``build_team_stats_pipeline`` but stops before the
        ``$group`` stage so each document represents a single team's performance
        in a single match.  Used by the consistency service to calculate
        intra-team per-game standard deviations and CV.

        Safe-division of percentages is done here so MongoDB avoids divide-by-zero.

        Returns:
            List of aggregation pipeline stages.
        """
        pipeline = [
            TeamStatsPipelineMixin._add_match_level_fields(),
            TeamStatsPipelineMixin._unwind_teams(),
            TeamStatsPipelineMixin._project_match_data(),
            # the rates divide by the REAL possessions of the game; ``possessions`` is per 40 minutes and stays the pace (#1154). Its own stage: the next one reads them
            {"$addFields": {"real_poss": real_possessions("$possessions"), "opp_real_poss": real_possessions("$opponent_possessions")}},
            # Add per-game derived values needed for std-dev computation
            {
                "$addFields": {
                    "fg3_pct_game": {
                        "$cond": {
                            "if":  {"$gt": ["$fg3_attempts", 0]},
                            "then": {"$multiply": [{"$divide": ["$fg3_made", "$fg3_attempts"]}, 100]},
                            "else": None,
                        }
                    },
                    "fg2_pct_game": {
                        "$cond": {
                            "if":  {"$gt": ["$fg2_attempts", 0]},
                            "then": {"$multiply": [{"$divide": ["$fg2_made", "$fg2_attempts"]}, 100]},
                            "else": None,
                        }
                    },
                    "ft_pct_game": {
                        "$cond": {
                            "if":  {"$gt": ["$ft_attempts", 0]},
                            "then": {"$multiply": [{"$divide": ["$ft_made", "$ft_attempts"]}, 100]},
                            "else": None,
                        }
                    },
                    "total_rebounds": {"$add": ["$def_rebounds", "$off_rebounds"]},
                }
            },
            {
                "$project": {
                    "team_name": 1,
                    "points": 1,
                    "opponent_points": 1,
                    "fg3_made": 1, "fg3_attempts": 1, "fg3_pct_game": 1,
                    "fg2_made": 1, "fg2_attempts": 1, "fg2_pct_game": 1,
                    "ft_made": 1,  "ft_attempts": 1,  "ft_pct_game": 1,
                    "total_rebounds": 1,
                    "def_rebounds": 1, "off_rebounds": 1,
                    "assists": 1, "steals": 1, "turnovers": 1, "blocks": 1,
                    "possessions": 1, "opponent_possessions": 1, "real_poss": 1, "opp_real_poss": 1,
                    # Opponent (rival) raw fields for defensive consistency.
                    # These reference the fields added in _project_match_data() so
                    # they survive the earlier $project stage (team_0_*/team_1_* do not).
                    "opp_fg3_made":     "$opponent_fg3_made",
                    "opp_fg3_attempts": "$opponent_fg3_attempts",
                    "opp_fg2_made":     "$opponent_fg2_made",
                    "opp_fg2_attempts": "$opponent_fg2_attempts",
                    "opp_ft_made":      "$opponent_ft_made",
                    "opp_ft_attempts":  "$opponent_ft_attempts",
                    "opp_assists":      "$opponent_assists",
                    "opp_steals":       "$opponent_steals",
                    "opp_turnovers":    "$opponent_turnovers",
                    "opp_blocks":       "$opponent_blocks",
                    "opp_def_rebounds": "$opponent_def_rebounds",
                    "opp_off_rebounds": "$opponent_off_rebounds",
                }
            },
            # Compute opponent shooting percentages per game
            {
                "$addFields": {
                    "opp_fg3_pct_game": {
                        "$cond": {"if": {"$gt": ["$opp_fg3_attempts", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_fg3_made", "$opp_fg3_attempts"]}, 100]},
                                  "else": None}
                    },
                    "opp_fg2_pct_game": {
                        "$cond": {"if": {"$gt": ["$opp_fg2_attempts", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_fg2_made", "$opp_fg2_attempts"]}, 100]},
                                  "else": None}
                    },
                    "opp_ft_pct_game": {
                        "$cond": {"if": {"$gt": ["$opp_ft_attempts", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_ft_made", "$opp_ft_attempts"]}, 100]},
                                  "else": None}
                    },
                    "opp_total_rebounds": {"$add": ["$opp_def_rebounds", "$opp_off_rebounds"]},
                }
            },
            # Stage A — helper intermediate fields for advanced rival+own rate stats.
            # Must be a separate stage so Stage B can reference these new fields.
            {
                "$addFields": {
                    "opp_possessions": "$opponent_possessions",
                    "opp_fga_game": {"$add": ["$opp_fg2_attempts", "$opp_fg3_attempts"]},
                    "opp_fgm_game": {"$add": ["$opp_fg2_made",     "$opp_fg3_made"]},
                    # Own helpers: fga_game was dropped by the earlier $project
                    "fga_game":     {"$add": ["$fg2_attempts", "$fg3_attempts"]},
                    "fgm_game":     {"$add": ["$fg2_made",     "$fg3_made"]},
                }
            },
            # Stage B — every rate of the game, own and rival's, from the registry (config/formulas.json, #1153). An empty denominator is None (the consistency skips the game).
            {"$addFields": per_game_rates()},
        ]
        return pipeline
