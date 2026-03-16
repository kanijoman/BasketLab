"""Collections router — list available collections and their metadata."""

from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_db
from src.services import CollectionService

router = APIRouter()


@router.get("/list", summary="List all available basketball collections")
def list_collections(db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Return metadata for every FEB/FBCYL collection in MongoDB.

    Returns:
        List of objects with ``name``, ``league``, ``competition``,
        ``season``, ``group``, and ``game_count``.
        Sorted league → season desc → competition → group.
    """
    svc = CollectionService(db)
    return svc.list_available()


@router.delete("/{name}", summary="Drop a basketball collection")
def delete_collection(name: str, db=Depends(get_db)) -> Dict[str, str]:
    """Permanently drop the collection *name* from MongoDB.

    Args:
        name: Collection name, must start with ``FEB_`` or ``FBCYL_``.

    Returns:
        Confirmation message.

    Raises:
        400 if the name does not match the expected prefix.
        500 on database error.
    """
    svc = CollectionService(db)
    try:
        svc.drop_collection(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"message": f"Collection '{name}' dropped."}



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
