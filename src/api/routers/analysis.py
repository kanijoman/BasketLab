"""FastAPI router for predictive analytics endpoints (FASE 2-5).

Prefixed at /api/v1/analysis

Endpoints
---------
GET  /analysis/{collection}/rival_adjusted           FASE 2
POST /analysis/elasticity/train                      FASE 3/4
GET  /analysis/elasticity/models                     FASE 3/4
GET  /analysis/elasticity/predict/{team_id}          FASE 3/4
POST /analysis/montecarlo/{team_id}                  FASE 5
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.deps import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# FASE 2 — Rival-adjusted stats
# ---------------------------------------------------------------------------

@router.get(
    "/{collection}/rival_adjusted",
    summary="Estadísticas ajustadas por calidad del rival",
)
def get_rival_adjusted(
    collection: str,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return per-team stats adjusted for opponent strength.

    ``adj_avg = raw_avg - (opp_avg_allowed - league_avg_allowed)``

    Positive ``adj`` means better-than-expected performance vs schedule
    difficulty; negative means underperformance.

    Args:
        collection: MongoDB collection name.

    Returns:
        ``{team_name: {stat_key: {raw_avg, adj_avg, adj, sos, n}}}``
    """
    from src.services.rival_adjusted_service import RivalAdjustedService
    svc = RivalAdjustedService(db)
    result = svc.get_rival_adjusted_stats(collection)
    if not result:
        return {}
    return result


# ---------------------------------------------------------------------------
# FASE 3/4 — Elasticity models
# ---------------------------------------------------------------------------

class ElasticityTrainRequest(BaseModel):
    leagues: Optional[List[str]] = Field(
        None,
        description='Ligas a incluir ("FEB", "FBCYL"). None = todas.',
    )
    competitions: Optional[List[str]] = Field(
        None,
        description='Competiciones a incluir ("LF2", etc.). None = todas.',
    )


