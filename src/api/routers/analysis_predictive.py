"""FastAPI router for predictive analytics endpoints (FASE 6-9).

Prefixed at /api/v1/analysis (same prefix as analysis.py, registered separately)

Endpoints
---------
GET  /analysis/backtesting/{team_id}                          FASE 6 (histórico)
GET  /analysis/backtesting-live/{collection}/{team_name}      FASE 6 (temporada actual)
POST /analysis/game-prediction/{team_id}                      FASE 7
GET  /analysis/player-prediction/{collection}/{player_id}     FASE 8
GET  /analysis/season-projection/{collection}                 FASE 9
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.deps import get_db

router = APIRouter()


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
    """Run walk-forward backtesting for a team's season."""
    from src.services.backtesting_service import BacktestingService
    leagues_list = [leagues] if leagues else None
    comps_list   = [competitions] if competitions else None
    svc = BacktestingService(db.connection)
    return svc.run_backtest(team_id, season, leagues_list, comps_list)


@router.get(
    "/backtesting-live/{collection}/{team_name}",
    summary="Validación walk-forward en temporada actual (sin HISTORICAL)",
)
def get_backtesting_live(
    collection: str,
    team_name: str,
    is_fbcyl: bool = Query(False, description="True si la colección es formato FBCYL"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Run walk-forward backtesting on current-season live data."""
    from src.services.backtesting_service import BacktestingService
    svc = BacktestingService(db.connection)
    return svc.run_backtest_live(collection, team_name, is_fbcyl)


# ---------------------------------------------------------------------------
# FASE 7 — Game prediction (Win/Loss classifier)
# ---------------------------------------------------------------------------

class GamePredictionRequest(BaseModel):
    season:          Optional[str]        = Field(None, description='Temporada normalizada, e.g. "2024-25". Requerida en modo histórico.')
    is_home:         bool                 = Field(..., description="¿El equipo juega en casa?")
    opp_net_rtg:     float                = Field(0.0, description="Net rating del rival en la temporada")
    live_collection: Optional[str]        = Field(None, description="Nombre de la colección en vivo (modo temporada actual)")
    live_team_name:  Optional[str]        = Field(None, description="Nombre del equipo en la colección en vivo")
    live_is_fbcyl:   bool                 = Field(False, description="True si la colección en vivo es formato FBCYL")
    leagues:         Optional[List[str]]  = None
    competitions:    Optional[List[str]]  = None


@router.post(
    "/game-prediction/{team_id}",
    summary="Predicción Victoria/Derrota para el próximo partido (FASE 7)",
)
def predict_game(
    team_id: str,
    req: GamePredictionRequest,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Predict Win/Loss probability using a calibrated Logistic Regression."""
    from src.services.game_prediction_service import GamePredictionService
    svc = GamePredictionService(db.connection)

    # Live mode: use current-season collection directly
    if req.live_collection and req.live_team_name:
        result = svc.predict_live(
            live_collection=req.live_collection,
            live_team_name=req.live_team_name,
            is_fbcyl=req.live_is_fbcyl,
            is_home=req.is_home,
            opp_net_rtg=req.opp_net_rtg,
        )
    elif req.season:
        result = svc.predict(
            team_id, req.season,
            is_home=req.is_home,
            opp_net_rtg=req.opp_net_rtg,
            leagues=req.leagues,
            competitions=req.competitions,
        )
    else:
        raise HTTPException(status_code=422, detail="Debes indicar 'season' (modo histórico) o 'live_collection' + 'live_team_name' (modo actual)")

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# FASE 8 — Player-level predictions
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
    """Predict a player's next-game counting stats using Ridge regression."""
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


# ---------------------------------------------------------------------------
# FASE 9 — Season-End Projections (Monte Carlo standings)
# ---------------------------------------------------------------------------

@router.get(
    "/season-projection/{collection}",
    summary="Proyección de clasificación final de liga por Monte Carlo (FASE 9)",
)
def get_season_projection(
    collection: str,
    season_length: int = Query(22, description="Número total de partidos por equipo en la temporada"),
    n_simulations: int = Query(1000, description="Número de simulaciones Monte Carlo"),
    playoff_spots: int = Query(4, description="Puestos de playoff"),
    is_fbcyl: bool = Query(False, description="True si la colección es formato FBCYL"),
    season: Optional[str] = Query(None, description='Temporada normalizada (sólo modo histórico), e.g. "2024-25"'),
    db=Depends(get_db),
) -> Any:
    """Project final league standings via Monte Carlo simulation.

    When ``season`` is omitted the live collection is used directly (temporada actual).
    When ``season`` is provided the data is loaded from HISTORICAL.
    """
    from src.services.season_projection_service import SeasonProjectionService
    svc = SeasonProjectionService(db.connection)
    result = svc.project(
        collection=collection,
        season_length=season_length,
        n_simulations=n_simulations,
        playoff_spots=playoff_spots,
        season=season,
        is_fbcyl=is_fbcyl,
    )
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
