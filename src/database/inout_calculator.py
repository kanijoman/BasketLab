"""IN/OUT statistics calculator -- extracted from playbyplay_analyzer.py."""

from typing import Dict, List, Tuple, Optional
from src.live_core.clock import GAME_SECONDS
from src.pbp.playbyplay_core import PlayByPlayAnalyzer
from .pbp_stat_counters import add_points, bump, count_rebound, count_shot, empty_stats, first_match

# FBCYL writes the action as Spanish text in ``move``; a row is (phrases, value) and the first one that matches wins (an ``elif`` chain).
_FBCYL_POINTS = (
    (('Canasta de 2', 'canasta de 2'), 2),
    (('Canasta de 3', 'canasta de 3'), 3),
    (('Canasta de 1', 'canasta de 1', 'Tiro libre anotado'), 1),
)
_FBCYL_SHOTS = (
    (('Canasta de 2', 'canasta de 2'), (2, True)),
    (('Intento fallado de 2', 'intento fallado de 2'), (2, False)),
    (('Canasta de 3', 'canasta de 3'), (3, True)),
    (('Intento fallado de 3', 'intento fallado de 3'), (3, False)),
    (('Canasta de 1', 'canasta de 1', 'Tiro libre anotado'), (1, True)),
    (('Intento fallado de 1', 'intento fallado de 1'), (1, False)),
)
_SHOT_WORDS = ('TIRO', 'CANASTA', 'TRIPLE', 'FALLADO')      # a FEB text that is a shot: the line before a rebound is classified by them


def _is_miss_text(text: str) -> bool:
    return 'FALLADO' in text or 'FALLA' in text


def _in_segments(segments, timestamp: int) -> bool:
    return any(start <= timestamp <= end for start, end in segments)


