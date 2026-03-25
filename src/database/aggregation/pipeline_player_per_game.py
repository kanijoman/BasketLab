"""Per-player per-game aggregation pipeline (FEB format only)."""

from typing import List, Dict


class PlayerPerGamePipelineMixin:
    """Mixin providing a pipeline that returns one document per player per game.

    Used by PlayerStatsService.get_consistency() to compute intra-player std dev
    and CV game-to-game.  Only valid for FEB collections.
    """

    @staticmethod
    def build_per_player_per_game_pipeline() -> List[Dict]:
        """Return one document per player per game with raw counting stats.

        Each document represents a single player's performance in a single game.
        Minutes are returned in **minutes** (divided by 60 from the raw FEB
        field which stores seconds).

        Returns:
            List of aggregation pipeline stages.
        """
        _fga_game = {"$add": ["$p2a", "$p3a"]}
        _fgm_game = {"$add": ["$p2m", "$p3m"]}
        _denom_ts  = {"$add": ["$p2a", "$p3a", {"$multiply": [0.44, "$p1a"]}]}

        return [
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$HEADER.starttime",
                            "format": "%d-%m-%Y - %H:%M",
                            "onError": None, "onNull": None,
                        }
                    },
                    "localPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
                    "awayPoints":  {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}},
                }
            },
            {"$unwind": {"path": "$BOXSCORE.TEAM", "includeArrayIndex": "teamIndex"}},
            {"$unwind": {"path": "$BOXSCORE.TEAM.PLAYER", "preserveNullAndEmptyArrays": False}},
            {
                "$project": {
                    "player_id":   "$BOXSCORE.TEAM.PLAYER.id",
                    "player_name": "$BOXSCORE.TEAM.PLAYER.name",
                    "team_name":   "$BOXSCORE.TEAM.TOTAL.name",
                    # minutes: raw FEB field is in seconds → divide by 60
                    "minutes": {
                        "$divide": [
                            {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.min", "0"]}},
                            60,
                        ]
                    },
                    "pllss": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.pllss", "0"]}},
                    "pts":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.pts",   "0"]}},
                    "assist":{"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.assist","0"]}},
                    "ro":    {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.ro",    "0"]}},
                    "rd":    {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.rd",    "0"]}},
                    "rt":    {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.rt",    "0"]}},
                    "st":    {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.st",    "0"]}},
                    "to":    {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.to",    "0"]}},
                    "bs":    {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.bs",    "0"]}},
                    "pf":    {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.pf",    "0"]}},
                    "val":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.val",   "0"]}},
                    "p1m":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p1m",   "0"]}},
                    "p1a":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p1a",   "0"]}},
                    "p2m":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p2m",   "0"]}},
                    "p2a":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p2a",   "0"]}},
                    "p3m":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p3m",   "0"]}},
                    "p3a":   {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p3a",   "0"]}},
                    # Team totals for this game — needed to compute per-game usage/share proxies
                    "tm_p2m": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.p2m", "0"]}},
                    "tm_p2a": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.p2a", "0"]}},
                    "tm_p3m": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.p3m", "0"]}},
                    "tm_p3a": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.p3a", "0"]}},
                    "tm_p1a": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.p1a", "0"]}},
                    "tm_to":  {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.to",  "0"]}},
                    "tm_ro":  {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.ro",  "0"]}},
                    "tm_rd":  {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.rd",  "0"]}},
                    "tm_st":  {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.st",  "0"]}},
                    "tm_bs":  {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.TOTAL.bs",  "0"]}},
                }
            },
            {"$match": {"minutes": {"$gt": 0}}},
            {
                "$addFields": {
                    # Rename pllss → pllss_game to match FIELD_MAP key in service
                    "pllss_game": "$pllss",
                    # Shooting percentages
                    "fg1_pct_game": {
                        "$cond": {
                            "if": {"$gt": ["$p1a", 0]},
                            "then": {"$multiply": [{"$divide": ["$p1m", "$p1a"]}, 100]},
                            "else": None,
                        }
                    },
                    "fg2_pct_game": {
                        "$cond": {
                            "if": {"$gt": ["$p2a", 0]},
                            "then": {"$multiply": [{"$divide": ["$p2m", "$p2a"]}, 100]},
                            "else": None,
                        }
                    },
                    "fg3_pct_game": {
                        "$cond": {
                            "if": {"$gt": ["$p3a", 0]},
                            "then": {"$multiply": [{"$divide": ["$p3m", "$p3a"]}, 100]},
                            "else": None,
                        }
                    },
                    # Advanced shooting
                    "efg_pct_game": {
                        "$cond": {
                            "if": {"$gt": [_fga_game, 0]},
                            "then": {
                                "$multiply": [
                                    {"$divide": [{"$add": ["$p2m", {"$multiply": [1.5, "$p3m"]}]}, _fga_game]},
                                    100,
                                ]
                            },
                            "else": None,
                        }
                    },
                    "ts_pct_game": {
                        "$cond": {
                            "if": {"$gt": [_denom_ts, 0]},
                            "then": {
                                "$multiply": [
                                    {"$divide": ["$pts", {"$multiply": [2.0, _denom_ts]}]},
                                    100,
                                ]
                            },
                            "else": None,
                        }
                    },
                    "ftr_game": {
                        "$cond": {
                            "if": {"$gt": [_fga_game, 0]},
                            "then": {"$multiply": [{"$divide": ["$p1a", _fga_game]}, 100]},
                            "else": None,
                        }
                    },
                    "three_pr_game": {
                        "$cond": {
                            "if": {"$gt": [_fga_game, 0]},
                            "then": {"$multiply": [{"$divide": ["$p3a", _fga_game]}, 100]},
                            "else": None,
                        }
                    },
                    "tov_pct_game": {
                        "$cond": {
                            "if": {
                                "$gt": [
                                    {"$add": [_fga_game, {"$multiply": [0.44, "$p1a"]}, "$to"]},
                                    0,
                                ]
                            },
                            "then": {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            "$to",
                                            {"$add": [_fga_game, {"$multiply": [0.44, "$p1a"]}, "$to"]},
                                        ]
                                    },
                                    100,
                                ]
                            },
                            "else": None,
                        }
                    },
                    # ── Per-game team-share proxies for advanced stats ────────────────────
                    # Usage: player's share of team possessions (FGA+0.44FTA+TO denominator)
                    "usg_pct_game": {
                        "$cond": {
                            "if": {"$gt": [{"$add": ["$tm_p2a", "$tm_p3a", {"$multiply": [0.44, "$tm_p1a"]}, "$tm_to"]}, 0]},
                            "then": {
                                "$multiply": [
                                    {"$divide": [
                                        {"$add": [_fga_game, {"$multiply": [0.44, "$p1a"]}, "$to"]},
                                        {"$add": ["$tm_p2a", "$tm_p3a", {"$multiply": [0.44, "$tm_p1a"]}, "$tm_to"]},
                                    ]},
                                    100,
                                ]
                            },
                            "else": None,
                        }
                    },
                    # AST%: player assists / (team FGM − player FGM)
                    "ast_pct_game": {
                        "$cond": {
                            "if": {"$gt": [{"$subtract": [{"$add": ["$tm_p2m", "$tm_p3m"]}, {"$add": ["$p2m", "$p3m"]}]}, 0]},
                            "then": {
                                "$multiply": [
                                    {"$divide": [
                                        "$assist",
                                        {"$subtract": [{"$add": ["$tm_p2m", "$tm_p3m"]}, {"$add": ["$p2m", "$p3m"]}]},
                                    ]},
                                    100,
                                ]
                            },
                            "else": None,
                        }
                    },
                    # ORB%/DRB%/STL%/BLK%: player's share of team total for that game
                    "orb_pct_game": {
                        "$cond": {
                            "if": {"$gt": ["$tm_ro", 0]},
                            "then": {"$multiply": [{"$divide": ["$ro", "$tm_ro"]}, 100]},
                            "else": None,
                        }
                    },
                    "drb_pct_game": {
                        "$cond": {
                            "if": {"$gt": ["$tm_rd", 0]},
                            "then": {"$multiply": [{"$divide": ["$rd", "$tm_rd"]}, 100]},
                            "else": None,
                        }
                    },
                    "stl_pct_game": {
                        "$cond": {
                            "if": {"$gt": ["$tm_st", 0]},
                            "then": {"$multiply": [{"$divide": ["$st", "$tm_st"]}, 100]},
                            "else": None,
                        }
                    },
                    "blk_pct_game": {
                        "$cond": {
                            "if": {"$gt": ["$tm_bs", 0]},
                            "then": {"$multiply": [{"$divide": ["$bs", "$tm_bs"]}, 100]},
                            "else": None,
                        }
                    },
                }
            },
        ]
