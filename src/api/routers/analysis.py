"""FastAPI router for team-level analytics endpoints (FASE 2-5).

Prefixed at /api/v1/analysis

Endpoints
---------
GET  /analysis/{collection}/rival_adjusted           FASE 2
POST /analysis/elasticity/train                      FASE 3/4
GET  /analysis/elasticity/models                     FASE 3/4
GET  /analysis/elasticity/predict/{team_id}          FASE 3/4
POST /analysis/montecarlo/{team_id}                  FASE 5

FASE 6-9 live in analysis_predictive.py
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.deps import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# FASE 2 â€” Rival-adjusted stats
# ---------------------------------------------------------------------------

@router.get(
    "/{collection}/rival_adjusted",
    summary="EstadÃ­sticas ajustadas por calidad del rival",
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
# FASE 3/4 â€” Elasticity models
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
    summary="Predecir prÃ³ximo partido con modelo de elasticidad",
)
def predict_next_game(
    team_id: str,
    season: str = Query(..., description='Temporada normalizada, e.g. "2024-25"'),
    is_home: Optional[bool] = Query(None, description="Â¿El equipo juega en casa?"),
    opp_net_rtg: Optional[float] = Query(
        None, description="Net rating del rival en la temporada"
    ),
    leagues: Optional[str] = Query(
        None, description="Liga para selecciÃ³n de modelo (FEB, FBCYL)"
    ),
    competitions: Optional[str] = Query(
        None, description="CompeticiÃ³n para selecciÃ³n de modelo (LF2, etc.)"
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
# FASE 5 â€” Monte Carlo simulation
# ---------------------------------------------------------------------------

class MonteCarloRequest(BaseModel):
    # Historical mode (requires season + team_id in URL)
    season: Optional[str] = Field(None, description='Temporada normalizada, e.g. "2024-25". Requerida en modo histÃ³rico.')
    # Live mode (reads current season from the active collection)
    live_collection: Optional[str] = Field(None, description="Nombre de la colecciÃ³n activa (modo temporada actual)")
    live_team_name: Optional[str] = Field(None, description="Nombre exacto del equipo en la colecciÃ³n activa")
    live_is_fbcyl: bool = Field(False, description="True si la colecciÃ³n es formato FBCYL")
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
    summary="ProyecciÃ³n Monte Carlo de prÃ³ximos partidos",
)
def run_monte_carlo(
    team_id: str,
    req: MonteCarloRequest,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Run a Monte Carlo simulation projecting the next n_games for a team.

    Supports two modes:
    - **HistÃ³rico**: supply ``season``. Uses HISTORICAL collection (trained data).
    - **Temporada actual**: supply ``live_collection``, ``live_team_name``, ``live_is_fbcyl``.
      Normalises live docs on-the-fly â€” does not affect elasticity training.

    Args:
        team_id: Team identifier (HISTORICAL) â€” ignored in live mode.
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
            raise HTTPException(status_code=422, detail="season es obligatorio en modo histÃ³rico.")
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


# FASE 6-9 endpoints are in analysis_predictive.py
