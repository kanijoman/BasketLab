"""MongoDB aggregation pipeline builder for FBCYL statistics.

IMPORTANT: FBCYL Team ID Usage
-------------------------------
FBCYL has TWO team ID fields with different purposes:

1. teamIdExtern: CONSISTENT across all games for the same team
   - Use for: Aggregation, grouping teams, statistics
   - Example: "C.B. SANTA MARTA" always has teamIdExtern=34588

2. teamIdIntern: CHANGES per game for the same team
   - Use for: Play-by-play moves (moves[].idTeam uses this)
   - Example: "C.B. SANTA MARTA" has teamIdIntern=33865 in one game, 34138 in another

Summary:
- Aggregation pipelines → use teamIdExtern (consistent)
- Play-by-play analysis → use teamIdIntern (matches moves[].idTeam)
"""

from typing import List, Dict, Optional
from datetime import datetime, time


class FBCYLPipelineBuilder:
    """Builds MongoDB aggregation pipeline for FBCYL team statistics."""

    @staticmethod
    def build_team_stats_pipeline(date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Build aggregation pipeline for FBCYL team statistics.

        FBCYL data structure:
        {
            "_id": "uuid",
            "uuid": "uuid",
            "moves": { ... },
            "stats": {
                "teams": [
                    {  // Team 0 (local)
                        "teamId": ...,
                        "teamName": ...,
                        "players": [...],
                        "data": {
                            "score": ...,
                            "shotsOfTwoSuccessful": ...,
                            "shotsOfTwoAttempted": ...,
                            "shotsOfThreeSuccessful": ...,
                            "shotsOfThreeAttempted": ...,
                            "shotsOfOneSuccessful": ...,
                            "shotsOfOneAttempted": ...,
                            "rebounds": ...,
                            "offensiveRebound": ...,
                            "defensiveRebound": ...,
                            "assists": ...,
                            "steals": ...,
                            "lost": ...,  // turnovers
                            "block": ...,
                            "faults": ...
                        }
                    },
                    {  // Team 1 (visitor)
                        // Same structure
                    }
                ]
            }
        }

        Args:
            date_filter: Optional date filter (not applicable for FBCYL yet)
            venue_filter: Optional venue filter (True=home, False=away, None=all)
            result_filter: Optional result filter ('won', 'lost', None=all)

        Returns:
            List of pipeline stages
        """
        pipeline = []

        # Phase 0: Add date conversion and filter if provided
        if date_filter:
            # Normalize the date_filter to start of day (remove time component)
            normalized_filter = {}
            for operator, dt_value in date_filter.items():
                if isinstance(dt_value, datetime):
                    # Convert to start of day (00:00:00)
                    normalized_filter[operator] = datetime.combine(dt_value.date(), time.min)
                else:
                    normalized_filter[operator] = dt_value

            # First, add a field that converts the string date to a date object
            # FBCYL uses "stats.time" field with format "Oct 4, 2025 7:00:00 PM"
            # Extract just the date part "Oct 4, 2025" and parse it
            pipeline.append({
                "$addFields": {
                    "timeParts": {"$split": ["$stats.time", " "]}
                }
            })

            # Build the date string from parts: month, day, year
            pipeline.append({
                "$addFields": {
                    "dateString": {
                        "$concat": [
                            {"$arrayElemAt": ["$timeParts", 0]},  # Month (Oct)
                            " ",
                            {"$arrayElemAt": ["$timeParts", 1]},  # Day (4,)
                            " ",
                            {"$arrayElemAt": ["$timeParts", 2]}   # Year (2025)
                        ]
                    }
                }
            })

            # Parse the date string to date object
            pipeline.append({
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$dateString",
                            "format": "%b %d, %Y",
                            "timezone": "UTC",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            })

            # Apply the normalized date filter
            pipeline.append({"$match": {"parsedDate": normalized_filter}})

        # Stage 1: Filter out documents without stats
        pipeline.append({
            "$match": {
                "stats.teams": {"$exists": True, "$ne": None}
            }
        })

        # Add a debug stage to see what dates we have (only when debugging)
        # Uncomment to see parsed dates:
        # pipeline.append({"$project": {"time": 1, "dateString": 1, "parsedDate": 1}})

        # Stage 2: Preserve original teams array before unwinding
        pipeline.append({
            "$addFields": {
                "teams": "$stats.teams",  # Extract teams from stats
                "original_teams": "$stats.teams"
            }
        })

        # Stage 3: Unwind teams array to create one document per team
        pipeline.append({
            "$unwind": {
                "path": "$teams",
                "includeArrayIndex": "teamIndex"
            }
        })

        # Stage 4: Add team info and opponent data
        # Note: Use teamIdExtern for aggregation (consistent across games)
        # teamIdIntern changes per game and is only used in moves[]
        pipeline.append({
            "$addFields": {
                "team_name": "$teams.name",
                "team_id": "$teams.teamIdExtern",
                "is_home": {"$eq": ["$teamIndex", 0]},
                "team_score": "$teams.data.score",
                # Get opponent score by checking the other team in the original array
                "opponent_score": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": {"$arrayElemAt": ["$original_teams", 1]},
                        "else": {"$arrayElemAt": ["$original_teams", 0]}
                    }
                }
            }
        })

        # Stage 5: Calculate result
        pipeline.append({
            "$addFields": {
                "opponent_score_value": "$opponent_score.data.score",
                "result": {
                    "$cond": {
                        "if": {"$gt": ["$team_score", "$opponent_score.data.score"]},
                        "then": "won",
                        "else": {
                            "$cond": {
                                "if": {"$lt": ["$team_score", "$opponent_score.data.score"]},
                                "then": "lost",
                                "else": "tied"
                            }
                        }
                    }
                }
            }
        })

        # Stage 6: Apply filters
        match_conditions = []

        if venue_filter is not None:
            match_conditions.append({"is_home": venue_filter})

        if result_filter:
            match_conditions.append({"result": result_filter})

        if match_conditions:
            pipeline.append({"$match": {"$and": match_conditions}})

        # Stage 7: Group by team and aggregate statistics
        pipeline.append({
            "$group": {
                "_id": {"team_id": "$team_id", "team_name": "$team_name"},
                "team_name": {"$first": "$team_name"},
                "team_id": {"$first": "$team_id"},

                # Game counts
                "games_played": {"$sum": 1},
                "total_games": {"$sum": 1},  # Alias for compatibility
                "games_won": {
                    "$sum": {"$cond": [{"$eq": ["$result", "won"]}, 1, 0]}
                },
                "games_lost": {
                    "$sum": {"$cond": [{"$eq": ["$result", "lost"]}, 1, 0]}
                },
                "games_home": {
                    "$sum": {"$cond": ["$is_home", 1, 0]}
                },
                "games_away": {
                    "$sum": {"$cond": ["$is_home", 0, 1]}
                },

                # Scoring
                "points_scored": {"$sum": "$teams.data.score"},
                "points_received": {"$sum": "$opponent_score_value"},

                # Field Goals
                "fg2_made": {"$sum": "$teams.data.shotsOfTwoSuccessful"},
                "fg2_attempted": {"$sum": "$teams.data.shotsOfTwoAttempted"},
                "fg3_made": {"$sum": "$teams.data.shotsOfThreeSuccessful"},
                "fg3_attempted": {"$sum": "$teams.data.shotsOfThreeAttempted"},
                "ft_made": {"$sum": "$teams.data.shotsOfOneSuccessful"},
                "ft_attempted": {"$sum": "$teams.data.shotsOfOneAttempted"},

                # Rebounds
                "total_rebounds": {"$sum": "$teams.data.rebounds"},
                "rebounds_off": {"$sum": "$teams.data.offensiveRebound"},
                "rebounds_def": {"$sum": "$teams.data.defensiveRebound"},

                # Other stats
                "assists": {"$sum": "$teams.data.assists"},
                "steals": {"$sum": "$teams.data.steals"},
                "turnovers": {"$sum": "$teams.data.lost"},
                "blocks": {"$sum": "$teams.data.block"},
                "fouls": {"$sum": "$teams.data.faults"},

                # Opponent stats for advanced metrics
                "opp_fg2_made": {"$sum": "$opponent_score.data.shotsOfTwoSuccessful"},
                "opp_fg2_attempted": {"$sum": "$opponent_score.data.shotsOfTwoAttempted"},
                "opp_fg3_made": {"$sum": "$opponent_score.data.shotsOfThreeSuccessful"},
                "opp_fg3_attempted": {"$sum": "$opponent_score.data.shotsOfThreeAttempted"},
                "opp_ft_attempted": {"$sum": "$opponent_score.data.shotsOfOneAttempted"},
                "opponent_rebounds_off": {"$sum": "$opponent_score.data.offensiveRebound"},
                "opponent_rebounds_def": {"$sum": "$opponent_score.data.defensiveRebound"},
                "opp_turnovers": {"$sum": "$opponent_score.data.lost"},

                # Calculate possessions per game during grouping
                "total_possessions": {
                    "$sum": {
                        "$add": [
                            "$teams.data.shotsOfTwoAttempted",
                            "$teams.data.shotsOfThreeAttempted",
                            {"$multiply": [0.44, "$teams.data.shotsOfOneAttempted"]},
                            "$teams.data.lost",
                            {"$multiply": [-1, "$teams.data.offensiveRebound"]}
                        ]
                    }
                },
                "opponent_possessions": {
                    "$sum": {
                        "$add": [
                            "$opponent_score.data.shotsOfTwoAttempted",
                            "$opponent_score.data.shotsOfThreeAttempted",
                            {"$multiply": [0.44, "$opponent_score.data.shotsOfOneAttempted"]},
                            "$opponent_score.data.lost",
                            {"$multiply": [-1, "$opponent_score.data.offensiveRebound"]}
                        ]
                    }
                }
            }
        })

        # Stage 8: Calculate derived statistics
        pipeline.append({
            "$addFields": {
                # Per game averages
                "points_per_game": {"$divide": ["$points_scored", "$games_played"]},
                "points_against_per_game": {"$divide": ["$points_received", "$games_played"]},
                "points_allowed_per_game": {"$divide": ["$points_received", "$games_played"]},  # Alias
                "possessions_per_game": {"$divide": ["$total_possessions", "$games_played"]},
                "rebounds_per_game": {"$divide": ["$total_rebounds", "$games_played"]},
                "def_rebounds_per_game": {"$divide": ["$rebounds_def", "$games_played"]},
                "off_rebounds_per_game": {"$divide": ["$rebounds_off", "$games_played"]},
                "assists_per_game": {"$divide": ["$assists", "$games_played"]},
                "steals_per_game": {"$divide": ["$steals", "$games_played"]},
                "turnovers_per_game": {"$divide": ["$turnovers", "$games_played"]},
                "blocks_per_game": {"$divide": ["$blocks", "$games_played"]},

                # Shooting percentages
                "fg_percentage": {
                    "$cond": {
                        "if": {"$gt": [{"$add": ["$fg2_attempted", "$fg3_attempted"]}, 0]},
                        "then": {"$multiply": [
                            {"$divide": [
                                {"$add": ["$fg2_made", "$fg3_made"]},
                                {"$add": ["$fg2_attempted", "$fg3_attempted"]}
                            ]},
                            100
                        ]},
                        "else": 0
                    }
                },
                "fg2_percentage": {
                    "$cond": {
                        "if": {"$gt": ["$fg2_attempted", 0]},
                        "then": {"$multiply": [{"$divide": ["$fg2_made", "$fg2_attempted"]}, 100]},
                        "else": 0
                    }
                },
                "fg3_percentage": {
                    "$cond": {
                        "if": {"$gt": ["$fg3_attempted", 0]},
                        "then": {"$multiply": [{"$divide": ["$fg3_made", "$fg3_attempted"]}, 100]},
                        "else": 0
                    }
                },
                "ft_percentage": {
                    "$cond": {
                        "if": {"$gt": ["$ft_attempted", 0]},
                        "then": {"$multiply": [{"$divide": ["$ft_made", "$ft_attempted"]}, 100]},
                        "else": 0
                    }
                },
                "efg_percentage": {
                    "$cond": {
                        "if": {"$gt": [{"$add": ["$fg2_attempted", "$fg3_attempted"]}, 0]},
                        "then": {
                            "$multiply": [
                                {
                                    "$divide": [
                                        {"$add": ["$fg2_made", {"$multiply": ["$fg3_made", 1.5]}]},
                                        {"$add": ["$fg2_attempted", "$fg3_attempted"]}
                                    ]
                                },
                                100
                            ]
                        },
                        "else": 0
                    }
                },

                # Win percentage
                "win_pct": {
                    "$cond": {
                        "if": {"$gt": ["$games_played", 0]},
                        "then": {"$multiply": [{"$divide": ["$games_won", "$games_played"]}, 100]},
                        "else": 0
                    }
                }
            }
        })

        # Stage 9: Calculate advanced metrics
        pipeline.append({
            "$addFields": {
                # Offensive Rating (points per 100 possessions)
                "offensive_rating": {
                    "$cond": {
                        "if": {"$gt": ["$total_possessions", 0]},
                        "then": {"$multiply": [{"$divide": ["$points_scored", "$total_possessions"]}, 100]},
                        "else": 0
                    }
                },
                # Defensive Rating (opponent points per 100 possessions)
                "defensive_rating": {
                    "$cond": {
                        "if": {"$gt": ["$opponent_possessions", 0]},
                        "then": {"$multiply": [{"$divide": ["$points_received", "$opponent_possessions"]}, 100]},
                        "else": 0
                    }
                },
                # Net Rating
                "net_rating": {
                    "$subtract": [
                        {
                            "$cond": {
                                "if": {"$gt": ["$total_possessions", 0]},
                                "then": {"$multiply": [{"$divide": ["$points_scored", "$total_possessions"]}, 100]},
                                "else": 0
                            }
                        },
                        {
                            "$cond": {
                                "if": {"$gt": ["$opponent_possessions", 0]},
                                "then": {"$multiply": [{"$divide": ["$points_received", "$opponent_possessions"]}, 100]},
                                "else": 0
                            }
                        }
                    ]
                },
                # Pace (possessions per 40 minutes) - simplified to possessions per game
                "pace": {"$divide": ["$total_possessions", "$games_played"]},

                # Four Factors (with standard names)
                "turnover_rate": {
                    "$cond": {
                        "if": {"$gt": ["$total_possessions", 0]},
                        "then": {"$multiply": [{"$divide": ["$turnovers", "$total_possessions"]}, 100]},
                        "else": 0
                    }
                },
                "offensive_rebound_rate": {
                    "$cond": {
                        "if": {"$gt": [{"$add": ["$rebounds_off", "$opponent_rebounds_def"]}, 0]},
                        "then": {"$multiply": [
                            {"$divide": ["$rebounds_off", {"$add": ["$rebounds_off", "$opponent_rebounds_def"]}]},
                            100
                        ]},
                        "else": 0
                    }
                },
                "free_throw_rate": {
                    "$cond": {
                        "if": {"$gt": [{"$add": ["$fg2_attempted", "$fg3_attempted"]}, 0]},
                        "then": {"$multiply": [
                            {"$divide": ["$ft_attempted", {"$add": ["$fg2_attempted", "$fg3_attempted"]}]},
                            100
                        ]},
                        "else": 0
                    }
                },

                # Additional advanced shooting metrics
                "three_point_rate": {
                    "$cond": {
                        "if": {"$gt": [{"$add": ["$fg2_attempted", "$fg3_attempted"]}, 0]},
                        "then": {"$multiply": [
                            {"$divide": ["$fg3_attempted", {"$add": ["$fg2_attempted", "$fg3_attempted"]}]},
                            100
                        ]},
                        "else": 0
                    }
                },
                "true_shooting": {
                    "$cond": {
                        "if": {"$gt": [{"$add": [{"$add": ["$fg2_attempted", "$fg3_attempted"]}, {"$multiply": [0.44, "$ft_attempted"]}]}, 0]},
                        "then": {"$multiply": [
                            {"$divide": [
                                "$points_scored",
                                {"$multiply": [2, {"$add": [{"$add": ["$fg2_attempted", "$fg3_attempted"]}, {"$multiply": [0.44, "$ft_attempted"]}]}]}
                            ]},
                            100
                        ]},
                        "else": 0
                    }
                },

                # Playmaking metrics
                "assist_fg_rate": {
                    "$cond": {
                        "if": {"$gt": [{"$add": ["$fg2_made", "$fg3_made"]}, 0]},
                        "then": {"$multiply": [
                            {"$divide": ["$assists", {"$add": ["$fg2_made", "$fg3_made"]}]},
                            100
                        ]},
                        "else": 0
                    }
                },
                "assist_rate": {
                    "$cond": {
                        "if": {"$gt": ["$total_possessions", 0]},
                        "then": {"$multiply": [{"$divide": ["$assists", "$total_possessions"]}, 100]},
                        "else": 0
                    }
                },
                "steal_rate": {
                    "$cond": {
                        "if": {"$gt": ["$total_possessions", 0]},
                        "then": {"$multiply": [{"$divide": ["$steals", "$total_possessions"]}, 100]},
                        "else": 0
                    }
                },
                "block_rate": {
                    "$cond": {
                        "if": {"$gt": ["$total_possessions", 0]},
                        "then": {"$multiply": [{"$divide": ["$blocks", "$total_possessions"]}, 100]},
                        "else": 0
                    }
                },

                # Rebounding metrics
                "defensive_rebound_rate": {
                    "$cond": {
                        "if": {"$gt": [{"$add": ["$rebounds_def", "$opponent_rebounds_off"]}, 0]},
                        "then": {"$multiply": [
                            {"$divide": ["$rebounds_def", {"$add": ["$rebounds_def", "$opponent_rebounds_off"]}]},
                            100
                        ]},
                        "else": 0
                    }
                }
            }
        })

        # Stage 10: Sort by team name
        pipeline.append({
            "$sort": {"team_name": 1}
        })

        return pipeline

    @staticmethod
    def build_opponent_stats_pipeline(date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Build aggregation pipeline for opponent statistics (similar to team stats but inverted).

        Args:
            date_filter: Optional date filter
            venue_filter: Optional venue filter
            result_filter: Optional result filter

        Returns:
            List of pipeline stages
        """
        # For now, return same as team stats - can be customized later
        return FBCYLPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)

    @staticmethod
    def build_player_stats_pipeline(date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Build aggregation pipeline for FBCYL player statistics.

        FBCYL player data structure:
        stats.teams[].players[] = {
            "actorId": 607322,
            "uuid": "b1f5826b-1af3-4ff7-aefc-d0ba877c8fbc",
            "name": "PLAYER NAME",
            "dorsal": "4",
            "timePlayed": 32,
            "data": {
                "score": 24,
                "valoration": 12,
                "shotsOfOneAttempted": 2,
                "shotsOfOneSuccessful": 2,
                "shotsOfTwoAttempted": 21,
                "shotsOfTwoSuccessful": 8,
                "shotsOfThreeAttempted": 11,
                "shotsOfThreeSuccessful": 2,
                "rebounds": 10,
                "assists": 0,
                "lost": 4,
                "block": 0,
                "steals": 0,
                "faults": 1,
                "offensiveRebound": 7,
                "defensiveRebound": 3,
                ...
            }
        }

        Args:
            date_filter: Optional date filter
            venue_filter: Optional venue filter (True=home, False=away, None=all)
            result_filter: Optional result filter ('won', 'lost', None=all)

        Returns:
            List of pipeline stages
        """
        pipeline = []

        # Phase 0: Add date conversion and filter if provided
        if date_filter:
            # Normalize the date_filter to start of day (remove time component)
            normalized_filter = {}
            for operator, dt_value in date_filter.items():
                if isinstance(dt_value, datetime):
                    # Convert to start of day (00:00:00)
                    normalized_filter[operator] = datetime.combine(dt_value.date(), time.min)
                else:
                    normalized_filter[operator] = dt_value

            # First, add a field that converts the string date to a date object
            # FBCYL uses "stats.time" field with format "Oct 4, 2025 7:00:00 PM"
            # Extract just the date part "Oct 4, 2025" and parse it
            pipeline.append({
                "$addFields": {
                    "timeParts": {"$split": ["$stats.time", " "]}
                }
            })

            # Build the date string from parts: month, day, year
            pipeline.append({
                "$addFields": {
                    "dateString": {
                        "$concat": [
                            {"$arrayElemAt": ["$timeParts", 0]},  # Month (Oct)
                            " ",
                            {"$arrayElemAt": ["$timeParts", 1]},  # Day (4,)
                            " ",
                            {"$arrayElemAt": ["$timeParts", 2]}   # Year (2025)
                        ]
                    }
                }
            })

            # Parse the date string to date object
            pipeline.append({
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$dateString",
                            "format": "%b %d, %Y",
                            "timezone": "UTC",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            })

            # Apply the normalized date filter
            pipeline.append({"$match": {"parsedDate": normalized_filter}})

        # Stage 1: Filter out documents without stats
        pipeline.append({
            "$match": {
                "stats.teams": {"$exists": True, "$ne": None}
            }
        })

        # Stage 2: Unwind teams array but keep original array for opponent lookup
        pipeline.append({
            "$addFields": {
                "all_teams": "$stats.teams"  # Save reference to full array before unwind
            }
        })

        pipeline.append({
            "$unwind": {
                "path": "$stats.teams",
                "includeArrayIndex": "teamIndex"
            }
        })

        # Stage 3: Add team context, venue info, and result
        pipeline.append({
            "$addFields": {
                "team_name": "$stats.teams.name",
                "team_id": "$stats.teams.teamIdExtern",
                # Determine if this is home team (index 0 = home/local, index 1 = away/visitor)
                "is_home": {"$eq": ["$teamIndex", 0]},
                # Get team score
                "team_score": "$stats.teams.data.score",
                # Get opponent info (other team in the saved array)
                "opponent_score": {
                    "$arrayElemAt": [
                        "$all_teams",
                        {"$cond": [{"$eq": ["$teamIndex", 0]}, 1, 0]}
                    ]
                }
            }
        })

        # Stage 3b: Calculate result (won/lost)
        pipeline.append({
            "$addFields": {
                "result": {
                    "$cond": {
                        "if": {"$gt": ["$team_score", "$opponent_score.data.score"]},
                        "then": "won",
                        "else": {
                            "$cond": {
                                "if": {"$lt": ["$team_score", "$opponent_score.data.score"]},
                                "then": "lost",
                                "else": "tied"
                            }
                        }
                    }
                }
            }
        })

        # Stage 3c: Apply venue and result filters if provided
        match_conditions = []
        if venue_filter is not None:
            match_conditions.append({"is_home": venue_filter})
        if result_filter:
            match_conditions.append({"result": result_filter})

        if match_conditions:
            pipeline.append({"$match": {"$and": match_conditions}})

        # Stage 4: Unwind players
        pipeline.append({
            "$unwind": {
                "path": "$stats.teams.players",
                "preserveNullAndEmptyArrays": False
            }
        })

        # Stage 5: Filter players with playing time > 0.
        # Also exclude phantom players: inscribed but never played; the raw
        # FBCYL data assigns them timePlayed=40 (full game) while every
        # activity stat remains zero.
        # $nor excludes any player where timePlayed==40 AND every listed stat
        # is zero or absent.
        pipeline.append({
            "$match": {
                "stats.teams.players.timePlayed": {"$gt": 0},
                "$nor": [{
                    "stats.teams.players.timePlayed": 40,
                    "stats.teams.players.data.score":               {"$in": [0, None]},
                    "stats.teams.players.data.shotsOfTwoAttempted":   {"$in": [0, None]},
                    "stats.teams.players.data.shotsOfThreeAttempted": {"$in": [0, None]},
                    "stats.teams.players.data.shotsOfOneAttempted":   {"$in": [0, None]},
                    "stats.teams.players.data.offensiveRebound":      {"$in": [0, None]},
                    "stats.teams.players.data.defensiveRebound":      {"$in": [0, None]},
                    "stats.teams.players.data.assists":               {"$in": [0, None]},
                    "stats.teams.players.data.lost":                  {"$in": [0, None]},
                    "stats.teams.players.data.block":                 {"$in": [0, None]},
                    "stats.teams.players.data.steals":                {"$in": [0, None]},
                }],
            }
        })

        # Stage 6: Project player data and create normalized name for matching
        pipeline.append({
            "$project": {
                "player_uuid": "$stats.teams.players.uuid",
                "player_id": "$stats.teams.players.actorId",
                "player_name": "$stats.teams.players.name",
                "team_name": "$team_name",
                "team_id": "$team_id",
                # Create normalized name for matching (initial + surnames)
                "normalized_name": {
                    "$let": {
                        "vars": {
                            "words": {"$split": ["$stats.teams.players.name", " "]}
                        },
                        "in": {
                            "$concat": [
                                {"$substrCP": [{"$arrayElemAt": ["$$words", 0]}, 0, 1]},
                                " ",
                                {"$arrayElemAt": [
                                    "$$words",
                                    {"$subtract": [{"$size": "$$words"}, 2]}
                                ]},
                                " ",
                                {"$arrayElemAt": [
                                    "$$words",
                                    {"$subtract": [{"$size": "$$words"}, 1]}
                                ]}
                            ]
                        }
                    }
                },
                "minutes": {"$ifNull": ["$stats.teams.players.timePlayed", 0]},
                "pts": {"$ifNull": ["$stats.teams.players.data.score", 0]},
                "val": {"$ifNull": ["$stats.teams.players.data.valoration", 0]},
                "p1a": {"$ifNull": ["$stats.teams.players.data.shotsOfOneAttempted", 0]},
                "p1m": {"$ifNull": ["$stats.teams.players.data.shotsOfOneSuccessful", 0]},
                "p2a": {"$ifNull": ["$stats.teams.players.data.shotsOfTwoAttempted", 0]},
                "p2m": {"$ifNull": ["$stats.teams.players.data.shotsOfTwoSuccessful", 0]},
                "p3a": {"$ifNull": ["$stats.teams.players.data.shotsOfThreeAttempted", 0]},
                "p3m": {"$ifNull": ["$stats.teams.players.data.shotsOfThreeSuccessful", 0]},
                # Calculate total rebounds as sum of offensive + defensive rebounds
                "ro": {"$ifNull": ["$stats.teams.players.data.offensiveRebound", 0]},
                "rd": {"$ifNull": ["$stats.teams.players.data.defensiveRebound", 0]},
                "rt": {
                    "$add": [
                        {"$ifNull": ["$stats.teams.players.data.offensiveRebound", 0]},
                        {"$ifNull": ["$stats.teams.players.data.defensiveRebound", 0]}
                    ]
                },
                "assist": {"$ifNull": ["$stats.teams.players.data.assists", 0]},
                "to": {"$ifNull": ["$stats.teams.players.data.lost", 0]},
                "bs": {"$ifNull": ["$stats.teams.players.data.block", 0]},
                "st": {"$ifNull": ["$stats.teams.players.data.steals", 0]},
                "pf": {"$ifNull": ["$stats.teams.players.data.faults", 0]},
                "rf": {"$ifNull": ["$stats.teams.players.data.faultReceived", 0]},
                # Calculate plus/minus from inOutsList
                "pllss": {
                    "$let": {
                        "vars": {
                            "inOuts": {"$ifNull": ["$stats.teams.players.inOutsList", []]}
                        },
                        "in": {
                            "$reduce": {
                                "input": {"$range": [0, {"$floor": {"$divide": [{"$size": "$$inOuts"}, 2]}}]},
                                "initialValue": 0,
                                "in": {
                                    "$let": {
                                        "vars": {
                                            "inIndex": {"$multiply": ["$$this", 2]},
                                            "outIndex": {"$add": [{"$multiply": ["$$this", 2]}, 1]}
                                        },
                                        "in": {
                                            "$add": [
                                                "$$value",
                                                {
                                                    "$cond": [
                                                        {"$lt": ["$$outIndex", {"$size": "$$inOuts"}]},
                                                        {
                                                            "$subtract": [
                                                                {"$getField": {
                                                                    "field": "pointDiff",
                                                                    "input": {"$arrayElemAt": ["$$inOuts", "$$outIndex"]}
                                                                }},
                                                                {"$getField": {
                                                                    "field": "pointDiff",
                                                                    "input": {"$arrayElemAt": ["$$inOuts", "$$inIndex"]}
                                                                }}
                                                            ]
                                                        },
                                                        0
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        })

        # Stage 7: Pre-group by team + normalized name to find valid UUID for each player
        pipeline.append({
            "$group": {
                "_id": {
                    "team_id": "$team_id",
                    "normalized_name": "$normalized_name"
                },
                # Collect all data for this player identity
                "player_appearances": {
                    "$push": {
                        "uuid": "$player_uuid",
                        "actor_id": "$player_id",
                        "name": "$player_name",
                        "minutes": "$minutes",
                        "pts": "$pts",
                        "val": "$val",
                        "p1a": "$p1a",
                        "p1m": "$p1m",
                        "p2a": "$p2a",
                        "p2m": "$p2m",
                        "p3a": "$p3a",
                        "p3m": "$p3m",
                        "rt": "$rt",
                        "ro": "$ro",
                        "rd": "$rd",
                        "assist": "$assist",
                        "to": "$to",
                        "bs": "$bs",
                        "st": "$st",
                        "pf": "$pf",
                        "rf": "$rf",
                        "pllss": "$pllss"
                    }
                },
                "team_name": {"$first": "$team_name"},
                # Find first non-null UUID using $max (null values are ignored)
                "valid_uuid": {
                    "$max": "$player_uuid"
                }
            }
        })

        # Stage 8: Unwind appearances to process individually with completed UUID
        pipeline.append({
            "$unwind": "$player_appearances"
        })

        # Stage 9: Project with completed UUID (use valid_uuid if original was null)
        pipeline.append({
            "$project": {
                "team_id": "$_id.team_id",
                "team_name": 1,
                "normalized_name": "$_id.normalized_name",
                "completed_uuid": {
                    "$ifNull": [
                        "$player_appearances.uuid",
                        {"$ifNull": ["$valid_uuid", "$_id.normalized_name"]}
                    ]
                },
                "player_id": "$player_appearances.actor_id",
                "player_name": "$player_appearances.name",
                "minutes": "$player_appearances.minutes",
                "pts": "$player_appearances.pts",
                "val": "$player_appearances.val",
                "p1a": "$player_appearances.p1a",
                "p1m": "$player_appearances.p1m",
                "p2a": "$player_appearances.p2a",
                "p2m": "$player_appearances.p2m",
                "p3a": "$player_appearances.p3a",
                "p3m": "$player_appearances.p3m",
                "rt": "$player_appearances.rt",
                "ro": "$player_appearances.ro",
                "rd": "$player_appearances.rd",
                "assist": "$player_appearances.assist",
                "to": "$player_appearances.to",
                "bs": "$player_appearances.bs",
                "st": "$player_appearances.st",
                "pf": "$player_appearances.pf",
                "rf": "$player_appearances.rf",
                "pllss": "$player_appearances.pllss"
            }
        })

        # Stage 10: Final grouping by completed UUID and team
        pipeline.append({
            "$group": {
                "_id": {
                    "uuid": "$completed_uuid",
                    "team_id": "$team_id"
                },
                "player_id": {"$first": "$player_id"},
                "player_name": {"$first": "$player_name"},
                "team_name": {"$first": "$team_name"},
                "team_id": {"$first": "$team_id"},
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
                "total_taps": {"$sum": "$bs"},  # Alias for blocks used in advanced stats
                "total_pf": {"$sum": "$pf"},
                "total_rf": {"$sum": "$rf"},
                "total_pllss": {"$sum": "$pllss"},
                "total_val": {"$sum": "$val"}
            }
        })

        # Stage 8: Calculate percentages and averages
        pipeline.append({
            "$project": {
                "player_uuid": "$_id.uuid",  # Extract UUID from _id
                "player_id": 1,
                "player_name": 1,
                "team_name": 1,
                "team_id": 1,
                "games_played": 1,
                "total_minutes": 1,
                "minutes_per_game": {
                    "$cond": [
                        {"$gt": ["$games_played", 0]},
                        {"$divide": ["$total_minutes", "$games_played"]},
                        0
                    ]
                },
                "total_p1m": 1,
                "total_p1a": 1,
                "total_p2m": 1,
                "total_p2a": 1,
                "total_p3m": 1,
                "total_p3a": 1,
                "total_pts": 1,
                "total_assist": 1,
                "total_as": "$total_assist",  # Alias for ranking window
                "total_ro": 1,
                "total_rd": 1,
                "total_rt": 1,
                "total_st": 1,
                "total_to": 1,
                "total_bs": 1,
                "total_bl": "$total_bs",  # Alias for ranking window (tapones/blocks)
                "total_pf": 1,
                "total_rf": 1,
                "total_pllss": 1,
                "total_val": 1,
                "fg1_percentage": {
                    "$cond": [
                        {"$gt": ["$total_p1a", 0]},
                        {"$multiply": [{"$divide": ["$total_p1m", "$total_p1a"]}, 100]},
                        0
                    ]
                },
                "ft_percentage": {  # Alias for ranking window (free throw percentage)
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
                "ppg": {  # Alias for ranking window
                    "$cond": [
                        {"$gt": ["$games_played", 0]},
                        {"$divide": ["$total_pts", "$games_played"]},
                        0
                    ]
                },
                "mpg": {  # Alias for ranking window (minutes per game)
                    "$cond": [
                        {"$gt": ["$games_played", 0]},
                        {"$divide": ["$total_minutes", "$games_played"]},
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
                "ast_pg": {  # Alias for ranking window
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
                "stl_pg": {  # Alias for ranking window
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
                "blk_pg": {  # Alias for ranking window
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
                "tov_pg": {  # Alias for ranking window
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
                "val_pg": {  # Alias for ranking window
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

                # Advanced statistics
                # True Shooting Percentage
                "ts": {
                    "$cond": [
                        {"$gt": [{"$add": [{"$add": ["$total_p2a", "$total_p3a"]}, {"$multiply": [0.44, "$total_p1a"]}]}, 0]},
                        {"$multiply": [
                            {"$divide": [
                                "$total_pts",
                                {"$multiply": [2, {"$add": [{"$add": ["$total_p2a", "$total_p3a"]}, {"$multiply": [0.44, "$total_p1a"]}]}]}
                            ]},
                            100
                        ]},
                        0
                    ]
                },
                # Effective Field Goal Percentage
                "efg": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                        {"$multiply": [
                            {"$divide": [
                                {"$add": [{"$add": ["$total_p2m", "$total_p3m"]}, {"$multiply": [0.5, "$total_p3m"]}]},
                                {"$add": ["$total_p2a", "$total_p3a"]}
                            ]},
                            100
                        ]},
                        0
                    ]
                },
                # Three Point Rate (3PA / FGA)
                "three_pr": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_p3a", {"$add": ["$total_p2a", "$total_p3a"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Free Throw Rate (FTA / FGA)
                "ftr": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_p1a", {"$add": ["$total_p2a", "$total_p3a"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Assist Percentage (AST% = AST / possessions approximation)
                "ast_pct": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_assist", {"$add": ["$total_p2a", "$total_p3a"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Turnover Percentage (TO% = TO / possessions approximation)
                "tov_pct": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_to", {"$add": ["$total_p2a", "$total_p3a"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Steal Percentage (STL% = STL / possessions approximation)
                "stl_pct": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_st", {"$add": ["$total_p2a", "$total_p3a"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Block Percentage (BLK% = BLK / possessions approximation)
                "blk_pct": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", "$total_p3a"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_taps", {"$add": ["$total_p2a", "$total_p3a"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Offensive Rebound Percentage (approximation without team totals)
                "orb_pct": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_ro", "$total_rd"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_ro", {"$add": ["$total_ro", "$total_rd"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Defensive Rebound Percentage (approximation without team totals)
                "drb_pct": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_ro", "$total_rd"]}, 0]},
                        {"$multiply": [
                            {"$divide": ["$total_rd", {"$add": ["$total_ro", "$total_rd"]}]},
                            100
                        ]},
                        0
                    ]
                },
                # Usage Percentage (approximation: FGA + FTA*0.44 + TO + AST)
                "usage": {
                    "$cond": [
                        {"$gt": ["$games_played", 0]},
                        {"$multiply": [
                            {"$divide": [
                                {"$add": [
                                    {"$add": ["$total_p2a", "$total_p3a"]},
                                    {"$multiply": [0.44, "$total_p1a"]},
                                    "$total_to"
                                ]},
                                {"$multiply": ["$games_played", 100]}
                            ]},
                            100
                        ]},
                        0
                    ]
                },
                # Offensive Rating (approximation: points per 100 possessions)
                "orating": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_p2a", {"$add": ["$total_p3a", {"$multiply": [0.44, "$total_p1a"]}]}]}, 0]},
                        {"$multiply": [
                            {"$divide": [
                                "$total_pts",
                                {"$add": ["$total_p2a", {"$add": ["$total_p3a", {"$multiply": [0.44, "$total_p1a"]}]}]}
                            ]},
                            100
                        ]},
                        0
                    ]
                },
                # Defensive Rating (approximation: inverse of steal+block rate)
                "drating": {
                    "$cond": [
                        {"$gt": [{"$add": ["$total_st", "$total_taps"]}, 0]},
                        {"$subtract": [
                            120,
                            {"$multiply": [
                                {"$divide": [
                                    {"$add": ["$total_st", "$total_taps"]},
                                    "$games_played"
                                ]},
                                5
                            ]}
                        ]},
                        120
                    ]
                }
            }
        })

        # Stage 12: Sort by team and total points
        pipeline.append({
            "$sort": {
                "team_name": 1,
                "total_pts": -1
            }
        })

        return pipeline
