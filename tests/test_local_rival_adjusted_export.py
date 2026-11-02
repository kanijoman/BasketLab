"""The rival-adjusted figures of every team of a competition, published for the web (#710): what ``GET /teams/{collection}/rival-adjusted`` answers, computed once at publication.

The endpoint takes no filter, and pairs the two rows of a game by their crossed scoreline (not by match id), a quirk a port would have to reproduce; with the endpoint's own function the
published answer cannot differ. Built over the real sample games of both leagues.
"""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from lineup_games import FBCYL, FEB, sample_games  # noqa: E402
from src.local_data.export import FORMAT  # noqa: E402
from src.local_data.rival_adjusted_export import export_rival_adjusted  # noqa: E402
from src.services.rival_adjusted_service import RivalAdjustedService  # noqa: E402

PLAN = [{"day": f"2025-{month:02d}-{day:02d}"} for month, day in ((10, 5), (10, 12), (10, 19), (10, 26), (11, 2), (11, 9))]


@pytest.fixture()
def handler(monkeypatch):
    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    db[FEB].insert_many(sample_games("feb", PLAN))
    db[FBCYL].insert_many(sample_games("fbcyl", PLAN))
    yield handler
    deps._create_handler.cache_clear()


@pytest.mark.parametrize("name, league", [(FEB, "feb"), (FBCYL, "fbcyl")])
def test_each_team_has_what_the_endpoint_answers_for_it(handler, name, league):
    payload = export_rival_adjusted(handler, name)
    assert (payload["format"], payload["league"], payload["collection"]) == (FORMAT, league, name)
    expected = json.loads(json.dumps(RivalAdjustedService(handler).get_rival_adjusted_stats(name), default=str))
    assert payload["teams"] == expected and payload["teams"]
    team = next(iter(payload["teams"].values()))
    assert set(team["ortg"]) == {"raw_avg", "adj_avg", "adj", "sos", "n"} and team["net_rtg"]["n"] >= 5          # at least five paired games: with fewer the adjusted figure is None
    json.dumps(payload)


def test_a_competition_with_no_games_publishes_no_teams(handler):
    assert export_rival_adjusted(handler, "L_F_-2_2099_Liga_Regular_B")["teams"] == {}
