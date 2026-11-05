"""Atlas is no longer written or read by the scheduled jobs (issue #724, step 5): the archive is the only source of the games.

Before: ``atlas-refresh.yml`` kept writing Atlas three times a day next to ``archive-refresh.yml``, and ``web-data``, ``live-packages`` and ``rule-evaluation`` fell back to
Atlas when the archive key was missing, so a lost secret would silently serve stale data. The only workflow that still names Atlas is ``atlas-compare.yml`` (read only, kept
for the final comparison before the last copy, step 6).
"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
READERS = ("web-data.yml", "live-packages.yml", "rule-evaluation.yml")


def _load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _steps(name):
    return next(iter(_load(name)["jobs"].values()))["steps"]


@pytest.mark.parametrize("path", ["config/atlas_refresh.json", "run_atlas_refresh.py", ".github/workflows/atlas-refresh.yml"])
def test_the_atlas_refresh_is_gone(path):
    assert not (ROOT / path).exists(), path


def test_the_refresh_entry_point_is_the_one_of_the_archive_workflow():
    assert (ROOT / "run_refresh.py").exists()
    run = " ".join(s.get("run", "") for s in _steps("archive-refresh.yml"))
    assert "run_refresh.py --config config/competitions.json" in run and "run_atlas_refresh" not in run


def test_only_the_comparison_names_atlas_secrets():
    named = sorted(p.name for p in WORKFLOWS.glob("*.yml") if "secrets.ATLAS" in p.read_text(encoding="utf-8"))
    assert named == ["atlas-compare.yml"]


@pytest.mark.parametrize("name", READERS)
def test_a_reader_has_no_fallback_to_atlas_and_always_restores_the_archive(name):
    steps = _steps(name)
    assert not any(s.get("id") == "source" for s in steps), "the archive is not optional any more"
    restore = [s for s in steps if "restore-archive" in str(s.get("uses", "")) or "run_archive.py pull" in s.get("run", "")]
    assert len(restore) == 1 and "ARCHIVE_DEPLOY_KEY" in str(restore[0])
    assert "if" not in restore[0] or "pull_request" in restore[0]["if"]     # pull requests only validate the entry points


def test_the_planner_of_the_recorder_runs_after_the_archive_refresh():
    triggers = _load("feb-record.yml")[True]
    assert triggers["workflow_run"]["workflows"] == ["Archive refresh"]


def test_the_crests_script_reads_the_catalogue_not_the_deleted_file():
    script = (ROOT / "apps" / "live-android" / "scripts" / "fetch-logos.mjs").read_text(encoding="utf-8")
    assert "config/competitions.json" in script and "atlas_refresh" not in script
