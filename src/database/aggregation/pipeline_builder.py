"""MongoDB aggregation pipeline builder for team statistics."""

from typing import List, Dict
from .basic_stats import get_shooting_percentages, get_per_game_stats, get_possessions_calculation
from .advanced_stats import get_all_advanced_stats


class AggregationPipelineBuilder:
    """Builds MongoDB aggregation pipeline for team statistics."""

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
                "opponent_possessions": {"$sum": "$opponent_possessions"},
                "match_list": {"$push": "$match_id"}
            }
        }

