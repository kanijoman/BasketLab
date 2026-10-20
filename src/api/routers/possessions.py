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
from src.services.pbp_extended_stats_service import PBPExtendedStatsService
from src.services.pbp_situation_stats_service import PBPSituationStatsService

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


@router.get("/{collection}/points-by-origin", summary="Season points by origin, bench and paint per team")
def get_points_by_origin(collection: str, db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Per team (FEB and FBCYL, #432): points per game after turnovers, steals and offensive rebounds (second chance), bench and paint, their
    efficiency per origin (points per 100 possessions that started that way), the bench share and the same figures conceded
    (``opp_``). Games that are not reliable (#390: more than 10 % of their points of unknown origin, or a possession count more than 10 % off the estimate) are left out (``games_unreliable``; ``games_doubtful`` = games used whose feed has alternation breaks, not shown in the web). Empty for collections whose
    games lack ``DERIVED`` (not backfilled: ``python run_backfill_derived.py``). FBCYL: grouped by the stable ``teamIdExtern``, no paint points (no shot chart)."""
    return PBPExtendedStatsService(db).get_points_by_origin(collection)


@router.get("/{collection}/by-period", summary="Season figures per team and period (Q1-Q4, OT)")
def get_by_period(collection: str, db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Per team (FEB and FBCYL): points for and against, possessions, ORtg/DRtg, net rating, pace (per 40 min), eFG%, TOV%, ORB%/DRB%, FTr and
    fouls in each of Q1-Q4 and OT (all the overtimes together), with the rival's (``opp_``: what the team concedes). Games with an
    ``unreliable`` play-by-play are left out (``games_unreliable``; ``games_doubtful`` = games used whose feed has alternation breaks, not shown in the web). Empty for collections whose games lack ``DERIVED`` (FBCYL, or
    games not backfilled: ``python run_backfill_derived.py``)."""
    return PBPExtendedStatsService(db).get_by_period(collection)


@router.get("/{collection}/situations", summary="Season after-timeout possessions, first possessions and first / last two minutes")
def get_situations(collection: str, db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Per team (FEB and FBCYL): points per possession after a timeout it called (``ato_own``) or the rival called (``ato_rival``), of the first
    possession of the periods it started (``first_poss``) and the first / last two minutes of the periods against the rest of them
    (``edges``: net rating, points, turnover rate, ``vs_rest``). games that are not reliable (#390: more than 10 % of their points of unknown origin, or a possession count more than 10 % off the estimate) are left out (``games_unreliable``; ``games_doubtful`` = games used whose feed has alternation breaks, not shown in the web). Empty for
    collections whose games lack ``DERIVED`` v4 (not backfilled)."""
    return PBPSituationStatsService(db).get_situations(collection)


@router.get("/{collection}/timeouts", summary="Season effect of the timeouts on the net rating")
def get_timeout_effects(collection: str, db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Per team (FEB and FBCYL): the net rating of the 5 possessions of each team before and after each timeout it called (``own``) and each one
    the rival called (``rival``), the change and the share of timeouts after which the caller improved. Timeouts of the last minute of a
    period and those without a complete window are not analysed. Empty for collections without ``DERIVED`` v4."""
    return PBPSituationStatsService(db).get_timeout_effects(collection)


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
    """Stream a CSV with PBP vs. boxscore accuracy metrics per team per game.

    Each row compares play-by-play derived counts (T2M/T2A/T3M/T3A/T1M/T1A,
    OReb/DReb, AST, ST, TOV) against official boxscore totals, computing an
    accuracy % per metric and an overall Precision_Equipo score.

    Intended for research validation of PBP data quality.
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
