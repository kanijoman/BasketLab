"""Recorded feed (issue #174): a real recording packed in a compact file and replayed with its real timeline.

``recording_pack`` turns what the recorder saved (every poll + the bodies that changed) into one small file:
the play-by-play of a match is append-only, so every line is stored once with the frame it first appeared in;
``RecordedFeed`` (standard library only, usable on the tablet too) rebuilds the document FEB was serving at any
second, including the windows where an endpoint answered 404 in the middle of the match.
"""
import copy
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.live_core.recorded_feed import FORMAT_VERSION, RecordedFeed
from src.live_prep.recorder import ENDPOINTS, Recorder, Response
from src.live_prep.recording_pack import pack_recording, write_pack
from src.live_prep.recording_report import merged_documents


# -- a small, hand-made pack --------------------------------------------------------------------------

def line(num, text="x", **kw):
    return {"num": str(num), "text": text, "quarter": "1", "time": "09:00", **kw}


def pack(**over):
    data = {
        "v": FORMAT_VERSION, "match": "777",
        "base": {"HEADER": {"status": "3", "statusText": "FINISHED", "quarter": 1, "time": "FINAL",
                            "TEAM": [{"id": "1", "pts": "4"}, {"id": "2", "pts": "2"}]},
                 "BOXSCORE": {"TEAM": [{"id": "1", "PLAYER": [{"id": "9", "name": "A"}]}, {"id": "2", "PLAYER": []}]},
                 "PLAYBYPLAY": {"duration": None, "hasExtension": False},
                 "SHOTCHART": {"quarters": 4, "duration": None, "TEAM": []}},
        # newest first, like the feed: line 3 is the last one that happened
        "lines": [{"f": 2, "l": line(3, "c")}, {"f": 1, "l": line(2, "b"), "fix": [[3, line(2, "b corrected")]]},
                  {"f": 0, "l": line(1, "a"), "r": 3}],
        "shots": [{"f": 2, "s": {"x": "3"}}, {"f": 1, "s": {"x": "2"}}],
        "frames": [{"t": 0.0, "h": {"status": "1", "statusText": "NOT STARTED", "quarter": 1, "time": "10:00", "pts": {"1": 0, "2": 0}}},
                   {"t": 10.0, "h": {"status": "2", "statusText": "LIVE", "quarter": 1, "time": "09:30", "pts": {"1": 2, "2": 0}}},
                   {"t": 20.0, "h": {"status": "2", "statusText": "LIVE", "quarter": 1, "time": "09:00", "pts": {"1": 2, "2": 2}}},
                   {"t": 30.0, "h": {"status": "3", "statusText": "FINISHED", "quarter": 1, "time": "FINAL", "pts": {"1": 4, "2": 2}}}],
        "gaps": {"boxscore": [[12.0, 18.0]], "keyfacts": [[14.0, 16.0]]},
    }
    data.update(over)
    return data


def nums(doc):
    return [l["num"] for l in doc["PLAYBYPLAY"]["LINES"]]


