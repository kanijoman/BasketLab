"""
Reports router — Phase 5.

Endpoints:
  GET /{collection}/player-scouting/{player_id}  → DOCX bytes
  GET /{collection}/team-scouting/{team_name}     → PDF bytes
  GET /{collection}/season-summary                → PDF bytes
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from src.api.deps import get_db
from src.services.report_service import (
    build_player_scouting_docx,
    build_team_scouting_pdf,
    build_season_summary_pdf,
)

router = APIRouter(tags=["reports"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MIME  = "application/pdf"


@router.get("/{collection}/player-scouting/{player_id}", summary="Player scouting DOCX")
def player_scouting(collection: str, player_id: str, db=Depends(get_db)):
    """Generate a one-page individual scouting sheet as DOCX."""
    data = build_player_scouting_docx(collection, player_id, db)
    filename = f"scouting_{player_id}.docx"
    return Response(
        content=data,
        media_type=_DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{collection}/team-scouting/{team_name}", summary="Team scouting PDF")
def team_scouting(collection: str, team_name: str, db=Depends(get_db)):
    """Generate an offensive/defensive breakdown scouting PDF for a team."""
    safe_name = team_name.replace(" ", "_")[:40]
    filename  = f"scouting_{safe_name}.pdf"
    data = build_team_scouting_pdf(collection, team_name, db)
    return Response(
        content=data,
        media_type=_PDF_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{collection}/season-summary", summary="Season summary PDF")
def season_summary(collection: str, db=Depends(get_db)):
    """Generate a league-wide season efficiency ranking PDF."""
    data = build_season_summary_pdf(collection, db)
    filename = f"temporada_{collection[:30]}.pdf"
    return Response(
        content=data,
        media_type=_PDF_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
