"""Tests for AggregationPipelineBuilder and FBCYLPipelineBuilder.

These are pure structural tests — pipelines are lists of dicts, no DB needed.
"""

import unittest
from datetime import datetime

from src.database.aggregation.pipeline_builder import AggregationPipelineBuilder
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder


class TestAggregationPipelineBuilderStructure(unittest.TestCase):
    """Verify that AggregationPipelineBuilder returns well-formed pipelines."""

    # ------------------------------------------------------------------ #
    # build_team_stats_pipeline
    # ------------------------------------------------------------------ #

    def test_team_stats_pipeline_returns_list(self):
        result = AggregationPipelineBuilder.build_team_stats_pipeline()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_team_stats_pipeline_stages_are_dicts(self):
        result = AggregationPipelineBuilder.build_team_stats_pipeline()
        for stage in result:
            self.assertIsInstance(stage, dict, f"Stage is not a dict: {stage}")

    def test_team_stats_pipeline_has_match_with_date_filter(self):
        """$match is only added when filters are applied."""
        date_filter = {"$gte": datetime(2024, 1, 1)}
        result = AggregationPipelineBuilder.build_team_stats_pipeline(date_filter=date_filter)
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$match", stage_keys)

    def test_team_stats_pipeline_no_filter_has_no_match_or_has_match(self):
        """Without filters pipeline is valid regardless of whether $match is present."""
        result = AggregationPipelineBuilder.build_team_stats_pipeline()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        result = AggregationPipelineBuilder.build_team_stats_pipeline()
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$group", stage_keys)

    def test_team_stats_pipeline_with_date_filter(self):
        date_filter = {"$gte": datetime(2024, 1, 1)}
        result = AggregationPipelineBuilder.build_team_stats_pipeline(date_filter=date_filter)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_team_stats_pipeline_with_home_venue_filter(self):
        result = AggregationPipelineBuilder.build_team_stats_pipeline(venue_filter=True)
        self.assertIsInstance(result, list)

    def test_team_stats_pipeline_with_away_venue_filter(self):
        result = AggregationPipelineBuilder.build_team_stats_pipeline(venue_filter=False)
        self.assertIsInstance(result, list)

    def test_team_stats_pipeline_with_result_filter_won(self):
        result = AggregationPipelineBuilder.build_team_stats_pipeline(
            result_filter=AggregationPipelineBuilder.RESULT_WON
        )
        self.assertIsInstance(result, list)

    def test_team_stats_pipeline_with_result_filter_lost(self):
        result = AggregationPipelineBuilder.build_team_stats_pipeline(
            result_filter=AggregationPipelineBuilder.RESULT_LOST
        )
        self.assertIsInstance(result, list)

    def test_team_stats_pipeline_invalid_result_filter_raises(self):
        with self.assertRaises((ValueError, KeyError)):
            AggregationPipelineBuilder.build_team_stats_pipeline(result_filter="invalid")

    def test_team_stats_pipeline_group_has_id(self):
        result = AggregationPipelineBuilder.build_team_stats_pipeline()
        group_stages = [s["$group"] for s in result if "$group" in s]
        self.assertTrue(len(group_stages) > 0)
        for group in group_stages:
            self.assertIn("_id", group, "$group stage must have _id")

    # ------------------------------------------------------------------ #
    # build_opponent_stats_pipeline
    # ------------------------------------------------------------------ #

    def test_opponent_stats_pipeline_returns_list(self):
        result = AggregationPipelineBuilder.build_opponent_stats_pipeline()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_opponent_stats_pipeline_contains_group(self):
        result = AggregationPipelineBuilder.build_opponent_stats_pipeline()
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$group", stage_keys)

    # ------------------------------------------------------------------ #
    # build_player_stats_pipeline
    # ------------------------------------------------------------------ #

    def test_player_stats_pipeline_returns_list(self):
        result = AggregationPipelineBuilder.build_player_stats_pipeline()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_player_stats_pipeline_contains_unwind(self):
        result = AggregationPipelineBuilder.build_player_stats_pipeline()
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$unwind", stage_keys)

    def test_player_stats_pipeline_with_all_filters(self):
        date_filter = {"$gte": datetime(2025, 1, 1)}
        result = AggregationPipelineBuilder.build_player_stats_pipeline(
            date_filter=date_filter,
            venue_filter=True,
            result_filter="won",
        )
        self.assertIsInstance(result, list)

    # ------------------------------------------------------------------ #
    # build_team_matches_timeline_pipeline
    # ------------------------------------------------------------------ #

    def test_timeline_pipeline_returns_list(self):
        result = AggregationPipelineBuilder.build_team_matches_timeline_pipeline("Equipo A")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_timeline_pipeline_contains_match_stage(self):
        result = AggregationPipelineBuilder.build_team_matches_timeline_pipeline("Equipo A")
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$match", stage_keys)

    # ------------------------------------------------------------------ #
    # Result filter constants
    # ------------------------------------------------------------------ #

    def test_result_filter_constants_defined(self):
        self.assertEqual(AggregationPipelineBuilder.RESULT_WON, "won")
        self.assertEqual(AggregationPipelineBuilder.RESULT_LOST, "lost")
        self.assertIn("won", AggregationPipelineBuilder.VALID_RESULT_FILTERS)
        self.assertIn("lost", AggregationPipelineBuilder.VALID_RESULT_FILTERS)