@router.post(
    "/elasticity/train",
    summary="Entrenar modelos de elasticidad Ridge (Modelo A + B)",
)
def train_elasticity(
    req: ElasticityTrainRequest,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Train Modelo A (global Ridge) and Modelo B (conditional Ridge) and
    persist them to the ELASTICITIES MongoDB collection.

    Requires data in the HISTORICAL collection (see /historical/ingest).

    Returns:
        ``{stat: {model_a: {r2, n}, model_b: {r2, n}}}``
    """
    from src.services.elasticity_service import ElasticityService
    svc = ElasticityService(db.connection)
    result = svc.train(req.leagues, req.competitions)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.get(
    "/elasticity/models",
    summary="Listar modelos de elasticidad entrenados",
)
def list_elasticity_models(db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Return metadata summary of all stored elasticity models."""
    from src.services.elasticity_service import ElasticityService
    svc = ElasticityService(db.connection)
    return svc.list_models()


@router.get(
    "/elasticity/predict/{team_id}",
    summary="Predecir próximo partido con modelo de elasticidad",
)
def predict_next_game(
    team_id: str,
    season: str = Query(..., description='Temporada normalizada, e.g. "2024-25"'),
    is_home: Optional[bool] = Query(None, description="¿El equipo juega en casa?"),
    opp_net_rtg: Optional[float] = Query(
        None, description="Net rating del rival en la temporada"
    ),
    leagues: Optional[str] = Query(
        None, description="Liga para selección de modelo (FEB, FBCYL)"
    ),
    competitions: Optional[str] = Query(
        None, description="Competición para selección de modelo (LF2, etc.)"
    ),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Predict next-game stats for a team using trained Ridge elasticity models.

    Args:
        team_id:     Team ID as stored in HISTORICAL.
        season:      Normalised season label.
        is_home:     Whether the next game is at home (enables Modelo B).
        opp_net_rtg: Opponent season net_rtg (enables Modelo B conditioning).
        leagues:     Filter for model selection.
        competitions: Filter for model selection.

    Returns:
        ``{stat: {model_a: {estimate, ci_low, ci_high, r2}, model_b: {...}}}``
    """
    from src.services.elasticity_service import ElasticityService
    leagues_list = [leagues] if leagues else None
    comps_list   = [competitions] if competitions else None
    svc = ElasticityService(db.connection)
    result = svc.predict_next_game(
        team_id, season,
        is_home=is_home, opp_net_rtg=opp_net_rtg,
        leagues=leagues_list, competitions=comps_list,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# FASE 5 — Monte Carlo simulation
# ---------------------------------------------------------------------------

class MonteCarloRequest(BaseModel):
    # Historical mode (requires season + team_id in URL)
    season: Optional[str] = Field(None, description='Temporada normalizada, e.g. "2024-25". Requerida en modo histórico.')
    # Live mode (reads current season from the active collection)
    live_collection: Optional[str] = Field(None, description="Nombre de la colección activa (modo temporada actual)")
    live_team_name: Optional[str] = Field(None, description="Nombre exacto del equipo en la colección activa")
    live_is_fbcyl: bool = Field(False, description="True si la colección es formato FBCYL")
    # Shared simulation params
    n_games: int = Field(5, ge=1, le=10, description="Partidos a proyectar")
    n_simulations: int = Field(
        1000, ge=100, le=5000, description="Simulaciones Monte Carlo"
    )
    is_home_schedule: Optional[List[bool]] = Field(
        None, description="Lista de local/visitante para cada partido proyectado"
    )
    opp_net_rtg_schedule: Optional[List[float]] = Field(
        None, description="Net rating rival para cada partido proyectado"
    )
    leagues: Optional[List[str]] = None
    competitions: Optional[List[str]] = None


@router.post(
    "/montecarlo/{team_id}",
    summary="Proyección Monte Carlo de próximos partidos",
)
def run_monte_carlo(
    team_id: str,
    req: MonteCarloRequest,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Run a Monte Carlo simulation projecting the next n_games for a team.

    Supports two modes:
    - **Histórico**: supply ``season``. Uses HISTORICAL collection (trained data).
    - **Temporada actual**: supply ``live_collection``, ``live_team_name``, ``live_is_fbcyl``.
      Normalises live docs on-the-fly — does not affect elasticity training.

    Args:
        team_id: Team identifier (HISTORICAL) — ignored in live mode.
        req:     Simulation parameters.

    Returns:
        Simulation results (see MonteCarloService).
    """
    from src.services.monte_carlo_service import MonteCarloService
    svc = MonteCarloService(db.connection)

    if req.live_collection:
        if not req.live_team_name:
            raise HTTPException(status_code=422, detail="live_team_name es obligatorio en modo temporada actual.")
        result = svc.simulate_from_live(
            live_collection=req.live_collection,
            team_name=req.live_team_name,
            is_fbcyl=req.live_is_fbcyl,
            n_games=req.n_games,
            n_simulations=req.n_simulations,
            is_home_schedule=req.is_home_schedule,
            opp_net_rtg_schedule=req.opp_net_rtg_schedule,
            leagues=req.leagues,
            competitions=req.competitions,
        )
    else:
        if not req.season:
            raise HTTPException(status_code=422, detail="season es obligatorio en modo histórico.")
        result = svc.simulate(
            team_id, req.season,
            n_games=req.n_games,
            n_simulations=req.n_simulations,
            is_home_schedule=req.is_home_schedule,
            opp_net_rtg_schedule=req.opp_net_rtg_schedule,
            leagues=req.leagues,
            competitions=req.competitions,
        )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# FASE 6 — Backtesting (walk-forward validation)
# ---------------------------------------------------------------------------

@router.get(
    "/backtesting/{team_id}",
    summary="Validación walk-forward de modelos de elasticidad (FASE 6)",
)
def get_backtesting(
    team_id: str,
    season: str = Query(..., description='Temporada normalizada, e.g. "2024-25"'),
    leagues: Optional[str] = Query(None, description="Liga para filtrar datos (FEB, FBCYL)"),
    competitions: Optional[str] = Query(None, description="Competición para filtrar datos"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Run walk-forward backtesting for a team's season.

    For each game from MIN_TRAIN_SIZE onwards, trains a Ridge model on all
    previous games and evaluates its prediction against the actual observed value.
    No future data is used in any training fold (strict time-series split).

    Args:
        team_id:      Team ID as stored in HISTORICAL.
        season:       Normalised season label.
        leagues:      Optional league filter.
        competitions: Optional competition filter.

    Returns:
        ``{stat: {model_a: {mae, rmse, mape, n_evaluated}, model_b: {...}}}``
    """
    from src.services.backtesting_service import BacktestingService
    leagues_list = [leagues] if leagues else None
    comps_list   = [competitions] if competitions else None
    svc = BacktestingService(db.connection)
    result = svc.run_backtest(team_id, season, leagues_list, comps_list)
    return result


# ---------------------------------------------------------------------------
# FASE 7 — Game prediction (Win/Loss classifier)
# ---------------------------------------------------------------------------

class GamePredictionRequest(BaseModel):
    season:       str   = Field(..., description='Temporada normalizada, e.g. "2024-25"')
    is_home:      bool  = Field(..., description="¿El equipo juega en casa?")
    opp_net_rtg:  float = Field(0.0, description="Net rating del rival en la temporada")
    leagues:      Optional[List[str]] = None
    competitions: Optional[List[str]] = None


@router.post(
    "/game-prediction/{team_id}",
    summary="Predicción Victoria/Derrota para el próximo partido (FASE 7)",
)
def predict_game(
    team_id: str,
    req: GamePredictionRequest,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Predict Win/Loss probability using a calibrated Logistic Regression.

    Trains on the team's season-to-date game history from HISTORICAL using
    rolling-window features + home/away context + opponent strength.

    Args:
        team_id: Team ID as stored in HISTORICAL.
        req:     Request body with season, context, and optional filters.

    Returns:
        ``{win_prob, ci_low, ci_high, feature_importances, n_train, accuracy}``
    """
    from src.services.game_prediction_service import GamePredictionService
    svc = GamePredictionService(db.connection)
    result = svc.predict(
        team_id,
        req.season,
        is_home=req.is_home,
        opp_net_rtg=req.opp_net_rtg,
        leagues=req.leagues,
        competitions=req.competitions,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# FASE 9 — Season-End Projections (Monte Carlo standings)
# ---------------------------------------------------------------------------

@router.get(
    "/season-projection/{collection}",
    summary="Proyección de clasificación final de liga por Monte Carlo (FASE 9)",
)
def get_season_projection(
    collection: str,
    season: str = Query(..., description='Temporada normalizada, e.g. "2024-25"'),
    season_length: int = Query(22, description="Número total de partidos por equipo en la temporada"),
    n_simulations: int = Query(1000, description="Número de simulaciones Monte Carlo"),
    playoff_spots: int = Query(4, description="Puestos de playoff"),
    db=Depends(get_db),
) -> Any:
    """Project final league standings via Monte Carlo simulation.

    For each remaining game, samples the outcome from a Bernoulli distribution
    based on the net-rating difference between teams.  Returns the projected
    wins distribution, playoff probability, and rank probability per team.

    Args:
        collection:    MongoDB live collection (used to scope HISTORICAL filter).
        season:        Normalised season label.
        season_length: Total games each team will play.
        n_simulations: Monte Carlo samples.
        playoff_spots: How many teams qualify for playoffs.

    Returns:
        List of team projection entries sorted by projected wins (desc).
    """
    from src.services.season_projection_service import SeasonProjectionService
    svc = SeasonProjectionService(db.connection)
    result = svc.project(
        collection=collection,
        season=season,
        season_length=season_length,
        n_simulations=n_simulations,
        playoff_spots=playoff_spots,
    )
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
# ---------------------------------------------------------------------------

@router.get(
    "/player-prediction/{collection}/{player_id}",
    summary="Predicción de estadísticas del próximo partido para un jugador (FASE 8)",
)
def predict_player(
    collection: str,
    player_id: str,
    is_home: bool = Query(..., description="¿El equipo juega en casa?"),
    opp_net_rtg: float = Query(0.0, description="Net rating del rival en la temporada"),
    is_fbcyl: bool = Query(False, description="True si la colección es formato FBCYL"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Predict a player's next-game counting stats using Ridge regression.

    Trains per-target-stat Ridge models on the player's game history from the
    live collection, using rolling-window features + context (home/opp strength).

    Args:
        collection: MongoDB live collection name.
        player_id:  Player identifier (FEB integer string or FBCYL UUID).
        is_home:    Whether the next game is at home.
        opp_net_rtg: Opponent net rating for context bucketing.
        is_fbcyl:   True for FBCYL format collections.

    Returns:
        ``{pts: {estimate, ci_low, ci_high, n_train}, reb: {...}, ast: {...}, val: {...}}``
    """
    from src.services.player_prediction_service import PlayerPredictionService
    svc = PlayerPredictionService(db.connection)
    result = svc.predict(
        collection=collection,
        player_id=player_id,
        is_home=is_home,
        opp_net_rtg=opp_net_rtg,
        is_fbcyl=is_fbcyl,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
