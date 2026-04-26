"""Monte Carlo projection service (FASE 5).

Simulates future game outcomes for a team using the fitted elasticity models
(Ridge + Bootstrap CI) from FASE 3/4.  Each simulation samples from the
Bootstrap CI distribution of next-game predictions, producing a probability
distribution over outcomes rather than a single point estimate.

For N games ahead:
  - Draw M samples per game from the Bootstrap prediction distribution.
  - Each sample is a full stat vector: net_rtg, efg_pct, tov_rate, etc.
  - Win probability per game = fraction of samples where net_rtg > 0.
  - Summary: expected value ± σ per stat, cumulative win probability.

The service deliberately uses only boxscore / aggregate data (no positional
or tactical context) consistent with the project's data constraints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from database.historical_repository import HistoricalRepository
from services.elasticity_service import (
    ElasticityRepository,
    TARGET_STATS,
    ROLLING_WINDOWS,
    _predict_with_ci,
)
from services.live_history_adapter import LiveHistoryAdapter

N_SIMULATIONS_DEFAULT = 1000
MAX_GAMES_AHEAD = 10


class MonteCarloService:
    """Project future team performance with uncertainty via Monte Carlo sampling.

    Workflow
    --------
    1. Load team's season-to-date game history from HISTORICAL.
    2. For each target stat, retrieve the Modelo A/B Ridge model.
    3. Compute rolling-window features from the last games.
    4. Sample N_SIMULATIONS draws from N(estimate, σ_bootstrap) per stat.
    5. Project n_games_ahead by feeding each simulation's output back as
       the next game's history (auto-regressive rollout).
    6. Return mean, std, CI, and win probability per future game.
    """

    def __init__(self, connection) -> None:
        self._conn = connection
        self._hist = HistoricalRepository(connection)
        self._repo = ElasticityRepository(connection)
        self._live = LiveHistoryAdapter(connection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(
        self,
        team_id: str,
        season: str,
        n_games: int = 5,
        n_simulations: int = N_SIMULATIONS_DEFAULT,
        is_home_schedule: Optional[List[bool]] = None,
        opp_net_rtg_schedule: Optional[List[float]] = None,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation using HISTORICAL data for a team.

        Args:
            team_id:              Team identifier (as stored in HISTORICAL).
            season:               Normalised season ("2024-25").
            n_games:              Number of future games to project (1–10).
            n_simulations:        Number of Monte Carlo draws per game.
            is_home_schedule:     Home/away schedule. Defaults to alternating.
            opp_net_rtg_schedule: Opponent net_rtg per game. Defaults to 0.0.
            leagues:              Model filter.
            competitions:         Model filter.

        Returns:
            Simulation dict or ``{"error": str}`` on failure.
        """
        n_games = max(1, min(n_games, MAX_GAMES_AHEAD))
        records = self._hist.get_team_history(team_id, season)
        if not records:
            return {"error": f"Sin historial para equipo {team_id} temporada {season}"}
        records.sort(key=lambda r: r.get("date") or datetime.min)
        return self._simulate_from_records(
            records=records,
            team_label=team_id,
            season_label=season,
            n_games=n_games,
            n_simulations=n_simulations,
            is_home_schedule=is_home_schedule,
            opp_net_rtg_schedule=opp_net_rtg_schedule,
            leagues=leagues,
            competitions=competitions,
        )

    def simulate_from_live(
        self,
        live_collection: str,
        team_name: str,
        is_fbcyl: bool,
        n_games: int = 5,
        n_simulations: int = N_SIMULATIONS_DEFAULT,
        is_home_schedule: Optional[List[bool]] = None,
        opp_net_rtg_schedule: Optional[List[float]] = None,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation using the current live collection.

        Reads game documents from ``live_collection`` and normalises them
        on-the-fly via ``LiveHistoryAdapter`` — no HISTORICAL ingestion needed.
        Elasticity model training is unaffected (still uses HISTORICAL only).

        Args:
            live_collection: MongoDB collection name (e.g. ``"FBCYL_...2026"``).
            team_name:       Exact team name as stored in the live collection.
            is_fbcyl:        True for FBCYL format, False for FEB format.
            n_games:         Games to project (1–10).
            n_simulations:   Monte Carlo draws per game.
            is_home_schedule:     Home/away schedule. Defaults to alternating.
            opp_net_rtg_schedule: Opponent net_rtg per game. Defaults to 0.0.
            leagues:         Model filter.
            competitions:    Model filter.

        Returns:
            Simulation dict or ``{"error": str}`` on failure.
        """
        n_games = max(1, min(n_games, MAX_GAMES_AHEAD))
        records = self._live.get_team_history(live_collection, team_name, is_fbcyl)
        if not records:
            return {
                "error": (
                    f"Sin datos para '{team_name}' en la colección '{live_collection}'. "
                    "Comprueba el nombre del equipo y el formato (FEB/FBCYL)."
                )
            }
        season_label = records[0].get("season", live_collection)
        return self._simulate_from_records(
            records=records,
            team_label=team_name,
            season_label=season_label,
            n_games=n_games,
            n_simulations=n_simulations,
            is_home_schedule=is_home_schedule,
            opp_net_rtg_schedule=opp_net_rtg_schedule,
            leagues=leagues,
            competitions=competitions,
        )

    # ------------------------------------------------------------------
    # Core simulation loop (shared by both public methods)
    # ------------------------------------------------------------------

    def _simulate_from_records(
        self,
        records: List[Dict[str, Any]],
        team_label: str,
        season_label: str,
        n_games: int,
        n_simulations: int,
        is_home_schedule: Optional[List[bool]],
        opp_net_rtg_schedule: Optional[List[float]],
        leagues: Optional[List[str]],
        competitions: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Execute the Monte Carlo simulation given pre-loaded game records."""
        league_tag = ",".join(leagues) if leagues else "ALL"
        comp_tag   = ",".join(competitions) if competitions else "ALL"

        if is_home_schedule is None:
            is_home_schedule = [i % 2 == 0 for i in range(n_games)]
        if opp_net_rtg_schedule is None:
            opp_net_rtg_schedule = [0.0] * n_games

        # Pre-load Modelo A for each target stat
        models: Dict[str, Dict] = {}
        for stat in TARGET_STATS:
            doc = self._repo.get_model("A", stat, league_tag, comp_tag)
            if doc:
                models[stat] = doc

        if not models:
            return {"error": "No hay modelos entrenados. Ejecuta /elasticity/train primero."}

        # Build initial rolling history per stat
        history: Dict[str, List[float]] = {
            stat: [r[stat] for r in records if r.get(stat) is not None]
            for stat in models
        }

        game_samples: List[Dict[str, np.ndarray]] = []

        for g_idx in range(n_games):
            game_draws: Dict[str, np.ndarray] = {}

            for stat, model_doc in models.items():
                vals = history[stat]
                rolling: List[float] = []
                for w in ROLLING_WINDOWS:
                    window = vals[-w:] if len(vals) >= w else vals
                    rolling.append(float(np.mean(window)) if window else 0.0)

                pred = _predict_with_ci(model_doc, rolling)
                estimate = pred["estimate"]
                ci_range = pred["ci_high"] - pred["ci_low"]
                sigma = ci_range / 3.29 if ci_range > 0 else 1.0

                rng = np.random.default_rng(42 + g_idx)
                draws = rng.normal(estimate, sigma, n_simulations)
                game_draws[stat] = draws

            game_samples.append(game_draws)

            for stat in models:
                history[stat].append(float(np.mean(game_samples[-1][stat])))

        games_result: List[Dict[str, Any]] = []
        all_net_rtg_sim: List[np.ndarray] = []

        for g_idx, game_draws in enumerate(game_samples):
            nr = game_draws.get("net_rtg", np.zeros(n_simulations))
            win_prob = float(np.mean(nr > 0))
            all_net_rtg_sim.append(nr)

            stats_out: Dict[str, Dict[str, float]] = {
                stat: {
                    "mean":    round(float(np.mean(arr)), 2),
                    "std":     round(float(np.std(arr)), 2),
                    "ci_low":  round(float(np.percentile(arr, 5)), 2),
                    "ci_high": round(float(np.percentile(arr, 95)), 2),
                }
                for stat, arr in game_draws.items()
            }

            games_result.append({
                "game_index":  g_idx + 1,
                "is_home":     is_home_schedule[g_idx] if g_idx < len(is_home_schedule) else None,
                "opp_net_rtg": opp_net_rtg_schedule[g_idx] if g_idx < len(opp_net_rtg_schedule) else None,
                "win_prob":    round(win_prob, 3),
                "stats":       stats_out,
            })

        wins_per_sim = np.zeros(n_simulations)
        for nr in all_net_rtg_sim:
            wins_per_sim += (nr > 0).astype(float)

        return {
            "team_id":              team_label,
            "season":               season_label,
            "n_games":              n_games,
            "n_simulations":        n_simulations,
            "games":                games_result,
            "projected_wins_mean":  round(float(np.mean(wins_per_sim)), 2),
            "projected_wins_std":   round(float(np.std(wins_per_sim)), 2),
            "projected_wins_ci_low":  round(float(np.percentile(wins_per_sim, 5)), 2),
            "projected_wins_ci_high": round(float(np.percentile(wins_per_sim, 95)), 2),
        }
