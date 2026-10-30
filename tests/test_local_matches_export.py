"""The match list and the analysis of every match of a competition, published for the web (#677): what ``GET /matches/{collection}`` and ``GET /matches/{collection}/{id}``
answer, computed once at publication with the same service (a tenth of a second per ten matches), so the page reads them instead of asking the server."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.local_data.export import FORMAT  # noqa: E402
from src.local_data.matches_export import export_matches  # noqa: E402
from src.services.match_analysis_service import MatchAnalysisService  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


@pytest.fixture()
def handler():
    database = new_mock_db("matches")
    database[FEB].insert_many(games.build_games())
    database[FBCYL].insert_many(fbcyl_games.build_games())
    db = MagicMock()
    db.connection.get_collection.side_effect = lambda name: database[name]
    return db


def _plain(value):
    return json.loads(json.dumps(value, default=str))


@pytest.mark.parametrize("name, fbcyl, count", [(FEB, False, 12), (FBCYL, True, 12)])
def test_every_match_has_its_list_entry_and_its_analysis_as_the_service_answers(handler, name, fbcyl, count):
    payload = export_matches(handler, name)
    service = MatchAnalysisService(handler, name)
    assert (payload["format"], payload["league"], payload["collection"], payload["games"]) == (FORMAT, "fbcyl" if fbcyl else "feb", name, count)
    assert payload["matches"] == _plain([{**summary, "analysis": service.get_match_analysis(summary["match_id"], fbcyl)} for summary in service.get_match_list(fbcyl)])
    assert all(m["analysis"] and m["analysis"]["comparison"] for m in payload["matches"])
    json.dumps(payload)


def test_the_list_keeps_the_order_of_the_collection(handler):
    ids = [m["match_id"] for m in export_matches(handler, FEB)["matches"]]
    assert ids == [g["_id"] for g in games.build_games()]


def test_a_competition_with_no_games_has_no_matches(handler):
    handler.connection.get_collection.side_effect = lambda name: new_mock_db("empty")["NONE"]
    assert export_matches(handler, FEB)["matches"] == []
