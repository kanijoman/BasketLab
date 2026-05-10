"""Matches router — single-match analysis endpoints.

Endpoints:
  GET /{collection}            → list all matches (lightweight)
  GET /{collection}/{match_id} → full head-to-head comparison
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_db
from src.services.collection_service import CollectionService
from src.services.match_analysis_service import MatchAnalysisService

router = APIRouter()


@router.get("/{collection}", summary="List all matches in a collection")
def list_matches(
    collection: str,
    is_fbcyl: bool = Query(False, description="Set true for FBCYL collections"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return a lightweight list of all matches in *collection*.

    Each item contains match_id, date, round, home/away team names and scores.
    Ordered as returned by MongoDB (insertion order).
    """
    svc = MatchAnalysisService(db, collection)
    return svc.get_match_list(is_fbcyl=is_fbcyl)


@router.get("/{collection}/{match_id}", summary="Full stats comparison for one match")
def get_match_analysis(
    collection: str,
    match_id: str,
    is_fbcyl: bool = Query(False, description="Set true for FBCYL collections"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return head-to-head stats comparison for a single match.

    The response contains:
    - ``home`` — home team name + full stats dict
    - ``away`` — away team name + full stats dict
    - ``comparison`` — ordered list of comparison rows, each with:
      ``stat_key``, ``label``, ``section``, ``home_value``, ``away_value``,
      ``delta``, ``winner`` (``"home"`` | ``"away"`` | ``"tie"``),
      ``lower_is_better``

    Returns HTTP 404 if *match_id* is not found in the collection.
    """
    # FEB collections use integer _id; FBCYL use string hex _id
    parsed_id: Any = match_id
    if not is_fbcyl:
        try:
            parsed_id = int(match_id)
        except ValueError:
            pass

    svc = MatchAnalysisService(db, collection)
    result = svc.get_match_analysis(match_id=parsed_id, is_fbcyl=is_fbcyl)
    if result is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    return result
