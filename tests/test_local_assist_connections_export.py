"""The assist connections of every team of a competition, published for the web (#773): what ``AssistConnectionService.get_connections`` answers for each team,
from one pass over the games."""
import json

from src.local_data.assist_connections_export import export_assist_connections
from src.local_data.export import FORMAT
from tests.db_helpers import new_mock_db
from tests.test_assist_connection_service import FBCYL, FEB, Handler, feb_game
from tests.test_assist_links import fb_doc, mv


def test_a_feb_competition_publishes_every_team_with_baskets_and_its_connections():
    db = new_mock_db()
    db[FEB].insert_one(feb_game())
    payload = export_assist_connections(Handler(db, [{"id": "10", "name": "ALFA"}, {"id": "20", "name": "BETA"}]), FEB)
    assert (payload["format"], payload["collection"], payload["league"]) == (FORMAT, FEB, "feb")
    assert [t["team_id"] for t in payload["teams"]] == ["10"]
    analysis = payload["teams"][0]["analysis"]
    assert analysis["assisted_baskets"] == 1 and analysis["receivers"][0]["from"][0]["name"] == "ANA"


def test_an_fbcyl_competition_publishes_the_same_shape():
    db = new_mock_db()
    doc = fb_doc([mv("Canasta de 2", 1, 12, "e1"), mv("Asistencia", 1, 11, "e2")], [(12, "e1")])
    doc["uuid"] = "m1"
    db[FBCYL].insert_one(doc)
    payload = export_assist_connections(Handler(db, [{"id": "100", "name": "ALFA"}]), FBCYL)
    assert payload["league"] == "fbcyl" and payload["teams"][0]["analysis"]["receivers"][0]["zones"][0]["assisted"] == 1


def test_a_competition_without_games_publishes_no_teams_and_the_payload_is_json():
    payload = export_assist_connections(Handler(new_mock_db(), [{"id": "10", "name": "ALFA"}]), FEB)
    assert payload["teams"] == [] and json.loads(json.dumps(payload)) == payload
