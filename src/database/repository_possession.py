"""Possession-stats repository mixin."""

from typing import Dict, Tuple
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl


def _aggregate_game_possession(game_stats: Dict) -> Tuple[float, Dict, Dict, Dict]:
    """Extract per-game possession totals from a single game's calculate_possessions result.

    Args:
        game_stats: Dict returned by PossessionAnalyzer.calculate_possessions().

    Returns:
        Tuple of (weighted_duration_sum, short_stats, medium_stats, long_stats) where
        weighted_duration_sum = avg_duration * total_possessions for this game,
        and each stats dict has keys 'count' and 'total_points'.
    """
    by_dur = game_stats.get("possessions_by_duration", {})
    total = game_stats.get("total_possessions", 0)
    weighted = game_stats.get("avg_duration", 0.0) * total
    return (
        weighted,
        by_dur.get("<=8s",  {"count": 0, "total_points": 0}),
        by_dur.get("8-16s", {"count": 0, "total_points": 0}),
        by_dur.get(">16s",  {"count": 0, "total_points": 0}),
    )


class PossessionRepositoryMixin:
    """Mixin providing team possession statistics query methods."""

    def get_team_possession_stats(self, collection_name: str, team_id: str,
                                   date_filter: Dict = None) -> Dict:
        """Get possession statistics for a team using play-by-play data.

        Args:
            collection_name: Name of the collection
            team_id: Team's ID
            date_filter: Optional MongoDB date filter dict with datetime object

        Returns:
            Dictionary with possession statistics:
            - total_possessions: Total number of possessions across all games
            - avg_duration: Average possession duration in seconds (weighted)
            - possessions_by_duration: Stats for <=8s, 8-16s, >16s with count,
              total_points, and OER
            - games_analyzed: Number of games included in analysis
        """
        if not self.connection.is_connected():
            return {}

        try:
            from .playbyplay_analyzer import PossessionAnalyzer

            is_fbcyl = _is_fbcyl(collection_name)
            # Narrow projections: only the fields PossessionAnalyzer actually reads
            # from each array item — avoids loading 15-20 extra fields per move.
            projection = (
                {
                    "moves.move":   1,
                    "moves.period": 1,
                    "moves.min":    1,
                    "moves.sec":    1,
                    "moves.idTeam": 1,
                    "stats.teams.teamIdIntern": 1,
                    "stats.teams.teamIdExtern": 1,
                    "_id": 0,
                }
                if is_fbcyl
                else {
                    "PLAYBYPLAY.LINES.text":    1,
                    "PLAYBYPLAY.LINES.quarter": 1,
                    "PLAYBYPLAY.LINES.time":    1,
                    "PLAYBYPLAY.LINES.action":  1,
                    "PLAYBYPLAY.LINES.idTeam":  1,
                    "HEADER.TEAM.id":           1,
                    "_id": 0,
                }
            )
            games = self.get_games_for_team(
                collection_name, team_id,
                only_with_playbyplay=True,
                projection=projection,
            )

            if not games:
                return _empty_possession_result()

            return self._accumulate_possession_stats(games, team_id, is_fbcyl)

        except PyMongoError:
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _accumulate_possession_stats(games: list, team_id: str, is_fbcyl: bool) -> Dict:
        """Aggregate possession stats across all games for a team."""
        from .playbyplay_analyzer import PossessionAnalyzer

        total_duration_sum = 0.0
        total_weighted_count = 0
        short_poss = {"count": 0, "total_points": 0}
        medium_poss = {"count": 0, "total_points": 0}
        long_poss = {"count": 0, "total_points": 0}
        games_analyzed = 0

        for game in games:
            try:
                analyzer = PossessionAnalyzer(game, is_fbcyl=is_fbcyl)
                game_stats = analyzer.calculate_possessions(team_id)
                weighted, fast, med, slow = _aggregate_game_possession(game_stats)

                total_duration_sum += weighted
                total_weighted_count += game_stats.get("total_possessions", 0)

                short_poss["count"] += fast["count"]
                short_poss["total_points"] += fast["total_points"]
                medium_poss["count"] += med["count"]
                medium_poss["total_points"] += med["total_points"]
                long_poss["count"] += slow["count"]
                long_poss["total_points"] += slow["total_points"]
                games_analyzed += 1
            except Exception:
                continue

        total_possessions = short_poss["count"] + medium_poss["count"] + long_poss["count"]
        avg_duration = (
            total_duration_sum / total_weighted_count if total_weighted_count > 0 else 0.0
        )

        def _oer(count: int, points: int) -> float:
            return round((points / count) * 100, 2) if count > 0 else 0.0

        return {
            "total_possessions": total_possessions,
            "avg_duration": round(avg_duration, 2),
            "possessions_by_duration": {
                "<=8s": {**short_poss, "oer": _oer(short_poss["count"], short_poss["total_points"])},
                "8-16s": {**medium_poss, "oer": _oer(medium_poss["count"], medium_poss["total_points"])},
                ">16s": {**long_poss, "oer": _oer(long_poss["count"], long_poss["total_points"])},
            },
            "games_analyzed": games_analyzed,
        }


def _empty_possession_result() -> Dict:
    return {
        "total_possessions": 0,
        "avg_duration": 0.0,
        "possessions_by_duration": {
            "<=8s":  {"count": 0, "total_points": 0, "oer": 0.0},
            "8-16s": {"count": 0, "total_points": 0, "oer": 0.0},
            ">16s":  {"count": 0, "total_points": 0, "oer": 0.0},
        },
        "games_analyzed": 0,
    }

