"""Guards of ``talent-rosters.yml`` (#905): the daily roster sweep is the ONLY writer of ``rosters/`` in ``basketlab-archive-ext`` and a reader of everything else.

The workflow only runs on GitHub (secrets, SSH, a service container): these tests fix what can go wrong silently when someone edits it. A second writer on the folder would race, a write to the
main archive would break the rule that ``archive-refresh.yml`` is its only writer, and a push to a branch of this repository would be a surprise."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / ".github" / "workflows" / "talent-rosters.yml").read_text(encoding="utf-8")
WORKFLOW = yaml.safe_load(TEXT)
NAMED = [step for step in WORKFLOW["jobs"]["sweep"]["steps"] if "name" in step]
STEPS = {step["name"]: step for step in NAMED}
ORDER = [step["name"] for step in NAMED]


def _triggers():
    return WORKFLOW.get("on") or WORKFLOW.get(True)                # YAML 1.1 reads the key `on` as True


def test_it_runs_every_day_and_by_hand_with_a_season_filter_and_a_budget():
    triggers = _triggers()
    assert len(triggers["schedule"]) == 1 and triggers["schedule"][0]["cron"].split()[2:] == ["*", "*", "*"]
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"seasons", "budget"}
    assert "run_roster_sweep.py" in triggers["pull_request"]["paths"] and "push" not in triggers      # nothing runs on a merge: the sweep is a daily job, not a build of the code


def test_it_has_its_own_concurrency_group_and_never_cancels_a_run_half_way():
    assert WORKFLOW["concurrency"]["group"] == "talent-rosters" and WORKFLOW["concurrency"]["cancel-in-progress"] is False


def test_the_only_thing_it_pushes_is_rosters_to_the_archive_ext_and_the_token_of_the_repository_cannot_write():
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert TEXT.count("git push") == 1 and "git push -q origin HEAD" in STEPS["Save the rosters"]["run"]
    assert "git add rosters" in STEPS["Save the rosters"]["run"] and "git add -A" not in STEPS["Save the rosters"]["run"]
    assert "x-access-token" not in TEXT                                  # no push with the token of this repository: web-data and talent-data are not touched here


def test_it_reads_the_main_archive_and_never_writes_it():
    assert STEPS["Restore the archive"]["uses"] == "./.github/actions/restore-archive"
    assert not [n for n in ORDER if n.startswith(("Scrape", "Fill DERIVED", "Save the archive"))]
    assert "ARCHIVE_DEPLOY_KEY" not in STEPS["Save the rosters"].get("env", {}) and "ARCHIVE_DEPLOY_KEY" not in STEPS["Download the rosters"]["env"]


def test_the_order_is_restore_download_sweep_save():
    names = ["Restore the archive", "Download the rosters", "Sweep the rosters", "Save the rosters"]
    assert [ORDER.index(n) for n in names] == sorted(ORDER.index(n) for n in names)


def test_what_did_answer_is_saved_even_if_the_sweep_ended_red_and_nothing_changed_is_no_commit():
    save = STEPS["Save the rosters"]
    assert "!cancelled()" in save["if"] and "pull_request" in save["if"]
    assert "git diff --cached --quiet" in save["run"] and "exit 0" in save["run"]


def test_a_failed_restore_or_clone_stops_the_run_and_a_pull_request_touches_no_secret():
    for name in ("Restore the archive", "Download the rosters"):
        assert "continue-on-error" not in STEPS[name] and STEPS[name]["if"] == "github.event_name != 'pull_request'"
    assert STEPS["Validate the entry points (pull requests)"]["if"] == "github.event_name == 'pull_request'"


def test_the_entry_point_imports_and_has_a_default_budget():
    import importlib

    module = importlib.import_module("run_roster_sweep")
    assert callable(module.main) and module.DEFAULT_BUDGET > 0
