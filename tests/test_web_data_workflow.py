"""Guards of ``web-data.yml`` (#646, #724): the job builds the web data from the archive, so the order and conditions of its steps are part of the contract.

Since #724 it no longer scrapes or saves the archive (``archive-refresh.yml`` does, see ``test_archive_refresh_workflow.py``): it restores it and builds from it.
The workflow itself only runs on GitHub (secrets, SSH, a service container): these tests fix what can go wrong silently when someone edits it.
"""
from pathlib import Path

import yaml

WORKFLOW = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github" / "workflows" / "web-data.yml").read_text(encoding="utf-8"))
NAMED = [step for step in WORKFLOW["jobs"]["publish"]["steps"] if "name" in step]      # checkout and setup-python have none
STEPS = {step["name"]: step for step in NAMED}
ORDER = [step["name"] for step in NAMED]


def test_a_failed_download_or_restore_stops_everything_that_would_use_the_empty_database():
    assert STEPS["Restore the archive"]["uses"] == "./.github/actions/restore-archive" and STEPS["Restore the archive"]["if"] == "github.event_name != 'pull_request'"
    assert "continue-on-error" not in STEPS["Restore the archive"]       # a red restore must turn the run red


def test_the_order_is_download_restore_build_publish():
    names = ["Restore the archive", "Build the artifacts", "Publish to the web-data branch"]
    assert [ORDER.index(n) for n in names] == sorted(ORDER.index(n) for n in names)


def test_it_neither_scrapes_nor_saves_the_archive():
    assert not [n for n in ORDER if n.startswith(("Scrape", "Fill DERIVED", "Save the archive"))]


def test_the_build_reads_the_ephemeral_mongo_and_never_atlas():
    build = STEPS["Build the artifacts"]["env"]["MONGODB_CONNECTION_STRING"]
    assert build == "${{ env.EPHEMERAL_MONGO }}"


def test_the_ephemeral_mongo_is_a_service_container_and_the_build_reads_it():
    assert WORKFLOW["jobs"]["publish"]["services"]["mongo"]["image"].startswith("mongo:")
    assert WORKFLOW["jobs"]["publish"]["env"]["EPHEMERAL_MONGO"] == "mongodb://localhost:27017"      # the action restores into the default of its `mongo-uri`


# ---- issue #781: a change that shapes the published files publishes them when it is merged, not when somebody remembers --------
def _triggers():
    return WORKFLOW.get("on") or WORKFLOW.get(True)               # YAML 1.1 reads the key `on` as True


def test_a_push_to_main_publishes_when_the_code_that_shapes_the_files_changes():
    push = _triggers()["push"]
    assert push["branches"] == ["main"]
    paths = push["paths"]
    assert "src/**" in paths and "run_web_data.py" in paths and "config/competitions.json" in paths
    assert "!src/api/**" in paths, "the routers do not shape a published file (build_cache._OUT_OF_THE_BUILD): changing one must not rebuild everything"


def test_the_push_trigger_does_not_fire_for_the_web_or_the_docs():
    paths = _triggers()["push"]["paths"]
    assert not [p for p in paths if p.startswith(("frontend", "docs", "apps", "tests"))]


def test_the_paths_of_the_push_are_the_ones_that_change_the_code_version_of_the_build_cache():
    """If a new source folder stopped counting for the versions of the sections (``build_cache._OUT_OF_THE_BUILD``), the push trigger must follow."""
    from src.local_data.build_cache import _OUT_OF_THE_BUILD

    assert {p[1:].split("/")[1] for p in _triggers()["push"]["paths"] if p.startswith("!src/")} == set(_OUT_OF_THE_BUILD)


def test_a_push_run_publishes_like_a_manual_one_and_runs_one_at_a_time():
    assert STEPS["Build the artifacts"]["if"] == "github.event_name != 'pull_request'"      # push is not a pull request: it builds and publishes
    assert WORKFLOW["concurrency"] == {"group": "web-data", "cancel-in-progress": False}


# ---- issue #789: a failed build must not publish what it had computed (run 42212803334, 06/11/2026, pushed 23 orphan files to the branch) ----------
def test_a_failed_build_publishes_nothing_regression():
    """The publish step ran with ``!cancelled()`` after a red build and pushed the files of the competitions it had finished (the manifest, written last, stayed the old one)."""
    build, publish = STEPS["Build the artifacts"], STEPS["Publish to the web-data branch"]
    assert build.get("id") == "build" and "continue-on-error" not in build
    assert "steps.build.conclusion == 'success'" in publish["if"], "publish only when the build succeeded"
    assert "github.event_name != 'pull_request'" in publish["if"]


def test_the_step_that_publishes_is_after_the_build_and_nothing_between_can_swallow_its_failure():
    between = ORDER[ORDER.index("Build the artifacts") + 1:ORDER.index("Publish to the web-data branch")]
    assert between == [] and "continue-on-error" not in STEPS["Build the artifacts"]
