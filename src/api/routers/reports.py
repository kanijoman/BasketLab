"""
Reports router — Phase 5.

Endpoints:
  GET  /{collection}/player-scouting/{player_id}  → DOCX bytes
  GET  /{collection}/team-scouting/{team_name}     → PDF bytes
  GET  /{collection}/season-summary                → PDF bytes
  POST /{collection}/weekly-report                 → ZIP bytes (PNG bundle)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

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


class _WeeklyReportRequest(BaseModel):
    team_a: str
    team_b: str


@router.post("/{collection}/weekly-report", summary="Informe semanal ZIP")
def weekly_report(
    collection: str,
    body: _WeeklyReportRequest,
    db=Depends(get_db),
):
    """Generate a full weekly report ZIP (PNG bundle) for two selected teams.

    The ZIP structure mirrors the Qt WeeklyReportGenerator output:
    ``General/`` with competition-wide stats + last-match tables, plus one
    sub-folder per team with individual player stats and shot-chart images.

    Args:
        collection: MongoDB collection name.
        body: JSON body with ``team_a`` (own team) and ``team_b`` (rival).

    Returns:
        ZIP file download with all PNG images.
    """
    from src.services.weekly_report_service import WeeklyReportService
    svc = WeeklyReportService(db)
    zip_bytes = svc.generate_report_zip(collection, body.team_a, body.team_b)
    safe = collection[:20].replace(' ', '_')
    return Response(
        content=zip_bytes,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="informe_{safe}.zip"'},
    )
