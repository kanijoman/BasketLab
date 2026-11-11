"""The publication does not redo what did not change (#700).

The heavy sections of a competition (matches, possessions, lineups, IN/OUT, rotations, shots…) took the ``web-data`` build past its 60 minutes. A competition whose rows,
derived figures and code are the same as in the previous publication reuses its sealed files and computes nothing; any change in one of them recomputes the competition.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data import build_cache, sections, web_data  # noqa: E402
from src.local_data.web_data import SECTIONS, publish_web_data  # noqa: E402
from tests.test_local_web_data import FBCYL, FEB, MASTER, cheap_lineups, handler  # noqa: E402,F401  (fixtures)

HEAVY = [s for s in SECTIONS if s != "derived"]


@pytest.fixture(autouse=True)
def cheap_exporters(monkeypatch):
    """These tests are about what is computed and when, not about what the heavy exporters say (their own tests do): each answers a payload of the shape the publisher reads."""
    def small(**extra):
        return lambda handler, name: {"format": 1, "collection": name, "league": "fbcyl" if "FBCYL" in name else "feb", **extra}

    monkeypatch.setattr(sections, "export_matches", small(matches=[1]))
    monkeypatch.setattr(sections, "export_possessions", small(table=[1]))
    monkeypatch.setattr(sections, "export_possession_csv", small(csv="x"))
    monkeypatch.setattr(sections, "export_rotations", small(teams=[{"analysis": {"games_with_playbyplay": 1}}]))


@pytest.fixture()
def calls(monkeypatch):
    """The heavy sections that are computed, as ``(section, competition)``."""
    seen = []
    real = web_data.section_payload

    def counting(section, handler, db, collection):
        if section != "derived":
            seen.append((section, collection))
        return real(section, handler, db, collection)

    monkeypatch.setattr(web_data, "section_payload", counting)
    return seen


def _publish(handler, out, names=(FEB, FBCYL)):
    return publish_web_data(handler, out, ScopedSealer(MASTER), list(names))


def _files(out: Path) -> dict:
    return {str(p.relative_to(out)).replace("\\", "/"): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def test_a_refresh_without_news_computes_no_heavy_section_and_changes_no_byte(handler, tmp_path, calls):
    first = _publish(handler, tmp_path)
    assert {c for _, c in calls} == {FEB, FBCYL}
    before, calls[:] = _files(tmp_path), []
    assert _publish(handler, tmp_path) == first
    assert calls == [] and _files(tmp_path) == before


def test_a_competition_with_a_changed_game_is_computed_again_and_the_other_is_not(handler, tmp_path, calls):
    _publish(handler, tmp_path)
    calls[:] = []
    handler.connection.client["BASKETBALL"][FEB].delete_one({})
    _publish(handler, tmp_path)
    assert {c for _, c in calls} == {FEB} and {s for s, _ in calls} >= {"matches", "lineups", "inout"}


def _with_versions(monkeypatch, **changed):
    """The next publication sees these sections with another version of their code (the others keep theirs)."""
    real = build_cache.section_versions
    monkeypatch.setattr(web_data, "section_versions", lambda modules, *a, **k: {**real(modules, *a, **k), **changed})


def test_new_code_in_every_section_computes_everything_again(handler, tmp_path, calls, monkeypatch):
    _publish(handler, tmp_path)
    calls[:] = []
    _with_versions(monkeypatch, **{s: "another-version" for s in HEAVY})
    _publish(handler, tmp_path)
    assert {c for _, c in calls} == {FEB, FBCYL} and {s for s, _ in calls} == set(HEAVY)


def test_new_code_in_one_section_recomputes_only_that_section_in_every_competition_issue_783(handler, tmp_path, calls, monkeypatch):
    """The point of #783: the code of ONE exporter changed, the other sections (and the 25 minutes they cost) are not computed again."""
    _publish(handler, tmp_path)
    calls[:] = []
    _with_versions(monkeypatch, inout="another-version")
    _publish(handler, tmp_path)
    assert {s for s, _ in calls} == {"inout"} and {c for _, c in calls} == {FEB, FBCYL}


def test_a_section_the_memory_never_saw_is_computed_and_the_others_are_not_issue_783(handler, tmp_path, calls, monkeypatch):
    """A section added to the publication: the memory of the previous one has no version for it."""
    _publish(handler, tmp_path)
    memory = json.loads((tmp_path / "build-cache.json").read_text(encoding="utf-8"))
    for entry in memory["competitions"].values():
        entry["versions"].pop("lineups")
        entry["sections"] = [x for x in entry["sections"] if x != "lineups"]
    (tmp_path / "build-cache.json").write_text(json.dumps(memory), encoding="utf-8")
    calls[:] = []
    _publish(handler, tmp_path)
    assert {s for s, _ in calls} == {"lineups"}