class TestFBCYLPipelineBuilderStructure(unittest.TestCase):
    """Verify that FBCYLPipelineBuilder returns well-formed pipelines."""

    # ------------------------------------------------------------------ #
    # build_team_stats_pipeline
    # ------------------------------------------------------------------ #

    def test_team_stats_pipeline_returns_list(self):
        result = FBCYLPipelineBuilder.build_team_stats_pipeline()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_team_stats_pipeline_stages_are_dicts(self):
        result = FBCYLPipelineBuilder.build_team_stats_pipeline()
        for stage in result:
            self.assertIsInstance(stage, dict)

    def test_team_stats_pipeline_contains_match(self):
        """$match is present when a date filter forces it."""
        date_filter = {"$gte": datetime(2024, 1, 1)}
        result = FBCYLPipelineBuilder.build_team_stats_pipeline(date_filter=date_filter)
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$match", stage_keys)

    def test_team_stats_pipeline_no_filter_valid(self):
        result = FBCYLPipelineBuilder.build_team_stats_pipeline()
        self.assertIsInstance(result, list)

    def test_team_stats_pipeline_contains_group(self):
        result = FBCYLPipelineBuilder.build_team_stats_pipeline()
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$group", stage_keys)

    def test_team_stats_pipeline_group_has_id(self):
        result = FBCYLPipelineBuilder.build_team_stats_pipeline()
        group_stages = [s["$group"] for s in result if "$group" in s]
        for group in group_stages:
            self.assertIn("_id", group)

    def test_team_stats_pipeline_with_date_filter(self):
        date_filter = {"$gte": datetime(2024, 1, 1)}
        result = FBCYLPipelineBuilder.build_team_stats_pipeline(date_filter=date_filter)
        self.assertIsInstance(result, list)

    def test_team_stats_pipeline_with_venue_filter(self):
        result = FBCYLPipelineBuilder.build_team_stats_pipeline(venue_filter=True)
        self.assertIsInstance(result, list)

    def test_team_stats_pipeline_with_result_filter_won(self):
        result = FBCYLPipelineBuilder.build_team_stats_pipeline(result_filter="won")
        self.assertIsInstance(result, list)

    # ------------------------------------------------------------------ #
    # build_opponent_stats_pipeline
    # ------------------------------------------------------------------ #

    def test_opponent_stats_pipeline_returns_list(self):
        result = FBCYLPipelineBuilder.build_opponent_stats_pipeline()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    # ------------------------------------------------------------------ #
    # build_player_stats_pipeline
    # ------------------------------------------------------------------ #

    def test_player_stats_pipeline_returns_list(self):
        result = FBCYLPipelineBuilder.build_player_stats_pipeline()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_player_stats_pipeline_contains_unwind(self):
        result = FBCYLPipelineBuilder.build_player_stats_pipeline()
        stage_keys = [list(s.keys())[0] for s in result]
        self.assertIn("$unwind", stage_keys)


