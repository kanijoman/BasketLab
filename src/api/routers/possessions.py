"""Possessions router — per-team pace and efficiency stats.

Exposes pace (possessions per game), Offensive Efficiency Rating (OER),
Defensive Efficiency Rating (DER) and net rating for all teams in a
collection.  These values are computed by the existing team-stats
aggregation pipeline — no extra DB passes are needed.
"""

from typing import Any, Dict, List, Optional
import csv
import io
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from src.api.deps import get_db
from src.services import TeamStatsService
from src.services.possession_export_service import PossessionExportService
from src.services.pbp_quality_service import PBPQualityService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{collection}", summary="Per-team pace and efficiency ratings")
def get_possession_stats(
    collection: str,
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return pace / OER / DER stats for every team in *collection* with data quality metrics.

    The scatter quadrants of the PossessionsPage use:

    * **X axis** — ``pace`` (possessions per game)
    * **Y axis** — ``oer`` (offensive efficiency rating = points per 100 poss.)
      NOTE: When ``data_quality_score < 80``, OER is a hybrid or boxscore-based estimate.

    Four quadrants are labelled based on league median:
    fast+efficient, fast+inefficient, slow+efficient, slow+inefficient.

    **Data Quality Fields:**
    * ``data_quality_score`` (0-100): Higher = more reliable play-by-play data
    * ``phantom_pct``: % of phantom possessions inserted (should be <10%)
    * ``reconciliation``: "use_boxscore" | "use_hybrid" | "use_playbyplay"
    * ``boxscore_oer``: OER from boxscore formula (when play-by-play quality is poor)

    Args:
        collection: MongoDB collection name.

    Returns:
        List of dicts with ``team_name``, ``pace``, ``oer`` (reconciled), ``der``,
        ``net_rating``, ``possessions_per_game``, ``total_games``, plus data quality
        fields: ``data_quality_score``, ``phantom_pct``, ``reconciliation``, ``boxscore_oer``.
    """
    svc = TeamStatsService(db)
    logger.info("possessions: collection_name=%r", collection)
    return svc.get_possession_stats(collection)


@router.get("/{collection}/export/csv", summary="Export per-possession data as CSV")
def export_possessions_csv(
    collection: str,
    team_id: Optional[str] = Query(None, description="Filter to a single team ID"),
    db=Depends(get_db),
) -> StreamingResponse:
    """Stream a CSV file with one row per possession for every game in *collection*.

    The CSV uses UTF-8 BOM encoding so it opens correctly in Excel.

    Columns: ID_Partido, Equipo, Equipo_ID, Rival, Rival_ID, Local_Visitante,
    Cuarto, Tiempo_de_juego, Timestamp_inicio, Diferencia_marcador,
    Origen_posesion, Duracion_posesion, Tipo_finalizacion, Puntos_obtenidos.
    """
    is_fbcyl = "FBCYL" in collection.upper()

    def _generate():
        header_sent = False
        for game_doc in PossessionExportService.iter_collection(db, collection, team_id):
            raw_id = game_doc.get("_id", "")
            if isinstance(raw_id, dict):
                raw_id = raw_id.get("$numberInt") or raw_id.get("$oid") or str(raw_id)
            game_id = str(raw_id)
            svc = PossessionExportService(game_doc, is_fbcyl, game_id)
            rows = svc.extract_possessions()
            if not rows:
                continue
            import csv, io
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=PossessionExportService.CSV_COLUMNS, extrasaction="ignore")
            if not header_sent:
                writer.writeheader()
                header_sent = True
            writer.writerows(rows)
            yield buf.getvalue().encode("utf-8-sig")

    filename = f"posesiones_{collection}.csv"
    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{collection}/quality/csv", summary="Export PBP quality check CSV")
def export_quality_csv(
    collection: str,
    db=Depends(get_db),
) -> StreamingResponse:
    """Stream one PBP quality audit row per game for research validation.

    The score is the equal-weight mean of made/attempted field goals and free
    throws, offensive/defensive rebounds, and turnovers for both teams. Each
    row also shows the raw PBP-recovered and official boxscore values by team.
    """
    is_fbcyl = "FBCYL" in collection.upper()

    def _generate():
        header_sent = False
        buf = None
        for game_doc in PossessionExportService.iter_collection(db, collection, None):
            raw_id = game_doc.get("_id", "")
            if isinstance(raw_id, dict):
                raw_id = raw_id.get("$numberInt") or raw_id.get("$oid") or str(raw_id)
            game_id = str(raw_id)
            svc = PBPQualityService(game_doc, is_fbcyl, collection, game_id)
            rows = svc.compute()
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=PBPQualityService.CSV_COLUMNS, extrasaction="ignore")
            if not header_sent:
                writer.writeheader()
                header_sent = True
            writer.writerows(rows)
            yield buf.getvalue().encode("utf-8-sig")

    filename = f"calidad_pbp_{collection}.csv"
    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