class TestRecordedFeed:
    def test_nothing_is_served_before_the_first_frame(self):
        assert RecordedFeed(pack()).document_at(-1) is None

    def test_a_document_is_the_latest_frame_up_to_that_second(self):
        feed = RecordedFeed(pack())
        assert nums(feed.document_at(0)) == ["1"]
        assert nums(feed.document_at(19.9)) == ["2", "1"]
        assert nums(feed.document_at(20)) == ["3", "2", "1"]  # newest first, as FEB serves it
        assert nums(feed.document_at(9999)) == ["3", "2"]  # line 1 is removed from frame 3 on

    def test_the_header_follows_the_frame(self):
        feed = RecordedFeed(pack())
        h = feed.document_at(10)["HEADER"]
        assert (h["status"], h["statusText"], h["quarter"], h["time"]) == ("2", "LIVE", 1, "09:30")
        assert [t["pts"] for t in h["TEAM"]] == ["2", "0"]
        assert feed.document_at(30)["HEADER"]["time"] == "FINAL"

    def test_a_corrected_line_shows_its_new_text_only_from_the_frame_of_the_correction(self):
        feed = RecordedFeed(pack())
        assert feed.document_at(20)["PLAYBYPLAY"]["LINES"][1]["text"] == "b"
        assert feed.document_at(30)["PLAYBYPLAY"]["LINES"][1]["text"] == "b corrected"

    def test_a_line_can_disappear_after_its_removal_frame(self):
        feed = RecordedFeed(pack())
        assert "1" in nums(feed.document_at(20))
        assert "1" not in nums(feed.document_at(30))

    def test_shots_appear_with_their_frame(self):
        feed = RecordedFeed(pack())
        assert feed.document_at(0)["SHOTCHART"]["SHOTS"] == []
        assert feed.document_at(10)["SHOTCHART"]["SHOTS"] == [{"x": "2"}]
        assert feed.document_at(20)["SHOTCHART"]["SHOTS"] == [{"x": "3"}, {"x": "2"}]

    def test_an_endpoint_in_a_gap_answers_nothing_while_the_others_keep_serving(self):
        feed = RecordedFeed(pack())
        assert feed.document_at(13, "boxscore") is None
        assert feed.document_at(13, "keyfacts") is not None  # its gap starts at 14
        assert feed.document_at(15, "keyfacts") is None
        assert feed.document_at(17, "keyfacts") is not None
        assert feed.document_at(17, "shotchart") is not None
        assert feed.document_at(18, "boxscore") is not None  # the gap is [from, to): it is back at 18

    def test_duration_is_the_last_thing_that_happened(self):
        assert RecordedFeed(pack()).duration == 30.0
        assert RecordedFeed(pack(gaps={"boxscore": [[40.0, 55.0]]})).duration == 55.0

    def test_documents_are_independent_copies(self):
        feed = RecordedFeed(pack())
        feed.document_at(20)["PLAYBYPLAY"]["LINES"].clear()
        assert nums(feed.document_at(20)) == ["3", "2", "1"]

    def test_loads_from_a_gzipped_file(self, tmp_path):
        path = tmp_path / "m.rec.json.gz"
        path.write_bytes(gzip.compress(json.dumps(pack()).encode("utf-8")))
        assert RecordedFeed.load(path).match == "777"

    def test_rejects_an_unknown_format_version(self):
        with pytest.raises(ValueError, match="version"):
            RecordedFeed(pack(v=99))


# -- packing a real recording -----------------------------------------------------------------------------

class ScriptedFeb:
    """Serves one scripted body per poll and endpoint; the last one repeats (a minimal FEB)."""

    def __init__(self, script):
        self.script, self.calls = script, {k: 0 for k in script}

    def get(self, url, token):
        ep = next(k for k, template in ENDPOINTS.items() if url == template.format(match_code="777"))
        seq = self.script[ep]
        status, body = seq[min(self.calls[ep], len(seq) - 1)]
        self.calls[ep] += 1
        return Response(status, {"Date": "x"}, json.dumps(body).encode() if body is not None else b"")

    def token(self, code, force=False):
        return "tok"


def box(status, time, pts=(0, 0)):
    return {"HEADER": {"status": status, "statusText": {"1": "NOT STARTED", "2": "LIVE", "3": "FINISHED"}[status],
                       "quarter": 1, "time": time, "TEAM": [{"id": "1", "pts": str(pts[0])}, {"id": "2", "pts": str(pts[1])}]},
            "BOXSCORE": {"TEAM": [{"id": "1", "name": "A", "PLAYER": [{"id": "9", "name": "N", "no": "7", "pts": "99"}]},
                                  {"id": "2", "name": "B", "PLAYER": []}]}}


def kf(*lines):
    return {"PLAYBYPLAY": {"duration": None, "hasExtension": False, "LINES": list(reversed(lines))}}


def sc(*shots):
    return {"SHOTCHART": {"quarters": 4, "duration": None, "TEAM": [], "SHOTS": list(shots)}}


