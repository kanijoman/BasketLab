"""Validation tests for PossessionExportService using the local FEB game sample."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.services.possession_export_service import PossessionExportService

_SAMPLE = Path(__file__).parent.parent / "src" / "JSON_samples" / "feb_game.json"

_TEAM_SANFER = "982047"   # ACEITES ABRIL ADBA SANFER — 74 pts
_TEAM_MANRESA = "981204"  # MANRESA CBF A — 56 pts

_VALID_ENDINGS = {
    "violacion", "recuperacion", "triple", "tiro_2", "bandeja", "mate",
    "tiros_libres", "tiro_fallado", "rebote_defensivo", "otro",
}

_VALID_ORIGINS = {
    "inicio_partido", "saque_inicial_periodo", "saque_fondo",
    "rebote_defensivo", "rebote_ofensivo", "recuperacion", "violacion",
}


@pytest.fixture(scope="module")
def game_data():
    return json.loads(_SAMPLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def feb_rows(game_data):
    game_id = str(game_data.get("_id", {}).get("$numberInt", "test"))
    svc = PossessionExportService(game_data, is_fbcyl=False, game_id=game_id)
    return svc.extract_possessions()


def test_feb_game_points_match_final_score(feb_rows):
    """Sum of Puntos_obtenidos per team must equal the game final score."""
    pts_sanfer = sum(r["Puntos_obtenidos"] for r in feb_rows if r["Equipo_ID"] == _TEAM_SANFER)
    pts_manresa = sum(r["Puntos_obtenidos"] for r in feb_rows if r["Equipo_ID"] == _TEAM_MANRESA)
    assert pts_sanfer == 74, f"Expected 74 for SANFER, got {pts_sanfer}"
    assert pts_manresa == 56, f"Expected 56 for MANRESA, got {pts_manresa}"


def test_feb_game_no_negative_durations(feb_rows):
    """All possession durations must be >= 0."""
    bad = [r for r in feb_rows if r["Duracion_posesion"] < 0]
    assert not bad, f"{len(bad)} possessions have negative duration"


def test_feb_game_valid_possession_types(feb_rows):
    """Every Tipo_finalizacion must be in the known ending vocabulary."""
    unknown = {r["Tipo_finalizacion"] for r in feb_rows} - _VALID_ENDINGS
    assert not unknown, f"Unknown ending type(s): {unknown}"


def test_feb_game_valid_origins(feb_rows):
    """Every Origen_posesion must be in the known origin vocabulary."""
    unknown = {r["Origen_posesion"] for r in feb_rows} - _VALID_ORIGINS
    assert not unknown, f"Unknown origin type(s): {unknown}"


def test_feb_game_no_perdida_ending(feb_rows):
    """'perdida' must never appear as an ending; use recuperacion/violacion instead."""
    perdida = [r for r in feb_rows if r["Tipo_finalizacion"] == "perdida"]
    assert not perdida, f"{len(perdida)} rows still use deprecated 'perdida' ending"


def test_feb_game_violacion_origin_exists(feb_rows):
    """At least one possession must originate from a non-steal turnover (violacion)."""
    viols = [r for r in feb_rows if r["Origen_posesion"] == "violacion"]
    assert viols, "No 'violacion' origins found — violation detection may be broken"


def test_feb_game_saque_fondo_only_after_score(feb_rows):
    """saque_fondo must only appear after the opponent scored in a previous possession."""
    scored_endings = {"tiro_2", "triple", "tiros_libres", "bandeja", "mate"}
    # Build sequence: for each possession, prev team's ending
    prev_ending: dict = {}  # team_id -> last ending for that team
    for r in feb_rows:
        origin = r["Origen_posesion"]
        if origin == "saque_fondo":
            rival_last = prev_ending.get(r["Rival_ID"], None)
            assert rival_last in scored_endings or rival_last is None, (
                f"saque_fondo but rival's last ending was '{rival_last}' (not a score)"
            )
        prev_ending[r["Equipo_ID"]] = r["Tipo_finalizacion"]


def test_feb_game_tipoff_count(feb_rows):
    """Exactly one saque_inicial_periodo per quarter (4 in a standard game)."""
    tipoffs = [r for r in feb_rows if r["Origen_posesion"] == "saque_inicial_periodo"]
    assert len(tipoffs) == 4, f"Expected 4 tip-offs (one per quarter), got {len(tipoffs)}"


def _boxscore_tov_st(game_data: dict) -> dict:
    """Return {team_id: {to, st, tc}} from FEB boxscore TOTAL."""
    result = {}
    for team in game_data.get("BOXSCORE", {}).get("TEAM", []):
        tot = team.get("TOTAL", {})
        result[str(team["id"])] = {
            "to": int(tot.get("to") or 0),
            "st": int(tot.get("st") or 0),
            "tc": int(tot.get("tc") or 0),  # technical fouls — may add hidden TOVs
        }
    return result


def test_feb_game_turnovers_match_boxscore(feb_rows, game_data):
    """possession-derived turnovers must match boxscore TO within TC+1 tolerance."""
    bx = _boxscore_tov_st(game_data)
    team_ids = list(bx.keys())
    for tid in team_ids:
        tov_poss = sum(
            1 for r in feb_rows
            if r["Equipo_ID"] == tid and r["Tipo_finalizacion"] in ("recuperacion", "violacion")
        )
        bx_to = bx[tid]["to"]
        tc = bx[tid]["tc"]
        # Allow TC dead-ball turnovers plus one further unit for tracker correction rows
        tolerance = tc + 1
        assert abs(tov_poss - bx_to) <= tolerance, (
            f"TOV mismatch for {tid}: possession={tov_poss} boxscore={bx_to} "
            f"(diff={tov_poss - bx_to}, allowed \u00b1{tolerance} due to TC={tc})"
        )


def test_feb_game_steals_match_boxscore(feb_rows, game_data):
    """possession-derived steals (opp possession ending in recuperacion) must match boxscore ST exactly."""
    bx = _boxscore_tov_st(game_data)
    team_ids = list(bx.keys())
    opp_map = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}
    for tid in team_ids:
        # steals by tid = opponent possessions that ended via steal
        stl_poss = sum(
            1 for r in feb_rows
            if r["Equipo_ID"] == opp_map[tid] and r["Tipo_finalizacion"] == "recuperacion"
        )
        bx_st = bx[tid]["st"]
        assert stl_poss == bx_st, (
            f"STL mismatch for {tid}: possession={stl_poss} boxscore={bx_st}"
        )
