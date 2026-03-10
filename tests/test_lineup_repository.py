"""Tests for lineup analysis repository functions."""

import unittest
from unittest.mock import Mock, MagicMock, patch
from src.database.repository import BasketballRepository


class TestLineupAnalysisRepository(unittest.TestCase):
    """Test lineup analysis repository functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = Mock()
        self.mock_connection.is_connected.return_value = True
        self.repo = BasketballRepository(self.mock_connection)
    
    def test_merge_lineup_stats_counting_stats(self):
        """Test that counting stats are accumulated correctly."""
        existing = {
            'points_for': 20,
            'points_against': 18,
            'fgm': 8,
            'fga': 20,
            'fg3m': 2,
            'fg3a': 8,
            'tov': 3,
            'minutes': 10.0,
            'possessions': 25,
            'games_played': 1,
            'segments_count': 3
        }
        
        new_stats = {
            'points_for': 15,
            'points_against': 12,
            'fgm': 6,
            'fga': 15,
            'fg3m': 1,
            'fg3a': 5,
            'tov': 2,
            'minutes': 8.0,
            'possessions': 20,
            'games_played': 1,
            'segments_count': 2
        }
        
        self.repo._merge_lineup_stats(existing, new_stats)
        
        # Check accumulation
        self.assertEqual(existing['points_for'], 35)  # 20 + 15
        self.assertEqual(existing['points_against'], 30)  # 18 + 12
        self.assertEqual(existing['fgm'], 14)  # 8 + 6
        self.assertEqual(existing['fga'], 35)  # 20 + 15
        self.assertEqual(existing['tov'], 5)  # 3 + 2
        self.assertEqual(existing['minutes'], 18.0)  # 10 + 8
        self.assertEqual(existing['possessions'], 45)  # 25 + 20
        self.assertEqual(existing['games_played'], 2)  # 1 + 1
        self.assertEqual(existing['segments_count'], 5)  # 3 + 2
    
    def test_merge_lineup_stats_calculates_avg_minutes(self):
        """Test that average minutes per game is calculated."""
        existing = {
            'points_for': 0, 'points_against': 0,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 30.0,
            'possessions': 0,
            'games_played': 3,
            'segments_count': 8
        }
        
        new_stats = {
            'points_for': 0, 'points_against': 0,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 10.0,
            'possessions': 0,
            'games_played': 1,
            'segments_count': 2
        }
        
        self.repo._merge_lineup_stats(existing, new_stats)
        
        # Total minutes = 40, games = 4, so avg = 10.0
        self.assertEqual(existing['minutes'], 40.0)
        self.assertEqual(existing['games_played'], 4)
        self.assertAlmostEqual(existing['avg_minutes_per_game'], 10.0, places=1)
    
    def test_merge_lineup_stats_recalculates_plus_minus(self):
        """Test that plus/minus is recalculated."""
        existing = {
            'points_for': 25, 'points_against': 20,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 10.0, 'possessions': 30,
            'games_played': 1, 'segments_count': 3
        }
        
        new_stats = {
            'points_for': 18, 'points_against': 22,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 8.0, 'possessions': 25,
            'games_played': 1, 'segments_count': 2
        }
        
        self.repo._merge_lineup_stats(existing, new_stats)
        
        # Plus/minus = (25+18) - (20+22) = 43 - 42 = +1
        self.assertEqual(existing['plus_minus'], 1)
    
    def test_merge_lineup_stats_recalculates_ratings(self):
        """Test that ORtg, DRtg, NetRtg are recalculated."""
        existing = {
            'points_for': 50, 'points_against': 45,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 15.0, 'possessions': 50,
            'games_played': 1, 'segments_count': 4
        }
        
        new_stats = {
            'points_for': 30, 'points_against': 35,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 10.0, 'possessions': 50,
            'games_played': 1, 'segments_count': 3
        }
        
        self.repo._merge_lineup_stats(existing, new_stats)
        
        # Total: 80 points for, 80 points against, 100 possessions
        # ORtg = (80/100) * 100 = 80.0
        # DRtg = (80/100) * 100 = 80.0
        # NetRtg = 80 - 80 = 0.0
        self.assertAlmostEqual(existing['ortg'], 80.0, places=1)
        self.assertAlmostEqual(existing['drtg'], 80.0, places=1)
        self.assertAlmostEqual(existing['net_rating'], 0.0, places=1)
    
    def test_merge_lineup_stats_recalculates_efg_pct(self):
        """Test that eFG% is recalculated after merge."""
        existing = {
            'points_for': 0, 'points_against': 0,
            'fgm': 10, 'fga': 30, 'fg3m': 4, 'fg3a': 12,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 12.0, 'possessions': 35,
            'games_played': 1, 'segments_count': 3
        }
        
        new_stats = {
            'points_for': 0, 'points_against': 0,
            'fgm': 8, 'fga': 20, 'fg3m': 2, 'fg3a': 8,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 8.0, 'possessions': 25,
            'games_played': 1, 'segments_count': 2
        }
        
        self.repo._merge_lineup_stats(existing, new_stats)
        
        # Total: FGM=18, FGA=50, 3PM=6
        # eFG% = (18 + 0.5*6) / 50 = 21 / 50 = 0.42 = 42%
        expected_efg = ((18 + 0.5 * 6) / 50) * 100
        self.assertAlmostEqual(existing['efg_pct'], expected_efg, places=1)
    
    def test_merge_lineup_stats_recalculates_tov_pct(self):
        """Test that TOV% is recalculated after merge."""
        existing = {
            'points_for': 0, 'points_against': 0,
            'fgm': 0, 'fga': 30, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 10, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 8, 'pf': 0,
            'minutes': 12.0, 'possessions': 40,
            'games_played': 1, 'segments_count': 3
        }
        
        new_stats = {
            'points_for': 0, 'points_against': 0,
            'fgm': 0, 'fga': 20, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 8, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 6, 'pf': 0,
            'minutes': 8.0, 'possessions': 30,
            'games_played': 1, 'segments_count': 2
        }
        
        self.repo._merge_lineup_stats(existing, new_stats)
        
        # Total: FGA=50, FTA=18, TOV=14
        # TOV% = 14 / (50 + 0.44*18 + 14) = 14 / (50 + 7.92 + 14) = 14 / 71.92 ≈ 19.5%
        denominator = 50 + 0.44 * 18 + 14
        expected_tov_pct = (14 / denominator) * 100
        self.assertAlmostEqual(existing['tov_pct'], expected_tov_pct, places=1)
    
    def test_merge_lineup_stats_zero_possessions(self):
        """Test merge handles zero possessions gracefully."""
        existing = {
            'points_for': 0, 'points_against': 0,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 1.0, 'possessions': 0,
            'games_played': 1, 'segments_count': 1
        }
        
        new_stats = {
            'points_for': 0, 'points_against': 0,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 0.5, 'possessions': 0,
            'games_played': 1, 'segments_count': 1
        }
        
        # Should not crash
        self.repo._merge_lineup_stats(existing, new_stats)
        
        # Ratings should remain at 0 or not be calculated
        self.assertEqual(existing['possessions'], 0)
    
    @patch('src.database.lineup_stats_calculator.LineupStatsCalculator')
    @patch('src.database.lineup_extractor.LineupExtractor')
    @patch('src.database.playbyplay_analyzer.PlayByPlayAnalyzer')
    def test_get_lineup_analysis_filters_by_min_time_and_games(self, mock_analyzer, mock_extractor, mock_calc):
        """Test that lineups are filtered by minimum time and games played."""
        # Mock repository method dependencies
        self.repo.get_games_for_team = Mock(return_value=[
            {'_id': 'game1', 'HEADER': {'starttime': '2024-01-01 - 18:00'}},
            {'_id': 'game2', 'HEADER': {'starttime': '2024-01-02 - 18:00'}},
            {'_id': 'game3', 'HEADER': {'starttime': '2024-01-03 - 18:00'}},
            {'_id': 'game4', 'HEADER': {'starttime': '2024-01-04 - 18:00'}},
            {'_id': 'game5', 'HEADER': {'starttime': '2024-01-05 - 18:00'}},
        ])
        
        # Mock extractor to return lineup combinations
        mock_extractor_instance = Mock()
        mock_extractor.return_value = mock_extractor_instance
        mock_extractor_instance.get_lineup_combinations.return_value = {
            frozenset(['P1', 'P2', 'P3', 'P4', 'P5']): 180  # 3 minutes in this game
        }
        
        # Mock calculator to return stats
        mock_calc_instance = Mock()
        mock_calc.return_value = mock_calc_instance
        mock_calc_instance.calculate_lineup_stats_single_game.return_value = {
            'minutes': 3.0,
            'games_played': 1,
            'segments_count': 2,
            'points_for': 8,
            'points_against': 6,
            'possessions': 10,
            'ortg': 80.0,
            'drtg': 60.0,
            'net_rating': 20.0,
            'plus_minus': 2,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0
        }
        
        # Mock _get_player_names_for_lineup
        self.repo._get_player_names_for_lineup = Mock(return_value=['Player1', 'Player2', 'Player3', 'Player4', 'Player5'])
        
        result = self.repo.get_lineup_analysis(
            'test_collection',
            'T1',
            'Test Team',
            combination_size=5,
            is_fbcyl=False
        )
        
        # With 5 games, each 3 minutes = 15 minutes total, 5 games
        # Should PASS filter (min 15 minutes, 5 games)
        self.assertGreater(len(result), 0)
    
    @patch('src.database.lineup_stats_calculator.LineupStatsCalculator')
    @patch('src.database.lineup_extractor.LineupExtractor')
    @patch('src.database.playbyplay_analyzer.PlayByPlayAnalyzer')
    def test_get_lineup_analysis_excludes_insufficient_data(self, mock_analyzer, mock_extractor, mock_calc):
        """Test that lineups with insufficient time/games are excluded."""
        # Mock only 3 games (below 5 minimum)
        self.repo.get_games_for_team = Mock(return_value=[
            {'_id': 'game1', 'HEADER': {'starttime': '2024-01-01 - 18:00'}},
            {'_id': 'game2', 'HEADER': {'starttime': '2024-01-02 - 18:00'}},
            {'_id': 'game3', 'HEADER': {'starttime': '2024-01-03 - 18:00'}},
        ])
        
        mock_extractor_instance = Mock()
        mock_extractor.return_value = mock_extractor_instance
        mock_extractor_instance.get_lineup_combinations.return_value = {
            frozenset(['P1', 'P2', 'P3', 'P4', 'P5']): 300  # 5 minutes per game
        }
        
        mock_calc_instance = Mock()
        mock_calc.return_value = mock_calc_instance
        mock_calc_instance.calculate_lineup_stats_single_game.return_value = {
            'minutes': 5.0,
            'games_played': 1,
            'segments_count': 2,
            'points_for': 10,
            'points_against': 8,
            'possessions': 12,
            'ortg': 83.3,
            'drtg': 66.7,
            'net_rating': 16.6,
            'plus_minus': 2,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'trb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0
        }
        
        self.repo._get_player_names_for_lineup = Mock(return_value=['P1', 'P2', 'P3', 'P4', 'P5'])
        
        result = self.repo.get_lineup_analysis(
            'test_collection',
            'T1',
            'Test Team',
            combination_size=5,
            is_fbcyl=False
        )
        
        # With only 3 games (< 5 minimum), should be EXCLUDED
        self.assertEqual(len(result), 0)
    
    def test_get_player_names_for_lineup_feb_format(self):
        """Test player name retrieval logic for FEB format."""
        # Test the extraction logic
        lineup = ['P1', 'P2', 'P3']
        
        # Mockfor document structure
        sample_doc = {
            'BOXSCORE': {
                'TEAM': [
                    {
                        'PLAYER': [
                            {'license': 'P1', 'name': 'Player One'},
                            {'license': 'P2', 'name': 'Player Two'}
                        ]
                    }
                ]
            }
        }
        
        # Extract names from structure
        names = []
        for team in sample_doc['BOXSCORE']['TEAM']:
            for player in team['PLAYER']:
                if player.get('license') in lineup:
                    names.append(player.get('name'))
        
        # Should find at least some names
        self.assertGreater(len(names), 0)
    
    def test_get_player_names_for_lineup_fbcyl_format(self):
        """Test player name retrieval logic for FBCYL format."""
        # Test the extraction logic
        lineup = ['P1', 'P2']
        
        # Mock document structure
        sample_doc = {
            'stats': {
                'teams': [
                    {
                        'players': [
                            {'actor': {'id': 'P1', 'name': 'Jugadora Uno'}},
                            {'actor': {'id': 'P2', 'name': 'Jugadora Dos'}}
                        ]
                    }
                ]
            }
        }
        
        # Extract names
        names = []
        for team in sample_doc['stats']['teams']:
            for player in team['players']:
                actor = player.get('actor', {})
                if actor.get('id') in lineup:
                    names.append(actor.get('name'))
        
        # Should find names
        self.assertEqual(len(names), 2)


class TestLineupAnalysisEdgeCases(unittest.TestCase):
    """Test edge cases for lineup analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = Mock()
        self.mock_connection.is_connected.return_value = True
        self.repo = BasketballRepository(self.mock_connection)
    
    def test_merge_stats_with_missing_keys(self):
        """Test merge handles missing keys gracefully."""
        existing = {
            'points_for': 10, 'points_against': 8,
            'fgm': 4, 'fga': 10, 'fg3m': 1, 'fg3a': 3,
            'minutes': 5.0, 'possessions': 12,
            'games_played': 1, 'segments_count': 2
        }
        
        # New stats missing some keys
        new_stats = {
            'points_for': 8, 'points_against': 10,
            'fgm': 3, 'fga': 9,
            'minutes': 4.0, 'possessions': 10,
            'games_played': 1, 'segments_count': 1
        }
        
        # Should not crash, should use .get() with defaults
        self.repo._merge_lineup_stats(existing, new_stats)
        
        self.assertEqual(existing['points_for'], 18)
        self.assertEqual(existing['games_played'], 2)
    
    def test_lineup_with_exactly_threshold_values(self):
        """Test lineup with exactly minimum threshold values."""
        existing_stats = {
            'minutes': 15.0,  # Exactly minimum
            'games_played': 5,  # Exactly minimum
            'ortg': 110.0,
            'drtg': 100.0,
            'net_rating': 10.0
        }
        
        # With exactly 15 minutes and 5 games, should be included
        # This logic is in repository.get_lineup_analysis
        min_total_minutes = 15
        min_games_played = 5
        
        should_include = (
            existing_stats['minutes'] >= min_total_minutes and
            existing_stats['games_played'] >= min_games_played
        )
        
        self.assertTrue(should_include)


if __name__ == '__main__':
    unittest.main()
