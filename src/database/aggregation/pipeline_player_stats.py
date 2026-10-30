"""Player statistics aggregation pipeline builders."""

from typing import List, Dict, Optional

from .fbcyl_date_expr import parse_day_stages


def player_game_fields() -> Dict:
    """The ``$project`` of a player in a game (id, team, date, minutes in seconds and the box-score counting stats, all as integers).

    Shared by the season pipeline and by the rows of the local-first contract (``build_season_player_rows_pipeline``, issue #327).
    """
    return {
        "player_id": "$BOXSCORE.TEAM.PLAYER.id",
        "player_name": "$BOXSCORE.TEAM.PLAYER.name",
        "team_name": "$BOXSCORE.TEAM.TOTAL.name",
        "team_id": "$BOXSCORE.TEAM.TOTAL.id",
        "date": "$parsedDate",
        # minutes: keep raw seconds from FEB min field; conversion happens in Stage 7
        "minutes": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.min", "0"]}},
        "pllss": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.pllss", "0"]}},
        "p1m": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p1m", "0"]}},
        "p1a": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p1a", "0"]}},
        "p2m": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p2m", "0"]}},
        "p2a": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p2a", "0"]}},
        "p3m": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p3m", "0"]}},
        "p3a": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.p3a", "0"]}},
        "pts": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.pts", "0"]}},
        "assist": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.assist", "0"]}},
        "ro": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.ro", "0"]}},
        "rd": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.rd", "0"]}},
        "rt": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.rt", "0"]}},
        "st": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.st", "0"]}},
        "to": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.to", "0"]}},
        "bs": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.bs", "0"]}},
        "pf": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.pf", "0"]}},
        "rf": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.rf", "0"]}},
        "val": {"$toInt": {"$ifNull": ["$BOXSCORE.TEAM.PLAYER.val", "0"]}}
    }