class TestPipelineBuilderSymmetry(unittest.TestCase):
    """Both builders should expose the same public method surface."""

    SHARED_METHODS = [
        "build_team_stats_pipeline",
        "build_opponent_stats_pipeline",
        "build_player_stats_pipeline",
    ]

    def test_feb_builder_has_all_shared_methods(self):
        for method in self.SHARED_METHODS:
            self.assertTrue(
                hasattr(AggregationPipelineBuilder, method),
                f"AggregationPipelineBuilder missing: {method}",
            )

    def test_fbcyl_builder_has_all_shared_methods(self):
        for method in self.SHARED_METHODS:
            self.assertTrue(
                hasattr(FBCYLPipelineBuilder, method),
                f"FBCYLPipelineBuilder missing: {method}",
            )

    def test_both_team_pipelines_have_same_top_level_structure(self):
        """Both pipelines must have $group. $match only required with filters."""
        feb_stages = {list(s.keys())[0] for s in AggregationPipelineBuilder.build_team_stats_pipeline()}
        fbcyl_stages = {list(s.keys())[0] for s in FBCYLPipelineBuilder.build_team_stats_pipeline()}
        for required in ("$group",):
            self.assertIn(required, feb_stages, f"FEB pipeline missing {required}")
            self.assertIn(required, fbcyl_stages, f"FBCYL pipeline missing {required}")


class TestPerGameRawPipelineStructure(unittest.TestCase):
    """Structural tests for build_per_game_raw_pipeline.

    Ensures the pipeline shape is correct and that opponent counting fields
    (opp_assists, opp_steals, etc.) are declared in the $project stage.
    These were previously null because team_0_*/team_1_* scalars were dropped
    by the earlier _project_match_data() $project before they could be used.
    """

    def _get_pipeline(self):
        return AggregationPipelineBuilder.build_per_game_raw_pipeline()

    def test_returns_list_of_dicts(self):
        pipeline = self._get_pipeline()
        self.assertIsInstance(pipeline, list)
        self.assertGreater(len(pipeline), 0)
        for stage in pipeline:
            self.assertIsInstance(stage, dict)

    def test_has_no_group_stage(self):
        """Per-game pipeline must NOT group — one document per team per game."""
        pipeline = self._get_pipeline()
        stage_keys = [list(s.keys())[0] for s in pipeline]
        self.assertNotIn("$group", stage_keys)

    def test_opp_counting_fields_declared_regression(self):
        """Regression: opp_assists/steals/turnovers/blocks/fg*_made must be declared
        in the $project stage as simple field references ("$opponent_*"), NOT as
        _opponent_conditional_field() expressions that reference team_0_*/team_1_*
        which are already gone by that point in the pipeline.
        """
        pipeline = self._get_pipeline()
        # Find the $project stage that declares opp_assists
        project_stage = None
        for stage in pipeline:
            if "$project" in stage and "opp_assists" in stage["$project"]:
                project_stage = stage["$project"]
                break
        self.assertIsNotNone(
            project_stage,
            "No $project stage declares opp_assists — field will always be null"
        )
        required_fields = [
            "opp_assists", "opp_steals", "opp_turnovers", "opp_blocks",
            "opp_fg2_made", "opp_fg2_attempts",
            "opp_fg3_made", "opp_fg3_attempts",
            "opp_ft_made",  "opp_ft_attempts",
        ]
        for field in required_fields:
            self.assertIn(
                field, project_stage,
                f"$project stage missing '{field}' — badge will be absent"
            )
            # Must be a plain string reference, not a conditional expression
            self.assertIsInstance(
                project_stage[field], str,
                f"'{field}' should be a '$...' string reference, not an expression"
            )


