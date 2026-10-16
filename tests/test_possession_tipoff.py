"""Every period starts with exactly one tip-off possession ("saque_inicial_periodo").

The sample has a gap in the feed at the start of period 1 (the team with the ball loses it with no event), so that
possession is inferred and the exporter drops it: all rows have 4 tip-offs, the exported ones at least 3."""
import json
from pathlib import Path

import pytest

from src.pbp.possession_core import extract_possession_rows
from src.services.possession_export_service import PossessionExportService

_SAMPLE = Path(__file__).resolve().parent.parent / "src" / "JSON_samples" / "feb_game.json"


@pytest.fixture(scope="module")
def game_data():
    return json.loads(_SAMPLE.read_text("utf-8"))


@pytest.fixture(scope="module")
def feb_rows(game_data):
    game_id = str(game_data.get("_id", {}).get("$numberInt", "test"))
    return PossessionExportService(game_data, is_fbcyl=False, game_id=game_id).extract_possessions()


def test_every_period_has_one_tipoff_possession(game_data):
    info = {str(t["id"]): {"name": t["name"], "home_away": "x"} for t in game_data["HEADER"]["TEAM"]}
    tipoffs = [r for r in extract_possession_rows(game_data, False, "t", info) if r["Origen_posesion"] == "saque_inicial_periodo"]
    assert sorted(str(r["Cuarto"]) for r in tipoffs) == ["1", "2", "3", "4"]


def test_exported_possessions_keep_the_tipoffs_that_are_real(feb_rows):
    tipoffs = [r for r in feb_rows if r["Origen_posesion"] == "saque_inicial_periodo"]
    assert sorted(str(r["Cuarto"]) for r in tipoffs) == ["2", "3", "4"]
