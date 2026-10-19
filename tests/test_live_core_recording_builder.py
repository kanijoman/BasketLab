"""Recording the match the app follows live (issue #416).

The CI recorder is independent of the app and can come late (Leon-Unibasket lost its first 19 minutes). When the app follows a match it
receives every document, so it keeps its own recording in the very same format (``recorded_feed``): the play-by-play is append-only, so
each line and each shot is stored once with the frame it appeared in, was corrected in or disappeared in. Standard library only.
"""
import copy
import json
from pathlib import Path

import pytest

from src.live_core.recorded_feed import FORMAT_VERSION, RecordedFeed
from src.live_core.recording_builder import RecordingBuilder
from src.live_core.session import LiveSession, begin_recording_json, record_gap_json, recording_json, start_json, update_json

RECORDINGS = Path(__file__).parent / "recordings"
STARTED = "2026-10-10T14:55:03+00:00"


@pytest.fixture(scope="module")
def original():
    return RecordedFeed.loads((RECORDINGS / "2524470.rec.json.gz").read_bytes())


def frames_of(feed):
    return [(f["t"], feed.document_at(f["t"])) for f in feed.frames]


def line(num, text="x"):
    return {"num": str(num), "text": text, "quarter": "1", "time": "09:00"}


def doc(lines, shots=(), status="2", time="09:00", pts=(0, 0)):
    return {"HEADER": {"status": status, "statusText": "LIVE", "quarter": 1, "time": time,
                       "TEAM": [{"id": "1", "pts": str(pts[0])}, {"id": "2", "pts": str(pts[1])}]},
            "BOXSCORE": {"TEAM": [{"id": "1", "PLAYER": [{"id": "9", "name": "A", "no": "4"}]}, {"id": "2", "PLAYER": []}]},
            "PLAYBYPLAY": {"duration": None, "LINES": list(lines)}, "SHOTCHART": {"quarters": 4, "SHOTS": list(shots), "TEAM": []}}


# -- it packs what it is given, so the replay of the pack is the feed it saw --------------------------------------------------------

def test_replaying_what_the_builder_packed_gives_back_every_document_regression(original):
    """The Zamora-Leon feed, document by document, through the builder: the pack replays to the same play-by-play and shots."""
    builder = RecordingBuilder("2524470", STARTED)
    for t, document in frames_of(original):
        builder.add(t, copy.deepcopy(document))
    packed = RecordedFeed(builder.pack())
    for t, document in frames_of(original):
        got = packed.document_at(t)
        assert got["PLAYBYPLAY"]["LINES"] == document["PLAYBYPLAY"]["LINES"], t
        assert got["SHOTCHART"]["SHOTS"] == document["SHOTCHART"]["SHOTS"], t
        assert got["HEADER"]["time"] == document["HEADER"]["time"] and got["HEADER"]["TEAM"] == document["HEADER"]["TEAM"]


def test_a_pack_is_small_not_a_document_per_poll(original):
    builder = RecordingBuilder("2524470", STARTED)
    for t, document in frames_of(original):
        builder.add(t, copy.deepcopy(document))
    assert len(json.dumps(builder.pack(), separators=(",", ":"))) < 400_000


def test_corrected_and_removed_lines_are_kept_with_their_frame():
    builder = RecordingBuilder("1", STARTED)
    builder.add(0, doc([line(1, "a")]))
    builder.add(10, doc([line(2, "b"), line(1, "a corrected")]))
    builder.add(20, doc([line(2, "b")]))
    packed = builder.pack()
    by_num = {e["l"]["num"]: e for e in packed["lines"]}
    assert by_num["1"]["fix"] == [[1, line(1, "a corrected")]] and by_num["1"]["r"] == 2
    feed = RecordedFeed(packed)
    assert [l["text"] for l in feed.document_at(10)["PLAYBYPLAY"]["LINES"]] == ["b", "a corrected"]
    assert [l["text"] for l in feed.document_at(20)["PLAYBYPLAY"]["LINES"]] == ["b"]


def test_the_pack_has_the_format_the_player_reads():
    builder = RecordingBuilder("777", STARTED)
    builder.add(5, doc([line(1)], pts=(2, 0)))
    packed = builder.pack()
    assert packed["v"] == FORMAT_VERSION and packed["match"] == "777" and packed["started"] == STARTED
    assert packed["frames"] == [{"t": 5, "h": {"status": "2", "statusText": "LIVE", "quarter": 1, "time": "09:00", "pts": {"1": 2, "2": 0}}}]
    assert "LINES" not in packed["base"]["PLAYBYPLAY"] and packed["gaps"] == {}


# -- the failures of FEB in the middle of the match --------------------------------------------------------------------------------

def test_a_failed_poll_opens_a_gap_that_closes_when_the_endpoint_answers_again():
    builder = RecordingBuilder("1", STARTED)
    builder.add(0, doc([line(1)]))
    builder.gap("boxscore", 12)
    builder.gap("boxscore", 22)            # still failing: the same gap
    builder.gap("keyfacts", 22)
    builder.add(30, doc([line(1), line(2)]))
    assert builder.pack()["gaps"] == {"boxscore": [[12, 30]], "keyfacts": [[22, 30]]}


def test_failures_before_the_first_document_are_not_gaps_and_an_open_one_ends_at_the_last_frame():
    builder = RecordingBuilder("1", STARTED)
    builder.gap("boxscore", 3)             # the match has not started: nothing to hold
    builder.add(10, doc([line(1)]))
    builder.gap("shotchart", 40)
    assert builder.pack()["gaps"] == {"shotchart": [[40, 40]]}


def test_with_nothing_received_there_is_nothing_to_pack():
    assert RecordingBuilder("1", STARTED).pack() is None


# -- inside the session (what the tablet calls) --------------------------------------------------------------------------------------

def test_the_session_records_every_document_it_is_given_a_time_for(original):
    package = (RECORDINGS / "2524470.package.json").read_text(encoding="utf-8")
    session = LiveSession(package)
    session.begin_recording("2524470", STARTED)
    for t, document in frames_of(original)[:200]:
        session.update(copy.deepcopy(document), at=t)
    session.update(frames_of(original)[200][1])             # no time: not recorded (a replay of the demo is not a feed)
    packed = RecordedFeed.loads(session.recording())
    assert len(packed.frames) == 200 and packed.match == "2524470"


def test_the_session_without_begin_recording_records_nothing(original):
    session = LiveSession((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    session.update(frames_of(original)[0][1], at=1.0)
    assert session.recording() is None


def test_the_pyodide_entry_points_round_trip_through_json_text(original):
    start_json((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    begin_recording_json("2524470", STARTED)
    t0, doc0 = frames_of(original)[0]
    update_json(json.dumps(doc0), t0)
    record_gap_json("boxscore", 5.0)
    t1, doc1 = frames_of(original)[1]
    update_json(json.dumps(doc1), t1 + 20)
    packed = json.loads(recording_json())
    assert packed["v"] == FORMAT_VERSION and len(packed["frames"]) == 2 and packed["gaps"]["boxscore"][0][0] == 5.0
