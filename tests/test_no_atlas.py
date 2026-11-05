"""BasketLab has no dependency on Atlas (issue #724, steps 5 and 6): the private archive is the only source of the games.

Step 5 retired the refresh of Atlas and its fallback in the readers; step 6 retires the rest: the read-only comparison (it served its purpose: the archive held everything Atlas held),
the secrets, the name of the module that still said «atlas» and the messages that sent the operator to the Atlas console. These guards keep it that way: no file of the repository
(the dated reports of ``docs/evaluaciones/`` and the docs that record the decision aside) names a secret, a script, a module or a workflow of Atlas, and the planners of both recorders
wait for the workflow that exists.
"""
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
READERS = ("web-data.yml", "live-packages.yml", "rule-evaluation.yml")
HISTORY = ("docs/evaluaciones/",)
SKIP = {"tests/test_no_atlas.py", ".test_durations"}
# what only Atlas had: a secret, a script, a module, a workflow, a connection string. The docs may quote them to record what was retired; code, workflows and configuration may not.
INTEGRATION = re.compile(r"ATLAS_(?:READ|WRITE)_URI|atlas[_-]refresh|atlas[_-]compare|\"Atlas refresh\"|Atlas compare")
DOCS = {"CLAUDE.md", "README.md", "docs/ARCHITECTURE.md", "docs/OPERATIONS.md", "docs/ROADMAP.md", "docs/TESTING.md", "docs/LIVE.md", "docs/UI.md"}


def _load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _steps(name):
    return next(iter(_load(name)["jobs"].values()))["steps"]


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    return [p for p in out if p and not p.endswith(("package-lock.json", ".png", ".jpg", ".ico", ".gz", ".bpkg", ".bpkgz", ".pdf", ".woff2", ".jar"))]


@pytest.mark.parametrize("path", ["config/atlas_refresh.json", "run_atlas_refresh.py", ".github/workflows/atlas-refresh.yml", ".github/workflows/atlas-compare.yml", "run_atlas_compare.py",
                                  "src/local_data/atlas_compare.py", "src/services/atlas_refresh.py", "tests/test_atlas_compare.py", "tests/test_run_atlas_compare.py", "tests/test_atlas_refresh.py"])
def test_what_only_atlas_had_is_gone(path):
    assert not (ROOT / path).exists(), path


def test_the_refresh_lives_in_a_module_that_says_what_it_does_and_reads_the_catalogue_by_default():
    from src.services import competition_refresh

    assert competition_refresh.DEFAULT_CONFIG == "config/competitions.json" and (ROOT / competition_refresh.DEFAULT_CONFIG).exists()
    assert (ROOT / "run_refresh.py").exists()


def test_no_file_of_the_repository_names_a_secret_script_module_or_workflow_of_atlas():
    found = []
    for path in _tracked():
        if path in SKIP or path in DOCS or path.startswith(HISTORY) or not (ROOT / path).is_file():
            continue
        text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        found += [f"{path}: {m.group(0)}" for m in INTEGRATION.finditer(text)][:2]
    assert not found, found


def test_no_workflow_reads_a_secret_of_atlas():
    assert not [p.name for p in WORKFLOWS.glob("*.yml") if "secrets.ATLAS" in p.read_text(encoding="utf-8")]


def test_the_refresh_entry_point_is_the_one_of_the_archive_workflow():
    run = " ".join(s.get("run", "") for s in _steps("archive-refresh.yml"))
    assert "run_refresh.py --config config/competitions.json" in run and "atlas" not in run.lower()


@pytest.mark.parametrize("name", READERS)
def test_a_reader_has_no_fallback_to_atlas_and_always_restores_the_archive(name):
    steps = _steps(name)
    assert not any(s.get("id") == "source" for s in steps), "the archive is not optional any more"
    restore = [s for s in steps if "restore-archive" in str(s.get("uses", "")) or "run_archive.py pull" in s.get("run", "")]
    assert len(restore) == 1 and "ARCHIVE_DEPLOY_KEY" in str(restore[0])
    assert "if" not in restore[0] or "pull_request" in restore[0]["if"]     # pull requests only validate the entry points


@pytest.mark.parametrize("name", ["feb-record.yml", "fbcyl-record.yml"])
def test_the_planner_of_each_recorder_runs_after_the_archive_refresh_that_exists(name):
    """Regression: ``fbcyl-record.yml`` kept waiting for «Atlas refresh», a workflow that no longer exists, so after every refresh it was never planned (only the schedule did)."""
    triggers = _load(name)[True]
    assert triggers["workflow_run"]["workflows"] == ["Archive refresh"]
    assert "Archive refresh" == _load("archive-refresh.yml")["name"]


def test_the_crests_script_reads_the_catalogue_not_the_deleted_file():
    script = (ROOT / "apps" / "live-android" / "scripts" / "fetch-logos.mjs").read_text(encoding="utf-8")
    assert "config/competitions.json" in script and "atlas_refresh" not in script


def test_the_hints_for_a_database_that_does_not_answer_do_not_send_the_operator_to_a_console_of_atlas():
    from src.database.db_health import HINTS

    assert not [kind for kind, hint in HINTS.items() if "Atlas" in hint], HINTS
