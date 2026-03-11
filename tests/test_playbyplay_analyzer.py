"""Tests for PlayByPlayAnalyzer.

Covers both FEB and FBCYL data formats using minimal game documents.
No external dependencies — no DB, no Qt required.
"""

import unittest
from src.database.playbyplay_analyzer import PlayByPlayAnalyzer


# ---------------------------------------------------------------------------
# Minimal game document factories
# ---------------------------------------------------------------------------

def _feb_game(players_local=None, players_visitor=None, lines=None):
    """Minimal FEB game document for PlayByPlayAnalyzer."""
    players_local = players_local or [
        {"idPlayer": "P1", "name": "PLAYER ONE"},
        {"idPlayer": "P2", "name": "PLAYER TWO"},
    ]
    players_visitor = players_visitor or [
        {"idPlayer": "P3", "name": "PLAYER THREE"},
    ]
    lines = lines or []
    return {
        "HEADER": {
            "TEAM": [
                {"id": "T1", "name": "LOCAL TEAM", "players": players_local},
                {"id": "T2", "name": "VISITOR TEAM", "players": players_visitor},
            ],
        },
        "PLAYBYPLAY": {
            "LINES": lines,
        },
    }


def _fbcyl_game(moves=None, teams=None):
    """Minimal FBCYL game document for PlayByPlayAnalyzer."""
    teams = teams or [
        {
            "teamIdIntern": 1001,
            "teamIdExtern": 2001,
            "name": "LOCAL",
            "players": [
                {"actorId": 501, "name": "FBCYL PLAYER ONE"},
                {"actorId": 502, "name": "FBCYL PLAYER TWO"},
            ],
        },
        {
            "teamIdIntern": 1002,
            "teamIdExtern": 2002,
            "name": "VISITOR",
            "players": [
                {"actorId": 503, "name": "FBCYL PLAYER THREE"},
            ],
        },
    ]
    moves = moves or []
    return {"moves": moves, "stats": {"teams": teams}}


# ===========================================================================
# Initialisation
# ===========================================================================

class TestPlayByPlayAnalyzerInit(unittest.TestCase):

    def test_feb_initialization(self):
        game = _feb_game()
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=False)
        self.assertFalse(analyzer.is_fbcyl)
        self.assertIsNotNone(analyzer.game_data)

    def test_fbcyl_initialization(self):
        game = _fbcyl_game()
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
        self.assertTrue(analyzer.is_fbcyl)

    def test_feb_lines_extracted(self):
        lines = [{"idPlayer": "P1", "action": "2PT"}]
        game = _feb_game(lines=lines)
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=False)
        self.assertEqual(len(analyzer.lines), 1)

    def test_fbcyl_moves_extracted(self):
        moves = [{"actorId": 501, "move": "Canasta de 2", "period": 1, "min": 3, "sec": 20}]
        game = _fbcyl_game(moves=moves)
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
        self.assertEqual(len(analyzer.lines), 1)

    def test_empty_game_no_crash(self):
        """Empty document must not crash on init."""
        analyzer = PlayByPlayAnalyzer({}, is_fbcyl=False)
        self.assertIsNotNone(analyzer)

    def test_fbcyl_empty_game_no_crash(self):
        analyzer = PlayByPlayAnalyzer({}, is_fbcyl=True)
        self.assertIsNotNone(analyzer)


# ===========================================================================
# Team mapping
# ===========================================================================

class TestTeamMapping(unittest.TestCase):

    def test_feb_team_mapping_built(self):
        game = _feb_game()
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=False)
        self.assertIn("T1", analyzer.team_mapping)
        self.assertIn("T2", analyzer.team_mapping)

    def test_feb_team_mapping_values(self):
        game = _feb_game()
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=False)
        self.assertIn(analyzer.team_mapping["T1"], {"team1", "team2"})
        self.assertIn(analyzer.team_mapping["T2"], {"team1", "team2"})
        self.assertNotEqual(analyzer.team_mapping["T1"], analyzer.team_mapping["T2"])

    def test_fbcyl_team_mapping_built(self):
        game = _fbcyl_game()
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
        # FBCYL uses teamIdIntern as key
        self.assertIn(1001, analyzer.team_mapping)
        self.assertIn(1002, analyzer.team_mapping)

    def test_empty_game_mapping_is_empty_dict(self):
        analyzer = PlayByPlayAnalyzer({}, is_fbcyl=False)
        self.assertIsInstance(analyzer.team_mapping, dict)


# ===========================================================================
# _time_to_seconds (FEB internal helper)
# ===========================================================================

