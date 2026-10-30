"""Per-game raw team pipeline (one document per team per match)."""

from typing import List, Dict, Optional
from .basic_stats import get_shooting_percentages, get_per_game_stats  # noqa: F401
from .advanced_stats import get_all_advanced_stats  # noqa: F401
from .pipeline_team_stats import TeamStatsPipelineMixin
from .possession_expr import game_minutes


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
                    # Advanced per-game: OER / DER / Net Rating
                    "oer_game": {
                        "$cond": {
                            "if":  {"$gt": ["$possessions", 0]},
                            "then": {"$multiply": [{"$divide": ["$points", "$possessions"]}, 100]},
                            "else": None,
                        }
                    },
                    "der_game": {
                        "$cond": {
                            "if":  {"$gt": ["$possessions", 0]},
                            "then": {"$multiply": [{"$divide": ["$opponent_points", "$possessions"]}, 100]},
                            "else": None,
                        }
                    },
                }
            },
            # Second addFields pass — net_game, efg and ts depend on previous stage values
            {
                "$addFields": {
                    "net_game": {
                        "$cond": {
                            "if":  {"$and": [{"$ne": ["$oer_game", None]}, {"$ne": ["$der_game", None]}]},
                            "then": {"$subtract": ["$oer_game", "$der_game"]},
                            "else": None,
                        }
                    },
                    "fga_game": {"$add": ["$fg2_attempts", "$fg3_attempts"]},
                }
            },
            {
                "$addFields": {
                    # eFG% = (FGM + 0.5*3PM) / FGA * 100
                    "efg_pct_game": {
                        "$cond": {
                            "if":  {"$gt": ["$fga_game", 0]},
                            "then": {
                                "$multiply": [
                                    {"$divide": [
                                        {"$add": ["$fg2_made", {"$multiply": ["$fg3_made", 1.5]}]},
                                        "$fga_game"
                                    ]},
                                    100
                                ]
                            },
                            "else": None,
                        }
                    },
                    # TS% = PTS / (2 * (FGA + 0.44*FTA)) * 100
                    "ts_pct_game": {
                        "$cond": {
                            "if":  {"$gt": [{"$add": ["$fga_game", {"$multiply": ["$ft_attempts", 0.44]}]}, 0]},
                            "then": {
                                "$multiply": [
                                    {"$divide": [
                                        "$points",
                                        {"$multiply": [
                                            2,
                                            {"$add": ["$fga_game", {"$multiply": ["$ft_attempts", 0.44]}]}
                                        ]}
                                    ]},
                                    100
                                ]
                            },
                            "else": None,
                        }
                    },
                    # TOV% = TOV / (FGA + 0.44*FTA + TOV) * 100
                    "tov_pct_game": {
                        "$cond": {
                            "if":  {"$gt": [{"$add": ["$fga_game", {"$multiply": ["$ft_attempts", 0.44]}, "$turnovers"]}, 0]},
                            "then": {
                                "$multiply": [
                                    {"$divide": [
                                        "$turnovers",
                                        {"$add": ["$fga_game", {"$multiply": ["$ft_attempts", 0.44]}, "$turnovers"]}
                                    ]},
                                    100
                                ]
                            },
                            "else": None,
                        }
                    },
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
                    "possessions": 1, "opponent_possessions": 1,
                    # Advanced computed fields
                    "oer_game": 1, "der_game": 1, "net_game": 1,
                    "efg_pct_game": 1, "ts_pct_game": 1, "tov_pct_game": 1,
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
            # Stage B — advanced per-game derived fields for rival and own rate stats.
            {
                "$addFields": {
                    # --- Opponent (rival) advanced per-game ---
                    "opp_oer_game": {
                        "$cond": {"if": {"$gt": ["$opp_possessions", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opponent_points", "$opp_possessions"]}, 100]},
                                  "else": None}
                    },
                    "opp_der_game": {
                        "$cond": {"if": {"$gt": ["$opp_possessions", 0]},
                                  "then": {"$multiply": [{"$divide": ["$points", "$opp_possessions"]}, 100]},
                                  "else": None}
                    },
                    "opp_net_game": {
                        "$cond": {"if": {"$gt": ["$opp_possessions", 0]},
                                  "then": {"$multiply": [{"$divide": [{"$subtract": ["$opponent_points", "$points"]}, "$opp_possessions"]}, 100]},
                                  "else": None}
                    },
                    "opp_efg_pct_game": {
                        "$cond": {"if": {"$gt": ["$opp_fga_game", 0]},
                                  "then": {"$multiply": [{"$divide": [{"$add": ["$opp_fg2_made", {"$multiply": [1.5, "$opp_fg3_made"]}]}, "$opp_fga_game"]}, 100]},
                                  "else": None}
                    },
                    "opp_ts_pct_game": {
                        "$cond": {
                            "if": {"$gt": [{"$add": ["$opp_fga_game", {"$multiply": [0.44, "$opp_ft_attempts"]}]}, 0]},
                            "then": {"$multiply": [{"$divide": ["$opponent_points", {"$multiply": [2, {"$add": ["$opp_fga_game", {"$multiply": [0.44, "$opp_ft_attempts"]}]}]}]}, 100]},
                            "else": None
                        }
                    },
                    "opp_tov_pct_game": {
                        "$cond": {
                            "if": {"$gt": [{"$add": ["$opp_fga_game", {"$multiply": [0.44, "$opp_ft_attempts"]}, "$opp_turnovers"]}, 0]},
                            "then": {"$multiply": [{"$divide": ["$opp_turnovers", {"$add": ["$opp_fga_game", {"$multiply": [0.44, "$opp_ft_attempts"]}, "$opp_turnovers"]}]}, 100]},
                            "else": None
                        }
                    },
                    "opp_three_point_rate_game": {
                        "$cond": {"if": {"$gt": ["$opp_fga_game", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_fg3_attempts", "$opp_fga_game"]}, 100]},
                                  "else": None}
                    },
                    "opp_free_throw_rate_game": {
                        "$cond": {"if": {"$gt": ["$opp_fga_game", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_ft_attempts", "$opp_fga_game"]}, 100]},
                                  "else": None}
                    },
                    "opp_assist_fg_rate_game": {
                        "$cond": {"if": {"$gt": ["$opp_fgm_game", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_assists", "$opp_fgm_game"]}, 100]},
                                  "else": None}
                    },
                    "opp_assist_rate_game": {
                        "$cond": {"if": {"$gt": ["$opp_possessions", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_assists", "$opp_possessions"]}, 100]},
                                  "else": None}
                    },
                    # steal_rate = rival steals / own possessions
                    "opp_steal_rate_game": {
                        "$cond": {"if": {"$gt": ["$possessions", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_steals", "$possessions"]}, 100]},
                                  "else": None}
                    },
                    # block_rate = rival blocks / own fg2_attempts
                    "opp_block_rate_game": {
                        "$cond": {"if": {"$gt": ["$fg2_attempts", 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_blocks", "$fg2_attempts"]}, 100]},
                                  "else": None}
                    },
                    "opp_orb_rate_game": {
                        "$cond": {"if": {"$gt": [{"$add": ["$opp_off_rebounds", "$def_rebounds"]}, 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_off_rebounds", {"$add": ["$opp_off_rebounds", "$def_rebounds"]}]}, 100]},
                                  "else": None}
                    },
                    "opp_drb_rate_game": {
                        "$cond": {"if": {"$gt": [{"$add": ["$opp_def_rebounds", "$off_rebounds"]}, 0]},
                                  "then": {"$multiply": [{"$divide": ["$opp_def_rebounds", {"$add": ["$opp_def_rebounds", "$off_rebounds"]}]}, 100]},
                                  "else": None}
                    },
                    # --- Own rate stats (new) — require opp_possessions from Stage A ---
                    "three_point_rate_game": {
                        "$cond": {"if": {"$gt": ["$fga_game", 0]},
                                  "then": {"$multiply": [{"$divide": ["$fg3_attempts", "$fga_game"]}, 100]},
                                  "else": None}
                    },
                    "free_throw_rate_game": {
                        "$cond": {"if": {"$gt": ["$fga_game", 0]},
                                  "then": {"$multiply": [{"$divide": ["$ft_attempts", "$fga_game"]}, 100]},
                                  "else": None}
                    },
                    "assist_fg_rate_game": {
                        "$cond": {"if": {"$gt": ["$fgm_game", 0]},
                                  "then": {"$multiply": [{"$divide": ["$assists", "$fgm_game"]}, 100]},
                                  "else": None}
                    },
                    "assist_rate_game": {
                        "$cond": {"if": {"$gt": ["$possessions", 0]},
                                  "then": {"$multiply": [{"$divide": ["$assists", "$possessions"]}, 100]},
                                  "else": None}
                    },
                    "steal_rate_game": {
                        "$cond": {"if": {"$gt": ["$opp_possessions", 0]},
                                  "then": {"$multiply": [{"$divide": ["$steals", "$opp_possessions"]}, 100]},
                                  "else": None}
                    },
                    "block_rate_game": {
                        "$cond": {"if": {"$gt": ["$opp_fg2_attempts", 0]},
                                  "then": {"$multiply": [{"$divide": ["$blocks", "$opp_fg2_attempts"]}, 100]},
                                  "else": None}
                    },
                    "oreb_rate_game": {
                        "$cond": {"if": {"$gt": [{"$add": ["$off_rebounds", "$opp_def_rebounds"]}, 0]},
                                  "then": {"$multiply": [{"$divide": ["$off_rebounds", {"$add": ["$off_rebounds", "$opp_def_rebounds"]}]}, 100]},
                                  "else": None}
                    },
                    "dreb_rate_game": {
                        "$cond": {"if": {"$gt": [{"$add": ["$def_rebounds", "$opp_off_rebounds"]}, 0]},
                                  "then": {"$multiply": [{"$divide": ["$def_rebounds", {"$add": ["$def_rebounds", "$opp_off_rebounds"]}]}, 100]},
                                  "else": None}
                    },
                }
            },
        ]
        return pipeline
