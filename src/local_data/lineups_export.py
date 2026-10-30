"""The lineups ("Combinaciones") of a competition for the web (#686): what each combination of 2 to 5 players did in each game of its team.

The page filters by size, statistic, period, minimums and last game, and the service answers each of them by merging the per-game results of every combination
(``repository_lineup._merge_lineup_stats``), so what is published is those per-game results (the counters, the minutes, the possessions and the three ratios that cannot be
recomputed from them) and the browser merges them with the same rules. The games are the ones the service reads (``iter_game_lineups`` over the team's games with
play-by-play, in the order of the collection): the figures cannot differ.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.local_data.export import FORMAT
from src.utils.collection_utils import is_fbcyl
from src.utils.time_utils import fbcyl_game_instant

SIZES = (2, 3, 4, 5)
# ``[game, minutes, segments, possessions, ortg, drtg, orb_pct, ...counters]``: ``game`` is the index in the team's ``games``; the three ratios are the game's own (ORtg and DRtg
# use the possessions before rounding, ORB% the opponent's rebounds) and the rest are the counters the browser sums
COLUMNS = ("game", "minutes", "segments", "possessions", "ortg", "drtg", "orb_pct", "points_for", "points_against", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
           "orb", "drb", "ast", "stl", "blk", "tov", "pf")
_FEB_PROJECTION = {"PLAYBYPLAY": 1, "HEADER": 1, "BOXSCORE.TEAM.id": 1, "BOXSCORE.TEAM.PLAYER.id": 1}
_FBCYL_PROJECTION = {"moves": 1, "stats.teams": 1, "stats.time": 1}


def game_at(raw: Any, fbcyl: bool) -> Optional[str]:
    """The instant of a game (``YYYY-MM-DDTHH:MM:SS``, UTC without zone) as MongoDB parses its stored date, or ``None`` when it cannot be read (the game stays out of any period)."""
    if not raw:
        return None
    if fbcyl:
        return fbcyl_game_instant(raw) or None
    try:
        return datetime.strptime(str(raw), "%d-%m-%Y - %H:%M").strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _row(game: int, stats: Dict[str, Any]) -> List[Any]:
    values = {"game": game, "segments": stats["segments_count"], **stats}
    return [values[column] for column in COLUMNS]


def _team(handler: Any, name: str, team_id: str, team_name: str, fbcyl: bool) -> Optional[Dict[str, Any]]:
    repository = getattr(handler, "repository", handler)                                        # the lineup loop and the names live in the repository, not in the handler
    games = handler.get_games_for_team(name, team_id, only_with_playbyplay=True, projection=_FBCYL_PROJECTION if fbcyl else _FEB_PROJECTION)
    if not games:
        return None
    sizes: Dict[int, Dict[frozenset, List[List[Any]]]] = {size: {} for size in SIZES}
    listed = []
    for index, game in enumerate(games):
        raw = (game.get("stats") or {}).get("time") if fbcyl else (game.get("HEADER") or {}).get("starttime")
        listed.append({"date": repository.iter_game_date(game, fbcyl), "at": game_at(raw, fbcyl)})
        for size in SIZES:
            try:
                found = [(key, stats) for key, stats, _ in repository.iter_game_lineups(game, team_id, size, fbcyl)]
            except Exception as error:                                                          # as the service: a game with an incomplete play-by-play is skipped
                print(f"Error processing game for lineup export: {error}")
                continue
            for key, stats in found:
                sizes[size].setdefault(key, []).append(_row(index, stats))
    ids = sorted({player for table in sizes.values() for key in table for player in key}, key=str)
    names = repository._bulk_load_player_names(name, ids, fbcyl)
    return {
        "team_id": str(team_id), "team_name": team_name, "games": listed,
        "players": {str(i): list(names.get(str(i), (f"Player {i}", None))) for i in ids},
        "sizes": {str(size): [[sorted(key, key=str), rows] for key, rows in sorted(table.items(), key=lambda item: sorted(item[0], key=str))] for size, table in sizes.items()},
    }


def export_lineups(handler: Any, name: str) -> Dict[str, Any]:
    """``{team_id, team_name, games, players, sizes}`` of every team of ``name`` with games with play-by-play, in the order of ``get_teams_with_ids``."""
    fbcyl = is_fbcyl(name)
    teams = []
    for team in handler.get_teams_with_ids(name) or []:
        published = _team(handler, name, team["id"], team["name"], fbcyl)
        if published:
            teams.append(json.loads(json.dumps(published, default=str)))
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if fbcyl else "feb", "columns": list(COLUMNS), "teams": teams}
