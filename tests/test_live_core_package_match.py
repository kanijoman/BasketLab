"""The package must be the one of the match (issue #417).

Found reviewing Leon-Unibasket with the package prepared for Leon-Zamora: the rival never appeared in the document, so the rules
about the rival read a team without a single basket ("El rival lleva 30:00 sin anotar", "Pintura: 30-0"). When the teams of the
package are not the teams of the match the session says so and raises no alerts: they would only mislead the staff.
"""
from pathlib import Path

from src.live_core.recorded_feed import RecordedFeed
from src.live_core.session import LiveSession

RECORDINGS = Path(__file__).parent / "recordings"
ZAMORA_PACKAGE = (RECORDINGS / "2524470.package.json").read_text(encoding="utf-8")


def final_doc(name):
    feed = RecordedFeed.loads((RECORDINGS / name).read_bytes())
    return feed.document_at(feed.duration)


def doc_at(name, t):
    return RecordedFeed.loads((RECORDINGS / name).read_bytes()).document_at(t)


def test_the_package_of_another_match_is_detected_and_raises_no_alerts_regression():
    session = LiveSession(ZAMORA_PACKAGE)                                    # Leon - Zamora
    out = session.update(final_doc("2524475.rec.json.gz"))                  # Leon - Unibasket
    check = out["package_match"]
    assert check["ok"] is False
    assert check["expected"] == ["1008631", "1008898"] and sorted(check["found"]) == ["1008631", "1008895"]
    assert out["alerts"] == [] and out["analysis"] == {}
    assert out["snapshot"]["score"], "the score and the clock are still the match's: only the advice is withheld"


def test_the_package_of_the_match_is_accepted_and_works_as_before():
    session = LiveSession(ZAMORA_PACKAGE)
    out = session.update(doc_at("2524470.rec.json.gz", 2500))          # mid-match: the final one ends on a stoppage, where lineup alerts wait (#413)
    check = out["package_match"]
    assert check["ok"] is True and check["expected"] == ["1008631", "1008898"] and sorted(check["found"]) == check["expected"]
    assert out["alerts"] and out["analysis"]


def test_the_replay_of_a_game_checks_it_too():
    session = LiveSession(ZAMORA_PACKAGE)
    session.load_replay(final_doc("2524475.rec.json.gz"))
    assert session.replay(1500)["package_match"]["ok"] is False
