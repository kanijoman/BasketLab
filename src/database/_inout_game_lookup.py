"""What the IN/OUT of a player needs to know about ONE game before counting it: who the player is in it, whether the player played and whether the team did.

Pure functions over a game document (FEB: ``BOXSCORE.TEAM[].PLAYER[]``; FBCYL: ``stats.teams[].players[]``), split out of
``InOutRepositoryMixin.get_player_in_out_stats`` (issue #200).
"""
from typing import Any, Dict, Optional, Tuple

# FBCYL gives timePlayed=40 to a player who is inscribed but never played, with every activity stat at zero
_FBCYL_ACTIVITY_KEYS = ('score', 'shotsOfTwoAttempted', 'shotsOfThreeAttempted', 'shotsOfOneAttempted',
                        'offensiveRebound', 'defensiveRebound', 'assists', 'lost', 'block', 'steals')


def normalize_name(name: Optional[str]) -> str:
    """First initial + surnames: ``'ANA PEREZ LOPEZ'`` → ``'A PEREZ LOPEZ'``; one surname when there are only two words."""
    if not name:
        return ""
    words = name.split()
    if len(words) >= 3:
        return f"{words[0][0]} {words[-2]} {words[-1]}"
    if len(words) >= 2:
        return f"{words[0][0]} {words[-1]}"
    return name


def _fbcyl_team_id(team: Dict[str, Any]) -> Any:
    return team.get('teamIdIntern') or team.get('teamIdExtern')


def find_fbcyl_player(game: Dict[str, Any], player_id: str) -> Optional[Tuple[Any, Any]]:
    """``(actorId, team id)`` of the player in THIS game, both of which change from game to game; None when the player is not in it.

    The player is the one with that ``uuid`` (stable across games) or, when the id is not a UUID (it has no four dashes), the one with the same
    normalized name.
    """
    target_normalized = normalize_name(player_id) if player_id.count('-') != 4 else None
    actor_id = team_id = None
    for team in game.get('stats', {}).get('teams', []):
        for player in team.get('players', []):
            if player.get('uuid') == player_id or (target_normalized and normalize_name(player.get('name', '')) == target_normalized):
                actor_id, team_id = player.get('actorId'), _fbcyl_team_id(team)
                break
        if actor_id:
            break
    return (actor_id, team_id) if actor_id and team_id else None


def find_feb_team_id(player_doc: Optional[Dict[str, Any]], player_id: str) -> Any:
    """Id of the team of a FEB player, from one game document (with ``BOXSCORE.TEAM.id`` and ``PLAYER.id``); None when it is not there."""
    for team in (player_doc or {}).get('BOXSCORE', {}).get('TEAM', []):
        if any(player.get('id') == player_id for player in team.get('PLAYER', [])):
            return team.get('id')
    return None


def _feb_minutes(value: Any) -> float:
    """Minutes of a FEB box player: a number, ``'mm:ss'`` or a plain number as text; 0 when empty or unreadable."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text in ('0', '0:00', ''):
        return 0.0
    try:
        if ':' in text:
            parts = text.split(':')
            return int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 60.0
        return float(text)
    except Exception:
        return 0.0


def _fbcyl_minutes(player: Dict[str, Any]) -> float:
    value = player.get('timePlayed')
    if value is None:
        return 0.0
    minutes = float(value)
    if minutes == 40.0:                                  # phantom player: inscribed, never played
        data = player.get('data', {}) or {}
        if sum(data.get(key, 0) or 0 for key in _FBCYL_ACTIVITY_KEYS) == 0:
            return 0.0
    return minutes


def player_minutes_played(game: Dict[str, Any], player_id: Any, is_fbcyl: bool) -> float:
    """Minutes the player played in this game according to the box (FBCYL: ``player_id`` is the ``actorId`` of the game); 0 when not in the box."""
    if is_fbcyl:
        for team in game.get('stats', {}).get('teams', []):
            for player in team.get('players', []):
                if player.get('actorId') == player_id:
                    return _fbcyl_minutes(player)
        return 0.0
    for team in game.get('BOXSCORE', {}).get('TEAM', []):
        for player in team.get('PLAYER', []):
            if player.get('id') == player_id:
                return _feb_minutes(player.get('min'))
    return 0.0


def team_participated(game: Dict[str, Any], team_id: Any, is_fbcyl: bool) -> bool:
    """Whether the team is in this game with players listed (whatever their minutes: a box with players and no minutes still counts)."""
    if is_fbcyl:
        for team in game.get('stats', {}).get('teams', []):
            if _fbcyl_team_id(team) == team_id:
                return bool(team.get('players', []))
        return False
    for team in game.get('BOXSCORE', {}).get('TEAM', []):
        if team.get('id') == team_id:
            return bool(team.get('PLAYER', []))
    return False
