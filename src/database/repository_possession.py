"""Possession-stats repository mixin."""

from typing import Dict
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl

from .possession_stats_helpers import (
    aggregate_game_possession as _aggregate_game_possession,
    boxscore_possession_stats,
    boxscore_projection,
    empty_possession_result as _empty_possession_result,
    opponent_id_from_game,
    possession_projection as _possession_projection,
    reconciliation_metrics,
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
            # Narrow projection: only the fields PossessionAnalyzer actually reads
            # from each array item — avoids loading 15-20 extra fields per move.
            projection = _possession_projection(is_fbcyl)
            games = self.get_games_for_team(
                collection_name, team_id,
                only_with_playbyplay=True,
                projection=projection,
            )

            if not games:
                return _empty_possession_result()

            pbp_stats = self._accumulate_possession_stats(games, team_id, is_fbcyl)

            # Rival (opponent) possession breakdown — reuses the same PBP games list
            rival_stats = self._accumulate_rival_possession_stats(games, team_id, is_fbcyl)
            pbp_stats.update(rival_stats)

            # Get boxscore stats for reconciliation
            boxscore_stats = self._get_boxscore_possession_stats(collection_name, team_id, is_fbcyl)
            
            # Merge boxscore data into results
            pbp_stats.update(boxscore_stats)
            
            # Add reconciliation metrics
            pbp_stats.update(self._calculate_reconciliation_metrics(pbp_stats))
            
            return pbp_stats

        except PyMongoError:
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_boxscore_possession_stats(self, collection_name: str, team_id: str, 
                                       is_fbcyl: bool) -> Dict:
        """Calculate boxscore-based possession statistics (formula-based, not event-based).
        
        Uses formula: Possessions = FGA - ORB + TOV + 0.44*FTA
        This is a statistical estimate not dependent on play-by-play data quality.
        
        Returns:
            Dict with boxscore_possessions, boxscore_oer, total_games
        """
        try:
            games = self.get_games_for_team(
                collection_name, team_id,
                only_with_playbyplay=False,  # Get all games, not just with play-by-play
                projection=boxscore_projection(is_fbcyl),
            )
            return boxscore_possession_stats(games, team_id, is_fbcyl)
        except Exception:
            return {"boxscore_possessions": 0, "boxscore_oer": 0, "total_games": 0}

    def _accumulate_possession_stats(self, games: list, team_id: str, is_fbcyl: bool) -> Dict:
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

    @staticmethod
    def _get_opponent_id_from_game(game: Dict, team_id: str, is_fbcyl: bool):
        """Return the opponent team ID from a game document, or None if not found."""
        return opponent_id_from_game(game, team_id, is_fbcyl)

    def _accumulate_rival_possession_stats(self, games: list, team_id: str,
                                           is_fbcyl: bool) -> Dict:
        """Aggregate opponent possession stats for all games involving team_id."""
        from .playbyplay_analyzer import PossessionAnalyzer

        total_duration_sum = 0.0
        total_weighted_count = 0
        short_poss = {"count": 0, "total_points": 0}
        medium_poss = {"count": 0, "total_points": 0}
        long_poss = {"count": 0, "total_points": 0}
        # Per-opponent possessions/duration — lets the caller compare this rival's
        # pace against us to that same rival's own season-wide average pace.
        opponent_breakdown: Dict[str, Dict[str, float]] = {}

        for game in games:
            try:
                opp_id = self._get_opponent_id_from_game(game, team_id, is_fbcyl)
                if not opp_id:
                    continue
                analyzer = PossessionAnalyzer(game, is_fbcyl=is_fbcyl)
                game_stats = analyzer.calculate_possessions(opp_id)
                weighted, fast, med, slow = _aggregate_game_possession(game_stats)
                game_poss = game_stats.get("total_possessions", 0)

                total_duration_sum += weighted
                total_weighted_count += game_poss

                short_poss["count"]        += fast["count"]
                short_poss["total_points"] += fast["total_points"]
                medium_poss["count"]        += med["count"]
                medium_poss["total_points"] += med["total_points"]
                long_poss["count"]          += slow["count"]
                long_poss["total_points"]   += slow["total_points"]

                opp_entry = opponent_breakdown.setdefault(
                    opp_id, {"possessions": 0, "weighted_duration": 0.0}
                )
                opp_entry["possessions"] += game_poss
                opp_entry["weighted_duration"] += weighted
            except Exception:
                continue

        total = short_poss["count"] + medium_poss["count"] + long_poss["count"]

        def _pct(count: int) -> float:
            return round(count / total * 100, 1) if total > 0 else 0.0

        def _oer(count: int, points: int) -> float:
            return round((points / count) * 100, 2) if count > 0 else 0.0

        return {
            "rival_pct_fast":   _pct(short_poss["count"]),
            "rival_pct_medium": _pct(medium_poss["count"]),
            "rival_pct_slow":   _pct(long_poss["count"]),
            "rival_oer_fast":   _oer(short_poss["count"],  short_poss["total_points"]),
            "rival_oer_medium": _oer(medium_poss["count"], medium_poss["total_points"]),
            "rival_oer_slow":   _oer(long_poss["count"],   long_poss["total_points"]),
            "rival_avg_duration": (
                round(total_duration_sum / total_weighted_count, 2)
                if total_weighted_count > 0 else 0.0
            ),
            "rival_opponent_breakdown": opponent_breakdown,
        }

    def _calculate_reconciliation_metrics(self, stats: Dict) -> Dict:
        """Calculate data quality metrics comparing play-by-play vs boxscore OER."""
        return reconciliation_metrics(stats)
