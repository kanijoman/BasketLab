"""MongoDB aggregation pipeline builder for team statistics."""

from typing import List, Dict, Optional
from .basic_stats import get_shooting_percentages, get_per_game_stats, get_possessions_calculation
from .advanced_stats import get_all_advanced_stats


class AggregationPipelineBuilder:
    """Builds MongoDB aggregation pipeline for team statistics."""

    # Result filter constants
    RESULT_WON = 'won'
    RESULT_LOST = 'lost'
    VALID_RESULT_FILTERS = {RESULT_WON, RESULT_LOST}

    @staticmethod
    def _conditional_field(team_0_field: str, team_1_field: str) -> Dict:
        """
        Create a conditional expression that selects between team 0 and team 1 fields.

        Args:
            team_0_field: Field name for team 0 (local)
            team_1_field: Field name for team 1 (away)

        Returns:
            MongoDB $cond expression
        """
        return {
            "$cond": {
                "if": {"$eq": ["$teamIndex", 0]},
                "then": f"${team_0_field}",
                "else": f"${team_1_field}"
            }
        }

    @staticmethod
    def _opponent_conditional_field(team_0_field: str, team_1_field: str) -> Dict:
        """
        Create a conditional expression for opponent fields (inverted logic).
        When teamIndex=0 (local), get team 1 (away) data.

        Args:
            team_0_field: Field name for team 0
            team_1_field: Field name for team 1

        Returns:
            MongoDB $cond expression
        """
        return {
            "$cond": {
                "if": {"$eq": ["$teamIndex", 0]},
                "then": f"${team_1_field}",
                "else": f"${team_0_field}"
            }
        }

    @staticmethod
    def _calculate_possessions(fg2_att: Dict, fg3_att: Dict, ft_att: Dict, turnovers: Dict, off_reb: Dict) -> Dict:
        """
        Calculate possessions adjusted for game duration (including overtime).
        Formula: (FGA2 + FGA3 + (0.45 * FTA) + TO - OREB) * (40 / total_minutes)

        Args:
            fg2_att: Field or expression for FG2 attempts
            fg3_att: Field or expression for FG3 attempts
            ft_att: Field or expression for FT attempts
            turnovers: Field or expression for turnovers
            off_reb: Field or expression for offensive rebounds

        Returns:
            MongoDB expression for possessions calculation
        """
        raw_possessions = {
            "$add": [
                fg2_att,
                fg3_att,
                {"$multiply": [0.45, ft_att]},
                turnovers,
                {"$multiply": [-1, off_reb]}
            ]
        }

        # Calculate total minutes based on number of quarters
        num_quarters = {"$size": "$HEADER.QUARTERS.QUARTER"}
        total_minutes = {
            "$add": [
                40,
                {"$multiply": [
                    {"$subtract": [num_quarters, 4]},
                    5
                ]}
            ]
        }

        # Adjust possessions: raw_possessions * (40 / total_minutes)
        return {
            "$multiply": [
                raw_possessions,
                {"$divide": [40, total_minutes]}
            ]
        }

    @staticmethod
    def _create_team_field_mappings() -> Dict[str, tuple]:
        """
        Create mappings for team fields that need to be extracted.

        Returns:
            Dictionary mapping field purpose to (path, team_0_name, team_1_name)
        """
        return {
            "off_reb": ("$BOXSCORE.TEAM.TOTAL.ro", "team_0_off_reb", "team_1_off_reb"),
            "def_reb": ("$BOXSCORE.TEAM.TOTAL.rd", "team_0_def_reb", "team_1_def_reb"),
            "fg2_made": ("$BOXSCORE.TEAM.TOTAL.p2m", "team_0_fg2_made", "team_1_fg2_made"),
            "fg2_att": ("$BOXSCORE.TEAM.TOTAL.p2a", "team_0_fg2_att", "team_1_fg2_att"),
            "fg3_made": ("$BOXSCORE.TEAM.TOTAL.p3m", "team_0_fg3_made", "team_1_fg3_made"),
            "fg3_att": ("$BOXSCORE.TEAM.TOTAL.p3a", "team_0_fg3_att", "team_1_fg3_att"),
            "ft_made": ("$BOXSCORE.TEAM.TOTAL.p1m", "team_0_ft_made", "team_1_ft_made"),
            "ft_att": ("$BOXSCORE.TEAM.TOTAL.p1a", "team_0_ft_att", "team_1_ft_att"),
            "assists": ("$BOXSCORE.TEAM.TOTAL.assist", "team_0_assists", "team_1_assists"),
            "steals": ("$BOXSCORE.TEAM.TOTAL.st", "team_0_steals", "team_1_steals"),
            "turnovers": ("$BOXSCORE.TEAM.TOTAL.to", "team_0_turnovers", "team_1_turnovers"),
            "blocks": ("$BOXSCORE.TEAM.TOTAL.bs", "team_0_blocks", "team_1_blocks")
        }

    @staticmethod
    def build_team_stats_pipeline(date_filter: Dict = None, venue_filter: bool = None, result_filter: Optional[str] = None) -> List[Dict]:
        """
        Build complete aggregation pipeline for team statistics.

        Args:
            date_filter: Optional MongoDB date filter dict with datetime object
                        Example: {"$gte": datetime(2024, 1, 1)}
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)

        Returns:
            List of aggregation pipeline stages

        Raises:
            ValueError: If result_filter is not None, 'won', or 'lost'
        """
        # Validate result_filter
        if result_filter is not None and result_filter not in AggregationPipelineBuilder.VALID_RESULT_FILTERS:
            raise ValueError(f"Invalid result_filter: {result_filter}. Must be 'won', 'lost', or None")

        pipeline = []

        # Phase 0: Add date conversion and filter if provided
        if date_filter:
            # First, add a field that converts the string date to a date object
            pipeline.append({
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$HEADER.starttime",
                            "format": "%d-%m-%Y - %H:%M",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            })
            # Then filter using the parsed date
            pipeline.append({"$match": {"parsedDate": date_filter}})

        # Phase 1: Add match-level fields
        pipeline.append(AggregationPipelineBuilder._add_match_level_fields())

        # Phase 2: Unwind teams array
        pipeline.append(AggregationPipelineBuilder._unwind_teams())

        # Phase 3: Project individual match data
        pipeline.append(AggregationPipelineBuilder._project_match_data())

        # Phase 3.5: Filter by venue if specified
        if venue_filter is not None:
            pipeline.append({"$match": {"is_local": venue_filter}})

        # Phase 3.6: Filter by result if specified
        if result_filter is not None:
            if result_filter == 'won':
                pipeline.append({"$match": {"won": True}})
            elif result_filter == 'lost':
                pipeline.append({"$match": {"won": False}})

        # Phase 4: Group by team
        pipeline.append(AggregationPipelineBuilder._group_by_team())

        # Phase 5: Calculate statistics
        pipeline.append(AggregationPipelineBuilder._calculate_statistics())

        # Phase 6: Sort results
        pipeline.append({"$sort": {"points_per_game": -1}})

        return pipeline

    @staticmethod
    def _add_match_level_fields() -> Dict:
        """
        Add match-level fields for easier access.
        Extracts data from both teams before unwinding.

        Returns:
            $addFields stage
        """
        fields = {
            "localPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
            "awayPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}}
        }

        # Add all team field mappings
        mappings = AggregationPipelineBuilder._create_team_field_mappings()
        for field_data in mappings.values():
            path, team_0_name, team_1_name = field_data
            fields[team_0_name] = {"$toInt": {"$arrayElemAt": [path, 0]}}
            fields[team_1_name] = {"$toInt": {"$arrayElemAt": [path, 1]}}

        return {"$addFields": fields}

    @staticmethod
    def _unwind_teams() -> Dict:
        """
        Unwind teams array to get one document per team per match.

        Returns:
            $unwind stage
        """
        return {
            "$unwind": {
                "path": "$BOXSCORE.TEAM",
                "includeArrayIndex": "teamIndex"
            }
        }

    @staticmethod
    def _project_match_data() -> Dict:
        """
        Project individual match data for each team.

        Returns:
            $project stage
        """
        builder = AggregationPipelineBuilder

        # Calculate opponent possessions
        opponent_poss = builder._calculate_possessions(
            builder._opponent_conditional_field("team_0_fg2_att", "team_1_fg2_att"),
            builder._opponent_conditional_field("team_0_fg3_att", "team_1_fg3_att"),
            builder._opponent_conditional_field("team_0_ft_att", "team_1_ft_att"),
            builder._opponent_conditional_field("team_0_turnovers", "team_1_turnovers"),
            builder._opponent_conditional_field("team_0_off_reb", "team_1_off_reb")
        )

        return {
            "$project": {
                "team_id": "$BOXSCORE.TEAM.id",
                "team_name": "$BOXSCORE.TEAM.name",
                "points": {"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"},
                "opponent_points": builder._conditional_field("awayPoints", "localPoints"),
                "fg2_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2m"},
                "fg2_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2a"},
                "fg3_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3m"},
                "fg3_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3a"},
                "ft_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1m"},
                "ft_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1a"},
                "def_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.rd"},
                "off_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"},
                "opponent_def_rebounds": builder._opponent_conditional_field("team_0_def_reb", "team_1_def_reb"),
                "opponent_off_rebounds": builder._opponent_conditional_field("team_0_off_reb", "team_1_off_reb"),
                "assists": {"$toInt": "$BOXSCORE.TEAM.TOTAL.assist"},
                "possessions": get_possessions_calculation(),
                "opponent_possessions": opponent_poss,
                "steals": {"$toInt": "$BOXSCORE.TEAM.TOTAL.st"},
                "turnovers": {"$toInt": "$BOXSCORE.TEAM.TOTAL.to"},
                "blocks": {"$toInt": "$BOXSCORE.TEAM.TOTAL.bs"},
                "match_id": "$_id",
                "is_local": {"$eq": ["$teamIndex", 0]},
                "won": {"$gt": [{"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"}, builder._conditional_field("awayPoints", "localPoints")]}
            }
        }

    @staticmethod
    def _group_by_team() -> Dict:
        """
        Group data by team to aggregate season statistics.

        Returns:
            $group stage
        """
        return {
            "$group": {
                "_id": "$team_id",
                "team_name": {"$first": "$team_name"},
                "total_games": {"$sum": 1},
                "games_home": {"$sum": {"$cond": ["$is_local", 1, 0]}},
                "games_away": {"$sum": {"$cond": ["$is_local", 0, 1]}},
                "points_scored": {"$sum": "$points"},
                "points_received": {"$sum": "$opponent_points"},
                "fg2_made": {"$sum": "$fg2_made"},
                "fg2_attempted": {"$sum": "$fg2_attempts"},
                "fg3_made": {"$sum": "$fg3_made"},
                "fg3_attempted": {"$sum": "$fg3_attempts"},
                "ft_made": {"$sum": "$ft_made"},
                "ft_attempted": {"$sum": "$ft_attempts"},
                "rebounds_def": {"$sum": "$def_rebounds"},
                "rebounds_off": {"$sum": "$off_rebounds"},
                "opponent_rebounds_def": {"$sum": "$opponent_def_rebounds"},
                "opponent_rebounds_off": {"$sum": "$opponent_off_rebounds"},
                "assists": {"$sum": "$assists"},
                "steals": {"$sum": "$steals"},
                "turnovers": {"$sum": "$turnovers"},
                "blocks": {"$sum": "$blocks"},
                "total_possessions": {"$sum": "$possessions"},
                "opponent_possessions": {"$sum": "$opponent_possessions"},
                "match_list": {"$push": "$match_id"}
            }
        }

    @staticmethod
    def _calculate_statistics() -> Dict:
        """
        Calculate all derived statistics.

        Returns:
            $addFields stage with all calculated statistics
        """
        stats = {
            "total_rebounds": {"$add": ["$rebounds_def", "$rebounds_off"]}
        }

        # Add basic stats
        stats.update(get_per_game_stats())
        stats.update(get_shooting_percentages())

        # Add advanced stats
        stats.update(get_all_advanced_stats())

        return {"$addFields": stats}

    @staticmethod
    def build_opponent_stats_pipeline(date_filter: Dict = None, venue_filter: bool = None, result_filter: Optional[str] = None) -> List[Dict]:
        """
        Build aggregation pipeline for opponent statistics grouped by team.
        This shows what each team's opponents have done against them.

        Args:
            date_filter: Optional MongoDB date filter dict with datetime object
                        Example: {"$gte": datetime(2024, 1, 1)}
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)

        Returns:
            List of aggregation pipeline stages

        Raises:
            ValueError: If result_filter is not None, 'won', or 'lost'
        """
        # Validate result_filter
        if result_filter is not None and result_filter not in AggregationPipelineBuilder.VALID_RESULT_FILTERS:
            raise ValueError(f"Invalid result_filter: {result_filter}. Must be 'won', 'lost', or None")

        pipeline = []

        # Phase 0: Add date conversion and filter if provided
        if date_filter:
            # First, add a field that converts the string date to a date object
            pipeline.append({
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$HEADER.starttime",
                            "format": "%d-%m-%Y - %H:%M",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            })
            # Then filter using the parsed date
            pipeline.append({"$match": {"parsedDate": date_filter}})

        # Phase 1: Add match-level fields including opponent stats
        pipeline.append(AggregationPipelineBuilder._add_opponent_match_level_fields())

        # Phase 2: Unwind teams array
        pipeline.append(AggregationPipelineBuilder._unwind_teams())

        # Phase 3: Project match data focusing on opponent stats
        pipeline.append(AggregationPipelineBuilder._project_opponent_match_data())

        # Phase 3.5: Filter by venue if specified
        if venue_filter is not None:
            pipeline.append({"$match": {"is_local": venue_filter}})

        # Phase 3.6: Filter by result if specified
        if result_filter is not None:
            if result_filter == AggregationPipelineBuilder.RESULT_WON:
                pipeline.append({"$match": {"won": True}})
            elif result_filter == AggregationPipelineBuilder.RESULT_LOST:
                pipeline.append({"$match": {"won": False}})

        # Phase 4: Group by team (aggregating their opponents' stats)
        pipeline.append(AggregationPipelineBuilder._group_opponent_by_team())

        # Phase 5: Calculate opponent statistics
        pipeline.append(AggregationPipelineBuilder._calculate_statistics())

        # Phase 6: Sort results
        pipeline.append({"$sort": {"points_per_game": -1}})

        return pipeline

    @staticmethod
    def _add_opponent_match_level_fields() -> Dict:
        """
        Add match-level fields including all opponent statistics.
        Reuses the same logic as _add_match_level_fields since we need all teams' data.

        Returns:
            $addFields stage
        """
        # Opponent stats need the same fields as team stats
        return AggregationPipelineBuilder._add_match_level_fields()

    @staticmethod
    def _project_opponent_match_data() -> Dict:
        """
        Project opponent match data for each team.
        This inverts the perspective to show opponent statistics.

        Returns:
            $project stage
        """
        builder = AggregationPipelineBuilder

        # Calculate opponent's possessions
        opponent_poss = builder._calculate_possessions(
            builder._opponent_conditional_field("team_0_fg2_att", "team_1_fg2_att"),
            builder._opponent_conditional_field("team_0_fg3_att", "team_1_fg3_att"),
            builder._opponent_conditional_field("team_0_ft_att", "team_1_ft_att"),
            builder._opponent_conditional_field("team_0_turnovers", "team_1_turnovers"),
            builder._opponent_conditional_field("team_0_off_reb", "team_1_off_reb")
        )

        return {
            "$project": {
                "team_id": "$BOXSCORE.TEAM.id",
                "team_name": "$BOXSCORE.TEAM.name",
                # Opponent's points (what they scored against this team)
                "points": builder._opponent_conditional_field("localPoints", "awayPoints"),
                # This team's points (for reference)
                "opponent_points": {"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"},
                # Opponent's shooting stats
                "fg2_made": builder._opponent_conditional_field("team_0_fg2_made", "team_1_fg2_made"),
                "fg2_attempts": builder._opponent_conditional_field("team_0_fg2_att", "team_1_fg2_att"),
                "fg3_made": builder._opponent_conditional_field("team_0_fg3_made", "team_1_fg3_made"),
                "fg3_attempts": builder._opponent_conditional_field("team_0_fg3_att", "team_1_fg3_att"),
                "ft_made": builder._opponent_conditional_field("team_0_ft_made", "team_1_ft_made"),
                "ft_attempts": builder._opponent_conditional_field("team_0_ft_att", "team_1_ft_att"),
                # Opponent's rebounds
                "def_rebounds": builder._opponent_conditional_field("team_0_def_reb", "team_1_def_reb"),
                "off_rebounds": builder._opponent_conditional_field("team_0_off_reb", "team_1_off_reb"),
                # This team's rebounds (for rate calculations)
                "opponent_def_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.rd"},
                "opponent_off_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"},
                # Opponent's other stats
                "assists": builder._opponent_conditional_field("team_0_assists", "team_1_assists"),
                "possessions": opponent_poss,
                # Team's possessions (for DER calculation)
                "opponent_possessions": get_possessions_calculation(),
                "steals": builder._opponent_conditional_field("team_0_steals", "team_1_steals"),
                "turnovers": builder._opponent_conditional_field("team_0_turnovers", "team_1_turnovers"),
                "blocks": builder._opponent_conditional_field("team_0_blocks", "team_1_blocks"),
                "match_id": "$_id",
                "is_local": {"$eq": ["$teamIndex", 0]},
                "won": {"$gt": [{"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"}, builder._opponent_conditional_field("localPoints", "awayPoints")]}
            }
        }

    @staticmethod
    def _group_opponent_by_team() -> Dict:
        """
        Group opponent data by team to aggregate opponent season statistics.

        Returns:
            $group stage
        """
        return {
            "$group": {
                "_id": "$team_id",
                "team_name": {"$first": "$team_name"},
                "total_games": {"$sum": 1},
                "games_home": {"$sum": {"$cond": ["$is_local", 1, 0]}},
                "games_away": {"$sum": {"$cond": ["$is_local", 0, 1]}},
                "points_scored": {"$sum": "$points"},
                "points_received": {"$sum": "$opponent_points"},
                "fg2_made": {"$sum": "$fg2_made"},
                "fg2_attempted": {"$sum": "$fg2_attempts"},
                "fg3_made": {"$sum": "$fg3_made"},
                "fg3_attempted": {"$sum": "$fg3_attempts"},
                "ft_made": {"$sum": "$ft_made"},
                "ft_attempted": {"$sum": "$ft_attempts"},
                "rebounds_def": {"$sum": "$def_rebounds"},
                "rebounds_off": {"$sum": "$off_rebounds"},
                "opponent_rebounds_def": {"$sum": "$opponent_def_rebounds"},
                "opponent_rebounds_off": {"$sum": "$opponent_off_rebounds"},
                "assists": {"$sum": "$assists"},
                "steals": {"$sum": "$steals"},
                "turnovers": {"$sum": "$turnovers"},
                "blocks": {"$sum": "$blocks"},
                "total_possessions": {"$sum": "$possessions"},
                "opponent_possessions": {"$sum": "$opponent_possessions"},
                "match_list": {"$push": "$match_id"}
            }
        }


    @staticmethod
    def build_team_matches_timeline_pipeline(team_name: str) -> List[Dict]:
        """
        Build a pipeline to get chronological match data for a team.

        This pipeline retrieves all matches for a specific team in chronological order,
        including opponent information and match statistics. Used for temporal evolution analysis.

        Args:
            team_name: Name of the team to get match data for

        Returns:
            MongoDB aggregation pipeline as a list of stages

        Example output format:
            [
                {
                    "date": datetime,
                    "opponent": "Team B",
                    "team_data": {...},  # BOXSCORE.TEAM.TOTAL for team
                    "opponent_data": {...},  # BOXSCORE.TEAM.TOTAL for opponent
                    "is_local": True
                },
                ...
            ]
        """
        return [
            # Stage 1: Parse date field
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$HEADER.starttime",
                            "format": "%d-%m-%Y - %H:%M",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            },
            # Stage 2: Filter matches where team participated
            {
                "$match": {
                    "HEADER.TEAM.name": team_name
                }
            },
            # Stage 3: Sort by date ascending (oldest to newest)
            {"$sort": {"parsedDate": 1}},
            # Stage 4: Capture both teams' data BEFORE unwinding
            # This avoids the $arrayElemAt error after $unwind
            {
                "$addFields": {
                    "team0_name": {"$arrayElemAt": ["$HEADER.TEAM.name", 0]},
                    "team1_name": {"$arrayElemAt": ["$HEADER.TEAM.name", 1]},
                    "team0_data": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL", 0]},
                    "team1_data": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL", 1]}
                }
            },
            # Stage 5: Unwind teams to identify which index is our team
            {
                "$unwind": {
                    "path": "$BOXSCORE.TEAM",
                    "includeArrayIndex": "teamIndex"
                }
            },
            # Stage 6: Filter to keep only the selected team's row
            {
                "$match": {
                    "BOXSCORE.TEAM.name": team_name
                }
            },
            # Stage 7: Project final structure with opponent data
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
                    "team_data": "$BOXSCORE.TEAM.TOTAL",
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

    @staticmethod
    def build_player_stats_pipeline(date_filter: Dict = None, venue_filter: bool = None, result_filter: Optional[str] = None) -> List[Dict]:
        """
        Build aggregation pipeline for player statistics across all matches.

        Args:
            date_filter: Optional date filter (e.g., {"$gte": datetime, "$lt": datetime})
            venue_filter: Optional venue filter (True=home, False=away, None=all)
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
            if result_filter == AggregationPipelineBuilder.RESULT_WON:
                pipeline.append({"$match": {"won": True}})
            elif result_filter == AggregationPipelineBuilder.RESULT_LOST:
                pipeline.append({"$match": {"won": False}})

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
                "$project": {
                    "player_id": "$BOXSCORE.TEAM.PLAYER.id",
                    "player_name": "$BOXSCORE.TEAM.PLAYER.name",
                    "team_name": "$BOXSCORE.TEAM.TOTAL.name",
                    "team_id": "$BOXSCORE.TEAM.TOTAL.id",
                    "date": "$parsedDate",
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
            },
            # Stage 5: Filter players who actually played (minutes > 0)
            {
                "$match": {
                    "minutes": {"$gt": 0}
                }
            },
            # Stage 6: Group by player
            {
                "$group": {
                    "_id": {
                        "player_id": "$player_id",
                        "player_name": "$player_name",
                        "team_name": "$team_name",
                        "team_id": "$team_id"
                    },
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
                    "player_name": "$_id.player_name",
                    "team_name": "$_id.team_name",
                    "team_id": "$_id.team_id",
                    "games_played": "$games_played",
                    "total_minutes": "$total_minutes",
                    "minutes_per_game": {
                        "$cond": [
                            {"$gt": ["$games_played", 0]},
                            {"$divide": ["$total_minutes", {"$multiply": ["$games_played", 60]}]},
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
                    }
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
            # Stage 1: Parse date field (FBCYL uses 'time' field at root level)
            # Format: "Oct 4, 2025 7:00:00 PM" - extract just the date part
            {
                "$addFields": {
                    "timeParts": {"$split": ["$time", " "]}
                }
            },
            # Stage 2: Build the date string from parts: month, day, year
            {
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
            },
            # Stage 3: Parse the date string to date object
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$dateString",
                            "format": "%b %d, %Y",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            },
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

