"""Season Projection Service — FASE 9: Monte Carlo season-end standings.

Projects the final standings distribution for a league by simulating the
remaining games of the season.  Each simulated game's outcome is drawn from
a Bernoulli distribution whose parameter is estimated from the Elo-like
logistic model ``win_prob_from_net_rtg()``.

Algorithm
---------
1. Load per-game HISTORICAL records for all teams in the collection/season.
2. Compute current record (wins, losses, avg net_rtg) per team.
3. Estimate remaining games: ``season_length - games_played``.
4. For each simulation:
   a. Build a round-robin schedule of the remaining games
      (opponents drawn proportionally, home/away alternated).
   b. Sample each game outcome from
      ``Bernoulli(win_prob_from_net_rtg(team_rtg, opp_rtg))``.
   c. Accumulate final wins per team.
5. Aggregate across simulations:
   - projected wins: mean (with 5th/95th percentile CI)
   - playoff probability: P(rank <= playoff_spots) across simulations
   - rank_probs: fraction of simulations where team finishes at each rank

Public API
----------
``SeasonProjectionService.project(collection, season, season_length, n_simulations)``
``win_prob_from_net_rtg(team_rtg, opp_rtg)``  — importable for unit tests
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

PLAYOFF_SPOTS_DEFAULT = 4   # top-4 qualify for playoffs by default
_MIN_GAMES_FOR_RTG = 1      # minimum games to estimate net_rtg


# ---------------------------------------------------------------------------
# Public helper — importable for unit tests
# ---------------------------------------------------------------------------

def win_prob_from_net_rtg(team_rtg: float, opp_rtg: float) -> float:
    """Logistic win probability from net-rating difference.

    Uses the same scale factor as Elo (400 / ln(10) ≈ 173.7).
    When team_rtg == opp_rtg the probability is exactly 0.5.

    Args:
        team_rtg: Home/subject team net rating (points per 100 poss).
        opp_rtg:  Opponent net rating.

    Returns:
        Win probability in [0, 1].
    """
    diff = float(team_rtg) - float(opp_rtg)
    return float(1.0 / (1.0 + np.exp(-diff / 10.0)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _team_net_rtg(records: List[Dict[str, Any]]) -> float:
    rtgs = [r.get("net_rtg") for r in records if r.get("net_rtg") is not None]
    if not rtgs:
        return 0.0
    return float(np.mean(rtgs))


def _team_wins(records: List[Dict[str, Any]]) -> int:
    """Count wins from records.

    Prefers the explicit ``result`` field (1 = win) when present.
    Falls back to ``net_rtg > 0`` for live records that have no result field.
    """
    wins = 0
    for r in records:
        res = r.get("result")
        if res is not None:
            wins += int(res == 1)
        else:
            nr = r.get("net_rtg")
            if nr is not None:
                wins += int(nr > 0)
    return wins


def _simulate_remaining(
    current_wins: Dict[str, int],
    remaining_per_team: Dict[str, int],
    team_rtgs: Dict[str, float],
    team_ids: List[str],
    rng: np.random.Generator,
) -> Dict[str, int]:
    """Simulate one set of remaining games; returns total wins after simulation."""
    sim_wins = dict(current_wins)

    # Build schedule: for each team, create opponent list.
    # The `if team_id < opp` guard ensures each pair is added only by the
    # lower-sorted team, so no deduplication is needed.  Repeats are
    # intentional: when remaining > n_opponents the same pair plays twice
    # (double/triple round-robin format).
    games: List[tuple] = []

    for team_id in team_ids:
        rem = remaining_per_team.get(team_id, 0)
        if rem <= 0:
            continue
        opponents = [t for t in team_ids if t != team_id]
        if not opponents:
            continue
        # Round-robin fill: repeat opponent list to cover remaining games
        n_opp = len(opponents)
        opp_list = (opponents * (rem // n_opp + 1))[:rem]
        for opp in opp_list:
            # Add game only once (the higher-sorted ID creates the pair)
            if team_id < opp:
                games.append((team_id, opp))

    for team_a, team_b in games:
        rtg_a = team_rtgs.get(team_a, 0.0)
        rtg_b = team_rtgs.get(team_b, 0.0)
        p_a   = win_prob_from_net_rtg(rtg_a, rtg_b)
        a_wins = rng.random() < p_a
        if a_wins:
            sim_wins[team_a] = sim_wins.get(team_a, 0) + 1
        else:
            sim_wins[team_b] = sim_wins.get(team_b, 0) + 1

    return sim_wins


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class SeasonProjectionService:
    """Project final league standings via Monte Carlo simulation.

    Uses net_rtg-based win probabilities (``win_prob_from_net_rtg``) to
    simulate each remaining game without requiring a pre-loaded schedule.
    """

    def __init__(self, connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def project(
        self,
        collection: str,
        season: Optional[str] = None,
        season_length: int = 22,
        n_simulations: int = 1000,
        playoff_spots: int = PLAYOFF_SPOTS_DEFAULT,
        is_fbcyl: bool = False,
    ) -> Any:
        """Project final standings distribution for a league season.

        When ``season`` is None the live collection is used directly via
        LiveHistoryAdapter (current-season mode, no HISTORICAL required).
        When ``season`` is provided, loads from HISTORICAL filtered by season.
        """
        if season:
            league_data = self._load_league_data(collection, season)
        else:
            league_data = self._load_league_data_live(collection, is_fbcyl)

        if not league_data:
            msg = (
                "No se encontraron datos en HISTORICAL para esta temporada"
                if season else
                "No se encontraron partidos en la colección activa"
            )
            return {"error": msg}

        team_ids   = list(league_data.keys())
        team_names = {}
        wins_so_far: Dict[str, int] = {}
        losses_so_far: Dict[str, int] = {}
        games_played: Dict[str, int] = {}
        team_rtgs:  Dict[str, float] = {}

        for team_id, records in league_data.items():
            valid = [r for r in records if r is not None]
            wins_so_far[team_id]   = _team_wins(valid)
            games_played[team_id]  = len(valid)
            losses_so_far[team_id] = len(valid) - wins_so_far[team_id]
            team_rtgs[team_id]     = _team_net_rtg(valid)
            team_names[team_id]    = (valid[0].get("team_name", team_id) if valid else team_id)

        # Auto-detect season_length when all teams have played more than the default.
        # If the user left the default (e.g., 22) but the season is longer, estimate
        # the real length from the round-robin structure: each team plays (N-1) games
        # per round; find the next complete round boundary above max_played.
        max_played = max(games_played.values()) if games_played else 0
        n_teams = len(team_ids)
        if n_teams > 1 and max_played > season_length:
            games_per_rr = n_teams - 1
            n_complete_rr = math.ceil(max_played / games_per_rr)
            effective_season_length = max(season_length, n_complete_rr * games_per_rr)
        else:
            effective_season_length = max(season_length, max_played)

        # Clamp: remaining games cannot be negative
        remaining_per_team = {
            tid: max(0, effective_season_length - games_played[tid])
            for tid in team_ids
        }

        # If all games played, compute rankings from current record directly
        if all(r == 0 for r in remaining_per_team.values()):
            sorted_teams = sorted(team_ids, key=lambda t: wins_so_far[t], reverse=True)
            rank_map = {tid: rank + 1 for rank, tid in enumerate(sorted_teams)}
            entries = []
            for tid in team_ids:
                rank = rank_map[tid]
                entries.append({
                    "team_id":           tid,
                    "team_name":         team_names[tid],
                    "wins_so_far":       wins_so_far[tid],
                    "losses_so_far":     losses_so_far[tid],
                    "proj_wins":         float(wins_so_far[tid]),
                    "proj_losses":       float(losses_so_far[tid]),
                    "proj_wins_ci_low":  float(wins_so_far[tid]),
                    "proj_wins_ci_high": float(wins_so_far[tid]),
                    "playoff_prob":      1.0 if rank <= playoff_spots else 0.0,
                    "rank_probs":        {rank: 1.0},
                })
            entries.sort(key=lambda e: e["proj_wins"], reverse=True)
            return entries

        # Monte Carlo
        rng = np.random.default_rng(42)
        all_sim_wins: Dict[str, List[int]] = {tid: [] for tid in team_ids}
        all_sim_ranks: Dict[str, List[int]] = {tid: [] for tid in team_ids}

        for _ in range(n_simulations):
            sim = _simulate_remaining(
                wins_so_far, remaining_per_team, team_rtgs, team_ids, rng
            )
            # Rank teams in this simulation (1 = most wins)
            sorted_teams = sorted(team_ids, key=lambda t: sim.get(t, 0), reverse=True)
            for rank_1based, tid in enumerate(sorted_teams, start=1):
                all_sim_wins[tid].append(sim.get(tid, wins_so_far[tid]))
                all_sim_ranks[tid].append(rank_1based)

        entries = []
        for tid in team_ids:
            sim_w   = np.array(all_sim_wins[tid], dtype=float)
            sim_r   = np.array(all_sim_ranks[tid], dtype=int)

            proj_w  = float(np.mean(sim_w))
            ci_low  = float(np.percentile(sim_w, 5))
            ci_high = float(np.percentile(sim_w, 95))

            playoff_prob = float(np.mean(sim_r <= playoff_spots))

            unique_ranks = sorted(set(sim_r.tolist()))
            rank_probs = {
                int(r): round(float(np.mean(sim_r == r)), 4)
                for r in unique_ranks
            }

            entries.append({
                "team_id":           tid,
                "team_name":         team_names[tid],
                "wins_so_far":       wins_so_far[tid],
                "losses_so_far":     losses_so_far[tid],
                "proj_wins":         round(proj_w, 2),
                "proj_losses":       round(effective_season_length - proj_w, 2),
                "proj_wins_ci_low":  round(ci_low, 2),
                "proj_wins_ci_high": round(ci_high, 2),
                "playoff_prob":      round(playoff_prob, 4),
                "rank_probs":        rank_probs,
            })

        entries.sort(key=lambda e: e["proj_wins"], reverse=True)
        return entries

    # ------------------------------------------------------------------
    # Internal helpers (patchable in tests)
    # ------------------------------------------------------------------

    def _load_league_data(
        self, collection: str, season: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Load per-team game histories for all teams in a season.

        Returns ``{team_id: [game_record, ...]}`` from the HISTORICAL collection.
        Filters to the given season label.
        """
        if not self._conn.is_connected():
            return {}
        try:
            from database.historical_repository import HistoricalRepository
            repo = HistoricalRepository(self._conn)
            all_docs = repo.get_seasons_for_elasticity()

            # Filter to the right collection (no direct field on HISTORICAL —
            # proxy via competition label extracted from collection name)
            season_docs = [d for d in all_docs if d.get("season") == season]

            league: Dict[str, List[Dict[str, Any]]] = {}
            for doc in season_docs:
                tid = str(doc.get("team_id", ""))
                if tid:
                    league.setdefault(tid, []).append(doc)
            return league
        except Exception:
            return {}

    def _load_league_data_live(
        self,
        collection: str,
        is_fbcyl: bool,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Load per-team game histories from a live collection via LiveHistoryAdapter.

        Gets distinct team names from the collection using the correct field paths
        for each format (FEB: BOXSCORE.TEAM.name, FBCYL: stats.teams.name),
        then retrieves each team's history in HISTORICAL-schema format.
        """
        if not self._conn.is_connected():
            return {}
        try:
            from services.live_history_adapter import LiveHistoryAdapter

            col = self._conn.get_collection(collection)
            if col is None:
                return {}

            if is_fbcyl:
                raw_names = col.distinct("stats.teams.name")
            else:
                raw_names = col.distinct("BOXSCORE.TEAM.name")

            raw_names = [n for n in raw_names if n]
            if not raw_names:
                return {}

            adapter = LiveHistoryAdapter(self._conn)
            league: Dict[str, List[Dict[str, Any]]] = {}
            for name in raw_names:
                records = adapter.get_team_history(collection, name, is_fbcyl)
                if records:
                    league[name] = records
            return league
        except Exception:
            return {}
