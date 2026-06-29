"""Rotation analysis service.

Computes season-level rotation metrics for a team:
- Per-player minutes aggregated across all games
- Starting five detection (plurality vote per game)
- Percentage of game time covered by starting-5 / top-5 / top-8
- Substitution count: combined events (simultaneous) and individual events
- Gini index and coefficient of variation of minutes distribution
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

import math

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.utils.collection_utils import is_fbcyl as _is_fbcyl
from src.database.playbyplay_analyzer import PlayByPlayAnalyzer
from src.database.lineup_extractor import LineupExtractor

# Gini thresholds for rotation classification
_GINI_AMPLIA = 0.15
_GINI_EQUILIBRADA = 0.25

# CV thresholds
_CV_HOMOGENEOUS = 20.0
_CV_MODERATE = 40.0

# Simultaneous-substitution tolerance in seconds
_SIMULTANEOUS_WINDOW_S = 1


class RotationService:
    """High-level service for team rotation analysis."""

    def __init__(self, db_handler: "MongoDBHandler") -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_rotation_analysis(
        self,
        collection_name: str,
        team_id: str,
        team_name: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        min_games: int = 5,
        min_total_min: float = 100.0,
    ) -> Dict[str, Any]:
        is_fbcyl = _is_fbcyl(collection_name)

        games = self._db.get_games_for_team(collection_name, team_id) or []
        total_games = len(games)

        if total_games == 0:
            return self._empty_result()

        # Per-player accumulators: player_id → {name, total_seconds, games_played}
        player_acc: Dict[str, Dict] = {}
        per_game_starters: List[Set[str]] = []
        per_game_minutes: List[Dict[str, float]] = []  # per-game {player_id: minutes}
        all_sub_timestamps: List[int] = []  # season-level substitution event timestamps
        pbp_minutes_acc: Dict[str, float] = {}   # minutes in PBP games per player
        pbp_stints_acc: Dict[str, int] = {}      # total stints in PBP games per player
        games_with_pbp = 0

        for idx, game in enumerate(games):
            if progress_callback:
                progress_callback(idx + 1, total_games)

            has_pbp = self._game_has_playbyplay(game, is_fbcyl)

            # --- Player minutes from boxscore (reliable even without PBP) ---
            game_min = self._accumulate_player_minutes(game, team_id, is_fbcyl, player_acc)
            if game_min:
                per_game_minutes.append(game_min)

            # --- PBP-derived data (starters + substitution events) ---
            if has_pbp:
                games_with_pbp += 1
                analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)
                extractor = LineupExtractor(analyzer)

                starters = extractor.detect_starting_lineup(team_id)
                if starters:
                    per_game_starters.append(starters)

                sub_timestamps = self._extract_sub_timestamps(analyzer, team_id, is_fbcyl)
                all_sub_timestamps.extend(sub_timestamps)

                # Stint accumulation (requires per-game minutes already captured above)
                if game_min:
                    timeline = analyzer.parse_substitutions()
                    self._accumulate_stints(timeline, game_min, pbp_minutes_acc, pbp_stints_acc)

        if not player_acc:
            return self._empty_result()

        # Build per-player stats with averages
        player_stats = self._build_player_stats(player_acc, total_games)

        # Identify significant players (exclude sporadic/junior players from all metrics)
        significant_ids = self._filter_significant_players(
            player_stats, min_games=min_games, min_total_min=min_total_min
        )
        significant_stats = {pid: player_stats[pid] for pid in significant_ids}

        # Derive ordered lists (significant players only, sorted by total_minutes desc)
        sorted_ids = sorted(
            significant_ids,
            key=lambda k: significant_stats[k]["total_minutes"],
            reverse=True,
        )

        # Aggregate starting five — returns (top_5_set, per_player_counts)
        season_starters, starter_counts = self._aggregate_starters(per_game_starters)

        # Re-derive top-5 from significant players only
        sig_starter_counts = Counter(
            {pid: c for pid, c in starter_counts.items() if pid in significant_ids}
        )
        season_starters = {pid for pid, _ in sig_starter_counts.most_common(5)}

        # How many games did the "most common" starting 5 ALL start together?
        games_with_pbp_for_starters = len(per_game_starters)
        starting_five_games_count = sum(
            1 for s in per_game_starters
            if season_starters and season_starters.issubset(s)
        )
        starting_five_games_pct = (
            round(starting_five_games_count / games_with_pbp_for_starters * 100, 1)
            if games_with_pbp_for_starters else 0.0
        )

        # Mark starters and starter counts for all players
        for pid in player_stats:
            player_stats[pid]["is_starter"] = pid in season_starters
            player_stats[pid]["starter_games"] = starter_counts.get(pid, 0)

        # Stint averages — must be computed before _make_player_entry so the closure works
        stint_avgs = self._compute_stint_averages(pbp_minutes_acc, pbp_stints_acc)
        sig_pbp_min = sum(pbp_minutes_acc.get(pid, 0.0) for pid in significant_ids)
        sig_pbp_stints = sum(pbp_stints_acc.get(pid, 0) for pid in significant_ids)
        team_avg_stint = round(sig_pbp_min / sig_pbp_stints, 1) if sig_pbp_stints > 0 else None

        def _make_player_entry(pid: str, stats: Dict, is_marginal: bool) -> Dict:
            return {
                "player_id": pid,
                "player_name": stats["name"],
                "total_minutes": round(stats["total_minutes"], 1),
                "games_played": stats["games_played"],
                "avg_min_per_game": round(stats["avg_min_per_game"], 1),
                "pct_game_time": round(stats["avg_min_per_game"] / 40.0 * 100, 1),
                "is_starter": stats["is_starter"],
                "starter_games": stats["starter_games"],
                "starter_pct": round(
                    stats["starter_games"] / games_with_pbp_for_starters * 100, 1
                ) if games_with_pbp_for_starters else 0.0,
                "avg_stint_min": stint_avgs.get(pid),
                "total_pbp_stints": pbp_stints_acc.get(pid, 0),
                "is_marginal": is_marginal,
            }

        # Build significant player list (sorted by total_minutes desc)
        players_list = [
            _make_player_entry(pid, significant_stats[pid], False) for pid in sorted_ids
        ]

        # Build marginal player list (sorted by total_minutes desc)
        marginal_ids = sorted(
            set(player_stats.keys()) - significant_ids,
            key=lambda k: player_stats[k]["total_minutes"],
            reverse=True,
        )
        marginal_list = [
            _make_player_entry(pid, player_stats[pid], True) for pid in marginal_ids
        ]

        # Percentages
        starting_ids = list(season_starters) if season_starters else sorted_ids[:5]
        # starting_five: season-level (fixed group of identified starters)
        pcts = self._compute_percentages(significant_stats, starting_ids)
        # top5/top8: per-game (in each game take the N highest-minute players)
        top5_mean, top5_std = self._compute_per_game_pct(per_game_minutes, 5)
        top8_mean, top8_std = self._compute_per_game_pct(per_game_minutes, 8)

        # Substitution counts
        total_combined, total_individual = self._count_substitutions(all_sub_timestamps)
        avg_combined = round(total_combined / games_with_pbp, 2) if games_with_pbp else 0.0
        avg_individual = round(total_individual / games_with_pbp, 2) if games_with_pbp else 0.0

        # Distribution metrics (significant players only)
        all_minutes = [significant_stats[pid]["total_minutes"] for pid in sorted_ids]
        gini = self._compute_gini(all_minutes)
        cv = self._compute_cv(all_minutes)

        # Starter names
        starter_names = [
            significant_stats[sid]["name"]
            for sid in starting_ids
            if sid in significant_stats
        ]

        return {
            "total_games": total_games,
            "games_with_playbyplay": games_with_pbp,
            "players": players_list,
            "marginal_players": marginal_list,
            "significant_player_count": len(significant_ids),
            "starting_five_ids": list(starting_ids),
            "starting_five_names": starter_names,
            "starting_five_games_count": starting_five_games_count,
            "starting_five_games_pct": starting_five_games_pct,
            "pct_minutes_starting_five": round(pcts["pct_minutes_starting_five"], 1),
            "pct_minutes_top5": top5_mean,
            "pct_minutes_top5_std": top5_std,
            "pct_minutes_top8": top8_mean,
            "pct_minutes_top8_std": top8_std,
            "total_combined_substitutions": total_combined,
            "total_individual_substitutions": total_individual,
            "avg_combined_subs_per_game": avg_combined,
            "avg_individual_subs_per_game": avg_individual,
            "gini_index": round(gini, 4),
            "cv": round(cv, 1),
            "rotation_label": self._rotation_label(gini),
            "cv_label": self._cv_label(cv),
            "avg_stint_min_team": team_avg_stint,
        }

    # ------------------------------------------------------------------
    # Math helpers (also callable from tests via __new__)
    # ------------------------------------------------------------------

    def _compute_per_game_pct(
        self,
        per_game_minutes: List[Dict[str, float]],
        n: int,
    ) -> Tuple[float, float]:
        """For each game take the top-N players by minutes; return (mean%, std%) across games.

        A player is MARGINAL only if BOTH conditions hold:
        In each game the top-N is dynamic (whoever played most that night),
        regardless of their season standing.  This captures rotation width
        game-by-game: if a team always uses exactly 8 different players,
        per-game top-8 ≈ 100% even if the identity of those 8 varies.

        Args:
            per_game_minutes: list of {player_id: minutes_in_game} dicts, one per game.
            n: size of the top group (5 or 8).

        Returns:
            (mean_pct, population_std_pct), both rounded to 1 decimal.
        """
        pcts: List[float] = []
        for game_min in per_game_minutes:
            total = sum(game_min.values())
            if total < 1e-9:
                continue
            top_n = sum(sorted(game_min.values(), reverse=True)[:n])
            pcts.append(top_n / total * 100)
        if not pcts:
            return 0.0, 0.0
        mean = sum(pcts) / len(pcts)
        variance = sum((p - mean) ** 2 for p in pcts) / len(pcts)
        std = math.sqrt(variance)
        return round(mean, 1), round(std, 1)

    def _compute_gini(self, values: List[float]) -> float:
        """Compute Gini coefficient for a list of values."""
        if not values:
            return 0.0
        vals = sorted(float(v) for v in values)
        n = len(vals)
        total = sum(vals)
        if total == 0:
            return 0.0
        cumsum = 0.0
        for i, v in enumerate(vals):
            cumsum += v * (2 * (i + 1) - n - 1)
        return cumsum / (n * total)

    def _compute_cv(self, values: List[float]) -> float:
        """Coefficient of variation = std / mean × 100, capped at 200%."""
        if not values:
            return 0.0
        n = len(values)
        mean = sum(values) / n
        if mean < 1e-9:
            return 200.0
        variance = sum((v - mean) ** 2 for v in values) / n
        cv = math.sqrt(variance) / mean * 100
        return min(cv, 200.0)

    def _rotation_label(self, gini: float) -> str:
        if gini < _GINI_AMPLIA:
            return "Rotación amplia"
        if gini < _GINI_EQUILIBRADA:
            return "Rotación equilibrada"
        return "Rotación corta"

    def _cv_label(self, cv: float) -> str:
        if cv < _CV_HOMOGENEOUS:
            return "Muy homogéneo"
        if cv < _CV_MODERATE:
            return "Moderado"
        return "Heterogéneo"

    def _aggregate_starters(
        self, per_game_starters: List[Set[str]]
    ) -> Tuple[Set[str], Dict[str, int]]:
        """Return (top_5_set, per_player_starter_counts) across all games.

        top_5_set: the 5 players who appeared most often in the starting lineup
            (plurality vote — the "most common" starting five).
        per_player_starter_counts: maps player_id → number of games they started.
        """
        if not per_game_starters:
            return set(), {}
        counter: Counter = Counter()
        for s in per_game_starters:
            for pid in s:
                counter[pid] += 1
        top_5 = {pid for pid, _ in counter.most_common(5)}
        return top_5, dict(counter)

    def _filter_significant_players(
        self,
        player_stats: Dict[str, Dict],
        min_games: int = 5,
        min_total_min: float = 100.0,
    ) -> Set[str]:
        """Return the set of player IDs considered significant for analysis.

        A player is SIGNIFICANT only if BOTH conditions hold:
          - games_played >= min_games
          - total_minutes >= min_total_min

        A player failing EITHER condition is considered marginal (e.g. a player
        who appeared in many games for 1-2 minutes each, or played only 1-2
        games regardless of minutes).

        Falls back to all players when the filtered set would be empty (e.g.
        very short seasons with little data).
        """
        significant = {
            pid for pid, s in player_stats.items()
            if s["games_played"] >= min_games and s["total_minutes"] >= min_total_min
        }
        # Safety fallback: never return an empty set
        return significant if significant else set(player_stats.keys())

    def _count_substitutions(
        self, timestamps: List[int]
    ) -> Tuple[int, int]:
        """Group substitution event timestamps into combined + individual counts.

        Events within _SIMULTANEOUS_WINDOW_S seconds of each other belong to
        the same combined substitution moment.

        Returns:
            (total_combined, total_individual)
        """
        if not timestamps:
            return 0, 0
        sorted_ts = sorted(timestamps)
        total_individual = len(sorted_ts)
        combined = 1
        prev = sorted_ts[0]
        for ts in sorted_ts[1:]:
            if ts - prev > _SIMULTANEOUS_WINDOW_S:
                combined += 1
            prev = ts
        return combined, total_individual

    def _compute_percentages(
        self,
        player_stats: Dict[str, Dict],
        starting_ids: List[str],
    ) -> Dict[str, float]:
        """Compute pct_minutes for the identified starting five.

        Formula: sum(group_avg_min) / sum(ALL_significant_avg_min) × 100.
        """
        total_avg_min = sum(s["avg_min_per_game"] for s in player_stats.values())
        denominator = total_avg_min if total_avg_min > 1e-9 else 1.0

        def _pct_for_group(ids: List[str]) -> float:
            valid = [player_stats[pid]["avg_min_per_game"] for pid in ids if pid in player_stats]
            return (sum(valid) / denominator * 100) if valid else 0.0

        return {
            "pct_minutes_starting_five": _pct_for_group(list(starting_ids)),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "total_games": 0,
            "games_with_playbyplay": 0,
            "players": [],
            "marginal_players": [],
            "significant_player_count": 0,
            "starting_five_ids": [],
            "starting_five_names": [],
            "starting_five_games_count": 0,
            "starting_five_games_pct": 0.0,
            "pct_minutes_starting_five": 0.0,
            "pct_minutes_top5": 0.0,
            "pct_minutes_top5_std": 0.0,
            "pct_minutes_top8": 0.0,
            "pct_minutes_top8_std": 0.0,
            "total_combined_substitutions": 0,
            "total_individual_substitutions": 0,
            "avg_combined_subs_per_game": 0.0,
            "avg_individual_subs_per_game": 0.0,
            "gini_index": 0.0,
            "cv": 0.0,
            "rotation_label": "Rotación amplia",
            "cv_label": "Muy homogéneo",
            "avg_stint_min_team": None,
        }

    @staticmethod
    def _accumulate_stints(
        timeline: Dict[str, List[Tuple[int, bool]]],
        game_min: Dict[str, float],
        pbp_minutes_acc: Dict[str, float],
        pbp_stints_acc: Dict[str, int],
    ) -> None:
        """Accumulate per-game stint data for players present in game_min.

        For each player in game_min (current team), count the number of
        on-court stints they have in this game's PBP timeline and add their
        game minutes and stint count to the accumulators.

        A stint is defined as a continuous on-court interval (one IN event).
        Starters have an implicit (0, True) event, so each starting spell also
        counts as a stint.
        """
        for pid, minutes in game_min.items():
            if minutes <= 0:
                continue
            # PBP IDs may be str or int; try both
            events = timeline.get(pid) or timeline.get(str(pid)) or []
            n_stints = sum(1 for _, is_on in events if is_on)
            # A player with boxscore minutes but NO PBP events at all played one
            # continuous stint (most common for starters who are never substituted).
            # Only apply the fallback when events is truly empty (not malformed data
            # where events exist but all are OUT — those are skipped deliberately).
            if n_stints == 0 and not events:
                n_stints = 1
            if n_stints > 0:
                pbp_minutes_acc[pid] = pbp_minutes_acc.get(pid, 0.0) + minutes
                pbp_stints_acc[pid] = pbp_stints_acc.get(pid, 0) + n_stints

    @staticmethod
    def _compute_stint_averages(
        pbp_minutes_acc: Dict[str, float],
        pbp_stints_acc: Dict[str, int],
    ) -> Dict[str, float]:
        """Return avg stint duration (minutes) per player.

        Only players with at least one PBP stint are included.
        Players with no PBP data (no timeline events) are absent from the result.
        """
        return {
            pid: round(pbp_minutes_acc[pid] / pbp_stints_acc[pid], 1)
            for pid in pbp_stints_acc
            if pbp_stints_acc.get(pid, 0) > 0 and pbp_minutes_acc.get(pid, 0) > 0
        }

    @staticmethod
    def _game_has_playbyplay(game: Dict, is_fbcyl: bool) -> bool:
        if is_fbcyl:
            moves = game.get("moves")
            return bool(moves)
        lines = game.get("PLAYBYPLAY", {}).get("LINES")
        return bool(lines)

    def _accumulate_player_minutes(
        self,
        game: Dict,
        team_id: str,
        is_fbcyl: bool,
        player_acc: Dict[str, Dict],
    ) -> Dict[str, float]:
        """Read player minutes from boxscore, accumulate into player_acc.

        Returns:
            {player_id: minutes_in_this_game} for per-game analysis.
        """
        if is_fbcyl:
            return self._accumulate_fbcyl(game, team_id, player_acc)
        return self._accumulate_feb(game, team_id, player_acc)

    def _accumulate_feb(
        self, game: Dict, team_id: str, player_acc: Dict[str, Dict]
    ) -> Dict[str, float]:
        game_min: Dict[str, float] = {}
        boxscore = game.get("BOXSCORE", {})
        for team in boxscore.get("TEAM", []):
            if str(team.get("id")) != str(team_id):
                continue
            for player in team.get("PLAYER", []):
                pid = str(player.get("id", ""))
                if not pid:
                    continue
                name = player.get("name", f"Player {pid}")
                # FEB field is 'min'; value is integer seconds OR 'MM:SS' string
                minutes = self._parse_feb_minutes(player.get("min", 0))
                if minutes <= 0:
                    continue
                if pid not in player_acc:
                    player_acc[pid] = {"name": name, "total_seconds": 0, "games_played": 0}
                player_acc[pid]["total_seconds"] += int(minutes * 60)
                player_acc[pid]["games_played"] += 1
                game_min[pid] = minutes
            break
        return game_min

    def _accumulate_fbcyl(
        self, game: Dict, team_id: str, player_acc: Dict[str, Dict]
    ) -> Dict[str, float]:
        game_min: Dict[str, float] = {}
        stats = game.get("stats", {})
        try:
            tid_int = int(team_id)
        except (ValueError, TypeError):
            tid_int = None

        for team in stats.get("teams", []):
            intern_id = team.get("teamIdIntern")
            extern_id = team.get("teamIdExtern")
            match = (
                str(intern_id) == str(team_id)
                or str(extern_id) == str(team_id)
                or (tid_int is not None and intern_id == tid_int)
                or (tid_int is not None and extern_id == tid_int)
            )
            if not match:
                continue
            for player in team.get("players", []):
                pid = str(player.get("licenseId") or player.get("uuid", ""))
                if not pid:
                    continue
                name = player.get("name", f"Player {pid}")
                minutes = float(player.get("timePlayed", 0) or 0)
                # Skip phantom players (inscribed but never played)
                if minutes <= 0:
                    continue
                if pid not in player_acc:
                    player_acc[pid] = {"name": name, "total_seconds": 0, "games_played": 0}
                player_acc[pid]["total_seconds"] += int(minutes * 60)
                player_acc[pid]["games_played"] += 1
                game_min[pid] = minutes
            break
        return game_min

    @staticmethod
    def _parse_feb_minutes(raw: Any) -> float:
        """Parse FEB 'min' field: integer/float in seconds OR 'MM:SS' string.

        The FEB BOXSCORE stores time as integer seconds in most collections.
        Some older exports use 'MM:SS' string format.  Both are handled.
        """
        if isinstance(raw, (int, float)):
            # Integer value is seconds — convert to minutes
            return float(raw) / 60.0
        if isinstance(raw, str):
            s = raw.strip()
            if ":" in s:
                parts = s.split(":")
                try:
                    return int(parts[0]) + int(parts[1]) / 60.0
                except (ValueError, IndexError):
                    pass
            try:
                return float(s) / 60.0
            except (ValueError, TypeError):
                pass
        return 0.0

    @staticmethod
    def _build_player_stats(
        player_acc: Dict[str, Dict], total_games: int
    ) -> Dict[str, Dict]:
        """Convert accumulated seconds to minute-based stats."""
        result = {}
        for pid, acc in player_acc.items():
            total_min = acc["total_seconds"] / 60.0
            games = acc["games_played"]
            avg = total_min / games if games > 0 else 0.0
            result[pid] = {
                "name": acc["name"],
                "total_minutes": total_min,
                "games_played": games,
                "avg_min_per_game": avg,
            }
        return result

    def _extract_sub_timestamps(
        self, analyzer: PlayByPlayAnalyzer, team_id: str, is_fbcyl: bool
    ) -> List[int]:
        """Extract substitution event timestamps (seconds) for a team's players."""
        timeline = analyzer.parse_substitutions()
        team_players = self._get_team_player_ids(analyzer.game_data, team_id, is_fbcyl, analyzer)
        timestamps: List[int] = []

        for pid in team_players:
            events = timeline.get(pid) or timeline.get(str(pid)) or []
            for ts, _ in events:
                # Skip the implicit (0, True) game-start event
                if ts > 0:
                    timestamps.append(ts)
        return timestamps

    @staticmethod
    def _get_team_player_ids(
        game: Dict, team_id: str, is_fbcyl: bool, analyzer: PlayByPlayAnalyzer
    ) -> Set[str]:
        """Return the set of player IDs belonging to the team in this game."""
        players: Set[str] = set()
        if is_fbcyl:
            try:
                tid_int = int(team_id)
            except (ValueError, TypeError):
                tid_int = None
            for team in game.get("stats", {}).get("teams", []):
                intern_id = team.get("teamIdIntern")
                extern_id = team.get("teamIdExtern")
                match = (
                    str(intern_id) == str(team_id)
                    or str(extern_id) == str(team_id)
                    or (tid_int is not None and intern_id == tid_int)
                    or (tid_int is not None and extern_id == tid_int)
                )
                if match:
                    for p in team.get("players", []):
                        actor_id = p.get("actorId")
                        pid = (
                            analyzer._fbcyl_actor_to_license.get(actor_id)
                            if actor_id is not None
                            else None
                        ) or str(p.get("licenseId") or p.get("uuid", ""))
                        if pid:
                            players.add(pid)
                    break
        else:
            for team in game.get("BOXSCORE", {}).get("TEAM", []):
                if str(team.get("id")) == str(team_id):
                    for p in team.get("PLAYER", []):
                        pid = str(p.get("id", ""))
                        if pid:
                            players.add(pid)
                    break
        return players