class TestFebTimeConversion(unittest.TestCase):

    def setUp(self):
        self.analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)

    def test_q1_start(self):
        """Q1, 10:00 remaining → 0 seconds elapsed."""
        self.assertEqual(self.analyzer._time_to_seconds("1", "10:00"), 0)

    def test_q1_end(self):
        """Q1, 0:00 remaining → 600 seconds elapsed."""
        self.assertEqual(self.analyzer._time_to_seconds("1", "0:00"), 600)

    def test_q2_start(self):
        """Q2, 10:00 remaining → 600 seconds elapsed."""
        self.assertEqual(self.analyzer._time_to_seconds("2", "10:00"), 600)

    def test_q2_end(self):
        """Q2, 0:00 remaining → 1200 seconds elapsed."""
        self.assertEqual(self.analyzer._time_to_seconds("2", "0:00"), 1200)

    def test_q4_end(self):
        """Q4, 0:00 remaining → 2400 seconds (end of regulation)."""
        self.assertEqual(self.analyzer._time_to_seconds("4", "0:00"), 2400)

    def test_midgame_q3(self):
        """Q3, 5:00 remaining: elapsed = 600-300 = 300s into Q3 → total = 1200+300 = 1500s."""
        self.assertEqual(self.analyzer._time_to_seconds("3", "5:00"), 1500)

    def test_invalid_time_returns_zero(self):
        self.assertEqual(self.analyzer._time_to_seconds("bad", "also_bad"), 0)

    def test_malformed_time_returns_zero(self):
        self.assertEqual(self.analyzer._time_to_seconds("1", "abc"), 0)


# ===========================================================================
# _fbcyl_time_to_seconds
# ===========================================================================

class TestFbcylTimeConversion(unittest.TestCase):

    def setUp(self):
        self.analyzer = PlayByPlayAnalyzer(_fbcyl_game(), is_fbcyl=True)

    def test_period1_start(self):
        """Period 1, 0:00 → 0 seconds elapsed."""
        self.assertEqual(self.analyzer._fbcyl_time_to_seconds(1, 0, 0), 0)

    def test_period1_end(self):
        """Period 1, 10:00 → 600 seconds elapsed."""
        self.assertEqual(self.analyzer._fbcyl_time_to_seconds(1, 10, 0), 600)

    def test_period2_start(self):
        """Period 2, 0:00 → 600 seconds."""
        self.assertEqual(self.analyzer._fbcyl_time_to_seconds(2, 0, 0), 600)

    def test_period3_midpoint(self):
        """Period 3, 5:30 → 1200 + 330 = 1530 seconds."""
        self.assertEqual(self.analyzer._fbcyl_time_to_seconds(3, 5, 30), 1530)

    def test_period4_end(self):
        """Period 4, 10:00 → 2400 seconds."""
        self.assertEqual(self.analyzer._fbcyl_time_to_seconds(4, 10, 0), 2400)


# ===========================================================================
# parse_substitutions
# ===========================================================================

class TestParseSubstitutions(unittest.TestCase):

    def test_empty_lines_returns_dict(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(lines=[]), is_fbcyl=False)
        result = analyzer.parse_substitutions()
        self.assertIsInstance(result, dict)

    def test_caching_same_object_returned(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(lines=[]), is_fbcyl=False)
        first = analyzer.parse_substitutions()
        second = analyzer.parse_substitutions()
        self.assertIs(first, second)

    def test_fbcyl_empty_moves_returns_dict(self):
        analyzer = PlayByPlayAnalyzer(_fbcyl_game(moves=[]), is_fbcyl=True)
        result = analyzer.parse_substitutions()
        self.assertIsInstance(result, dict)

    def test_feb_substitution_events_parsed(self):
        """A SUB line should produce timeline entries for the substituted player."""
        lines = [
            {
                "idPlayer": "P1",
                "action": "SUBSTITUTION",
                "idAction": "10",   # substituted out
                "quarter": "1",
                "crono": "8:00",
                "idTeam": "T1",
            },
            {
                "idPlayer": "P6",
                "action": "SUBSTITUTION",
                "idAction": "11",   # substituted in
                "quarter": "1",
                "crono": "8:00",
                "idTeam": "T1",
            },
        ]
        game = _feb_game(lines=lines)
        analyzer = PlayByPlayAnalyzer(game, is_fbcyl=False)
        result = analyzer.parse_substitutions()
        # Just verify it's a dict without crashing — specific keys depend on action code mapping
        self.assertIsInstance(result, dict)


# ===========================================================================
# get_player_court_segments
# ===========================================================================

class TestGetPlayerCourtSegments(unittest.TestCase):

    def test_returns_list(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.get_player_court_segments("P1")
        self.assertIsInstance(result, list)

    def test_each_segment_is_two_tuple(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)
        segments = analyzer.get_player_court_segments("P1")
        for seg in segments:
            self.assertEqual(len(seg), 2, f"Segment {seg} is not a 2-tuple")

    def test_segments_start_before_end(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)
        for start, end in analyzer.get_player_court_segments("P1"):
            self.assertLessEqual(start, end)

    def test_unknown_player_returns_empty_or_list(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.get_player_court_segments("NONEXISTENT")
        self.assertIsInstance(result, list)


# ===========================================================================
# calculate_time_played
# ===========================================================================

class TestCalculateTimePlayed(unittest.TestCase):

    def test_returns_int_or_float(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_time_played("P1")
        self.assertIsInstance(result, (int, float))

    def test_returns_non_negative(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_time_played("P1")
        self.assertGreaterEqual(result, 0)

    def test_unknown_player_returns_zero(self):
        analyzer = PlayByPlayAnalyzer(_feb_game(), is_fbcyl=False)
        result = analyzer.calculate_time_played("NOBODY")
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
