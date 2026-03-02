"""Tests for IN/OUT analysis repository functions."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from src.database.repository import BasketballRepository


class TestPlayerIndividualStats(unittest.TestCase):
    """Test individual player statistics extraction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = Mock()
        self.mock_connection.is_connected.return_value = True
        self.repo = BasketballRepository(self.mock_connection)
    
    def test_initialize_player_individual_stats(self):
        """Test that player stats are initialized with correct keys."""
        stats = self.repo._initialize_player_individual_stats()
        
        expected_keys = ['points', 'fgm_2', 'fga_2', 'fgm_3', 'fga_3', 
                        'ftm', 'fta', 'orb', 'drb', 'ast', 'stl', 
                        'blk', 'tov', 'pf', 'minutes', 'games']
        
        for key in expected_keys:
            self.assertIn(key, stats)
            self.assertEqual(stats[key], 0)
    
    def test_process_fbcyl_player_action_made_2pt(self):
        """Test FBCYL 2PT made action processing."""
        action = {'actorId': '12345', 'move': 'Canasta de 2'}
        stats = {'points': 0, 'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'ast': 0, 
                'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0}
        
        self.repo._process_fbcyl_player_action(action, '12345', stats)
        
        self.assertEqual(stats['points'], 2)
        self.assertEqual(stats['fgm_2'], 1)
        self.assertEqual(stats['fga_2'], 1)
    
    def test_process_fbcyl_player_action_missed_3pt(self):
        """Test FBCYL 3PT missed action processing."""
        action = {'actorId': '12345', 'move': 'Intento fallado de 3'}
        stats = {'points': 0, 'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'ast': 0, 
                'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0}
        
        self.repo._process_fbcyl_player_action(action, '12345', stats)
        
        self.assertEqual(stats['points'], 0)
        self.assertEqual(stats['fgm_3'], 0)
        self.assertEqual(stats['fga_3'], 1)
    
    def test_process_fbcyl_player_action_free_throw(self):
        """Test FBCYL free throw processing."""
        action = {'actorId': '12345', 'move': 'Canasta de 1'}
        stats = {'points': 0, 'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'ast': 0, 
                'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0}
        
        self.repo._process_fbcyl_player_action(action, '12345', stats)
        
        self.assertEqual(stats['points'], 1)
        self.assertEqual(stats['ftm'], 1)
        self.assertEqual(stats['fta'], 1)
    
    def test_process_fbcyl_player_action_ignores_other_player(self):
        """Test that actions from other players are ignored."""
        action = {'actorId': '99999', 'move': 'Canasta de 2'}
        stats = {'points': 0, 'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0, 'ast': 0, 
                'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0}
        
        self.repo._process_fbcyl_player_action(action, '12345', stats)
        
        # Stats should remain unchanged
        self.assertEqual(stats['points'], 0)
        self.assertEqual(stats['fgm_2'], 0)
    
    def test_process_feb_shot_made_2pt(self):
        """Test FEB 2PT made shot processing."""
        stats = {'points': 0, 'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0}
        text = 'TIRO DE 2 ANOTADO'
        
        self.repo._process_feb_shot(text, stats)
        
        self.assertEqual(stats['points'], 2)
        self.assertEqual(stats['fgm_2'], 1)
        self.assertEqual(stats['fga_2'], 1)
    
    def test_process_feb_shot_missed_3pt(self):
        """Test FEB 3PT missed shot processing."""
        stats = {'points': 0, 'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0}
        text = 'TIRO DE 3 FALLADO'
        
        self.repo._process_feb_shot(text, stats)
        
        self.assertEqual(stats['points'], 0)
        self.assertEqual(stats['fgm_3'], 0)
        self.assertEqual(stats['fga_3'], 1)
    
    def test_process_feb_free_throw_made(self):
        """Test FEB free throw made processing."""
        stats = {'points': 0, 'ftm': 0, 'fta': 0}
        text = 'TIRO DE 1 ANOTADO'
        
        self.repo._process_feb_free_throw(text, stats)
        
        self.assertEqual(stats['points'], 1)
        self.assertEqual(stats['ftm'], 1)
        self.assertEqual(stats['fta'], 1)
    
    def test_process_feb_free_throw_missed(self):
        """Test FEB free throw missed processing."""
        stats = {'points': 0, 'ftm': 0, 'fta': 0}
        text = 'TIRO DE 1 FALLADO'
        
        self.repo._process_feb_free_throw(text, stats)
        
        self.assertEqual(stats['points'], 0)
        self.assertEqual(stats['ftm'], 0)
        self.assertEqual(stats['fta'], 1)
    
    def test_process_feb_rebound_offensive(self):
        """Test FEB offensive rebound detection."""
        stats = {'orb': 0, 'drb': 0}
        context = {'last_shot_team': 'team1', 'player_team': 'team1'}
        
        self.repo._process_feb_rebound(stats, context)
        
        self.assertEqual(stats['orb'], 1)
        self.assertEqual(stats['drb'], 0)
        self.assertIsNone(context['last_shot_team'])
    
    def test_process_feb_rebound_defensive(self):
        """Test FEB defensive rebound detection."""
        stats = {'orb': 0, 'drb': 0}
        context = {'last_shot_team': 'team2', 'player_team': 'team1'}
        
        self.repo._process_feb_rebound(stats, context)
        
        self.assertEqual(stats['orb'], 0)
        self.assertEqual(stats['drb'], 1)
        self.assertIsNone(context['last_shot_team'])
    
    def test_calculate_possessions_from_stats(self):
        """Test possessions calculation formula."""
        stats = {
            'fga_2': 40,
            'fga_3': 20,  # Total FGA = 60
            'fta': 20,    # 0.45 * 20 = 9
            'tov': 15,
            'orb': 10
        }
        # Expected: 60 + 9 + 15 - 10 = 74
        
        possessions = self.repo._calculate_possessions_from_stats(stats)
        
        self.assertEqual(possessions, 74.0)
    
    def test_normalize_player_stats_per_100poss(self):
        """Test per-100-possession normalization."""
        stats = {
            'points': 20,
            'fgm_2': 5,
            'fga_2': 10,
            'fgm_3': 2,
        }
        possessions = 50.0  # Team had 50 possessions
        
        normalized = self.repo._normalize_player_stats_per_100poss(stats, possessions)
        
        # 20 points in 50 possessions = 40 points per 100
        self.assertEqual(normalized['points'], 40.0)
        # 5 FGM in 50 possessions = 10 FGM per 100
        self.assertEqual(normalized['fgm_2'], 10.0)
    
    def test_accumulate_player_individual_stats(self):
        """Test accumulation of player stats across games."""
        total = {'points': 10, 'fgm_2': 3, 'ast': 2}
        game = {'points': 15, 'fgm_2': 5, 'ast': 4}
        
        self.repo._accumulate_player_individual_stats(total, game)
        
        self.assertEqual(total['points'], 25)
        self.assertEqual(total['fgm_2'], 8)
        self.assertEqual(total['ast'], 6)


class TestProcessGameWithTeammate(unittest.TestCase):
    """Test game processing for teammate analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = Mock()
        self.mock_connection.is_connected.return_value = True
        self.repo = BasketballRepository(self.mock_connection)
    
    @patch('src.database.playbyplay_analyzer.PlayByPlayAnalyzer')
    @patch('src.database.inout_repository_helper.InOutRepositoryHelper')
    def test_process_game_returns_none_if_players_not_found(self, mock_helper_class, mock_analyzer_class):
        """Test that None is returned when players are not found together."""
        mock_player_info = Mock()
        mock_player_info.all_found = False
        mock_helper_class.find_players_in_game.return_value = mock_player_info
        
        game = {'_id': '123'}
        result = self.repo._process_game_with_teammate(game, 'p1', 'p2', False)
        
        self.assertIsNone(result)
    
    @patch('src.database.playbyplay_analyzer.InOutStatsCalculator')
    @patch('src.database.playbyplay_analyzer.PlayByPlayAnalyzer')
    @patch('src.database.inout_repository_helper.InOutRepositoryHelper')
    def test_process_game_returns_stats_when_players_found_together(self, mock_helper_class, mock_analyzer_class, mock_calculator_class):
        """Test game processing when players are found together."""
        # Setup mocks
        mock_player_info = Mock()
        mock_player_info.all_found = True
        mock_player_info.player1_actor_id = 'actor1'
        mock_player_info.player2_actor_id = 'actor2'
        mock_player_info.team_id = 'team1'
        mock_helper_class.find_players_in_game.return_value = mock_player_info
        
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.get_player_court_segments.side_effect = [
            [{'start': 0, 'end': 600}],  # Main player
            [{'start': 100, 'end': 500}]  # Teammate
        ]
        
        mock_helper_class.calculate_overlap_segments.return_value = [{'start': 100, 'end': 500}]
        mock_helper_class.calculate_total_time.return_value = 6.67
        mock_helper_class.filter_actions_by_segments.return_value = [
            {'actorId': 'actor1', 'move': 'Canasta de 2'}
        ]
        mock_helper_class.find_opponent_team_id.return_value = 'team2'
        
        mock_calculator = Mock()
        mock_calculator_class.return_value = mock_calculator
        mock_calculator._calculate_stats_from_actions.return_value = {
            'points_for': 20, 'points_against': 15
        }
        
        game = {'_id': '123'}
        result = self.repo._process_game_with_teammate(game, 'p1', 'p2', True)
        
        self.assertIsNotNone(result)
        self.assertIn('player_stats', result)
        self.assertIn('team_stats', result)
        self.assertIn('time_together', result)
        self.assertEqual(result['time_together'], 6.67)


if __name__ == '__main__':
    unittest.main()