class TestFBCYLPhantomPlayerFilter(unittest.TestCase):
    """Regression: FBCYL phantom-player validation.

    A player inscribed to a match but who never actually played can appear in
    the raw data with ``timePlayed = 40`` (full game) and all activity stats
    equal to zero.  Both FBCYL pipelines must exclude such records.
    """

    # ------------------------------------------------------------------
    # fbcyl_pipeline.py — Stage 5 $match
    # ------------------------------------------------------------------

    def _get_player_filter_stage(self):
        """Return the Stage-5 $match dict from FBCYLPipelineBuilder."""
        pipeline = FBCYLPipelineBuilder.build_player_stats_pipeline()
        for stage in pipeline:
            if "$match" in stage:
                mc = stage["$match"]
                if "stats.teams.players.timePlayed" in str(mc):
                    return mc
        return None

    def test_player_pipeline_filter_stage_exists(self):
        stage = self._get_player_filter_stage()
        self.assertIsNotNone(stage, "No $match stage filtering timePlayed found")

    def test_player_pipeline_filter_excludes_phantom_via_expr(self):
        """Stage 5 must contain a $nor condition that catches the phantom
        pattern (timePlayed==40 AND all stats==0)."""
        stage = self._get_player_filter_stage()
        self.assertIsNotNone(stage)
        stage_str = str(stage)
        self.assertIn(
            "$nor", stage_str,
            "Stage 5 $match must use $nor to exclude phantom players "
            "(timePlayed==40, all stats==0); missing $nor"
        )

    # ------------------------------------------------------------------
    # fbcyl_per_game_pipeline.py — Stage 4 $match
    # ------------------------------------------------------------------

    def _get_per_game_filter_stage(self):
        from database.aggregation.fbcyl_per_game_pipeline import (
            build_fbcyl_player_per_game_pipeline,
        )
        pipeline = build_fbcyl_player_per_game_pipeline()
        for stage in pipeline:
            if "$match" in stage:
                mc = stage["$match"]
                if "timePlayed" in str(mc):
                    return mc
        return None

    def test_per_game_pipeline_filter_excludes_phantom_via_expr(self):
        """Per-game pipeline Stage 4 must also use $nor to exclude phantom
        players."""
        stage = self._get_per_game_filter_stage()
        self.assertIsNotNone(stage, "No $match stage filtering timePlayed found in per-game pipeline")
        stage_str = str(stage)
        self.assertIn(
            "$nor", stage_str,
            "Per-game pipeline $match must use $nor to exclude phantom players; missing $nor"
        )


class TestFBCYLPlayerStatsShootingFields(unittest.TestCase):
    """Regression: FBCYL player stats pipeline must expose standard-named
    shooting fields (true_shooting, efg_percentage, three_point_rate,
    free_throw_rate) so the PlayerStatsPage advanced tab renders data.

    Bug: the pipeline computed these as 'ts', 'efg', 'three_pr', 'ftr' — the
    FEB-compatible names expected by the frontend were never added.
    """

    _REQUIRED = (
        "true_shooting",
        "efg_percentage",
        "three_point_rate",
        "free_throw_rate",
    )

    def _pipeline_str(self):
        return str(FBCYLPipelineBuilder.build_player_stats_pipeline())

    def test_pipeline_returns_list(self):
        pipeline = FBCYLPipelineBuilder.build_player_stats_pipeline()
        self.assertIsInstance(pipeline, list)
        self.assertGreater(len(pipeline), 0)

    def test_true_shooting_alias_present_regression(self):
        """Regression: 'true_shooting' must appear in the FBCYL player stats
        pipeline so the TS% column is populated for FBCYL players."""
        self.assertIn(
            "'true_shooting'", self._pipeline_str(),
            "FBCYL player pipeline missing 'true_shooting' alias — TS% will be empty"
        )

    def test_efg_percentage_alias_present_regression(self):
        """Regression: 'efg_percentage' must appear so the eFG% column renders."""
        self.assertIn(
            "'efg_percentage'", self._pipeline_str(),
            "FBCYL player pipeline missing 'efg_percentage' alias — eFG% will be empty"
        )

    def test_three_point_rate_alias_present_regression(self):
        """Regression: 'three_point_rate' must appear so the 3Pr column renders."""
        self.assertIn(
            "'three_point_rate'", self._pipeline_str(),
            "FBCYL player pipeline missing 'three_point_rate' alias — 3Pr will be empty"
        )

    def test_free_throw_rate_alias_present_regression(self):
        """Regression: 'free_throw_rate' must appear so the FTr column renders."""
        self.assertIn(
            "'free_throw_rate'", self._pipeline_str(),
            "FBCYL player pipeline missing 'free_throw_rate' alias — FTr will be empty"
        )

    def test_all_four_shooting_fields_present(self):
        """All four standard-named shooting fields must appear in the pipeline."""
        pipeline_str = self._pipeline_str()
        for field in self._REQUIRED:
            self.assertIn(
                f"'{field}'", pipeline_str,
                f"FBCYL player pipeline missing '{field}'"
            )




