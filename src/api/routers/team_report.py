"""Rule-based team report endpoints (own-team analysis / rival scouting).

Prefixed at /api/v1/reports

GET /team-report/{collection}?team_id=&mode=own|rival       -> JSON report
GET /team-report/{collection}/pdf?team_id=&mode=own|rival   -> PDF bytes
"""
from __future__ import annotations

from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from src.api.deps import get_db
from src.report_engine.html_renderer import render_report_html
from src.services.team_report_service import TeamNotFoundError, TeamReportService

router = APIRouter()

Mode = Literal["own", "rival"]


def _build(db, collection: str, team_id: str, mode: str) -> Dict[str, Any]:
    try:
        return TeamReportService(db).build(collection, team_id, mode)
    except TeamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Equipo no encontrado: {team_id}") from exc


@router.get("/team-report/{collection}", summary="Informe automático por reglas (JSON)")
def get_team_report(
    collection: str,
    team_id: str = Query(..., description="Stable team id"),
    mode: Mode = Query("own", description="own = análisis propio, rival = scouting"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    return _build(db, collection, team_id, mode)


@router.get("/team-report/{collection}/pdf", summary="Informe automático por reglas (PDF)")
def get_team_report_pdf(
    collection: str,
    team_id: str = Query(...),
    mode: Mode = Query("own"),
    db=Depends(get_db),
) -> Response:
    report = _build(db, collection, team_id, mode)
    try:
        from src.services.pdf_generator import PDFGenerator

        pdf = PDFGenerator.generate_bytes_from_html(render_report_html(report))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {exc}") from exc
    label = "Scouting" if mode == "rival" else "Analisis"
    safe = "".join(c if c.isalnum() else "_" for c in report["team"])
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{label}_{safe}.pdf"'},
    )
