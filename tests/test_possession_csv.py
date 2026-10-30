"""The two CSV exports of the possessions page (#679): the text of the file, made in one place, so the API streams it and the publication keeps it.

Bug found while moving them (regression): the endpoints encoded every chunk (the rows of one game) with ``utf-8-sig``, so the BOM that Excel needs at the start of a file was
written at the start of EVERY game: the first cell of each game's first row began with an invisible U+FEFF. The file has one BOM, at the start."""
import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.api.routers.possessions import export_possessions_csv, export_quality_csv  # noqa: E402
from src.services.pbp_quality_service import PBPQualityService  # noqa: E402
from src.services.possession_export_service import PossessionExportService  # noqa: E402

SAMPLE = Path(__file__).parent.parent / "src" / "JSON_samples" / "feb_game.json"          # a real game with play-by-play
FEB = "L_F_-2_2025_2026_Liga_Regular_B"
BOM = "\ufeff"


@pytest.fixture()
def handler():
    database = new_mock_db("possession_csv")
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    database[FEB].insert_many([{**copy.deepcopy(sample), "_id": f"game-{n}"} for n in (1, 2, 3)])
    db = MagicMock()
    db.repository.connection.get_collection.side_effect = lambda name: database[name]
    return db


def _body(response) -> bytes:
    async def collect():
        return b"".join([chunk async for chunk in response.body_iterator])

    return asyncio.run(collect())


def test_the_possession_csv_has_one_header_and_the_rows_of_every_game(handler):
    text = "".join(PossessionExportService.csv_chunks(handler, FEB))
    lines = text.splitlines()
    assert lines[0].split(",") == PossessionExportService.CSV_COLUMNS and len(lines) > 100
    assert sum(1 for line in lines if line.startswith("ID_Partido,")) == 1 and BOM not in text
    assert {line.split(",")[0] for line in lines[1:]} == {"game-1", "game-2", "game-3"}


def test_the_quality_csv_has_one_header_and_a_row_per_team_and_game(handler):
    text = "".join(PBPQualityService.csv_chunks(handler, FEB))
    lines = text.splitlines()
    assert lines[0].split(",") == PBPQualityService.CSV_COLUMNS and len(lines) > 3
    assert sum(1 for line in lines if line == lines[0]) == 1 and BOM not in text


@pytest.mark.parametrize("endpoint", [export_possessions_csv, export_quality_csv])
def test_the_file_has_the_bom_once_at_the_start_regression(handler, endpoint):
    body = _body(endpoint(FEB, db=handler) if endpoint is export_quality_csv else endpoint(FEB, None, db=handler))
    assert body.startswith(BOM.encode("utf-8")) and body.count(BOM.encode("utf-8")) == 1
    assert body.decode("utf-8-sig").splitlines()[0].startswith("ID_Partido")