def test_a_changed_game_recomputes_every_section_whatever_their_versions(handler, tmp_path, calls):
    _publish(handler, tmp_path)
    calls[:] = []
    handler.connection.client["BASKETBALL"][FEB].delete_one({})
    _publish(handler, tmp_path)
    assert {s for s, c in calls if c == FEB} >= {"matches", "lineups", "inout"}


def test_the_memory_of_the_old_format_one_version_for_all_the_code_is_not_trusted(handler, tmp_path, calls):
    _publish(handler, tmp_path)
    memory = json.loads((tmp_path / "build-cache.json").read_text(encoding="utf-8"))
    old = {"code": "abc", "competitions": {k: {"fingerprint": v["fingerprint"], "sections": v["sections"]} for k, v in memory["competitions"].items()}}
    (tmp_path / "build-cache.json").write_text(json.dumps(old), encoding="utf-8")
    calls[:] = []
    _publish(handler, tmp_path)
    assert {c for _, c in calls} == {FEB, FBCYL}


def test_raising_the_epoch_forces_everything_to_be_computed_again(handler, tmp_path, calls, monkeypatch):
    _publish(handler, tmp_path)
    calls[:] = []
    monkeypatch.setattr(build_cache, "EPOCH", build_cache.EPOCH + 1)
    _publish(handler, tmp_path)
    assert {c for _, c in calls} == {FEB, FBCYL}


@pytest.mark.parametrize("damage", ["missing", "corrupt", "wrong-shape"])
def test_a_missing_or_unreadable_memory_computes_again_and_publishes_the_same_content(handler, tmp_path, calls, damage):
    first = _publish(handler, tmp_path)
    memory = tmp_path / "build-cache.json"
    assert memory.is_file()
    {"missing": lambda: memory.unlink(), "corrupt": lambda: memory.write_text("{not json", encoding="utf-8"), "wrong-shape": lambda: memory.write_text("[1, 2]", encoding="utf-8")}[damage]()
    calls[:] = []
    again = _publish(handler, tmp_path)
    assert {c for _, c in calls} == {FEB, FBCYL}
    assert [(e["collection"], e["sha256"]) for s in ["rows", *HEAVY] for e in again.get(s, [])] == [(e["collection"], e["sha256"]) for s in ["rows", *HEAVY] for e in first.get(s, [])]


def test_a_file_that_is_gone_is_made_again_even_if_nothing_changed(handler, tmp_path, calls):
    first = _publish(handler, tmp_path)
    gone = first["matches"][0]
    (tmp_path / gone["file"]).unlink()
    calls[:] = []
    _publish(handler, tmp_path)
    assert (tmp_path / gone["file"]).is_file() and gone["collection"] in {c for _, c in calls}


def test_a_section_that_had_nothing_to_publish_is_not_asked_again(handler, tmp_path, calls):
    first = _publish(handler, tmp_path)
    empty = [s for s in HEAVY if not any(e["collection"] == FBCYL for e in first.get(s, []))]
    assert empty, "the fixture FBCYL competition has sections with nothing to publish (IN/OUT is left to the API)"
    calls[:] = []
    _publish(handler, tmp_path)
    assert calls == []


def test_the_memory_is_not_a_readable_copy_of_anything_it_only_has_hashes(handler, tmp_path):
    _publish(handler, tmp_path)
    memory = json.loads((tmp_path / "build-cache.json").read_text(encoding="utf-8"))
    assert set(memory) == {"epoch", "competitions"} and set(memory["competitions"]) == {FEB, FBCYL}
    assert all(set(v) == {"fingerprint", "sections", "versions"} for v in memory["competitions"].values())
    assert all(set(v["versions"]) == set(HEAVY) for v in memory["competitions"].values()), "one version per section, hashes only"


def test_a_partial_refresh_keeps_the_memory_of_the_competitions_it_did_not_touch(handler, tmp_path, calls):
    _publish(handler, tmp_path)
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB], keep_others=True)
    calls[:] = []
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL])
    assert calls == []


def test_the_log_also_says_what_the_rows_and_the_reports_of_each_competition_cost_issue_783(handler, tmp_path):
    """Not everything is a section: the rows and the reports (scouting, images) are computed on every publication; the next saving needs to know what they cost."""
    seen = []
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL], on_section=lambda name, section, seconds, reused: seen.append((name, section)))
    for name in (FEB, FBCYL):
        assert (name, "rows") in seen and (name, "reports") in seen
        assert seen.index((name, "rows")) < seen.index((name, "derived")) < seen.index((name, "reports"))
