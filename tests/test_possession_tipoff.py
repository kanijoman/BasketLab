"""Every period starts with exactly one tip-off possession ("saque_inicial_periodo")."""
import json
from pathlib import Path

import pytest

from src.services.possession_export_service import PossessionExportService

_SAMPLE = Path(__file__).resolve().parent.parent / "src" / "JSON_samples" / "feb_game.json"


@pytest.fixture(scope="module")
def feb_rows():
    game_data = json.loads(_SAMPLE.read_text("utf-8"))
    game_id = str(game_data.get("_id", {}).get("$numberInt", "test"))
    return PossessionExportService(game_data, is_fbcyl=False, game_id=game_id).extract_possessions()


def test_every_period_has_one_tipoff_possession(feb_rows):
    tipoffs = [r for r in feb_rows if r["Origen_posesion"] == "saque_inicial_periodo"]
    assert len(tipoffs) == 4, f"Expected 4 tip-offs (one per quarter), got {len(tipoffs)}"
    assert sorted(str(r["Cuarto"]) for r in tipoffs) == ["1", "2", "3", "4"]
