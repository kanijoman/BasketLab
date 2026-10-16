"""Team and opponent aggregation pipeline builders."""

from typing import List, Dict, Optional
from .basic_stats import get_shooting_percentages, get_per_game_stats
from .advanced_stats import get_all_advanced_stats
from .possession_expr import DERIVED_OR_BOX, derived_or_box, possessions_per_40


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
        for purpose, field_data in mappings.items():
            path, team_0_name, team_1_name = field_data
            for index, name in enumerate((team_0_name, team_1_name)):
                if purpose in DERIVED_OR_BOX:
                    fields[name] = derived_or_box(*DERIVED_OR_BOX[purpose], index)
                else:
                    fields[name] = {"$toInt": {"$arrayElemAt": [path, index]}}

        for index in (0, 1):
            fields[f"team_{index}_poss"] = TeamStatsPipelineMixin._team_possessions(index)

        return {"$addFields": fields}

    @staticmethod
    def _team_possessions(index: int) -> Dict:
        """Possessions of team ``index`` per 40 minutes (stored exact count, else the box-score estimate)."""
        def box(field: str) -> Dict:
            return {"$toInt": {"$arrayElemAt": [f"$BOXSCORE.TEAM.TOTAL.{field}", index]}}

        return possessions_per_40(
            index,
            fga={"$add": [box("p2a"), box("p3a")]}, fta=box("p1a"),
            orb=derived_or_box(*DERIVED_OR_BOX["off_reb"], index), tov=derived_or_box(*DERIVED_OR_BOX["turnovers"], index),
        )

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
                "def_rebounds": builder._conditional_field("team_0_def_reb", "team_1_def_reb"),
                "off_rebounds": builder._conditional_field("team_0_off_reb", "team_1_off_reb"),
                "opponent_def_rebounds": builder._opponent_conditional_field("team_0_def_reb", "team_1_def_reb"),
                "opponent_off_rebounds": builder._opponent_conditional_field("team_0_off_reb", "team_1_off_reb"),
                # Opponent counting stats — kept here so they survive this $project
                # and are available to build_per_game_raw_pipeline() downstream.
                "opponent_fg2_made":      builder._opponent_conditional_field("team_0_fg2_made",  "team_1_fg2_made"),
                "opponent_fg2_attempts":  builder._opponent_conditional_field("team_0_fg2_att",   "team_1_fg2_att"),
                "opponent_fg3_made":      builder._opponent_conditional_field("team_0_fg3_made",  "team_1_fg3_made"),
                "opponent_fg3_attempts":  builder._opponent_conditional_field("team_0_fg3_att",   "team_1_fg3_att"),
                "opponent_ft_made":       builder._opponent_conditional_field("team_0_ft_made",   "team_1_ft_made"),
                "opponent_ft_attempts":   builder._opponent_conditional_field("team_0_ft_att",    "team_1_ft_att"),
                "opponent_assists":       builder._opponent_conditional_field("team_0_assists",   "team_1_assists"),
                "opponent_steals":        builder._opponent_conditional_field("team_0_steals",    "team_1_steals"),
                "opponent_turnovers":     builder._opponent_conditional_field("team_0_turnovers", "team_1_turnovers"),
                "opponent_blocks":        builder._opponent_conditional_field("team_0_blocks",    "team_1_blocks"),
                "assists": {"$toInt": "$BOXSCORE.TEAM.TOTAL.assist"},
                "possessions": builder._conditional_field("team_0_poss", "team_1_poss"),
                "opponent_possessions": builder._opponent_conditional_field("team_0_poss", "team_1_poss"),
                "steals": {"$toInt": "$BOXSCORE.TEAM.TOTAL.st"},
                "turnovers": builder._conditional_field("team_0_turnovers", "team_1_turnovers"),
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
