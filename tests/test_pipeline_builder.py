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


if __name__ == "__main__":
    unittest.main()
