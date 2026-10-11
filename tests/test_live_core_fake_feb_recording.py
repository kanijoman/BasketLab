"""Fake FEB server replaying a REAL recording with its real timeline (issue #174): the same endpoints the
scraper/recorder consume, the same quirks (a 404 in the middle of the match, status 1 -> 2 -> 3)."""
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from src.live_core.fake_feb import FakeFebServer
from src.live_core.recorded_feed import RecordedFeed
from src.live_core.replay import ReplayClock

FIXTURE = Path(__file__).parent / "recordings" / "2524470.rec.json.gz"
TOKEN = "eyJhbGciFAKE.token"


@pytest.fixture()
def server():
    now = [0.0]
    feed = RecordedFeed.load(FIXTURE)
    clock = ReplayClock(start_elapsed=0, speed=1, end_elapsed=feed.duration, time_fn=lambda: now[0])
    srv = FakeFebServer(None, clock, token=TOKEN, feed=feed)
    srv.start()
    srv.at = lambda seconds: now.__setitem__(0, float(seconds))  # jump to a second of the recording
    yield srv
    srv.stop()


def get(server, endpoint, match="2524470", token=TOKEN):
    request = urllib.request.Request(f"{server.base_url}/LiveStats.API/api/v1/{endpoint}/{match}")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8") or "{}")


def test_serves_the_three_endpoints_of_the_moment(server):
    server.at(3000)
    status, box = get(server, "BoxScore")
    assert status == 200 and box["HEADER"]["status"] == "2"
    assert "PLAYBYPLAY" not in box and "SHOTCHART" not in box  # BoxScore carries neither, like the real endpoint
    _, kf = get(server, "KeyFacts")
    assert 0 < len(kf["PLAYBYPLAY"]["LINES"]) < 458
    _, shots = get(server, "ShotChart")
    assert shots["SHOTCHART"]["SHOTS"]


def test_what_is_served_grows_with_the_recording_clock(server):
    server.at(1000)
    early = len(get(server, "KeyFacts")[1]["PLAYBYPLAY"]["LINES"])
    server.at(5000)
    later = len(get(server, "KeyFacts")[1]["PLAYBYPLAY"]["LINES"])
    assert later > early


def test_nothing_is_served_before_the_first_poll(server):
    server.at(-5)
    assert get(server, "BoxScore")[0] == 404


def test_the_real_404_in_the_middle_of_the_match_is_reproduced_per_endpoint_regression(server):
    server.at(6000)  # boxscore answered 404 here in the real match, the others did not
    assert get(server, "BoxScore")[0] == 404
    assert get(server, "ShotChart")[0] == 200
    server.at(6065)  # ... and keyfacts 40 s later
    assert get(server, "KeyFacts")[0] == 404
    assert get(server, "BoxScore")[0] == 200


def test_the_match_ends_with_the_final_status_and_stays_there(server):
    server.at(99999)
    status, box = get(server, "BoxScore")
    assert status == 200 and box["HEADER"]["status"] == "3" and box["HEADER"]["time"] == "FINAL"
    assert len(get(server, "KeyFacts")[1]["PLAYBYPLAY"]["LINES"]) == 458


def test_the_token_is_still_required(server):
    server.at(3000)
    assert get(server, "BoxScore", token=None)[0] == 401
    assert get(server, "BoxScore", token="wrong")[0] == 401


def test_the_match_page_still_exposes_the_token(server):
    with urllib.request.urlopen(f"{server.base_url}/partido/2524470", timeout=5) as response:
        assert TOKEN in response.read().decode("utf-8")
