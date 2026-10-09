"""LiveSession: the facade the Android app calls inside Pyodide (issue #120).

Runs with the standard library only (no conftest fixtures), like the rest of live_core.
"""
import json
from pathlib import Path

import pytest

from src.live_core.package import ChecksumMismatchError
from src.live_core.session import LiveSession
from src.live_core.vectors import unwrap_extended_json

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "tests/live_vectors/vectors.json").read_text(encoding="utf-8"))
PACKAGE = VECTORS["engine"]["package"]
EXPECTED = VECTORS["expected"]["engine"]["checkpoints"]
GAME = unwrap_extended_json(json.loads((ROOT / "src/JSON_samples/feb_game.json").read_text(encoding="utf-8")))


@pytest.fixture()
def session():
    s = LiveSession(PACKAGE)
    s.load_replay(GAME)
    return s


def test_meta_describes_teams_and_package(session):
    meta = session.meta
    assert meta["team"]["name"] == "ACEITES ABRIL ADBA SANFER"
    assert meta["rival"]["name"] == "MANRESA CBF A"
    assert meta["package_id"] and meta["schema_version"] == 1


def test_replay_matches_the_reference_vectors(session):
    """Same checkpoints as the shared vectors: score, elapsed time and the NEW alerts must agree."""
    for exp in EXPECTED:
        out = session.replay(exp["elapsed"])
        assert out["snapshot"]["elapsed"] == exp["elapsed"]
        assert out["snapshot"]["score"] == exp["score"]
        assert [a["key"] for a in out["alerts"]] == exp["alerts"]


def test_alerts_carry_everything_the_ui_needs(session):
    alerts = [a for exp in EXPECTED for a in session.replay(exp["elapsed"])["alerts"]]
    assert alerts
    for a in alerts:
        assert {"key", "id", "severity", "category", "message"} <= set(a)


def test_analysis_exposes_four_factors(session):
    out = session.replay(1800)
    assert "four_factors" in out["analysis"]


def test_same_moment_twice_does_not_repeat_alerts(session):
    first = session.replay(1800)
    again = session.replay(1800)
    assert first["alerts"] and again["alerts"] == []


def test_replay_info_gives_the_duration(session):
    assert session.replay_info["duration"] == 2700  # 4 x 10 min + one 5 min overtime in the sample
    assert session.replay_info["status"]


def test_update_without_replay_uses_the_given_document():
    s = LiveSession(PACKAGE)
    from src.live_core.replay import truncate_doc

    out = s.update(truncate_doc(GAME, 2, 300))
    assert out["snapshot"]["period"] == 2


def test_replay_before_loading_a_game_is_an_error():
    with pytest.raises(RuntimeError, match="replay"):
        LiveSession(PACKAGE).replay(100)


def test_corrupted_package_is_rejected_with_a_clear_error():
    broken = json.loads(PACKAGE)
    broken["package"]["team"]["name"] = "otro"
    with pytest.raises(ChecksumMismatchError):
        LiveSession(json.dumps(broken))


def test_json_entry_points_for_pyodide():
    from src.live_core import session as mod

    meta = json.loads(mod.start_json(PACKAGE))
    assert meta["team"]["id"] == "982047"
    info = json.loads(mod.load_replay_json(json.dumps(GAME)))
    assert info["duration"] == 2700
    out = json.loads(mod.replay_json(1800))
    assert out["snapshot"]["score"] and isinstance(out["alerts"], list)
    out2 = json.loads(mod.update_json(json.dumps(__import__("src.live_core.replay", fromlist=["truncate_doc"]).truncate_doc(GAME, 3, 0))))
    assert out2["snapshot"]["elapsed"] == 1800
