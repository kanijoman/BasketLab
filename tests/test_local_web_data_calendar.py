"""The calendar in the publication (#842): a sealed ``calendar/`` file per competition of the newest season, read on EVERY publication (a calendar changes without a new game, so it is not part of
the build cache) and kept as it was when the federation cannot be read. Nothing is published without a source (a library call or a test never reaches for the network)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import games  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.web_data import UNCACHED, publish_web_data  # noqa: E402
from tests.test_local_calendar_export import Fake, _fbcyl_rows, _match  # noqa: E402,F401
from tests.test_local_web_data import FBCYL, FEB, MASTER, cheap_lineups, handler  # noqa: E402,F401  (fixtures)

GROUPS = {FBCYL: "7298"}


def _calendar(extra=()):
    return [_match("9001", "result", 1, "101", "102", score="70-60"), _match("9101", "scheduled", 2, "103", "104", start="2026-12-05T18:00"), *extra]


def _publish(handler, out, source, names=(FEB, FBCYL), **kwargs):
    return publish_web_data(handler, out, ScopedSealer(MASTER), list(names), calendar_source=source, fbcyl_groups=GROUPS, **kwargs)


def _entries(manifest):
    return {e["collection"]: e for e in manifest["calendar"]}


def _open(out, entry):
    envelope = json.loads((out / entry["file"]).read_text(encoding="utf-8"))
    scope = f"competicion:{entry['collection']}"
    return json.loads(open_sealed(envelope, entry["wraps"], {scope: scope_key(MASTER, scope)}))


def test_the_calendar_is_not_part_of_the_build_cache():
    assert "calendar" in UNCACHED and "derived" in UNCACHED


def test_without_a_source_no_calendar_is_published(handler, tmp_path):
    manifest = publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL])
    assert manifest["calendar"] == [] and not (tmp_path / "calendar").exists()


def test_each_competition_of_the_newest_season_gets_its_calendar_sealed_for_the_competition(handler, tmp_path):
    manifest = _publish(handler, tmp_path, Fake(feb=_calendar(), rows=_fbcyl_rows()))
    entries = _entries(manifest)
    assert set(entries) == {FEB, FBCYL} and entries[FEB]["league"] == "feb" and entries[FBCYL]["league"] == "fbcyl"
    assert entries[FEB]["games"] == 2 and entries[FEB]["file"].startswith("calendar/") and {w["scope"] for w in entries[FEB]["wraps"]} >= {f"competicion:{FEB}"}
    assert _open(tmp_path, entries[FEB])["matches"][1]["start"] == "2026-12-05T18:00" and _open(tmp_path, entries[FBCYL])["games"] == 156


def test_an_unchanged_calendar_keeps_its_bytes_and_a_changed_one_writes_a_new_file_and_removes_the_old(handler, tmp_path):
    source = Fake(feb=_calendar(), rows=_fbcyl_rows())
    first = _entries(_publish(handler, tmp_path, source))
    before = {e["file"]: (tmp_path / e["file"]).read_bytes() for e in first.values()}
    second = _entries(_publish(handler, tmp_path, source))
    assert {e["file"]: (tmp_path / e["file"]).read_bytes() for e in second.values()} == before
    changed = _entries(_publish(handler, tmp_path, Fake(feb=_calendar([_match("9102", "scheduled", 3, "101", "103", start="2026-12-12T18:00")]), rows=_fbcyl_rows())))
    assert changed[FEB]["file"] != first[FEB]["file"] and changed[FBCYL]["file"] == first[FBCYL]["file"]
    assert not (tmp_path / first[FEB]["file"]).exists() and (tmp_path / changed[FEB]["file"]).is_file()


def test_a_calendar_that_cannot_be_read_keeps_the_previous_one_and_a_competition_that_never_had_one_gets_none(handler, tmp_path):
    first = _entries(_publish(handler, tmp_path, Fake(feb=_calendar(), rows=_fbcyl_rows())))
    down = Fake(feb=RuntimeError("down"), rows=RuntimeError("down"))
    kept = _entries(_publish(handler, tmp_path, down))
    assert kept == first and all((tmp_path / e["file"]).is_file() for e in kept.values())
    fresh = tmp_path / "fresh"
    assert _publish(handler, fresh, down)["calendar"] == []


def test_a_partial_refresh_keeps_the_calendars_of_the_competitions_it_does_not_publish(handler, tmp_path):
    first = _entries(_publish(handler, tmp_path, Fake(feb=_calendar(), rows=_fbcyl_rows())))
    only_feb = _entries(_publish(handler, tmp_path, Fake(feb=_calendar(), rows=RuntimeError("not asked")), names=[FEB], keep_others=True))
    assert only_feb == first


def test_a_competition_that_is_not_of_the_newest_season_gets_no_calendar(handler, tmp_path):
    old = "L_F_-2_2024_2025_Liga_Regular_B"
    handler.connection.client["BASKETBALL"][old].insert_many(games.build_games())
    manifest = _publish(handler, tmp_path, Fake(feb=_calendar(), rows=_fbcyl_rows()), names=[FEB, old])
    assert set(_entries(manifest)) == {FEB}


def test_asking_for_the_calendar_is_reported_as_a_section(handler, tmp_path):
    seen = []
    _publish(handler, tmp_path, Fake(feb=_calendar(), rows=_fbcyl_rows()), names=[FEB], on_section=lambda name, section, seconds, reused: seen.append((name, section)))
    assert (FEB, "calendar") in seen
