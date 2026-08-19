"""Pytest-based debug for saque_inicial_periodo count."""
import json
from pathlib import Path
from collections import Counter

import pytest
from src.services.possession_export_service import PossessionExportService

_SAMPLE = Path("src/JSON_samples/feb_game.json")


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

        print("\n=== Period/no-team events in raw PBP ===")
        lines = game_data.get("PLAYBYPLAY", {}).get("LINES", [])
        for i, m in enumerate(lines):
            action = str(m.get("action", "")).lower()
            if action == "period" or not m.get("idTeam"):
                print(f"  [{i:3d}] action={action!r:12} q={m.get('quarter')} time={m.get('time')} text={str(m.get('text',''))[:70]}")

        print("\n=== Quarter transitions (sorted moves) ===")
        import re
        from src.database._possession_helpers import get_timestamp

        def sort_key(m):
            ts = get_timestamp(m, False)
            t = str(m.get("text") or "")
            if "TIRO DE 1" in t.upper() or "TIRO LIBRE" in t.upper():
                pts = re.search(r"Puntos:\s*(\d+)", t)
                if pts:
                    return (ts, int(pts.group(1)))
            return (ts, 0)

        moves = sorted(lines, key=sort_key)
        prev_q = None
        for i, m in enumerate(moves):
            q = m.get("quarter")
            if q != prev_q:
                print(f"  [{i:3d}] Q{prev_q}->{q} action={str(m.get('action',''))!r:12} tid={m.get('idTeam')} text={str(m.get('text',''))[:60]}")
                prev_q = q

        print("\n=== Sorted moves around Q3/Q4 boundary [343-360] ===")
        for i, m in enumerate(moves[343:361], start=343):
            print(f"  [{i:3d}] Q={m.get('quarter')} act={str(m.get('action',''))!r:10} tid={m.get('idTeam')} text={str(m.get('text',''))[:50]}")

    assert len(tipoffs) == 4, f"Expected 4 tip-offs (one per quarter), got {len(tipoffs)}"
