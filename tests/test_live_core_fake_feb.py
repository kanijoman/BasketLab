"""Fake FEB server replaying a recorded game as if it were live.

Mimics what the real scraper consumes: the match page carrying a JWT in a hidden input,
and the BoxScore / KeyFacts / ShotChart endpoints behind a Bearer token.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from src.live_core.clock import elapsed_seconds, period_and_remaining
from src.live_core.fake_feb import FakeFebServer
from src.live_core.replay import ReplayClock


@pytest.mark.parametrize(
    "elapsed, expected",
    [(0, (1, 600)), (30, (1, 570)), (600, (2, 600)), (2367, (4, 33)), (2400, (5, 300)), (2700, (6, 300))],
)
def test_period_and_remaining_inverts_elapsed(elapsed, expected):
    assert period_and_remaining(elapsed) == expected
    period, remaining = period_and_remaining(elapsed)
    assert elapsed_seconds(period, remaining) == elapsed


def test_replay_clock_advances_with_speed_and_stops_at_the_end():
    now = [100.0]
    clock = ReplayClock(start_elapsed=60, speed=30, end_elapsed=1000, time_fn=lambda: now[0])
    assert clock.elapsed() == 60
    now[0] += 10
    assert clock.elapsed() == 60 + 300
    now[0] += 1000
    assert clock.elapsed() == 1000 and clock.finished()


@pytest.fixture()
def server(feb_game_doc):
    now = [0.0]
    clock = ReplayClock(start_elapsed=600, speed=1, end_elapsed=2400, time_fn=lambda: now[0])
    srv = FakeFebServer(feb_game_doc, clock, token="eyJhbGciFAKE.token")
    srv.start()
    srv.advance = lambda seconds: now.__setitem__(0, now[0] + seconds)
    yield srv
    srv.stop()


def _get(url, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def test_match_page_exposes_the_token_in_a_hidden_input(server):
    status, html = _get(f"{server.base_url}/partido/123")
    assert status == 200
    assert 'type="hidden"' in html and "eyJhbGciFAKE.token" in html


def test_endpoints_require_the_bearer_token(server):
    url = f"{server.base_url}/LiveStats.API/api/v1/BoxScore/123"
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(url)
    assert exc.value.code == 401
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(url, token="wrong")
    assert exc.value.code == 401


def test_boxscore_looks_live_and_has_no_final_stats(server):
    _, body = _get(f"{server.base_url}/LiveStats.API/api/v1/BoxScore/123", server.token)
    doc = json.loads(body)
    assert doc["HEADER"]["status"] != "3"
    assert "BOXSCORE" in doc and "TOTAL" not in doc["BOXSCORE"]["TEAM"][0]


def test_keyfacts_grows_as_the_replay_advances(server):
    url = f"{server.base_url}/LiveStats.API/api/v1/KeyFacts/123"
    first = json.loads(_get(url, server.token)[1])["PLAYBYPLAY"]["LINES"]
    server.advance(600)
    later = json.loads(_get(url, server.token)[1])["PLAYBYPLAY"]["LINES"]
    assert len(later) > len(first)


def test_shotchart_endpoint_shape(server):
    _, body = _get(f"{server.base_url}/LiveStats.API/api/v1/ShotChart/123", server.token)
    assert "SHOTCHART" in json.loads(body)


def test_finished_replay_serves_the_final_document(server):
    server.advance(10_000)
    doc = json.loads(_get(f"{server.base_url}/LiveStats.API/api/v1/BoxScore/123", server.token)[1])
    assert doc["HEADER"]["status"] == "3"
    assert "TOTAL" in doc["BOXSCORE"]["TEAM"][0]


def test_engine_can_follow_the_fake_feed_end_to_end(server, feb_game_doc):
    """BoxScore + KeyFacts merged like FEBApiClient does, fed to the engine as the clock moves."""
    from src.live_core.engine import LiveEngine

    def fetch():
        box = json.loads(_get(f"{server.base_url}/LiveStats.API/api/v1/BoxScore/123", server.token)[1])
        kf = json.loads(_get(f"{server.base_url}/LiveStats.API/api/v1/KeyFacts/123", server.token)[1])
        box["PLAYBYPLAY"] = kf["PLAYBYPLAY"]
        return box

    engine, scores = LiveEngine(), []
    for _ in range(4):
        scores.append(sum(engine.update(fetch())["score"].values()))
        server.advance(450)
    assert scores == sorted(scores) and scores[-1] > scores[0]
    final = engine.update(fetch())
    assert final["score"] == {t["id"]: int(t["pts"]) for t in feb_game_doc["HEADER"]["TEAM"]}
