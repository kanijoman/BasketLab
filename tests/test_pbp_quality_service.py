"""Tests for the one-row-per-game PBP quality CSV export."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.pbp_quality_service import PBPQualityService


# ---------------------------------------------------------------------------
# Expected column list
# ---------------------------------------------------------------------------

CORE_METRICS = ["T2M", "T2A", "T3M", "T3A", "T1M", "T1A", "RebO", "RebD", "TOV"]
EXPECTED_COLUMNS = [
    "ID_Partido", "Coleccion", "Equipo_Local", "Equipo_Rival", "Quality_Score",
] + [
    f"{team}_{source}_{metric}"
    for team in ("Local", "Rival")
    for metric in CORE_METRICS
    for source in ("PBP", "BS")
]


# ---------------------------------------------------------------------------
# Synthetic game builders
# ---------------------------------------------------------------------------

def _feb_game(lines=None, local_id="T1", visitor_id="T2",
              t1_box=None, t2_box=None):
    """Minimal FEB game document with boxscore totals."""
    def _box(box):
        box = box or {}
        return {
            "p2m": str(box.get("p2m", 0)),
            "p2a": str(box.get("p2a", 0)),
            "p3m": str(box.get("p3m", 0)),
            "p3a": str(box.get("p3a", 0)),
            "p1m": str(box.get("p1m", 0)),
            "p1a": str(box.get("p1a", 0)),
            "ro": str(box.get("ro", 0)),
            "rd": str(box.get("rd", 0)),
            "assist": str(box.get("assist", 0)),
            "st": str(box.get("st", 0)),
            "to": str(box.get("to", 0)),
        }

    return {
        "HEADER": {"TEAM": [
            {"id": local_id,   "name": "Local"},
            {"id": visitor_id, "name": "Visitante"},
        ]},
        "PLAYBYPLAY": {"LINES": lines or []},
        "BOXSCORE": {"TEAM": [
            {"id": local_id,   "TOTAL": _box(t1_box), "PLAYER": []},
            {"id": visitor_id, "TOTAL": _box(t2_box), "PLAYER": []},
        ]},
    }


def _feb_m(team, text, action="shoot", quarter=1, time="9:00", id_player="P1"):
    move = {"action": action, "idTeam": team, "text": text,
            "quarter": str(quarter), "time": time}
    if id_player is not None:
        move["idPlayer"] = id_player
    return move


def _fbcyl_game(moves=None, local_id=100, visitor_id=200,
                t1_box=None, t2_box=None):
    """Minimal FBCYL game document with team-level data."""
    def _team_data(box):
        box = box or {}
        return {
            "shotsOfTwoSuccessful": box.get("p2m", 0),
            "shotsOfTwoAttempted":  box.get("p2a", 0),
            "shotsOfThreeSuccessful": box.get("p3m", 0),
            "shotsOfThreeAttempted":  box.get("p3a", 0),
            "shotsOfOneSuccessful": box.get("p1m", 0),
            "shotsOfOneAttempted":  box.get("p1a", 0),
            "assists": box.get("assist", 0),
            "steals":  box.get("st", 0),
            "lost":    box.get("to", 0),
        }

    def _team(tid, tname, box, role):
        players = [
            {
                "data": {
                    "offensiveRebound": box.get("ro", 0) if role == 0 else 0,
                    "defensiveRebound": box.get("rd", 0) if role == 0 else 0,
                }
            }
        ] if box else []
        return {
            "teamIdIntern": tid,
            "teamIdExtern": tid + 10000,
            "name": tname,
            "shortName": tname,
            "players": players,
            "data": _team_data(box),
        }

    return {
        "stats": {
            "teams": [
                _team(local_id,   "Local",   t1_box, 0),
                _team(visitor_id, "Visitante", t2_box, 1),
            ],
        },
        "moves": moves or [],
    }


# ---------------------------------------------------------------------------
# CSV_COLUMNS
# ---------------------------------------------------------------------------

def test_csv_columns_count():
    """The audit export has identity, score, and PBP/boxscore pairs per team."""
    assert len(PBPQualityService.CSV_COLUMNS) == len(EXPECTED_COLUMNS)


def test_csv_columns_names():
    """Service CSV_COLUMNS must match the expected list exactly."""
    assert PBPQualityService.CSV_COLUMNS == EXPECTED_COLUMNS


# ---------------------------------------------------------------------------
# One row per game
# ---------------------------------------------------------------------------

def test_feb_game_returns_one_row():
    """FEB game must produce exactly one global quality row."""
    game = _feb_game(
        lines=[_feb_m("T1", "TIRO DE 2 ANOTADO")],
        t1_box={"p2m": 1, "p2a": 1},
        t2_box={},
    )
    svc = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    rows = svc.compute()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"


def test_fbcyl_game_returns_one_row():
    """FBCYL game must produce exactly one global quality row."""
    game = _fbcyl_game(t1_box={"p2m": 5, "p2a": 10}, t2_box={"p2m": 3, "p2a": 8})
    svc = PBPQualityService(game, is_fbcyl=True, collection="test", game_id="G1")
    rows = svc.compute()
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"


# ---------------------------------------------------------------------------
# Row structure
# ---------------------------------------------------------------------------

def test_all_columns_present_in_rows():
    """Every row must contain all expected column keys."""
    game = _feb_game(t1_box={}, t2_box={})
    svc = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    rows = svc.compute()
    for row in rows:
        missing = [c for c in EXPECTED_COLUMNS if c not in row]
        assert not missing, f"Missing columns: {missing}"


# ---------------------------------------------------------------------------
# Accuracy formula
# ---------------------------------------------------------------------------

def test_accuracy_perfect_match():
    """When PBP counts match boxscore exactly, the global score is 100.00%."""
    lines = [
        _feb_m("T1", "TIRO DE 2 ANOTADO"),
        _feb_m("T1", "TIRO DE 2 FALLADO", time="8:00"),
        _feb_m("T1", "TRIPLE ANOTADO", time="7:00"),
    ]
    box = {"p2m": 1, "p2a": 2, "p3m": 1, "p3a": 1}
    game = _feb_game(lines=lines, t1_box=box, t2_box={})
    svc = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    rows = svc.compute()
    assert rows[0]["Quality_Score"] == "100.00%"


def test_accuracy_partial_mismatch_formula():
    """The global score is the equal-weight mean of 18 core team metrics."""
    lines = [
        _feb_m("T1", "TIRO DE 2 ANOTADO", time="9:00"),
        _feb_m("T1", "TIRO DE 2 ANOTADO", time="8:00"),
    ]
    box = {"p2m": 4, "p2a": 4}
    game = _feb_game(lines=lines, t1_box=box, t2_box={})
    svc = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    rows = svc.compute()
    assert rows[0]["Quality_Score"] == "94.44%"


def test_accuracy_zero_boxscore_uses_max_1():
    """When boxscore is 0, denominator is max(bs,1)=1 to avoid division by zero."""
    # PBP T2M = 2 but boxscore T2M = 0 → acc = max(0, 1 - 2/1) * 100 = 0
    lines = [
        _feb_m("T1", "TIRO DE 2 ANOTADO", time="9:00"),
        _feb_m("T1", "TIRO DE 2 ANOTADO", time="8:00"),
    ]
    box = {"p2m": 0, "p2a": 2}
    game = _feb_game(lines=lines, t1_box=box, t2_box={})
    svc = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    assert svc.compute()[0]["Quality_Score"] == "94.44%"


# ---------------------------------------------------------------------------
# FBCYL field mapping
# ---------------------------------------------------------------------------

def test_fbcyl_shots_from_team_data():
    """FBCYL shot counts must come from team-level data (not player data)."""
    game = _fbcyl_game(t1_box={"p2m": 10, "p2a": 25, "p3m": 3, "p3a": 12}, t2_box={})
    svc = PBPQualityService(game, is_fbcyl=True, collection="test", game_id="G1")
    boxscore = svc._extract_teams()["100"]["boxscore"]
    assert boxscore["T2M"] == 10
    assert boxscore["T2A"] == 25
    assert boxscore["T3M"] == 3
    assert boxscore["T3A"] == 12


def test_quality_export_returns_one_formatted_global_score():
    """The quality export provides one two-decimal global score per game."""
    game = _feb_game(
        lines=[_feb_m("T1", "TIRO DE 2 ANOTADO")],
        t1_box={"p2m": 1, "p2a": 1},
        t2_box={},
    )

    rows = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1").compute()

    assert PBPQualityService.CSV_COLUMNS == EXPECTED_COLUMNS
    assert rows[0]["Quality_Score"] == "100.00%"


def test_quality_counts_offensive_rebound_for_rebounding_team():
    """An offensive rebound belongs to the team that rebounds its missed shot."""
    game = _feb_game(
        lines=[
            _feb_m("T1", "TIRO DE 2 FALLADO", time="9:30"),
            _feb_m("T1", "REBOTE OFENSIVO", "rebound", time="9:28", id_player="P2"),
        ],
        t1_box={"p2a": 1, "ro": 1},
        t2_box={},
    )
    service = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    teams = service._extract_teams()

    assert service._count_pbp(teams)["T1"]["RebO"] == 1


def test_quality_counts_defensive_rebound_for_opponent_after_miss():
    """A defensive rebound belongs to the opponent of the missed shot team."""
    game = _feb_game(
        lines=[
            _feb_m("T1", "TIRO DE 2 FALLADO", time="9:30"),
            _feb_m("T2", "REBOTE DEFENSIVO", "rebound", time="9:28", id_player="P2"),
        ],
        t1_box={"p2a": 1},
        t2_box={"rd": 1},
    )
    service = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    teams = service._extract_teams()

    assert service._count_pbp(teams)["T2"]["RebD"] == 1


def test_quality_counts_defensive_rebound_after_neutral_event():
    """Neutral PBP events between a miss and rebound do not lose the rebound."""
    game = _feb_game(
        lines=[
            _feb_m("T1", "TIRO DE 2 FALLADO", time="9:30"),
            _feb_m("T1", "FALTA PERSONAL", "foul", time="9:29"),
            _feb_m("T2", "REBOTE DEFENSIVO", "rebound", time="9:28", id_player="P2"),
        ],
        t1_box={"p2a": 1},
        t2_box={"rd": 1},
    )
    service = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    teams = service._extract_teams()

    assert service._count_pbp(teams)["T2"]["RebD"] == 1


def test_quality_ignores_team_rebound_without_player_offensive():
    """Team rebounds (no idPlayer, e.g. after a ball out of bounds) aren't credited
    by the official boxscore ro/rd totals, so the quality audit must skip them too."""
    game = _feb_game(
        lines=[
            _feb_m("T1", "TIRO DE 2 FALLADO", time="9:30"),
            _feb_m("T1", "REBOTE", "rebound", time="9:28", id_player=None),
        ],
        t1_box={"p2a": 1, "ro": 0},
        t2_box={},
    )
    service = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    teams = service._extract_teams()

    assert service._count_pbp(teams)["T1"]["RebO"] == 0


def test_quality_ignores_team_rebound_without_player_defensive():
    """Same exclusion for a team rebound credited as defensive."""
    game = _feb_game(
        lines=[
            _feb_m("T1", "TIRO DE 2 FALLADO", time="9:30"),
            _feb_m("T2", "REBOTE", "rebound", time="9:28", id_player=None),
        ],
        t1_box={"p2a": 1},
        t2_box={"rd": 0},
    )
    service = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    teams = service._extract_teams()

    assert service._count_pbp(teams)["T2"]["RebD"] == 0


def test_quality_counts_fbcyl_defensive_rebound_for_opponent_after_miss():
    """FBCYL defensive rebounds are credited after an opponent's missed shot."""
    game = _fbcyl_game(moves=[
        {"idTeam": 100, "action": "shoot", "move": "Intento fallado de 2"},
        {"idTeam": 200, "action": "rebound", "move": "Rebote defensivo"},
    ])
    service = PBPQualityService(game, is_fbcyl=True, collection="FBCYL", game_id="G1")
    teams = service._extract_teams()

    assert service._count_pbp(teams)["200"]["RebD"] == 1


