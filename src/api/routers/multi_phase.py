"""Multi-phase router — combine stats across several collections (phases).

Endpoints:
  GET /multi/team-stats?collections=C1,C2[&is_fbcyl=false]
  GET /multi/player-stats?collections=C1,C2
  GET /multi/team-stats/breakdown?collections=C1,C2
  GET /multi/player-stats/breakdown?collections=C1,C2
  GET /multi/sibling-collections?collection=FEB_LF2_2025_A
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services.collection_service import CollectionService
from src.services.multi_phase_service import MultiPhaseService

router = APIRouter()


def _parse_collections(raw: str) -> List[str]:
    """Split comma-separated collection string, skip blanks."""
    return [c.strip() for c in raw.split(",") if c.strip()]


@router.get("/team-stats", summary="Combined team stats across phases")
def get_multi_team_stats(
    collections: str = Query(..., description="Comma-separated collection names"),
    is_fbcyl: bool = Query(False),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return one merged team-stats row per team across all given collections."""
    names = _parse_collections(collections)
    if not names:
        return []
    svc = MultiPhaseService(db, names)
    return svc.get_combined_team_stats(is_fbcyl=is_fbcyl)


@router.get("/player-stats", summary="Combined player stats across phases")
def get_multi_player_stats(
    collections: str = Query(..., description="Comma-separated collection names"),
    is_fbcyl: bool = Query(False),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return one merged player-stats row per player across all given collections."""
    names = _parse_collections(collections)
    if not names:
        return []
    svc = MultiPhaseService(db, names)
    return svc.get_combined_player_stats(is_fbcyl=is_fbcyl)


@router.get("/team-stats/breakdown", summary="Per-phase team stats breakdown")
def get_team_stats_breakdown(
    collections: str = Query(..., description="Comma-separated collection names"),
    is_fbcyl: bool = Query(False),
    db=Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    """Return per-collection team stats keyed by collection name."""
    names = _parse_collections(collections)
    if not names:
        return {}
    svc = MultiPhaseService(db, names)
    return svc.get_team_stats_breakdown(is_fbcyl=is_fbcyl)


@router.get("/player-stats/breakdown", summary="Per-phase player stats breakdown")
def get_player_stats_breakdown(
    collections: str = Query(..., description="Comma-separated collection names"),
    is_fbcyl: bool = Query(False),
    db=Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    """Return per-collection player stats keyed by collection name."""
    names = _parse_collections(collections)
    if not names:
        return {}
    svc = MultiPhaseService(db, names)
    return svc.get_player_stats_breakdown(is_fbcyl=is_fbcyl)


@router.get("/sibling-collections", summary="Find sibling phase collections")
def get_sibling_collections(
    collection: str = Query(..., description="Reference collection name"),
    db=Depends(get_db),
) -> List[str]:
    """Return all collections sharing the same competition and season.

    Uses ``CollectionService.get_sibling_collections`` which matches on the
    competition and season components parsed from the collection name.
    """
    svc = CollectionService(db)
    all_colls = [c["name"] for c in svc.list_available()]
    return svc.get_sibling_collections(collection, all_colls)