class TestPerPlayerPerGamePipelineStructure(unittest.TestCase):
    """Structural tests for build_per_player_per_game_pipeline.

    Verifies that the per-game player pipeline declares the fields required
    for CVBadge rendering (pllss, minutes in minutes not seconds, and advanced
    shooting metrics).
    """

    def _get_pipeline(self):
        return AggregationPipelineBuilder.build_per_player_per_game_pipeline()

    def test_returns_list_of_dicts(self):
        pipeline = self._get_pipeline()
        self.assertIsInstance(pipeline, list)
        self.assertGreater(len(pipeline), 0)
        for stage in pipeline:
            self.assertIsInstance(stage, dict)

    def test_has_no_group_stage(self):
        """Per-game pipeline must NOT group — one document per player per game."""
        pipeline = self._get_pipeline()
        stage_keys = [list(s.keys())[0] for s in pipeline]
        self.assertNotIn("$group", stage_keys)

    def test_pllss_field_in_project_stage_regression(self):
        """Regression: pllss must be declared in the $project stage so that the
        CVBadge for +/- is computed.  Was absent before this fix."""
        pipeline = self._get_pipeline()
        project_stage = None
        for stage in pipeline:
            if "$project" in stage and "player_id" in stage["$project"]:
                project_stage = stage["$project"]
                break
        self.assertIsNotNone(project_stage, "No $project stage found in per-player pipeline")
        self.assertIn(
            "pllss", project_stage,
            "pllss not in $project stage — +/- CVBadge will never render"
        )

    def test_minutes_divides_by_60_regression(self):
        """Regression: FEB stores minutes as seconds in the raw 'min' field.
        The pipeline must divide by 60 so minutes_per_game is in minutes, not
        in the range ~1500-1800 (seconds per 25-30 minute game)."""
        pipeline = self._get_pipeline()
        project_stage = None
        for stage in pipeline:
            if "$project" in stage and "player_id" in stage["$project"]:
                project_stage = stage["$project"]
                break
        self.assertIsNotNone(project_stage)
        minutes_expr = project_stage.get("minutes")
        self.assertIsInstance(
            minutes_expr, dict,
            "minutes in $project must be an expression (dict), not a plain field ref"
        )
        # The expression must contain a $divide operator somewhere
        expr_str = str(minutes_expr)
        self.assertIn(
            "$divide", expr_str,
            "minutes expression must include $divide to convert seconds→minutes"
        )

    def test_advanced_addfields_stage_present(self):
        """The advanced computed fields (efg_pct_game, ts_pct_game, etc.) must be
        declared in a $addFields stage after the $match stage."""
        pipeline = self._get_pipeline()
        addfields_keys: set = set()
        for stage in pipeline:
            if "$addFields" in stage:
                addfields_keys.update(stage["$addFields"].keys())
        for field in ("efg_pct_game", "ts_pct_game", "ftr_game", "three_pr_game", "tov_pct_game"):
            self.assertIn(
                field, addfields_keys,
                f"Advanced field '{field}' missing from per-player per-game pipeline"
            )


if __name__ == "__main__":
    unittest.main()