class InOutStatsCalculator:
    """Calculate team statistics when a player is on/off the court."""

    def __init__(self, analyzer: PlayByPlayAnalyzer):
        """
        Initialize the IN/OUT stats calculator.

        Args:
            analyzer: PlayByPlayAnalyzer instance
        """
        self.analyzer = analyzer

    @staticmethod
    def _empty_stats() -> Dict[str, int]:
        return empty_stats()

    def _extract_points_from_action(self, action: Dict) -> Tuple[int, str]:
        """
        Extract points scored from an action.

        Args:
            action: Action dictionary

        Returns:
            Tuple of (points, team_id)
        """
        team_id = action.get('idTeam')

        # FBCYL format (uses the 'move' field)
        if 'move' in action:
            points = first_match(action.get('move', ''), _FBCYL_POINTS)
            return (points, team_id) if points else (0, None)

        # FEB format: the text first, then the old logic with the action type and the logParams
        points = self._feb_text_points(action.get('text', '').upper())
        if points:
            return points, team_id

        action_type = action.get('action', '')
        if action_type == 'shoot':
            # logParam4: 1 = made, 0 = missed; logParam6: point value (2 or 3)
            made = action.get('logParam4') == '1'
            point_value = int(action.get('logParam6', 0)) if action.get('logParam6') else 0
            if made and point_value > 0:
                return point_value, team_id
        elif action_type == 'fthrow' and action.get('logParam4') == '1':
            return 1, team_id
        return 0, None

    @staticmethod
    def _feb_text_points(text: str) -> int:
        """Points the (upper-case) text of a FEB line says were scored; 0 when it says none or is not a shot."""
        if 'TIRO DE 2' in text or 'CANASTA DE 2' in text:
            return 0 if _is_miss_text(text) else 2
        if 'TIRO DE 3' in text or 'CANASTA DE 3' in text or 'TRIPLE' in text:
            return 0 if _is_miss_text(text) else 3
        if ('TIRO DE 1' in text or 'TIRO LIBRE' in text) and 'ANOTADO' in text:
            return 1
        return 0

    def _credit_points(self, line: Dict, id_team: str, target: Dict) -> None:
        points, scoring_team = self._extract_points_from_action(line)
        if points > 0 and scoring_team:
            add_points(target, points, str(scoring_team) == id_team)

    def _process_fbcyl_move(self, line: Dict, move_text: str, action_team: str,
                           id_team: str, target: Dict, idx: int, lines: List[Dict]) -> None:
        """
        Process a FBCYL move and update statistics.

        Note: FBCYL does NOT include rebounds in play-by-play data (moves list).
        Rebounds are only in pre-calculated stats, so we cannot determine when they
        occurred relative to player substitutions. Therefore, ORB/DRB remain 0 for FBCYL.
        """
        self._credit_points(line, id_team, target)
        is_team_action = (action_team == id_team)

        shot = first_match(move_text, _FBCYL_SHOTS)
        if shot:
            count_shot(target, shot[0], shot[1], is_team_action)
        if 'Pérdida' in move_text or 'pérdida' in move_text:
            bump(target, 'tov', is_team_action)
        if 'Personal' in move_text or 'personal' in move_text or 'Falta' in move_text:
            bump(target, 'pf', is_team_action)

    def _process_feb_action(self, line: Dict, upper_text: str, action_type: str,
                           action_team: str, id_team: str, target: Dict,
                           orig_idx: int, lines: List[Dict], last_shot_team: Optional[str]) -> Optional[str]:
        """Process a FEB action and update statistics. Returns updated last_shot_team."""
        # Track shots for rebound classification
        if action_type in ('shoot', 'fthrow'):
            is_miss = isinstance(line.get('logParam4'), str) and line.get('logParam4') == '0'
            last_shot_team = action_team if (_is_miss_text(upper_text) or is_miss) else None

        self._credit_points(line, id_team, target)
        self._count_feb_action(target, line, upper_text, action_type, action_team == id_team, action_team, orig_idx + 1, lines)
        return None if action_type == 'rebound' else last_shot_team

    def _count_feb_action(self, target: Dict, line: Dict, text: str, action_type: str, is_team: bool,
                          action_team, prev_idx: int, lines: List[Dict]) -> None:
        """The counters of one FEB action (shot, rebound, assist, steal, block, turnover, foul); ``lines[prev_idx]`` is the action before it in time."""
        shot = self._feb_shot(text, action_type, line)
        if shot:
            count_shot(target, shot[0], shot[1], is_team)
        if action_type == 'rebound':
            count_rebound(target, self._follows_own_shot(lines, prev_idx, action_team), is_team)
        if 'ASISTENCIA' in text or action_type == 'assist':
            bump(target, 'ast', is_team)
        if 'ROBO' in text or 'RECUPERA' in text or action_type in ('steal', 'recovery'):
            bump(target, 'stl', is_team)
        if 'TAPÓN' in text or 'TAPON' in text or action_type == 'block':
            bump(target, 'blk', is_team)
        if 'PÉRDIDA' in text or 'PERDIDA' in text or action_type in ('turnover', 'lose'):
            bump(target, 'tov', is_team)
        if 'FALTA' in text or action_type == 'foul':
            bump(target, 'pf', is_team)

    @staticmethod
    def _feb_shot(text: str, action_type: str, line: Dict) -> Optional[Tuple[int, bool]]:
        """(points of the shot, made) of a FEB line: from its text, else from the action type and the logParams; None when it is not a shot."""
        if 'TIRO DE 2' in text or 'CANASTA DE 2' in text:
            return 2, not _is_miss_text(text)
        if 'TIRO DE 3' in text or 'TRIPLE' in text or 'CANASTA DE 3' in text:
            return 3, not _is_miss_text(text)
        if 'TIRO DE 1' in text or 'TIRO LIBRE' in text:
            return 1, 'ANOTADO' in text or 'ANOTA' in text
        if action_type == 'shoot':
            point_value = int(line.get('logParam6', 0)) if line.get('logParam6') else 0
            return (point_value, line.get('logParam4') == '1') if point_value in (2, 3) else None
        if action_type == 'fthrow':
            return 1, line.get('logParam4') == '1'
        return None

    @staticmethod
    def _follows_own_shot(lines: List[Dict], prev_idx: int, action_team) -> bool:
        """Whether the line before a rebound (the next one in the list, which is in descending time) is a shot of the rebounding team: an offensive rebound."""
        if prev_idx >= len(lines):
            return False
        prev = lines[prev_idx]
        p_text = (prev.get('text') or '').upper()
        if (prev.get('action') or '').lower() in ('shoot', 'fthrow') or any(word in p_text for word in _SHOT_WORDS):
            shot_team = prev.get('idTeam')
            return shot_team is not None and shot_team == action_team
        return False

    def calculate_in_out_stats(self, player_id: str, id_team: str) -> Dict[str, Dict]:
        """
        Calculate statistics for when player is IN vs OUT.

        Args:
            player_id: Player's ID (idPlayer from JSON)
            id_team: Player's team ID

        Returns:
            Dictionary with 'in' and 'out' keys containing stats
        """
        # We iterate the full play-by-play in chronological order and apply identical processing to every action, assigning results to the IN or
        # OUT dictionary depending on whether the player was on court at that moment: rebound and possession classification uses the complete game.
        stats_in, stats_out = empty_stats(), empty_stats()
        lines = self.analyzer.lines or []
        if self.analyzer.is_fbcyl:
            self._count_fbcyl_game(lines, player_id, str(id_team), stats_in, stats_out)
        else:
            self._count_feb_game(lines, player_id, str(id_team), stats_in, stats_out)

        time_in = self.analyzer.calculate_time_played(player_id)
        stats_in['minutes'] = time_in / 60
        stats_out['minutes'] = (GAME_SECONDS - time_in) / 60
        return {'in': stats_in, 'out': stats_out}

    def _count_fbcyl_game(self, lines: List[Dict], player_id: str, id_team: str, stats_in: Dict, stats_out: Dict) -> None:
        """FBCYL moves are already chronological."""
        segments = self.analyzer.get_player_court_segments(player_id)
        # The position of the move among the player's substitutions decides, not the clock second (issue #378)
        spans = self.analyzer.get_player_move_spans(player_id)
        for idx, line in enumerate(lines):
            period, min_val, sec_val = line.get('period'), line.get('min'), line.get('sec')
            if period is None or min_val is None or sec_val is None:
                continue
            if spans is not None:
                on_court = any(after < idx < before for after, before in spans)
            else:
                on_court = _in_segments(segments, self.analyzer._fbcyl_time_to_seconds(period, min_val, sec_val))
            self._process_fbcyl_move(line, line.get('move', ''), str(line.get('idTeam', '')), id_team,
                                     stats_in if on_court else stats_out, idx, lines)

    def _count_feb_game(self, lines: List[Dict], player_id: str, id_team: str, stats_in: Dict, stats_out: Dict) -> None:
        """PLAYBYPLAY.LINES is stored reverse-chronologically: walk it backwards."""
        segments = self.analyzer.get_player_court_segments(player_id)
        last_shot_team = None
        for orig_idx in range(len(lines) - 1, -1, -1):
            line = lines[orig_idx]
            quarter, time_str = line.get('quarter'), line.get('time')
            if not quarter or not time_str:
                continue
            on_court = _in_segments(segments, self.analyzer._time_to_seconds(quarter, time_str))
            text = line.get('text', '')
            last_shot_team = self._process_feb_action(
                line, text.upper() if isinstance(text, str) else '', line.get('action', ''), str(line.get('idTeam', '')),
                id_team, stats_in if on_court else stats_out, orig_idx, lines, last_shot_team)

    def _calculate_stats_from_actions(self, actions: List[Dict],
                                      team_id: str, opponent_team: str) -> Dict:
        """
        Calculate statistics from a list of actions.

        Args:
            actions: List of action dictionaries
            team_id: Team ID to calculate stats for
            opponent_team: Opponent team ID

        Returns:
            Dictionary with calculated statistics (the team's, and the rival's prefixed ``opp_``)
        """
        stats = empty_stats()
        for idx, action in enumerate(actions):
            action_type = action.get('action', '')
            action_team = action.get('idTeam')
            text = action.get('text', '').upper()

            points, scoring_team = self._extract_points_from_action(action)
            if points > 0 and scoring_team and scoring_team in (team_id, opponent_team):
                add_points(stats, points, scoring_team == team_id)

            # The action after this one in the list is the one before it in time (the actions come in descending order)
            self._count_feb_action(stats, action, text, action_type, action_team == team_id, action_team, idx + 1, actions)
        return stats