class PlayerStatsPipelineMixin:
    """Mixin providing player stats and FBCYL timeline pipeline builders."""
    @staticmethod
    def build_player_stats_pipeline(date_filter: Dict = None, venue_filter: bool = None, result_filter: Optional[str] = None, team_filter: Optional[str] = None) -> List[Dict]:
        """
        Build aggregation pipeline for player statistics across all matches.

        Args:
            date_filter: Optional date filter (e.g., {"$gte": datetime, "$lt": datetime})
            venue_filter: Optional venue filter (True=home, False=away, None=all)
            team_filter: Optional team name — restricts to one team before player unwind
            result_filter: Optional result filter ('won' or 'lost')

        Returns:
            List of aggregation pipeline stages
        """
        pipeline = [
            # Stage 1: Parse date and add match-level fields BEFORE unwinding
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$HEADER.starttime",
                            "format": "%d-%m-%Y - %H:%M",
                            "onError": None,
                            "onNull": None
                        }
                    },
                    "localPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
                    "awayPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}}
                }
            }
        ]

        # Add match filter if any filters are provided
        match_stage = {}

        if date_filter is not None:
            match_stage["parsedDate"] = date_filter

        if match_stage:
            pipeline.append({"$match": match_stage})

        pipeline.extend([
            # Stage 2: Unwind teams
            {
                "$unwind": {
                    "path": "$BOXSCORE.TEAM",
                    "includeArrayIndex": "teamIndex"
                }
            },
            # Stage 2.5: Add venue and result fields (after unwind)
            {
                "$addFields": {
                    "is_local": {"$eq": ["$teamIndex", 0]},
                    "teamPoints": {
                        "$cond": {
                            "if": {"$eq": ["$teamIndex", 0]},
                            "then": "$localPoints",
                            "else": "$awayPoints"
                        }
                    },
                    "opponentPoints": {
                        "$cond": {
                            "if": {"$eq": ["$teamIndex", 0]},
                            "then": "$awayPoints",
                            "else": "$localPoints"
                        }
                    }
                }
            },
            # Stage 2.6: Add won field
            {
                "$addFields": {
                    "won": {"$gt": ["$teamPoints", "$opponentPoints"]}
                }
            }
        ])

        # Apply venue filter if specified
        if venue_filter is not None:
            pipeline.append({"$match": {"is_local": venue_filter}})

        # Apply result filter if specified
        if result_filter is not None:
            if result_filter == 'won':
                pipeline.append({"$match": {"won": True}})
            elif result_filter == 'lost':
                pipeline.append({"$match": {"won": False}})

        # Apply team filter BEFORE player unwind (reduces docs processed)
        if team_filter is not None:
            pipeline.append({"$match": {"BOXSCORE.TEAM.TOTAL.name": team_filter}})

        pipeline.extend([
            # Stage 3: Unwind players within each team
            {
                "$unwind": {
                    "path": "$BOXSCORE.TEAM.PLAYER",
                    "preserveNullAndEmptyArrays": False
                }
            },
            # Stage 4: Extract player data and filter players with minutes > 0
            {
                "$project": {**player_game_fields(), "starttime": "$HEADER.starttime"}
            },
            # Stage 5: Filter players who actually played (minutes > 0)
            {
                "$match": {
                    "minutes": {"$gt": 0}
                }
            },
            # Stage 5b: Chronological order, so that the name and the team name kept below are those of his LAST game (#652). ``dd-mm-yyyy - hh:mm`` is
            # put in year-first order with string operators (not ``parsedDate``: it is the same on every engine and a game without a readable date still sorts).
            {
                "$addFields": {
                    "played": {"$concat": [
                        {"$substr": ["$starttime", 6, 4]}, {"$substr": ["$starttime", 3, 2]},
                        {"$substr": ["$starttime", 0, 2]}, {"$substr": ["$starttime", 13, 5]},
                    ]}
                }
            },
            {"$sort": {"played": 1}},
            # Stage 6: Group by player: the identity is the player id within the team id. The names are NOT part of it: a team written with another
            # spelling in some games, or a corrected name, made the same person two rows with the games and totals split (#652).
            {
                "$group": {
                    "_id": {
                        "player_id": "$player_id",
                        "team_id": "$team_id"
                    },
                    "player_name": {"$last": "$player_name"},
                    "team_name": {"$last": "$team_name"},
                    "games_played": {"$sum": 1},
                    "total_minutes": {"$sum": "$minutes"},
                    "total_p1m": {"$sum": "$p1m"},
                    "total_p1a": {"$sum": "$p1a"},
                    "total_p2m": {"$sum": "$p2m"},
                    "total_p2a": {"$sum": "$p2a"},
                    "total_p3m": {"$sum": "$p3m"},
                    "total_p3a": {"$sum": "$p3a"},
                    "total_pts": {"$sum": "$pts"},
                    "total_assist": {"$sum": "$assist"},
                    "total_ro": {"$sum": "$ro"},
                    "total_rd": {"$sum": "$rd"},
                    "total_rt": {"$sum": "$rt"},
                    "total_st": {"$sum": "$st"},
                    "total_to": {"$sum": "$to"},
                    "total_bs": {"$sum": "$bs"},
                    "total_pf": {"$sum": "$pf"},
                    "total_rf": {"$sum": "$rf"},
                    "total_pllss": {"$sum": "$pllss"},
                    "total_val": {"$sum": "$val"}
                }
            },
            # Stage 7: Calculate averages and percentages
            {
                "$project": {
                    "_id": 0,
                    "player_id": "$_id.player_id",
                    "player_name": "$player_name",
                    "team_name": "$team_name",
                    "team_id": "$_id.team_id",
                    "games_played": "$games_played",
                    # total_minutes: raw sum is in seconds → convert to minutes here
                    "total_minutes": {
                        "$cond": [
                            {"$gt": ["$total_minutes", 0]},
                            {"$divide": ["$total_minutes", 60]},
                            0
                        ]
                    },
                    "minutes_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": [{"$divide": ["$total_minutes", 60]}, "$games_played"]},
                            0
                        ]
                    },
                    "total_p1m": "$total_p1m",
                    "total_p1a": "$total_p1a",
                    "total_p2m": "$total_p2m",
                    "total_p2a": "$total_p2a",
                    "total_p3m": "$total_p3m",
                    "total_p3a": "$total_p3a",
                    "total_pts": "$total_pts",
                    "total_assist": "$total_assist",
                    "total_ro": "$total_ro",
                    "total_rd": "$total_rd",
                    "total_rt": "$total_rt",
                    "total_st": "$total_st",
                    "total_to": "$total_to",
                    "total_bs": "$total_bs",
                    "total_pf": "$total_pf",
                    "total_rf": "$total_rf",
                    "total_pllss": "$total_pllss",
                    "total_val": "$total_val",
                    "fg1_percentage": {
                        "$cond": [
                            {"$gt": ["$total_p1a", 0]},
                            {"$multiply": [{"$divide": ["$total_p1m", "$total_p1a"]}, 100]},
                            0
                        ]
                    },
                    "fg2_percentage": {
                        "$cond": [
                            {"$gt": ["$total_p2a", 0]},
                            {"$multiply": [{"$divide": ["$total_p2m", "$total_p2a"]}, 100]},
                            0
                        ]
                    },
                    "fg3_percentage": {
                        "$cond": [
                            {"$gt": ["$total_p3a", 0]},
                            {"$multiply": [{"$divide": ["$total_p3m", "$total_p3a"]}, 100]},
                            0
                        ]
                    },
                    "points_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_pts", "$games_played"]},
                            0
                        ]
                    },
                    "assists_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_assist", "$games_played"]},
                            0
                        ]
                    },
                    "rebounds_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_rt", "$games_played"]},
                            0
                        ]
                    },
                    "steals_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_st", "$games_played"]},
                            0
                        ]
                    },
                    "blocks_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_bs", "$games_played"]},
                            0
                        ]
                    },
                    "turnovers_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_to", "$games_played"]},
                            0
                        ]
                    },
                    "valoracion_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_val", "$games_played"]},
                            0
                        ]
                    },
                    "pllss_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_pllss", "$games_played"]},
                            0
                        ]
                    },
                    "offensive_rebounds_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_ro", "$games_played"]},
                            0
                        ]
                    },
                    "defensive_rebounds_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_rd", "$games_played"]},
                            0
                        ]
                    },
                    "fouls_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_pf", "$games_played"]},
                            0
                        ]
                    },
                    # Advanced shooting / efficiency
                    "efg_percentage": {
                        "$cond": [
                            {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                            {"$multiply": [
                                {"$divide": [
                                    {"$add": ["$total_p2m", {"$multiply": [1.5, "$total_p3m"]}]},
                                    {"$add": ["$total_p2a", "$total_p3a"]},
                                ]},
                                100,
                            ]},
                            None,
                        ]
                    },
                    "true_shooting": {
                        "$cond": [
                            {"$gt": [{"$add": ["$total_p2a", "$total_p3a", {"$multiply": [0.44, "$total_p1a"]}]}, 0]},
                            {"$multiply": [
                                {"$divide": [
                                    "$total_pts",
                                    {"$multiply": [2.0, {"$add": ["$total_p2a", "$total_p3a", {"$multiply": [0.44, "$total_p1a"]}]}]},
                                ]},
                                100,
                            ]},
                            None,
                        ]
                    },
                    "free_throw_rate": {
                        "$cond": [
                            {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                            {"$multiply": [
                                {"$divide": ["$total_p1a", {"$add": ["$total_p2a", "$total_p3a"]}]},
                                100,
                            ]},
                            None,
                        ]
                    },
                    "three_point_rate": {
                        "$cond": [
                            {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                            {"$multiply": [
                                {"$divide": ["$total_p3a", {"$add": ["$total_p2a", "$total_p3a"]}]},
                                100,
                            ]},
                            None,
                        ]
                    },
                    "turnover_rate": {
                        "$cond": [
                            {"$gt": [{"$add": ["$total_p2a", "$total_p3a", {"$multiply": [0.44, "$total_p1a"]}, "$total_to"]}, 0]},
                            {"$multiply": [
                                {"$divide": [
                                    "$total_to",
                                    {"$add": ["$total_p2a", "$total_p3a", {"$multiply": [0.44, "$total_p1a"]}, "$total_to"]},
                                ]},
                                100,
                            ]},
                            None,
                        ]
                    },
                }
            },
            # Stage 8: Sort by team and then by points descending
            {
                "$sort": {
                    "team_name": 1,
                    "total_pts": -1
                }
            }
        ])

        return pipeline

    @staticmethod
    def build_team_matches_timeline_pipeline_fbcyl(team_name: str) -> List[Dict]:
        """
        Build a pipeline to get chronological match data for a team (FBCYL format).

        This pipeline retrieves all matches for a specific team in chronological order,
        including opponent information and match statistics. Used for temporal evolution analysis.
        Works with FBCYL data structure which uses 'teams' instead of 'BOXSCORE.TEAM'.

        Args:
            team_name: Name of the team to get match data for

        Returns:
            MongoDB aggregation pipeline as a list of stages

        Example output format:
            [
                {
                    "date": datetime,
                    "opponent": "Team B",
                    "team_data": {...},  # teams[x].data for team
                    "opponent_data": {...},  # teams[x].data for opponent
                    "is_local": True
                },
                ...
            ]
        """
        return [
            # Stages 1-3: the date of the game (the ``time`` field at the root level, both writings of FBCYL, #681)
            *parse_day_stages("$time", "parsedDate"),
            # Stage 4: Filter matches where team participated
            {
                "$match": {
                    "teams.name": team_name
                }
            },
            # Stage 5: Sort by date ascending (oldest to newest)
            {"$sort": {"parsedDate": 1}},
            # Stage 6: Capture both teams' data BEFORE unwinding
            {
                "$addFields": {
                    "team0_name": {"$arrayElemAt": ["$teams.name", 0]},
                    "team1_name": {"$arrayElemAt": ["$teams.name", 1]},
                    "team0_data": {"$arrayElemAt": ["$teams.data", 0]},
                    "team1_data": {"$arrayElemAt": ["$teams.data", 1]}
                }
            },
            # Stage 7: Unwind teams to identify which index is our team
            {
                "$unwind": {
                    "path": "$teams",
                    "includeArrayIndex": "teamIndex"
                }
            },
            # Stage 8: Filter to keep only the selected team's row
            {
                "$match": {
                    "teams.name": team_name
                }
            },
            # Stage 9: Project final structure with opponent data
            {
                "$project": {
                    "date": "$parsedDate",
                    "opponent": {
                        "$cond": [
                            {"$eq": ["$teamIndex", 0]},
                            "$team1_name",
                            "$team0_name"
                        ]
                    },
                    "team_data": "$teams.data",
                    "opponent_data": {
                        "$cond": [
                            {"$eq": ["$teamIndex", 0]},
                            "$team1_data",
                            "$team0_data"
                        ]
                    },
                    "is_local": {"$eq": ["$teamIndex", 0]}
                }
            }
        ]

    # build_per_player_per_game_pipeline moved to pipeline_player_per_game.py

