"""The session follows a FBCYL match from the streaming service and closes it with msstats (issue #446, PR 3: the app; this is its engine side).

``LiveSession.update_streaming(body)`` turns a reading of ``streaming/match-id/{adGameId}`` into the FEB document the engine reads (``fbcyl_adapter.from_streaming``) and updates it. The real
service, in the last minutes of Salamanca–UNILEON (7/11/2026, ``tests/fixtures/fbcyl_streaming_end_20261107.json.gz``), answers responses that go BACKWARDS mixed with the right ones
(period 1 with 48 moves after 593 of the 4th period; 525 moves after 609): the engine would follow them and put the clock back, so a reading that has less than the best one seen is ignored.
``update_fbcyl_final`` takes the definitive moves and stats of ``msstats`` once the match is over (the stream lacked 2 moves) and replaces what was seen.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.live_core.fbcyl_adapter import to_feb_document
from src.live_core.session import LiveSession, start_json, update_fbcyl_final_json, update_streaming_json
from src.live_prep.package_builder import SeasonAccumulator

FIXTURES = Path(__file__).parent / "fixtures"
HOME, AWAY = "39731", "39609"                        # Salamanca, UNILEON (teamIdExtern)


def _load(name):
    return json.loads(gzip.open(FIXTURES / name).read())


@pytest.fixture(scope="module")
def recording():
    return _load("fbcyl_streaming_20261107.json.gz")


@pytest.fixture(scope="module")
def ending():
    return [r["body"] for r in _load("fbcyl_streaming_end_20261107.json.gz")["readings"]]


@pytest.fixture(scope="module")
def package(recording):
    """The package of the match: one game of the two teams (the very match, through the adapter of msstats), as the publisher would have built it from their season."""
    final = recording["msstats_stats"]
    acc = SeasonAccumulator()
    acc.add_game(to_feb_document({"uuid": "u", "moves": recording["msstats_moves"], "stats": final}))
    return acc.to_package(collection="FBCYL_TEST", season="2026", team_id=AWAY, rival_id=HOME, competition_meta=None, created_at="2026-11-09T00:00:00Z").dumps()


@pytest.fixture
def session(package):
    return LiveSession(package)


def _shown(out):
    snap = out["snapshot"]
    return snap["period"], snap["score"][HOME], snap["score"][AWAY]


class TestReadingsThatGoBackwards:
    def test_the_engine_alone_would_follow_a_reading_of_the_first_period_after_the_fourth(self, session, ending):
        """The premise: without the guard the clock goes back to the 1st quarter (what made the guard necessary)."""
        session.update_streaming(ending[0])
        from src.live_core.fbcyl_adapter import from_streaming

        assert session.update(from_streaming(ending[1]))["snapshot"]["period"] == 1

    def test_the_real_end_of_the_match_never_goes_back_and_ends_81_75_regression(self, session, ending):
        shown, stale = [], []
        for body in ending:
            out = session.update_streaming(body)
            stale.append(bool(out.get("stale")))
            if not out.get("stale"):
                shown.append(_shown(out))
        assert stale == [False, True, False, True, False, True, True]     # 593 | 1st-period 48 | 609 | 525 | 609 again | 1st-period 103 | 607 (the best one had 609)
        assert shown[-1] == (4, 81, 75)
        assert shown == sorted(shown)                                      # period, then the scores of the home team: nothing goes backwards

    def test_a_reading_equal_to_the_best_is_not_stale_so_a_repeated_one_changes_nothing(self, session, ending):
        first = session.update_streaming(ending[2])
        again = session.update_streaming(ending[2])
        assert not again.get("stale") and (again["snapshot"]["score"], again["snapshot"]["elapsed"]) == (first["snapshot"]["score"], first["snapshot"]["elapsed"])

    def test_a_stale_reading_returns_nothing_to_show_and_leaves_the_session_as_it_was(self, session, ending):
        session.update_streaming(ending[2])
        before = session.update_streaming(ending[2])["snapshot"]
        out = session.update_streaming(ending[3])
        assert out == {"stale": True}
        assert session.update_streaming(ending[2])["snapshot"] == before


class TestTheClosingWithMsstats:
    def test_the_definitive_moves_replace_what_the_stream_gave_and_have_the_two_moves_it_lacked(self, session, recording, ending):
        session.update_streaming(ending[-3])                                # the stream's best reading: 609 moves of which 2 are not in msstats' 609 distinct ones
        stream_lines = len(session.update_streaming(ending[-3])["snapshot"]["log"])
        final = session.update_fbcyl_final(recording["msstats_moves"], recording["msstats_stats"])
        assert _shown(final) == (4, 81, 75) and len(final["snapshot"]["log"]) >= stream_lines
        assert final["snapshot"]["players"]                                   # the roster of the definitive stats

    def test_after_the_closing_no_reading_of_the_stream_is_followed(self, session, recording, ending):
        session.update_streaming(ending[-3])
        session.update_fbcyl_final(recording["msstats_moves"], recording["msstats_stats"])
        assert session.update_streaming(ending[-3]) == {"stale": True}


class TestTheLastDocument:
    """The app keeps the match followed to review it later: it needs the FEB document of the last reading, which only the engine has (the stream is not FEB-shaped)."""

    def test_there_is_none_before_a_reading_and_it_is_the_feb_document_of_the_last_accepted_one_after(self, session, ending):
        assert session.last_document() is None
        session.update_streaming(ending[2])
        doc = session.last_document()
        assert doc["HEADER"]["status"] == "2" and len(doc["PLAYBYPLAY"]["LINES"]) > 500
        session.update_streaming(ending[3])                              # stale: the document is still the 609 one
        assert session.last_document() == doc

    def test_after_the_closing_it_is_the_final_document(self, session, recording, ending):
        session.update_streaming(ending[2])
        session.update_fbcyl_final(recording["msstats_moves"], recording["msstats_stats"])
        assert session.last_document()["HEADER"]["status"] == "3"

    def test_the_entry_point_gives_json_or_null(self, package, ending):
        from src.live_core.session import last_document_json

        start_json(package)
        assert json.loads(last_document_json()) is None
        update_streaming_json(json.dumps(ending[2]))
        assert json.loads(last_document_json())["HEADER"]["source"] == "fbcyl"


class TestThePyodideEntryPoints:
    def test_the_json_entry_points_do_the_same_and_say_stale_as_json(self, package, ending, recording):
        start_json(package)
        ok = json.loads(update_streaming_json(json.dumps(ending[2]), 12.5))
        assert _shown(ok) == (4, 81, 75)
        assert json.loads(update_streaming_json(json.dumps(ending[3]), 22.5)) == {"stale": True}
        final = json.loads(update_fbcyl_final_json(json.dumps(recording["msstats_moves"]), json.dumps(recording["msstats_stats"]), 30.0))
        assert _shown(final) == (4, 81, 75)

    def test_the_recording_of_the_feed_keeps_what_was_followed(self, session, ending):
        session.begin_recording("fbcyl-149388", "2026-11-07T18:31:03Z")
        session.update_streaming(ending[0], 0.0)
        session.update_streaming(ending[2], 10.0)
        assert session.recording() is not None and json.loads(session.recording())
