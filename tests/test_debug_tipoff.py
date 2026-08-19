"""Debug: inspect TOV/STL detection gaps vs boxscore."""
import json
import re
from pathlib import Path
from collections import Counter

import pytest
from src.services.possession_export_service import PossessionExportService
from src.database._possession_helpers import (
    is_turnover, is_steal, detect_steal_turnover_indices, get_timestamp,
)

_SAMPLE = Path("src/JSON_samples/feb_game.json")
_TEAM_SANFER = "982047"
_TEAM_MANRESA = "981204"


@pytest.fixture(scope="module")
def game_data():
    return json.loads(_SAMPLE.read_text("utf-8"))


@pytest.fixture(scope="module")
def feb_rows(game_data):
    game_id = str(game_data.get("_id", {}).get("$numberInt", "test"))
    svc = PossessionExportService(game_data, is_fbcyl=False, game_id=game_id)
    return svc.extract_possessions()


def test_debug_tipoff_rows(feb_rows, game_data, capsys):
    tipoffs = [r for r in feb_rows if r["Origen_posesion"] == "saque_inicial_periodo"]
    with capsys.disabled():
        print(f"\n=== saque_inicial_periodo rows ({len(tipoffs)}) ===")
        for r in tipoffs:
            print(f"  Q{r['Cuarto']} {r['Tiempo_de_juego']} | {r['Equipo']} | ending={r['Tipo_finalizacion']}")

    assert len(tipoffs) == 4, f"Expected 4 tip-offs (one per quarter), got {len(tipoffs)}"


def test_debug_tov_stl_gaps(feb_rows, game_data, capsys):
    """Show which PBP turnover events are not being detected."""
    import re

    def sort_key(m):
        ts = get_timestamp(m, False)
        t = str(m.get("text") or "")
        if "TIRO DE 1" in t.upper() or "TIRO LIBRE" in t.upper():
            pts = re.search(r"Puntos:\s*(\d+)", t)
            if pts:
                return (ts, int(pts.group(1)))
        return (ts, 0)

    lines = game_data.get("PLAYBYPLAY", {}).get("LINES", [])
    moves = sorted(lines, key=sort_key)
    steal_tovs = detect_steal_turnover_indices(moves, False)

    with capsys.disabled():
        print("\n=== All MANRESA turnover events in PBP ===")
        manresa_tovs = [(i, m) for i, m in enumerate(moves)
                        if str(m.get("idTeam") or "") == _TEAM_MANRESA
                        and is_turnover(m, False)]
        print(f"  Detected: {len(manresa_tovs)} MANRESA turnovers")
        for i, m in manresa_tovs:
            steal_flag = "STEAL" if i in steal_tovs else "viol"
            print(f"    [{i:3d}] {steal_flag} Q{m.get('quarter')} {m.get('time')} act={m.get('action')} text={str(m.get('text',''))[:70]}")

        print("\n=== All SANFER steal events in PBP ===")
        sanfer_steals = [(i, m) for i, m in enumerate(moves)
                         if str(m.get("idTeam") or "") == _TEAM_SANFER
                         and is_steal(m, False)]
        print(f"  Detected: {len(sanfer_steals)} SANFER steals")
        for i, m in sanfer_steals:
            print(f"    [{i:3d}] Q{m.get('quarter')} {m.get('time')} act={m.get('action')} text={str(m.get('text',''))[:70]}")

        print("\n=== PBP events with 'robo' or 'perdida' keywords ===")
        for i, m in enumerate(moves):
            text = str(m.get("text") or "").lower()
            if "robo" in text or "pérdida" in text or "perdida" in text:
                if not is_turnover(m, False) and not is_steal(m, False):
                    print(f"  UNDETECTED [{i:3d}] tid={m.get('idTeam')} act={m.get('action')} text={str(m.get('text',''))[:80]}")

        print("\n=== Possession-derived vs boxscore ===")
        bx = {}
        for team in game_data["BOXSCORE"]["TEAM"]:
            bx[str(team["id"])] = {
                "to": int(team["TOTAL"]["to"]), "st": int(team["TOTAL"]["st"])
            }
        for tid, name in [(_TEAM_SANFER, "SANFER"), (_TEAM_MANRESA, "MANRESA")]:
            opp = _TEAM_MANRESA if tid == _TEAM_SANFER else _TEAM_SANFER
            tov_p = sum(1 for r in feb_rows if r["Equipo_ID"] == tid
                        and r["Tipo_finalizacion"] in ("recuperacion", "violacion"))
            stl_p = sum(1 for r in feb_rows if r["Equipo_ID"] == opp
                        and r["Tipo_finalizacion"] == "recuperacion")
            print(f"  {name}: TOV poss={tov_p} bx={bx[tid]['to']} | STL poss={stl_p} bx={bx[tid]['st']}")