def test_quality_counts_feb_defensive_rebound_from_reverse_stored_events():
    """FEB PBP is stored newest-first but must be counted in game-time order."""
    game = _feb_game(
        lines=[
            _feb_m("T1", "TIRO DE 2 FALLADO", time="9:30"),
            _feb_m("T2", "REBOTE DEFENSIVO", "rebound", time="9:28"),
        ][::-1],
        t1_box={"p2a": 1},
        t2_box={"rd": 1},
    )
    service = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1")
    teams = service._extract_teams()

    assert service._count_pbp(teams)["T2"]["RebD"] == 1


def test_quality_score_ignores_non_core_assists_and_steals():
    """Non-core PBP events must not break the compact quality export."""
    game = _feb_game(lines=[
        _feb_m("T1", "ASISTENCIA", "assist"),
        _feb_m("T2", "ROBO DE BALÓN", "steal"),
    ])

    rows = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1").compute()

    assert rows[0]["Quality_Score"] == "100.00%"


def test_quality_export_includes_local_rival_metric_comparisons():
    """The audit row exposes PBP and boxscore values for each team and metric."""
    game = _feb_game(
        lines=[
            _feb_m("T1", "TIRO DE 2 FALLADO", time="9:30"),
            _feb_m("T2", "REBOTE DEFENSIVO", "rebound", time="9:28"),
        ],
        t1_box={"p2a": 1},
        t2_box={"rd": 2},
    )

    row = PBPQualityService(game, is_fbcyl=False, collection="test", game_id="G1").compute()[0]

    assert row["Equipo_Local"] == "Local"
    assert row["Equipo_Rival"] == "Visitante"
    assert row["Local_PBP_T2A"] == 1
    assert row["Local_BS_T2A"] == 1
    assert row["Rival_PBP_RebD"] == 1
    assert row["Rival_BS_RebD"] == 2
