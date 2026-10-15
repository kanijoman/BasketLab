"""A LiveSession can play a real recording (issue #174, part 2): the app's "Partido real" demo feeds the engine
with the documents FEB served, at the recording's pace, through ``update`` (the very path the live mode will use).

Fixture: Zamora - Leon (10/10/2026), a preparation package built with the 8 matches played before it, and the
recording packed by ``recording_pack``.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.live_core.recorded_feed import RecordedFeed
from src.live_core.session import LiveSession, load_recording_json, play_recording_json, start_json

RECORDINGS = Path(__file__).parent / "recordings"
PACKAGE = (RECORDINGS / "2524470.package.json").read_text(encoding="utf-8")
RECORDING = (RECORDINGS / "2524470.rec.json.gz").read_bytes()
OWN, RIVAL = "1008631", "1008898"


@pytest.fixture()
def session():
    s = LiveSession(PACKAGE)
    s.load_recording(RECORDING)
    return s


class TestFirstEvent:
    """A recording starts with minutes of nothing (the match is SCHEDULED, no plays): the app starts at the first event (issue #346)."""

    def test_the_first_event_is_the_first_moment_with_a_play_by_play_line(self):
        feed = RecordedFeed.loads(RECORDING)
        start = feed.first_event_at()
        assert 200 < start < 400                                   # ~4.5 minutes of waiting in the real match
        assert (feed.document_at(start)["PLAYBYPLAY"]["LINES"])
        assert not (feed.document_at(start - 1)["PLAYBYPLAY"]["LINES"])

    def test_before_it_there_is_nothing_to_see(self):
        feed = RecordedFeed.loads(RECORDING)
        start = feed.first_event_at()
        assert all(not (feed.document_at(t) or {"PLAYBYPLAY": {"LINES": []}})["PLAYBYPLAY"]["LINES"] for t in range(0, int(start), 15))

    def test_a_recording_without_plays_starts_at_the_beginning(self):
        data = {"v": 1, "match": "1", "base": {"HEADER": {}, "BOXSCORE": {}, "PLAYBYPLAY": {}, "SHOTCHART": {}},
                "lines": [], "shots": [], "frames": [{"t": 0.0, "h": {"status": "1"}}, {"t": 30.0, "h": {"status": "1"}}], "gaps": {}}
        assert RecordedFeed(data).first_event_at() == 0.0

    def test_loading_a_recording_tells_where_to_start(self):
        s = LiveSession(PACKAGE)
        info = s.load_recording(RECORDING)
        assert info["start_at"] == RecordedFeed.loads(RECORDING).first_event_at()
        assert 0 <= info["start_at"] < info["duration"]


class TestFeed:
    def test_in_any_gap_covers_every_endpoint(self):
        feed = RecordedFeed.loads(RECORDING)
        assert feed.in_any_gap(6000) and feed.in_any_gap(6065)  # boxscore first, then keyfacts
        assert not feed.in_any_gap(5990) and not feed.in_any_gap(6080)


class TestPlay:
    def test_load_reports_the_recording(self, session):
        info = session.load_recording(RECORDING)
        assert info["match"] == "2524470" and info["frames"] == 353
        assert 7100 < info["duration"] < 7200

    def test_before_the_first_poll_the_match_is_not_there_yet(self, session):
        assert session.play(-5) == {"feed": "waiting", "output": None}

    def test_a_moment_of_the_match_gives_the_engine_output(self, session):
        result = session.play(3000)
        assert result["feed"] == "ok"
        snap = result["output"]["snapshot"]
        assert snap["elapsed"] > 1000 and set(snap["score"]) == {OWN, RIVAL}

    def test_a_real_404_in_the_middle_of_the_match_keeps_the_engine_untouched_regression(self, session):
        before = session.play(5990)["output"]["snapshot"]
        assert session.play(6000) == {"feed": "gap", "output": None}  # FEB did not answer: nothing to update
        assert session.play(6065) == {"feed": "gap", "output": None}
        after = session.play(6080)
        assert after["feed"] == "ok" and after["output"]["snapshot"]["elapsed"] >= before["elapsed"]

    def test_playing_the_whole_match_in_big_steps_ends_with_the_official_score(self, session):
        last = None
        for t in range(0, int(session.load_recording(RECORDING)["duration"]) + 60, 60):
            result = session.play(t)
            last = result["output"] or last
        assert last is not None
        assert (last["snapshot"]["score"][OWN], last["snapshot"]["score"][RIVAL]) == (38, 59)

    def test_the_alerts_and_the_pace_card_come_with_the_recording(self, session):
        alerts, pace = [], None
        for t in range(0, 7200, 30):
            result = session.play(t)
            if result["output"]:
                alerts += result["output"]["alerts"]
                pace = result["output"]["analysis"].get("pace") or pace
        assert len(alerts) >= 10 and {a["id"] for a in alerts} >= {"foul_trouble", "fatigue_high"}
        assert pace["reliable"] and pace["habit_own40"] == pytest.approx(72.4)

    def test_playing_needs_a_loaded_recording(self):
        with pytest.raises(RuntimeError, match="recording"):
            LiveSession(PACKAGE).play(10)


class TestPyodideEntryPoints:
    def test_json_text_in_json_text_out(self):
        start_json(PACKAGE)
        info = json.loads(load_recording_json(gzip.decompress(RECORDING).decode("utf-8")))
        assert info["match"] == "2524470"
        assert json.loads(play_recording_json(3000))["feed"] == "ok"
        assert json.loads(play_recording_json(6000)) == {"feed": "gap", "output": None}


class TestHomeTeam:
    """The scoreboard needs to know who plays at home before the first document arrives (issue #223)."""

    def test_meta_carries_the_home_team_of_the_match_of_the_package(self):
        assert LiveSession(PACKAGE).meta["home_id"] == "1008898"  # RECOLETAS ZAMORA hosts LEON

    def test_meta_without_match_details_has_no_home_team(self):
        from dataclasses import replace

        from src.live_core.package import PreparationPackage

        bare = replace(PreparationPackage.loads(PACKAGE), competition_meta={}).dumps()
        assert LiveSession(bare).meta["home_id"] is None
