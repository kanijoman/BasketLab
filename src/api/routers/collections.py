"""Collections router — list available collections and their metadata."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_db
from src.services import CollectionService

router = APIRouter()


@router.get("/", summary="List teams inside a collection")
def list_teams(collection: str, db=Depends(get_db)) -> List[str]:
    """Return the sorted list of team names stored in *collection*.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.

    Returns:
        Alphabetically-sorted list of team name strings.

    Raises:
        404 if the collection is empty or doesn't exist.
    """
    svc = CollectionService(db)
    if not svc.collection_has_data(collection):
        raise HTTPException(status_code=404, detail=f"Collection '{collection}' not found or empty.")
    return svc.get_teams(collection)


@router.get("/format", summary="Detect league format for a collection")
def detect_format(collection: str) -> dict:
    """Return whether a collection belongs to FBCYL or FEB league format.

    Args:
        collection: MongoDB collection name.

    Returns:
        JSON object with ``is_fbcyl`` boolean key.
    """
    return {"collection": collection, "is_fbcyl": CollectionService.format_is_fbcyl(collection)}


@router.get("/resolve", summary="Build a collection name from its components")
def resolve_name(competition: str, season: str, group: str) -> dict:
    """Generate a safe collection name from competition/season/group components.

    Args:
        competition: Competition name (e.g. ``FEB``).
        season: Season identifier (e.g. ``LF2_2025``).
        group: Group label (e.g. ``A``).

    Returns:
        JSON object with the resolved ``collection_name`` string.
    """
    return {
        "collection_name": CollectionService.resolve_name(competition, season, group)
    }
