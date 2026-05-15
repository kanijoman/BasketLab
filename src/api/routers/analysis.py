"""FastAPI router for team-level analytics endpoints (FASE 3-5).

Prefixed at /api/v1/analysis

Endpoints
---------
POST /analysis/elasticity/train                      FASE 3/4
GET  /analysis/elasticity/models                     FASE 3/4
GET  /analysis/elasticity/predict/{team_id}          FASE 3/4
POST /analysis/montecarlo/{team_id}                  FASE 5

FASE 6-9 live in analysis_predictive.py
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.deps import get_db

router = APIRouter()



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


@router.post(
    "/elasticity/train/stream",
    summary="Entrenar modelos de elasticidad con progreso SSE",
)
async def train_elasticity_stream(
    req: ElasticityTrainRequest,
    db=Depends(get_db),
) -> StreamingResponse:
    """Same as /elasticity/train but streams progress as Server-Sent Events.

    Each SSE event is ``data: <json>\\n\\n``.
    Progress events: ``{"step": str}``
    Final event:    ``{"done": true, "result": {...}}`` or ``{"done": true, "error": str}``
    """
    from src.services.elasticity_service import ElasticityService

    svc = ElasticityService(db.connection)
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _cb(msg: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {"step": msg})

    result_holder: Dict[str, Any] = {}

    def _worker() -> None:
        try:
            r = svc.train(req.leagues, req.competitions, progress_cb=_cb)
            result_holder["data"] = r
        except Exception as exc:  # pragma: no cover
            result_holder["error"] = str(exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    threading.Thread(target=_worker, daemon=True).start()

    async def _generate():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
        if "error" in result_holder:
            yield f"data: {json.dumps({'done': True, 'error': result_holder['error']})}\n\n"
        else:
            yield f"data: {json.dumps({'done': True, 'result': result_holder.get('data', {})})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    season: Optional[str] = Query(None, description='Temporada normalizada, e.g. "2024-25". Requerida en modo histórico.'),
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
    live_collection: Optional[str] = Query(
        None, description="Colección live para modo temporada actual (e.g. FEB_2526_Liga)"
    ),
    live_team_name: Optional[str] = Query(
        None, description="Nombre exacto del equipo en la colección live"
    ),
    live_is_fbcyl: Optional[bool] = Query(
        False, description="True si la colección live es formato FBCYL"
    ),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Predict next-game stats using trained Ridge elasticity models.

    Supports two modes:
    - **Histórico**: provide ``team_id`` (URL) + ``season`` query param.
    - **Live** (temporada actual): provide ``live_collection`` + ``live_team_name``.
      The ``team_id`` URL param is ignored in live mode.
    """
    from src.services.elasticity_service import ElasticityService
    leagues_list = [leagues] if leagues else None
    comps_list   = [competitions] if competitions else None
    svc = ElasticityService(db.connection)

    if live_collection:
        if not live_team_name:
            raise HTTPException(status_code=422, detail="live_team_name es obligatorio en modo live")
        result = svc.predict_next_game_live(
            live_collection=live_collection,
            team_name=live_team_name,
            is_fbcyl=live_is_fbcyl,
            is_home=is_home,
            opp_net_rtg=opp_net_rtg,
            leagues=leagues_list,
            competitions=comps_list,
        )
    else:
        if not season:
            raise HTTPException(status_code=422, detail="season es obligatorio en modo histórico")
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
