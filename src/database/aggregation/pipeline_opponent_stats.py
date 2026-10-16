"""Opponent-stats and team-timeline pipeline builders."""

from typing import List, Dict, Optional
from .basic_stats import get_shooting_percentages, get_per_game_stats  # noqa: F401
from .advanced_stats import get_all_advanced_stats  # noqa: F401
from .pipeline_team_stats import TeamStatsPipelineMixin


class OpponentStatsPipelineMixin:
    """Opponent-stats and team-timeline pipeline builders."""

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
        pipeline.append(OpponentStatsPipelineMixin._add_opponent_match_level_fields())

        # Phase 2: Unwind teams array
        pipeline.append(TeamStatsPipelineMixin._unwind_teams())

        # Phase 3: Project match data focusing on opponent stats
        pipeline.append(OpponentStatsPipelineMixin._project_opponent_match_data())

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
        pipeline.append(OpponentStatsPipelineMixin._group_opponent_by_team())

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
                "opponent_def_rebounds": builder._conditional_field("team_0_def_reb", "team_1_def_reb"),
                "opponent_off_rebounds": builder._conditional_field("team_0_off_reb", "team_1_off_reb"),
                # Opponent's other stats
                "assists": builder._opponent_conditional_field("team_0_assists", "team_1_assists"),
                "possessions": builder._opponent_conditional_field("team_0_poss", "team_1_poss"),
                # Team's possessions (for DER calculation)
                "opponent_possessions": builder._conditional_field("team_0_poss", "team_1_poss"),
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
