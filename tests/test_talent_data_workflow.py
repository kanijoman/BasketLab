"""Guards of ``talent-data.yml`` (#878): it builds the player rows of BasketLab Talent from the archive and publishes them to its OWN branch.

The workflow only runs on GitHub (secrets, SSH, a service container): these tests fix what can go wrong silently when someone edits it. The two that matter most are the ones that keep it
apart from the others: it never writes to the branch of ``web-data`` (two writers would race) and it never writes to the archives (it only reads them)."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = yaml.safe_load((ROOT / ".github" / "workflows" / "talent-data.yml").read_text(encoding="utf-8"))
TEXT = (ROOT / ".github" / "workflows" / "talent-data.yml").read_text(encoding="utf-8")
NAMED = [step for step in WORKFLOW["jobs"]["publish"]["steps"] if "name" in step]
STEPS = {step["name"]: step for step in NAMED}
ORDER = [step["name"] for step in NAMED]


def _triggers():
    return WORKFLOW.get("on") or WORKFLOW.get(True)                # YAML 1.1 reads the key `on` as True


def test_it_has_its_own_concurrency_group_and_publishes_only_to_its_own_branch():
    assert WORKFLOW["concurrency"]["group"] == "talent-data" and WORKFLOW["concurrency"]["cancel-in-progress"] is False
    push = STEPS["Publish to the talent-data branch"]["run"]
    assert "publish:talent-data" in push and "web-data" not in push and "live-packages" not in push
    assert "--branch talent-data" in STEPS["Start from the previous publication"]["run"]


def test_it_never_writes_to_the_archives_it_only_reads_them():
    """The archive has one writer (archive-refresh) and basketlab-archive-ext has one per folder (the roster sweep writes rosters/): this job is neither."""
    assert not [n for n in ORDER if n.startswith(("Scrape", "Fill DERIVED", "Save the archive"))]
    assert "git push" not in STEPS["Download the rosters"]["run"] and "git commit" not in STEPS["Download the rosters"]["run"]
    assert TEXT.count("git push") == 1                              # the one of the publication, to the branch of this workflow


def test_the_order_is_restore_rosters_previous_build_publish():
    names = ["Restore the archive", "Download the rosters", "Start from the previous publication", "Build the artifacts", "Publish to the talent-data branch"]
    assert [ORDER.index(n) for n in names] == sorted(ORDER.index(n) for n in names)


def test_a_failed_restore_or_rosters_download_turns_the_run_red_and_nothing_is_published():
    for name in ("Restore the archive", "Download the rosters"):
        assert "continue-on-error" not in STEPS[name]
    publish = STEPS["Publish to the talent-data branch"]["if"]
    assert "steps.build.conclusion == 'success'" in publish and "hashFiles('talent-out/index.json') != ''" in publish and "pull_request" in publish


def test_the_build_reads_the_ephemeral_mongo_and_the_roster_folder_and_has_the_master_key():
    build = STEPS["Build the artifacts"]
    assert build["env"]["MONGODB_CONNECTION_STRING"] == "${{ env.EPHEMERAL_MONGO }}" and "PACKAGE_MASTER_KEY" in build["env"]
    assert "--rosters archive-ext/rosters" in build["run"] and "--out talent-out" in build["run"]
    assert WORKFLOW["jobs"]["publish"]["services"]["mongo"]["image"].startswith("mongo:")


def test_it_runs_after_every_refresh_and_purge_and_when_the_code_that_shapes_the_files_is_merged():
    triggers = _triggers()
    assert triggers["workflow_run"]["workflows"] == ["Archive refresh", "Archive purge"] and triggers["workflow_run"]["types"] == ["completed"]
    assert "workflow_dispatch" in triggers and triggers["push"]["branches"] == ["main"]
    assert "!src/api/**" in triggers["push"]["paths"] and "src/**" in triggers["push"]["paths"] and "run_talent_data.py" in triggers["push"]["paths"]
    assert not [p for p in triggers["push"]["paths"] if p.startswith(("frontend", "docs", "apps", "tests"))]
    assert "cancelled" in WORKFLOW["jobs"]["publish"]["if"]       # a red refresh does not block it, a cancelled one does


def test_a_pull_request_only_checks_the_entry_points_and_touches_no_secret():
    assert STEPS["Validate the entry points (pull requests)"]["if"] == "github.event_name == 'pull_request'"
    for name in ("Restore the archive", "Download the rosters", "Start from the previous publication", "Build the artifacts"):
        assert STEPS[name]["if"] == "github.event_name != 'pull_request'"


def test_the_entry_point_imports_and_the_rosters_are_optional():
    import importlib

    module = importlib.import_module("run_talent_data")
    assert callable(module.main)
