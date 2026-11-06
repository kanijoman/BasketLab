"""Assist connections router: who passes, who receives and from which zones the receiver scores (issue #773)."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services.assist_connection_service import AssistConnectionService

router = APIRouter()


@router.get("/{collection}/{team_id}", summary="Assist connections of a team: passers, receivers and the zones they score from, assisted and not assisted")
def get_assist_connections(
    collection: str,
    team_id: str,
    player_id: Optional[str] = Query(default=None, description="Adds the detail of this player as receiver and as passer"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    return AssistConnectionService(db).get_connections(collection, team_id, player_id)
