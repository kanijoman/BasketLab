"""The vectors of the PDF of the team report in the browser (#714): reports of both leagues and modes (the real ``TeamReportService`` over the fixture games, as the publisher builds
them) with the HTML ``render_report_html`` makes of each, the reference of ``frontend/src/lib/teamReportPdf.test.ts`` (the web must write the very same HTML, string for string).

Besides the real ones, a few hand-made reports go through the branches the fixtures do not reach: the small-sample notice, an empty section, a finding with no difference to the median,
a team name with characters HTML escapes, and no ``zones`` key at all (FBCYL's reports have none).
"""
from typing import Any, Dict, List
from unittest.mock import patch

import mongomock

from fbcyl_games import build_games as build_fbcyl_games
from games import build_games

from src.local_data.team_reports import build_reports
from src.report_engine.html_renderer import render_report_html

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


def _handler() -> Any:
    from src.api import deps

    with patch("pymongo.MongoClient", mongomock.MongoClient):
        deps._create_handler.cache_clear()
        handler = deps._create_handler()
        db = handler.connection.client["BASKETBALL"]
        db[FEB].insert_many(build_games())
        db[FBCYL].insert_many(build_fbcyl_games())
    return handler


def _synthetic() -> List[Dict[str, Any]]:
    finding = {"key": "pts", "label": "Puntos", "formatted": "78,5", "quartile": 4, "diff_pct": 12.25, "kind": "strength", "text": "Anota & domina <el aro>."}
    base = {"mode": "own", "team": "A&B \"Ñandú\" <Club>", "games_played": 3, "low_sample": True, "strengths": [finding], "weaknesses": [{**finding, "diff_pct": None, "kind": "weakness"}],
            "differentials": [{"key": "pts", "label": "Puntos", "formatted": "78,5", "diff_pct": -0.04, "advantage": False}, {"key": "ast", "label": "Asistencias", "formatted": "15", "diff_pct": 2.5, "advantage": True}],
            "consistency": [{"key": "pts", "label": "Puntos", "cv": 12.5, "status": "consistent", "n": 3, "low_sample": True, "text": "Estable."},
                            {"key": "tov", "label": "Pérdidas", "cv": 30.5, "status": "inconsistent", "n": 3, "low_sample": False, "text": "Irregular."}],
            "zones": [{"zone": "rim", "label": "Aro", "points": 1.1, "fga": 20, "fg_pct": 62.5, "league_pct": 58.4, "delta_pp": 4.1, "low_sample": True, "kind": "hot", "text": "Caliente."},
                      {"zone": "mid", "label": "Media", "points": 0.7, "fga": 9, "fg_pct": 30.5, "league_pct": 40.0, "delta_pp": -9.5, "low_sample": False, "kind": "cold", "text": "Fría."}],
            "profile": ["Equipo físico & rápido", "Juega <abierto>"],
            "tactics": [{"key": "a", "label": "Ritmo", "area": "ofensiva", "kind": "leverage", "text": "Correr.", "priority": 1}, {"key": "b", "label": "Rebote", "area": "defensiva", "kind": "improve", "text": "Cerrar."}],
            "training": [{"key": "a", "label": "Ritmo", "area": "ofensiva", "kind": "improve", "text": "Trabajar."}]}
    empty = {**base, "mode": "rival", "team": "Vacío", "games_played": 12, "low_sample": False, "strengths": [], "weaknesses": [], "differentials": [], "consistency": [], "profile": [], "tactics": [], "training": []}
    empty.pop("zones")
    return [base, {**base, "mode": "rival", "low_sample": False, "tactics": [base["tactics"][1]]}, empty]


def build() -> Dict[str, Any]:
    handler = _handler()
    reports = [report for name in (FEB, FBCYL) for _id, _team, _mode, report in build_reports(handler, name)]
    return {"cases": [{"report": report, "html": render_report_html(report)} for report in reports + _synthetic()]}
