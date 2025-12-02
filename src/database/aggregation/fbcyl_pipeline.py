"""MongoDB aggregation pipeline builder for FBCYL statistics."""

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
                "original_teams": "$stats.teams"
            }
        })

        # Stage 3: Unwind teams array to create one document per team
        pipeline.append({
            "$unwind": {
                "path": "$stats.teams",
                "includeArrayIndex": "teamIndex"
            }
        })

        # Stage 4: Add team info and opponent data
        pipeline.append({
            "$addFields": {
                "team_name": "$stats.teams.name",
                "team_id": "$stats.teams.teamIdExtern",
                "is_home": {"$eq": ["$teamIndex", 0]},
                "team_score": "$stats.teams.data.score",
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
                "points_scored": {"$sum": "$stats.teams.data.score"},
                "points_received": {"$sum": "$opponent_score_value"},

                # Field Goals
                "fg2_made": {"$sum": "$stats.teams.data.shotsOfTwoSuccessful"},
                "fg2_attempted": {"$sum": "$stats.teams.data.shotsOfTwoAttempted"},
                "fg3_made": {"$sum": "$stats.teams.data.shotsOfThreeSuccessful"},
                "fg3_attempted": {"$sum": "$stats.teams.data.shotsOfThreeAttempted"},
                "ft_made": {"$sum": "$stats.teams.data.shotsOfOneSuccessful"},
                "ft_attempted": {"$sum": "$stats.teams.data.shotsOfOneAttempted"},

                # Rebounds
                "total_rebounds": {"$sum": "$stats.teams.data.rebounds"},
                "rebounds_off": {"$sum": "$stats.teams.data.offensiveRebound"},
                "rebounds_def": {"$sum": "$stats.teams.data.defensiveRebound"},

                # Other stats
                "assists": {"$sum": "$stats.teams.data.assists"},
                "steals": {"$sum": "$stats.teams.data.steals"},
                "turnovers": {"$sum": "$stats.teams.data.lost"},
                "blocks": {"$sum": "$stats.teams.data.block"},
                "fouls": {"$sum": "$stats.teams.data.faults"},

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
                            "$stats.teams.data.shotsOfTwoAttempted",
                            "$stats.teams.data.shotsOfThreeAttempted",
                            {"$multiply": [0.44, "$stats.teams.data.shotsOfOneAttempted"]},
                            "$stats.teams.data.lost",
                            {"$multiply": [-1, "$stats.teams.data.offensiveRebound"]}
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
