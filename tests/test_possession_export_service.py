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
    """saque_fondo must only appear after the opponent scored or a tracker correction."""
    scored_endings = {"tiro_2", "triple", "tiros_libres", "bandeja", "mate", "otro"}
    # 'otro' is allowed because tracker-correction closes (RC2 fix) produce 'otro'
    # and the next possession correctly starts via saque_fondo.
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


# ---------------------------------------------------------------------------
# Synthetic game helpers
# ---------------------------------------------------------------------------

def _make_feb_game(local_id="T1", visitor_id="T2", lines=None):
    return {
        "HEADER": {"TEAM": [
            {"id": local_id, "name": "Local"},
            {"id": visitor_id, "name": "Visitante"},
        ]},
        "PLAYBYPLAY": {"LINES": lines or []},
    }


def _feb_svc(lines, local_id="T1", visitor_id="T2"):
    game = _make_feb_game(local_id, visitor_id, lines)
    return PossessionExportService(game, is_fbcyl=False, game_id="TEST").extract_possessions()


def _m(team, text, action="shoot", quarter=1, time="9:00"):
    return {"action": action, "idTeam": team, "text": text, "quarter": str(quarter), "time": time}


# ---------------------------------------------------------------------------
# Feature A — Tiene_rebote_ofensivo column (FAIL before Phase 3 fix)
# ---------------------------------------------------------------------------

def test_tiene_rebote_ofensivo_column_present_in_all_rows(feb_rows):
    """Every row must contain the Tiene_rebote_ofensivo key (Feature A)."""
    missing = [r for r in feb_rows if "Tiene_rebote_ofensivo" not in r]
    assert not missing, f"{len(missing)} rows missing Tiene_rebote_ofensivo column"


def test_tiene_rebote_ofensivo_is_binary(feb_rows):
    """Tiene_rebote_ofensivo must be 0 or 1 for every row."""
    bad = [r for r in feb_rows if r.get("Tiene_rebote_ofensivo") not in (0, 1)]
    assert not bad, f"{len(bad)} rows have invalid Tiene_rebote_ofensivo value"


# ---------------------------------------------------------------------------
# OReb continuity (FAIL before Phase 3 fix)
# ---------------------------------------------------------------------------

def test_no_rebote_ofensivo_in_origen(feb_rows):
    """After the OReb continuity fix, no row may have Origen_posesion='rebote_ofensivo'."""
    bad = [r for r in feb_rows if r.get("Origen_posesion") == "rebote_ofensivo"]
    assert not bad, f"{len(bad)} rows still use removed 'rebote_ofensivo' origin"


def test_orb_flag_set_for_orb_possession():
    """Possession where OReb occurred must have Tiene_rebote_ofensivo=1 (not 0)."""
    lines = [
        # T2 scores → T1 starts (saque_fondo)
        _m("T2", "TIRO DE 2 ANOTADO", "shoot", 1, "9:30"),
        # T1 misses — T1 gets offensive rebound
        _m("T1", "TIRO DE 2 FALLADO", "shoot", 1, "9:00"),
        _m("T1", "REBOTE OFENSIVO", "rebound", 1, "8:55"),
        # T1 scores on the putback
        _m("T1", "TIRO DE 2 ANOTADO", "shoot", 1, "8:50"),
    ]
    rows = _feb_svc(lines)
    t1_scoring_rows = [r for r in rows if r["Equipo_ID"] == "T1" and r["Puntos_obtenidos"] > 0]
    assert len(t1_scoring_rows) == 1, f"Expected 1 T1 scoring possession, got {len(t1_scoring_rows)}"
    assert t1_scoring_rows[0]["Tiene_rebote_ofensivo"] == 1, "OReb possession must have flag=1"


def test_orb_possession_not_split():
    """Missed FG + offensive rebound must NOT create a separate possession row."""
    lines = [
        _m("T2", "TIRO DE 2 ANOTADO", "shoot", 1, "9:30"),
        _m("T1", "TIRO DE 2 FALLADO", "shoot", 1, "9:00"),   # miss — idx will be in orebs
        _m("T1", "REBOTE OFENSIVO", "rebound", 1, "8:55"),
        _m("T1", "TIRO DE 2 ANOTADO", "shoot", 1, "8:50"),
    ]
    rows = _feb_svc(lines)
    t1_rows = [r for r in rows if r["Equipo_ID"] == "T1"]
    # Before fix: 2 T1 rows (0-pt OReb row + 2-pt score row)
    # After fix:  1 T1 row  (single possession with pts=2 and flag=1)
    assert len(t1_rows) == 1, (
        f"OReb must not split possession; expected 1 T1 row, got {len(t1_rows)}"
    )


def test_orb_flag_zero_for_normal_possession():
    """Possession without offensive rebound must have Tiene_rebote_ofensivo=0."""
    lines = [
        _m("T1", "TIRO DE 2 ANOTADO", "shoot", 1, "9:00"),
    ]
    rows = _feb_svc(lines)
    t1_rows = [r for r in rows if r["Equipo_ID"] == "T1"]
    assert t1_rows, "T1 must have at least one possession"
    assert all(r["Tiene_rebote_ofensivo"] == 0 for r in t1_rows), (
        "Normal possession (no OReb) must have flag=0"
    )


