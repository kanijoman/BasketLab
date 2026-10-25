"""The version of the engine (issue #226): what the About screen shows and the diagnostics carry, so a report says WHICH engine ran.

It is a short hash of the engine's sources, not a number somebody has to remember to raise: it changes when the engine changes, it is the
same on the tablet (Pyodide) and under pytest, and it does not depend on the line endings of the checkout.
"""
import re
from pathlib import Path

from src.live_core.session import LiveSession
from src.live_core.version import engine_version

ROOT = Path(__file__).resolve().parent.parent


def tree(base: Path, files: dict) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (base / name).write_bytes(content)
    return base


def test_it_is_eight_hex_characters_and_stable():
    version = engine_version()
    assert re.fullmatch(r"[0-9a-f]{8}", version) and engine_version() == version


def test_it_changes_when_a_source_changes_and_not_with_the_line_endings(tmp_path):
    base = tree(tmp_path / "a", {"x.py": b"a = 1\nb = 2\n", "y.py": b"c = 3\n"})
    crlf = tree(tmp_path / "b", {"x.py": b"a = 1\r\nb = 2\r\n", "y.py": b"c = 3\r\n"})
    edited = tree(tmp_path / "c", {"x.py": b"a = 1\nb = 5\n", "y.py": b"c = 3\n"})
    assert engine_version(base) == engine_version(crlf) != engine_version(edited)


def test_a_new_or_renamed_module_changes_it_and_what_is_not_python_does_not(tmp_path):
    base = tree(tmp_path / "a", {"x.py": b"a = 1\n"})
    more = tree(tmp_path / "b", {"x.py": b"a = 1\n", "z.py": b"q = 1\n"})
    renamed = tree(tmp_path / "c", {"w.py": b"a = 1\n"})
    other = tree(tmp_path / "d", {"x.py": b"a = 1\n", "notes.txt": b"hello", "x.pyc": b"\x00"})
    assert engine_version(base) != engine_version(more) and engine_version(base) != engine_version(renamed)
    assert engine_version(base) == engine_version(other)


def test_the_session_meta_carries_it_for_the_app():
    package = (ROOT / "tests" / "recordings" / "2524470.package.json").read_text(encoding="utf-8")
    assert LiveSession(package).meta["engine_version"] == engine_version()


def test_the_replay_compatibility_is_a_number_the_app_knows_too_regression():
    """0.4.0 feedback (#562): a match saved with an earlier engine replays with errors (a lineup that is not illegal, an overtime that was not played). The app stamps what it keeps
    with ``REPLAY_COMPAT`` and warns about the matches kept under an older one, offering to delete them. It is raised on purpose when a change makes old replays unreliable
    (the hash of the engine changes with every edit, so it cannot be the stamp: every saved match would be flagged every week)."""
    from src.live_core.version import REPLAY_COMPAT

    assert isinstance(REPLAY_COMPAT, int) and REPLAY_COMPAT >= 2
    app = (ROOT / "apps" / "live-android" / "src" / "feed" / "replayCompat.ts").read_text(encoding="utf-8")
    assert int(re.search(r"REPLAY_COMPAT\s*=\s*(\d+)", app).group(1)) == REPLAY_COMPAT, "raise it in version.py AND in the app (feed/replayCompat.ts)"


def test_the_session_meta_carries_the_replay_compatibility():
    from src.live_core.version import REPLAY_COMPAT

    package = (ROOT / "tests" / "recordings" / "2524470.package.json").read_text(encoding="utf-8")
    assert LiveSession(package).meta["replay_compat"] == REPLAY_COMPAT
