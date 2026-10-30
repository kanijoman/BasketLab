"""The possessions page of a competition, published for the web (#679): the table, the consistency and the two CSV files, computed once at publication with the same code
the endpoints run, so the figures cannot differ from the API's. The per-possession CSV is the heavy part and has a payload of its own (downloaded only when it is asked for)."""
import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.local_data.export import FORMAT
from src.local_data.possessions_export import export_possession_csv, export_possessions
from src.services.pbp_quality_service import PBPQualityService
from src.services.possession_export_service import PossessionExportService
from src.services.team_stats_service import TeamStatsService

SAMPLE = Path(__file__).parent.parent / "src" / "JSON_samples" / "feb_game.json"
FEB = "L_F_-2_2025_2026_Liga_Regular_B"


@pytest.fixture()
def handler():
    database = new_mock_db("possessions")
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    database[FEB].insert_many([{**copy.deepcopy(sample), "_id": f"game-{n}"} for n in (1, 2)])
    db = MagicMock()
    db.repository.connection.get_collection.side_effect = lambda name: database[name]
    db.connection.get_collection.side_effect = lambda name: database[name]
    return db


def test_the_table_and_the_consistency_are_what_the_service_answers_and_the_quality_csv_is_the_endpoints(handler, monkeypatch):
    table = [{"team_name": "ALPHA", "pace": 70.5, "oer": 101.2}]
    consistency = {"own": {"ALPHA": {"points": {"mean": 80.0, "std": 5.0, "cv": 6.2, "n": 2}}}, "rival": {}}
    monkeypatch.setattr(TeamStatsService, "get_possession_stats", lambda self, name: table)
    monkeypatch.setattr(TeamStatsService, "get_consistency", lambda self, name: consistency)
    payload = export_possessions(handler, FEB)
    assert (payload["format"], payload["league"], payload["collection"]) == (FORMAT, "feb", FEB)
    assert payload["table"] == table and payload["consistency"] == consistency
    assert payload["quality_csv"] == "".join(PBPQualityService.csv_chunks(handler, FEB)) and payload["quality_csv"].startswith("ID_Partido")
    json.dumps(payload)


def test_the_per_possession_csv_is_the_text_of_the_endpoint_without_its_bom(handler):
    payload = export_possession_csv(handler, FEB)
    assert payload["csv"] == "".join(PossessionExportService.csv_chunks(handler, FEB)) and payload["csv"].startswith("ID_Partido")
    assert (payload["format"], payload["league"], payload["games"]) == (FORMAT, "feb", 2) and "\ufeff" not in payload["csv"]


def test_a_competition_with_no_play_by_play_has_no_possession_csv():
    database = new_mock_db("none")
    database[FEB].insert_many([{"_id": 1, "HEADER": {"TEAM": []}}])
    db = MagicMock()
    db.repository.connection.get_collection.side_effect = lambda name: database[name]
    assert export_possession_csv(db, FEB)["csv"] == ""
