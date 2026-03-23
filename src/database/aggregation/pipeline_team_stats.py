"""Team and opponent aggregation pipeline builders."""

from typing import List, Dict, Optional
from .basic_stats import get_shooting_percentages, get_per_game_stats, get_possessions_calculation
from .advanced_stats import get_all_advanced_stats


class TeamStatsPipelineMixin:
    """Mixin providing team and opponent stats pipeline builders, plus shared helpers."""

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
        if result_filter is not None and result_filter not in TeamStatsPipelineMixin.VALID_RESULT_FILTERS:
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
        pipeline.append(TeamStatsPipelineMixin._add_match_level_fields())

        # Phase 2: Unwind teams array
        pipeline.append(TeamStatsPipelineMixin._unwind_teams())

        # Phase 3: Project individual match data
        pipeline.append(TeamStatsPipelineMixin._project_match_data())

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
        pipeline.append(TeamStatsPipelineMixin._group_by_team())

        # Phase 5: Calculate statistics
        pipeline.append(TeamStatsPipelineMixin._calculate_statistics())

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
        mappings = TeamStatsPipelineMixin._create_team_field_mappings()
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
        builder = TeamStatsPipelineMixin

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
                    "possessions": 1,
                    # Advanced computed fields
                    "oer_game": 1, "der_game": 1, "net_game": 1,
                    "efg_pct_game": 1, "ts_pct_game": 1, "tov_pct_game": 1,
                    # Opponent (rival) raw fields for defensive consistency
                    "opp_fg3_made":     TeamStatsPipelineMixin._opponent_conditional_field("team_0_fg3_made",  "team_1_fg3_made"),
                    "opp_fg3_attempts": TeamStatsPipelineMixin._opponent_conditional_field("team_0_fg3_att",   "team_1_fg3_att"),
                    "opp_fg2_made":     TeamStatsPipelineMixin._opponent_conditional_field("team_0_fg2_made",  "team_1_fg2_made"),
                    "opp_fg2_attempts": TeamStatsPipelineMixin._opponent_conditional_field("team_0_fg2_att",   "team_1_fg2_att"),
                    "opp_ft_made":      TeamStatsPipelineMixin._opponent_conditional_field("team_0_ft_made",   "team_1_ft_made"),
                    "opp_ft_attempts":  TeamStatsPipelineMixin._opponent_conditional_field("team_0_ft_att",    "team_1_ft_att"),
                    "opp_assists":      TeamStatsPipelineMixin._opponent_conditional_field("team_0_assists",   "team_1_assists"),
                    "opp_steals":       TeamStatsPipelineMixin._opponent_conditional_field("team_0_steals",    "team_1_steals"),
                    "opp_turnovers":    TeamStatsPipelineMixin._opponent_conditional_field("team_0_turnovers", "team_1_turnovers"),
                    "opp_blocks":       TeamStatsPipelineMixin._opponent_conditional_field("team_0_blocks",    "team_1_blocks"),
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
        ]
        return pipeline

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
        if result_filter is not None and result_filter not in TeamStatsPipelineMixin.VALID_RESULT_FILTERS:
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
        pipeline.append(TeamStatsPipelineMixin._add_opponent_match_level_fields())

        # Phase 2: Unwind teams array
        pipeline.append(TeamStatsPipelineMixin._unwind_teams())

        # Phase 3: Project match data focusing on opponent stats
        pipeline.append(TeamStatsPipelineMixin._project_opponent_match_data())

        # Phase 3.5: Filter by venue if specified
        if venue_filter is not None:
            pipeline.append({"$match": {"is_local": venue_filter}})

        # Phase 3.6: Filter by result if specified
        if result_filter is not None:
            if result_filter == TeamStatsPipelineMixin.RESULT_WON:
                pipeline.append({"$match": {"won": True}})
            elif result_filter == TeamStatsPipelineMixin.RESULT_LOST:
                pipeline.append({"$match": {"won": False}})

        # Phase 4: Group by team (aggregating their opponents' stats)
        pipeline.append(TeamStatsPipelineMixin._group_opponent_by_team())

        # Phase 5: Calculate opponent statistics
        pipeline.append(TeamStatsPipelineMixin._calculate_statistics())

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
        return TeamStatsPipelineMixin._add_match_level_fields()

    @staticmethod
    def _project_opponent_match_data() -> Dict:
        """
        Project opponent match data for each team.
        This inverts the perspective to show opponent statistics.

        Returns:
            $project stage
        """
        builder = TeamStatsPipelineMixin

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

