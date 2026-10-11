"""The first real recording (Zamora - Leon, FEB match 2524470, 10/10/2026) as a regression fixture (issue #174).

``tests/recordings/2524470.rec.json.gz`` is the recorder's output packed by ``recording_pack`` (24 KB instead of
58 MB). It keeps what real live data does and a synthetic game never does: the feed answered 404 for a minute in
the middle of the match, the play-by-play arrives ~40 s late, the final status shows up 15 minutes after the last play.
"""
from pathlib import Path

import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.engine import LiveEngine
from src.live_core.recorded_feed import RecordedFeed

FIXTURE = Path(__file__).parent / "recordings" / "2524470.rec.json.gz"
OWN, RIVAL = "1008631", "1008898"
REAL_POSSESSIONS_PER_TEAM = 69.12


@pytest.fixture(scope="module")
def feed():
    return RecordedFeed.load(FIXTURE)


@pytest.fixture(scope="module")
def played(feed):
    """Every frame of the match through the engine, in order: [(recording second, snapshot)]."""
    engine, out = LiveEngine(), []
    for frame in feed.frames:
        out.append((frame["t"], engine.update(feed.document_at(frame["t"]))))
    return out


class TestTheRecording:
    def test_is_the_recorded_match_and_a_small_file(self, feed):
        assert feed.match == "2524470"
        assert len(feed.frames) == 353
        assert FIXTURE.stat().st_size < 60_000
        assert 7_100 < feed.duration < 7_200  # 1 h 59 min of feed

    def test_status_goes_from_not_started_to_live_to_final(self, feed):
        statuses = [f["h"]["status"] for f in feed.frames]
        assert statuses[0] == "1" and statuses[-1] == "3"
        assert set(statuses) <= {"1", "2", "3"}
        assert feed.frames[-1]["h"]["time"] == "FINAL"

    def test_the_feed_has_nothing_before_the_first_poll(self, feed):
        assert feed.document_at(-1) is None

    def test_boxscore_and_keyfacts_answered_404_for_a_while_in_the_fourth_quarter_regression(self, feed):
        """Real feed quirk: 62 s (boxscore) and 11 s (keyfacts) of 404 with the match in progress."""
        assert feed.document_at(5990, "boxscore") is not None
        assert feed.document_at(6000, "boxscore") is None
        assert feed.document_at(6065, "keyfacts") is None
        assert feed.document_at(6065, "shotchart") is not None
        assert feed.document_at(6075, "boxscore") is not None

    def test_the_play_by_play_only_grows(self, feed):
        sizes = [len(feed.document_at(f["t"])["PLAYBYPLAY"]["LINES"]) for f in feed.frames]
        assert sizes == sorted(sizes) and sizes[0] == 0 and sizes[-1] == 458


class TestTheEngineOnRealLiveDocuments:
    def test_digests_every_frame_and_ends_with_the_official_score(self, played):
        _, last = played[-1]
        assert (last["score"][OWN], last["score"][RIVAL]) == (38, 59)
        assert last["period"] == 4

    def test_game_time_never_goes_backwards_although_the_feed_is_late(self, played):
        elapsed = [snap["elapsed"] for _, snap in played]
        assert elapsed == sorted(elapsed)

    def test_the_pace_projection_settles_on_the_real_possessions(self, feed):
        """The numbers behind the pace card (#209): unreliable before minute 5, then closing in on 69.1."""
        engine, advice = LiveEngine(), AdviceEngine(OWN, RIVAL)
        by_minute = {}
        for frame in feed.frames:
            snap = engine.update(feed.document_at(frame["t"]))
            pace = advice.analyze(snap).get("pace")
            if pace:
                by_minute[snap["elapsed"] // 60] = pace
        assert by_minute[3]["reliable"] is False
        assert by_minute[5]["reliable"] is True
        assert abs(by_minute[30]["projected_possessions"] - REAL_POSSESSIONS_PER_TEAM) < 1.0
        assert abs(by_minute[10]["projected_possessions"] - REAL_POSSESSIONS_PER_TEAM) < 6.0
