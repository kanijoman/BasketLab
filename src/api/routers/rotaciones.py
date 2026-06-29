"""Rotaciones router — team rotation analysis."""

import asyncio
import json
import threading
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from src.api.deps import get_db
from src.services.rotation_service import RotationService

router = APIRouter()


@router.get(
    "/{collection}/{team_id}",
    summary="Analyse team rotation patterns for a full season",
)
def get_rotation_analysis(
    collection: str,
    team_id: str,
    team_name: str = Query(..., description="Human-readable team name"),
    min_games: int = Query(default=5, ge=0, description="Min games played to be significant"),
    min_total_min: float = Query(default=100.0, ge=0.0, description="Min total minutes to be significant"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return rotation metrics for a team across all games in the collection."""
    svc = RotationService(db)
    return svc.get_rotation_analysis(
        collection, team_id, team_name,
        min_games=min_games, min_total_min=min_total_min,
    )


@router.get(
    "/{collection}/{team_id}/stream",
    summary="Analyse rotation patterns with SSE progress stream",
)
async def stream_rotation_analysis(
    collection: str,
    team_id: str,
    team_name: str = Query(..., description="Human-readable team name"),
    min_games: int = Query(default=5, ge=0, description="Min games played to be significant"),
    min_total_min: float = Query(default=100.0, ge=0.0, description="Min total minutes to be significant"),
    db=Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events stream for rotation analysis.

    Emits ``{"progress": 0-100, "current": N, "total": N}`` events while
    processing, followed by a final ``{"done": true, "result": {...}}`` or
    ``{"done": true, "error": "..."}`` event.
    """
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
            svc = RotationService(db)
            data = svc.get_rotation_analysis(
                collection, team_id, team_name, progress_callback=_progress_cb,
                min_games=min_games, min_total_min=min_total_min,
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
            yield f"data: {json.dumps({'done': True, 'result': result_holder.get('data', {})})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
