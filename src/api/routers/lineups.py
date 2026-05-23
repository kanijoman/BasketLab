"""Lineups router — player combination analysis."""

import asyncio
import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.api.deps import get_db
from src.services import LineupService

router = APIRouter()

ALLOWED_STATS = {
    'net_rating', 'plus_minus', 'points_for', 'points_against',
    'ortg', 'drtg', 'efg_pct', 'tov_pct', 'orb_pct', 'ftr',
    'ast', 'trb',
}


@router.get("/{collection}/{team_id}", summary="Analyse player lineup combinations for a team")
def get_lineup_analysis(
    collection: str,
    team_id: str,
    team_name: str = Query(..., description="Human-readable team name"),
    size: int = Query(5, ge=2, le=5, description="Players per lineup (2-5)"),
    stat: str = Query("net_rating", description="Stat to sort by"),
    period: int = Query(0, ge=0, description="Days back filter (0 = full season)"),
    include_game_log: bool = Query(False, description="Include per-game breakdown in response"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return player combinations sorted by the chosen stat.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        team_id: Team identifier (FEB numeric string or FBCYL UUID-like).
        team_name: Human-readable team name for display purposes.
        size: Number of players per lineup group (default 5).
        stat: Stat key to sort by (default ``net_rating``).
        period: Number of days to look back; 0 means the full season.
        include_game_log: When True, each lineup includes a ``game_log`` list.

    Returns:
        List of lineup dicts sorted by ``stat`` (descending for higher-is-better
        stats, ascending for ``drtg`` and ``tov_pct``).
    """
    if stat not in ALLOWED_STATS:
        raise HTTPException(status_code=400, detail=f"Invalid stat '{stat}'. Allowed: {sorted(ALLOWED_STATS)}")

    date_filter: Optional[Dict] = None
    if period > 0:
        cutoff = datetime.utcnow() - timedelta(days=period)
        date_filter = {"$gte": cutoff.strftime("%Y-%m-%d")}

    svc = LineupService(db)
    return svc.get_lineup_analysis(
        collection,
        team_id,
        team_name,
        combination_size=size,
        stat=stat,
        date_filter=date_filter,
        include_game_log=include_game_log,
    )


@router.get("/{collection}/{team_id}/stream", summary="Analyse lineups with SSE progress stream")
async def stream_lineup_analysis(
    collection: str,
    team_id: str,
    team_name: str = Query(..., description="Human-readable team name"),
    size: int = Query(5, ge=2, le=5, description="Players per lineup (2-5)"),
    stat: str = Query("net_rating", description="Stat to sort by"),
    period: int = Query(0, ge=0, description="Days back filter (0 = full season)"),
    include_game_log: bool = Query(False, description="Include per-game breakdown in response"),
    db=Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events stream for lineup analysis.

    Emits progress events ``{"progress": 0-100, "current": N, "total": N}``
    while the analysis runs, then a final ``{"done": true, "result": [...]}``
    or ``{"done": true, "error": "..."}`` event.
    """
    if stat not in ALLOWED_STATS:
        raise HTTPException(status_code=400, detail=f"Invalid stat '{stat}'. Allowed: {sorted(ALLOWED_STATS)}")

    date_filter: Optional[Dict] = None
    if period > 0:
        cutoff = datetime.utcnow() - timedelta(days=period)
        date_filter = {"$gte": cutoff.strftime("%Y-%m-%d")}

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    result_holder: Dict[str, Any] = {}

    def _progress_cb(current: int, total: int) -> None:
        pct = round(current / total * 100) if total else 0
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"progress": pct, "current": current, "total": total},
        )

    def _worker() -> None:
        try:
            svc = LineupService(db)
            data = svc.get_lineup_analysis(
                collection,
                team_id,
                team_name,
                combination_size=size,
                stat=stat,
                date_filter=date_filter,
                include_game_log=include_game_log,
                progress_callback=_progress_cb,
            )
            result_holder["data"] = data
        except Exception as exc:  # noqa: BLE001
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
            yield f"data: {json.dumps({'done': True, 'result': result_holder.get('data', [])})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
