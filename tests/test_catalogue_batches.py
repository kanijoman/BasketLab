"""Loading the history in batches (#876, epic #872): ``active: true`` is turned on one batch of seasons at a time, never by hand on forty entries.

A batch is the history and youth entries of FEB (``packages: false``) of some seasons, without Tercera FEB (``--only``/``--exclude`` pick competitions: it has its own batches, about 1,770 games a season).
It never touches the current season (the entries with packages), FBCYL or what is already active, and a second run changes nothing. Real catalogue, copied to a temporary file.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.catalogue_batches import activate_seasons  # noqa: E402
from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TERCERA = "TERCERA FEB"


@pytest.fixture()
def catalogue(tmp_path):
    """The real catalogue as it was before any batch: the history and youth of 2020 to 2023 paused (the real file moves on with every batch, and these tests must not)."""
    path = tmp_path / "competitions.json"
    shutil.copy(ROOT / DEFAULT_CATALOGUE, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["competitions"]:
        if entry.get("league", "feb") == "feb" and not entry.get("packages", True) and entry["season_value"] in ("2020", "2021", "2022", "2023"):
            entry["active"] = False
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _entries(path):
    return json.loads(path.read_text(encoding="utf-8"))["competitions"]


def _active(path, season, only_history=True):
    return {e["competition"] for e in _entries(path) if e.get("league", "feb") == "feb" and e["season_value"] == season and e["active"] and (not only_history or not e.get("packages", True))}


def test_a_batch_turns_on_the_history_and_youth_of_those_seasons_without_tercera(catalogue):
    before = {(e["competition"], e["season_value"]): e["active"] for e in _entries(catalogue)}
    report = activate_seasons(catalogue, ["2023", "2022"], exclude=[TERCERA])
    assert report["activated"] == 22 and report["by_season"] == {"2023": 11, "2022": 11}
    for season in ("2023", "2022"):
        active = _active(catalogue, season)
        assert TERCERA not in active and len(active) == 11
        assert {"LF ENDESA", "PRIMERA FEB", "SEGUNDA FEB", "L.F.-2", "LF CHALLENGE", "C ESP CLUBES JR FEM", "CE SSAA Cadete Mas."} <= active
    changed = {(e["competition"], e["season_value"]) for e in _entries(catalogue) if e["active"] != before[(e["competition"], e["season_value"])]}
    assert {s for _, s in changed} == {"2023", "2022"} and len(changed) == 22                    # nothing else moved


def test_it_never_touches_the_current_season_the_seasons_already_active_fbcyl_or_other_seasons(catalogue):
    before = _entries(catalogue)
    activate_seasons(catalogue, ["2023"], exclude=[TERCERA])
    after = _entries(catalogue)
    for old, new in zip(before, after):
        if old["season_value"] != "2023" or old.get("league", "feb") != "feb" or old.get("packages", True) or old["competition"] == TERCERA:
            assert old == new
    assert not any(e["active"] for e in after if e.get("league", "feb") == "feb" and e["competition"] == TERCERA and not e.get("packages", True))      # the 2026 one has packages: it is the current season


def test_tercera_has_its_own_batch(catalogue):
    report = activate_seasons(catalogue, ["2025"], only=[TERCERA])
    assert report["activated"] == 1 and _active(catalogue, "2025") >= {TERCERA}
    assert TERCERA not in _active(catalogue, "2024")


def test_a_second_run_changes_nothing_not_even_a_byte(catalogue):
    activate_seasons(catalogue, ["2023"], exclude=[TERCERA])
    once = catalogue.read_bytes()
    again = activate_seasons(catalogue, ["2023"], exclude=[TERCERA])
    assert again == {"activated": 0, "by_season": {}} and catalogue.read_bytes() == once


def test_the_result_is_still_a_valid_catalogue_and_the_file_keeps_its_format(catalogue):
    original = catalogue.read_text(encoding="utf-8")
    activate_seasons(catalogue, ["2023"], exclude=[TERCERA])
    text = catalogue.read_text(encoding="utf-8")
    assert text.endswith("\n") and text == json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n"
    assert len(load_catalogue(catalogue)) == len(load_catalogue(ROOT / DEFAULT_CATALOGUE))
    assert text != original


def test_a_season_with_no_entries_or_nothing_to_turn_on_activates_nothing(catalogue):
    assert activate_seasons(catalogue, ["1999"]) == {"activated": 0, "by_season": {}}
    assert activate_seasons(catalogue, ["2025"], exclude=[TERCERA]) == {"activated": 0, "by_season": {}}          # already active


def test_fbcyl_seasons_are_turned_on_the_same_way_when_asked(catalogue):
    report = activate_seasons(catalogue, ["2025"], league="fbcyl")
    assert report["activated"] == 67 and all(e["active"] for e in _entries(catalogue) if e.get("league") == "fbcyl" and e["season_value"] == "2025")
    assert not any(e["active"] for e in _entries(catalogue) if e.get("league") == "fbcyl" and e["season_value"] == "2024")
