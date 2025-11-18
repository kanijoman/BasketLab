"""MongoDB aggregation pipeline builder for team statistics."""

from typing import List, Dict
from .basic_stats import get_shooting_percentages, get_per_game_stats, get_possessions_calculation
from .advanced_stats import get_all_advanced_stats


class AggregationPipelineBuilder:
    """Builds MongoDB aggregation pipeline for team statistics."""

    @staticmethod
    def build_team_stats_pipeline() -> List[Dict]:
        """
        Build complete aggregation pipeline for team statistics.

        Returns:
            List of aggregation pipeline stages
        """
        pipeline = []

        # Phase 1: Add match-level fields
        pipeline.append(AggregationPipelineBuilder._add_match_level_fields())

        # Phase 2: Unwind teams array
        pipeline.append(AggregationPipelineBuilder._unwind_teams())

        # Phase 3: Project individual match data
        pipeline.append(AggregationPipelineBuilder._project_match_data())

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

        Returns:
            $addFields stage
        """
        return {
            "$addFields": {
                "team_0_off_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 0]}},
                "team_1_off_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 1]}},
                "team_0_def_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 0]}},
                "team_1_def_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 1]}},
                "localPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
                "awayPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}}
            }
        }

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
        return {
            "$project": {
                "team_id": "$BOXSCORE.TEAM.id",
                "team_name": "$BOXSCORE.TEAM.name",
                "points": {"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"},
                "opponent_points": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$awayPoints",
                        "else": "$localPoints"
                    }
                },
                "fg2_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2m"},
                "fg2_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2a"},
                "fg3_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3m"},
                "fg3_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3a"},
                "ft_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1m"},
                "ft_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1a"},
                "def_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.rd"},
                "off_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"},
                "opponent_def_rebounds": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_def_reb",
                        "else": "$team_0_def_reb"
                    }
                },
                "opponent_off_rebounds": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_off_reb",
                        "else": "$team_0_off_reb"
                    }
                },
                "assists": {"$toInt": "$BOXSCORE.TEAM.TOTAL.assist"},
                "possessions": get_possessions_calculation(),
                "steals": {"$toInt": "$BOXSCORE.TEAM.TOTAL.st"},
                "turnovers": {"$toInt": "$BOXSCORE.TEAM.TOTAL.to"},
                "blocks": {"$toInt": "$BOXSCORE.TEAM.TOTAL.bs"},
                "match_id": "$_id",
                "is_local": {"$eq": ["$teamIndex", 0]}
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
    def build_opponent_stats_pipeline() -> List[Dict]:
        """
        Build aggregation pipeline for opponent statistics grouped by team.
        This shows what each team's opponents have done against them.

        Returns:
            List of aggregation pipeline stages
        """
        pipeline = []

        # Phase 1: Add match-level fields including opponent stats
        pipeline.append(AggregationPipelineBuilder._add_opponent_match_level_fields())

        # Phase 2: Unwind teams array
        pipeline.append(AggregationPipelineBuilder._unwind_teams())

        # Phase 3: Project match data focusing on opponent stats
        pipeline.append(AggregationPipelineBuilder._project_opponent_match_data())

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
        This must be done before $unwind to have access to both teams' data.

        Returns:
            $addFields stage
        """
        return {
            "$addFields": {
                # Rebounds
                "team_0_off_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 0]}},
                "team_1_off_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 1]}},
                "team_0_def_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 0]}},
                "team_1_def_reb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 1]}},
                # Points
                "localPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
                "awayPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}},
                # FG2
                "team_0_fg2_made": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2m", 0]}},
                "team_1_fg2_made": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2m", 1]}},
                "team_0_fg2_att": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2a", 0]}},
                "team_1_fg2_att": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2a", 1]}},
                # FG3
                "team_0_fg3_made": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3m", 0]}},
                "team_1_fg3_made": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3m", 1]}},
                "team_0_fg3_att": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 0]}},
                "team_1_fg3_att": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 1]}},
                # FT
                "team_0_ft_made": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1m", 0]}},
                "team_1_ft_made": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1m", 1]}},
                "team_0_ft_att": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 0]}},
                "team_1_ft_att": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 1]}},
                # Assists
                "team_0_assists": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.assist", 0]}},
                "team_1_assists": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.assist", 1]}},
                # Steals
                "team_0_steals": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.st", 0]}},
                "team_1_steals": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.st", 1]}},
                # Turnovers
                "team_0_turnovers": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.to", 0]}},
                "team_1_turnovers": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.to", 1]}},
                # Blocks
                "team_0_blocks": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.bs", 0]}},
                "team_1_blocks": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.bs", 1]}}
            }
        }

    @staticmethod
    def _project_opponent_match_data() -> Dict:
        """
        Project opponent match data for each team.
        This inverts the perspective to show opponent statistics.

        Returns:
            $project stage
        """
        return {
            "$project": {
                "team_id": "$BOXSCORE.TEAM.id",
                "team_name": "$BOXSCORE.TEAM.name",
                # Opponent's points (what they scored against this team)
                "points": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$awayPoints",
                        "else": "$localPoints"
                    }
                },
                # This team's points (for reference)
                "opponent_points": {"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"},
                # Opponent's FG2 stats
                "fg2_made": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_fg2_made",
                        "else": "$team_0_fg2_made"
                    }
                },
                "fg2_attempts": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_fg2_att",
                        "else": "$team_0_fg2_att"
                    }
                },
                # Opponent's FG3 stats
                "fg3_made": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_fg3_made",
                        "else": "$team_0_fg3_made"
                    }
                },
                "fg3_attempts": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_fg3_att",
                        "else": "$team_0_fg3_att"
                    }
                },
                # Opponent's FT stats
                "ft_made": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_ft_made",
                        "else": "$team_0_ft_made"
                    }
                },
                "ft_attempts": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_ft_att",
                        "else": "$team_0_ft_att"
                    }
                },
                # Opponent's rebounds
                "def_rebounds": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_def_reb",
                        "else": "$team_0_def_reb"
                    }
                },
                "off_rebounds": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_off_reb",
                        "else": "$team_0_off_reb"
                    }
                },
                # This team's rebounds (for possessions calculation)
                "opponent_def_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.rd"},
                "opponent_off_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"},
                # Opponent's assists
                "assists": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_assists",
                        "else": "$team_0_assists"
                    }
                },
                # Calculate possessions
                "possessions": get_possessions_calculation(),
                # Opponent's steals
                "steals": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_steals",
                        "else": "$team_0_steals"
                    }
                },
                # Opponent's turnovers
                "turnovers": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_turnovers",
                        "else": "$team_0_turnovers"
                    }
                },
                # Opponent's blocks
                "blocks": {
                    "$cond": {
                        "if": {"$eq": ["$teamIndex", 0]},
                        "then": "$team_1_blocks",
                        "else": "$team_0_blocks"
                    }
                },
                "match_id": "$_id",
                "is_local": {"$eq": ["$teamIndex", 0]}
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
                "match_list": {"$push": "$match_id"}
            }
        }