# ---------------------------------------------------------------------------
# RC2 — tracker-correction close must use 'otro' ending (FAIL before Phase 3)
# ---------------------------------------------------------------------------

def test_tracker_correction_uses_otro_ending():
    """When scoring event forces a tracker correction, the closed possession ends as 'otro'."""
    lines = [
        # T1 starts possession (rebounds at Q1)
        _m("T1", "REBOTE DEFENSIVO", "rebound", 1, "9:00"),
        # T2 scores immediately — triggers _is_scoring_event with current_team=T1 != T2
        _m("T2", "TIRO DE 2 ANOTADO", "shoot", 1, "8:30"),
    ]
    rows = _feb_svc(lines)
    t1_rows = [r for r in rows if r["Equipo_ID"] == "T1"]
    assert t1_rows, "T1 possession must be closed by tracker correction"
    forced_close = [r for r in t1_rows if r["Puntos_obtenidos"] == 0]
    assert forced_close, "T1 must have a 0-pt row from tracker correction"
    assert forced_close[0]["Tipo_finalizacion"] == "otro", (
        f"Tracker correction must close with 'otro', got '{forced_close[0]['Tipo_finalizacion']}'"
    )


# ---------------------------------------------------------------------------
# RC4 — FEB quarter boundary without action='period' event (FAIL before Phase 3)
# ---------------------------------------------------------------------------

def test_feb_quarter_change_closes_possession():
    """FEB: possession start in Q1, score in Q2 with no 'period' event must yield Q2 attribution."""
    lines = [
        # T1 rebounds near end of Q1 → starts possession
        _m("T1", "REBOTE DEFENSIVO", "rebound", 1, "0:20"),   # ts ≈ 580
        # No action='period' event; T1 scores early Q2
        _m("T1", "TIRO DE 2 ANOTADO", "shoot", 2, "9:40"),    # ts ≈ 620
    ]
    rows = _feb_svc(lines)
    t1_rows = [r for r in rows if r["Equipo_ID"] == "T1"]
    scoring_rows = [r for r in t1_rows if r["Puntos_obtenidos"] == 2]
    assert scoring_rows, "T1 must have a 2pt possession"
    # Before fix: the score is attributed to Q1 (possession started there)
    # After fix:  the quarter-change closes Q1 possession; score goes to Q2
    assert scoring_rows[0]["Cuarto"] == "2", (
        f"Score in Q2 must be attributed to Q2, got Q{scoring_rows[0]['Cuarto']}"
    )


def test_zero_second_scoring_is_flagged_as_controversial():
    """A scoreless same-timestamp turnover remains valid and unflagged."""
    lines = [
        _m("T1", "TIRO DE 2 ANOTADO", "shoot", 1, "9:05"),
        _m("T2", "PÉRDIDA DE BALÓN", "turnover", 1, "9:05"),
    ]
    rows = _feb_svc(lines)
    t2_rows = [r for r in rows if r["Equipo_ID"] == "T2"]
    assert t2_rows, "T2 must have a possession row"
    zero_zero = [r for r in t2_rows if r["Duracion_posesion"] == 0 and r["Puntos_obtenidos"] == 0]
    assert zero_zero, "Expected a same-timestamp zero-second turnover row"
    assert "Controversial_Possession" in zero_zero[0], "Controversial_Possession flag missing"
    assert zero_zero[0]["Controversial_Possession"] is False, (
        "Immediate turnover without points should remain non-controversial"
    )


def test_zero_second_score_is_flagged_as_controversial():
    """A zero-second scored possession should be marked for review without being dropped."""
    lines = [
        _m("T1", "TIRO DE 2 ANOTADO", "shoot", 1, "9:00"),
        _m("T2", "TIRO DE 2 ANOTADO", "shoot", 1, "9:00"),
    ]
    rows = _feb_svc(lines)
    t1_rows = [r for r in rows if r["Equipo_ID"] == "T1"]
    assert t1_rows, "T1 must have a possession row"
    scored = [r for r in t1_rows if r["Puntos_obtenidos"] > 0]
    assert scored, "T1 must have a scored possession"
    assert "Controversial_Possession" in scored[0], "Controversial_Possession flag missing"
    assert scored[0]["Controversial_Possession"] is True, (
        "A zero-second scored possession should be flagged as controversial"
    )


def test_period_opening_score_uses_period_boundary_and_updates_next_differential():
    """The first score in a period begins at 10:00 and updates the inbound score."""
    lines = [
        _m("T1", "TIRO DE 2 ANOTADO", "shoot", 1, "9:42"),
        _m("T2", "PÉRDIDA DE BALÓN", "turnover", 1, "9:42"),
    ]

    rows = _feb_svc(lines)

    opening_score = next(row for row in rows if row["Equipo_ID"] == "T1")
    inbound_possession = next(row for row in rows if row["Equipo_ID"] == "T2")
    assert opening_score["Duracion_posesion"] == 18
    assert inbound_possession["Diferencia_marcador"] == -2
    assert inbound_possession["Duracion_posesion"] == 0
    assert inbound_possession["Controversial_Possession"] is False
