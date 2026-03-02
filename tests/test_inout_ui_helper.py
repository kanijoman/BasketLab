"""Tests for IN/OUT analysis UI helper functions."""

import unittest
from unittest.mock import Mock, MagicMock
from src.ui.inout_stats_helper import InOutStatsHelper


class TestInOutStatsHelper(unittest.TestCase):
    """Test IN/OUT statistics helper functions."""
    
    def test_get_display_fields_returns_correct_structure(self):
        """Test that display fields have correct structure."""
        fields = InOutStatsHelper.get_display_fields()
        
        self.assertIsInstance(fields, list)
        self.assertGreater(len(fields), 0)
        
        # Check first field structure
        label, key, reverse = fields[0]
        self.assertIsInstance(label, str)
        self.assertIsInstance(key, str)
        self.assertIsInstance(reverse, bool)
    
    def test_get_display_fields_includes_key_metrics(self):
        """Test that key metrics are included in display fields."""
        fields = InOutStatsHelper.get_display_fields()
        field_keys = [key for label, key, reverse in fields]
        
        expected_metrics = ['offensive_rating', 'defensive_rating', 'net_rating', 
                           'efg_percentage', 'turnover_rate']
        
        for metric in expected_metrics:
            self.assertIn(metric, field_keys)
    
    def test_calculate_advanced_metrics_returns_dict(self):
        """Test that calculate_advanced_metrics returns a dictionary."""
        mock_calculator = Mock()
        # Mock the actual method called: calculate_single_match_stats
        mock_calculator.calculate_single_match_stats.return_value = {
            'offensive_rating': 110.0,
            'defensive_rating': 105.0,
            'net_rating': 5.0,
            'pace': 95.0,
            'efg_percentage': 52.5,
            'turnover_rate': 12.0,
            'offensive_rebound_rate': 30.0,
            'free_throw_rate': 0.25,
            'assist_rate': 60.0,
            'steal_rate': 8.0,
            'block_rate': 5.0
        }
        
        stats = {
            'points_for': 100,
            'points_against': 95,
            'fgm_2': 25,
            'fga_2': 40,
            'fgm_3': 8,
            'fga_3': 20,
            'ftm': 18,
            'fta': 20,
            'orb': 10,
            'drb': 30,
            'ast': 22,
            'stl': 8,
            'blk': 4,
            'tov': 12,
            'opp_fgm_2': 22,
            'opp_fga_2': 45,
            'opp_fgm_3': 7,
            'opp_fga_3': 22,
            'opp_ftm': 13,
            'opp_fta': 18,
            'opp_orb': 8,
            'opp_drb': 32,
            'opp_ast': 20,
            'opp_stl': 7,
            'opp_blk': 3,
            'opp_tov': 14,
            'minutes': 40.0
        }
        
        result = InOutStatsHelper.calculate_advanced_metrics(
            mock_calculator, stats, "Team A"
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('offensive_rating', result)
        self.assertIn('defensive_rating', result)
    
    def test_populate_comparison_table_updates_table(self):
        """Test that populate_comparison_table correctly populates table."""
        mock_table = Mock()
        mock_table.setRowCount = Mock()
        mock_table.setItem = Mock()
        
        adv1 = {'offensive_rating': 110.0, 'defensive_rating': 105.0}
        adv2 = {'offensive_rating': 108.0, 'defensive_rating': 107.0}
        display_fields = [
            ('Rating Ofensivo', 'offensive_rating', False),
            ('Rating Defensivo', 'defensive_rating', True)
        ]
        
        InOutStatsHelper.populate_comparison_table(
            mock_table, adv1, adv2, display_fields
        )
        
        # Should set row count
        mock_table.setRowCount.assert_called_once_with(2)
        
        # Should set items (4 per row: label, val1, val2, delta)
        self.assertEqual(mock_table.setItem.call_count, 8)
    
    def test_build_team_dict_creates_correct_structure(self):
        """Test that build_team_dict creates correct data structure."""
        stats = {
            'points_for': 100,
            'points_against': 95,
            'fga_2': 40,
            'fgm_2': 20,
            'fga_3': 20,
            'fgm_3': 8,
            'fta': 25,
            'ftm': 20,
            'orb': 10,
            'drb': 30,
            'ast': 22,
            'stl': 8,
            'blk': 4,
            'tov': 12,
            'pf': 18,
            'minutes': 40,
            'games': 1
        }
        team_name = "Test Team"
        
        result = InOutStatsHelper.build_team_dict(stats, team_name)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], team_name)
        # build_team_dict transforms keys: points_for -> pts, fgm_2 -> p2m, etc.
        self.assertEqual(result['pts'], 100)
        self.assertEqual(result['p2m'], 20)
        self.assertEqual(result['p2a'], 40)
        self.assertEqual(result['assist'], 22)
    
    def test_build_opp_dict_creates_opponent_structure(self):
        """Test that build_opp_dict creates opponent data structure."""
        stats = {
            'points_against': 95,
            'opp_fga_2': 45,
            'opp_fgm_2': 18,
            'opp_fga_3': 25,
            'opp_fgm_3': 9,
            'opp_fta': 20,
            'opp_ftm': 15,
            'opp_orb': 8,
            'opp_drb': 32,
            'opp_ast': 20,
            'opp_stl': 7,
            'opp_blk': 3,
            'opp_tov': 14,
            'opp_pf': 20
        }
        
        # build_opp_dict only takes stats parameter (no team_name)
        result = InOutStatsHelper.build_opp_dict(stats)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], 'OPP')
        # build_opp_dict transforms keys: points_against -> pts, opp_fgm_2 -> p2m, etc.
        self.assertEqual(result['pts'], 95)
        self.assertEqual(result['p2m'], 18)
        self.assertEqual(result['assist'], 20)
        # Should not contain original keys
        self.assertNotIn('opp_fgm_2', result)
        self.assertNotIn('points_against', result)


if __name__ == '__main__':
    unittest.main()