@pytest.fixture()
def recording(tmp_path):
    l1, l2, l3 = line(1, "a"), line(2, "b"), line(3, "c")
    feb = ScriptedFeb({
        "boxscore": [(200, box("1", "10:00")), (200, box("2", "09:30", (2, 0))), (404, None), (404, None),
                     (200, box("2", "09:00", (2, 2))), (200, box("3", "FINAL", (4, 2)))],
        "keyfacts": [(200, kf()), (200, kf(l1)), (200, kf(l1, l2)), (200, kf(l1, line(2, "b corrected"), l3)),
                     (200, kf(l1, line(2, "b corrected"), l3)), (200, kf(l1, line(2, "b corrected"), l3))],
        "shotchart": [(200, sc()), (200, sc({"x": "1"})), (200, sc({"x": "1"})), (200, sc({"x": "1"}, {"x": "2"}))],
    })
    state = {"t": 1_800_000_000.0}

    def sleep(seconds):
        state["t"] += seconds

    def utcnow():  # each request takes a few milliseconds, like the real thing: no two polls share a timestamp
        state["t"] += 0.01
        return datetime.fromtimestamp(state["t"], timezone.utc)

    rec = Recorder("777", tmp_path, feb.get, feb.token, interval=10, tail_polls=1, now=lambda: state["t"], sleep=sleep,
                   utcnow=utcnow)
    rec.run()
    return tmp_path


class TestPackRecording:
    def test_every_recorded_document_is_rebuilt_exactly(self, recording):
        feed = RecordedFeed(pack_recording(recording))
        docs = list(merged_documents(recording))
        assert docs
        for t, original in docs:
            rebuilt = feed.document_at(feed.frame_time_of(t))
            assert rebuilt["PLAYBYPLAY"]["LINES"] == original["PLAYBYPLAY"]["LINES"]
            assert rebuilt["SHOTCHART"]["SHOTS"] == original["SHOTCHART"]["SHOTS"]
            assert rebuilt["HEADER"]["status"] == original["HEADER"]["status"]
            assert rebuilt["HEADER"]["time"] == original["HEADER"]["time"]

    def test_the_play_by_play_is_stored_once_with_the_frame_it_appeared_in(self, recording):
        data = pack_recording(recording)
        assert sorted(entry["l"]["num"] for entry in data["lines"]) == ["1", "2", "3"]
        assert all(isinstance(entry["f"], int) for entry in data["lines"])
        fixed = next(entry for entry in data["lines"] if entry["l"]["num"] == "2")
        assert [v[1]["text"] for v in fixed.get("fix", [])] == ["b corrected"]  # the correction is kept, not lost

    def test_the_404_window_of_the_middle_of_the_match_is_kept_per_endpoint(self, recording):
        data = pack_recording(recording)
        (start, end), = data["gaps"]["boxscore"]
        assert end - start >= 60  # the recorder waits a minute after a 404
        assert "shotchart" not in data["gaps"]

    def test_the_file_is_compact_and_has_no_box_score_statistics(self, recording):
        data = pack_recording(recording)
        player = data["base"]["BOXSCORE"]["TEAM"][0]["PLAYER"][0]
        assert player == {"id": "9", "no": "7", "name": "N"}  # the engine only needs the roster
        assert "SCOREBOARD" not in data["base"] and "TEAMSTATS" not in data["base"]

    def test_times_are_seconds_since_the_first_poll(self, recording):
        data = pack_recording(recording)
        assert 0 <= data["frames"][0]["t"] < 1.0  # the first document comes with the first polls
        assert [f["t"] for f in data["frames"]] == sorted(f["t"] for f in data["frames"])

    def test_write_pack_creates_a_gzipped_file_the_feed_can_load(self, recording, tmp_path):
        out = write_pack(recording, tmp_path / "out" / "m.rec.json.gz")
        assert RecordedFeed.load(out).match == "777"
        assert Path(out).stat().st_size < 20_000

    def test_a_directory_without_a_recording_is_an_error(self, tmp_path):
        with pytest.raises(ValueError, match="polls"):
            pack_recording(tmp_path)
