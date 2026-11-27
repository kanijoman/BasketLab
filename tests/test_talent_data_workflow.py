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


def test_it_runs_after_every_refresh_purge_and_roster_sweep_and_when_the_code_that_shapes_the_files_is_merged():
    triggers = _triggers()
    assert triggers["workflow_run"]["workflows"] == ["Archive refresh", "Archive purge", "Talent rosters"] and triggers["workflow_run"]["types"] == ["completed"]
    assert "workflow_dispatch" in triggers and triggers["push"]["branches"] == ["main"]
    assert "src/**" in triggers["push"]["paths"] and "run_talent_data.py" in triggers["push"]["paths"]
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


def test_it_links_the_external_players_before_the_build_and_the_build_reads_them_regression_979():
    """#979: ``links/fiba.json`` was written by nobody and read by nobody. The workflow regenerates it from the archives it already downloaded (a derived file: it is NOT written back to
    basketlab-archive-ext, which keeps one writer per folder) and the build gives the linked players' bio to the FEB rows."""
    assert ORDER.index("Download the rosters") < ORDER.index("Link the external players") < ORDER.index("Build the artifacts")
    link = STEPS["Link the external players"]
    assert "run_identity_links.py --ext archive-ext --source fiba" in link["run"] and "git push" not in link["run"] and "git commit" not in link["run"]
    assert "pull_request" in link["if"]
    assert "--ext archive-ext" in STEPS["Build the artifacts"]["run"]
    assert "run_identity_links.py" in _triggers()["push"]["paths"]


def test_a_source_with_no_games_yet_does_not_turn_the_run_red_but_a_failing_link_does():
    run = STEPS["Link the external players"]["run"]
    assert "[ -d archive-ext/fiba ]" in run and "||" not in run.split("python run_identity_links.py")[1].splitlines()[0]


def test_it_links_the_fbcyl_players_after_the_archive_and_the_rosters_and_before_the_build_996():
    """#996: ``links/fbcyl.json`` (#978) was consumed by nobody. It needs the restored archive (``archive``), the rosters of FEB (``archive-ext/rosters``) and the catalogue, so it goes after both downloads; it
    is a derived file of the run (never written back) and a failing command turns the run red."""
    assert ORDER.index("Restore the archive") < ORDER.index("Download the rosters") < ORDER.index("Link the FBCYL players") < ORDER.index("Build the artifacts")
    step = STEPS["Link the FBCYL players"]
    assert "run_identity_links.py --ext archive-ext --source fbcyl --archive archive" in step["run"]
    assert "git push" not in step["run"] and "git commit" not in step["run"] and "||" not in step["run"] and "pull_request" in step["if"]


def test_it_links_the_acb_players_like_the_fiba_ones_with_no_games_yet_not_turning_the_run_red_886():
    """#886: ACB has birth, height and position for its players, so they are linked to FEB (``links/acb.json``) and lend it to the build like FIBA's. A source with no games yet is not an error; a failing
    link is. A derived file of the run: it is not written back to the archive."""
    assert ORDER.index("Download the rosters") < ORDER.index("Link the ACB players") < ORDER.index("Build the artifacts")
    link = STEPS["Link the ACB players"]
    run = link["run"]
    assert "run_identity_links.py --ext archive-ext --source acb" in run and "[ -d archive-ext/acb ]" in run and "git push" not in run and "git commit" not in run
    assert "||" not in run.split("python run_identity_links.py")[1].splitlines()[0] and "pull_request" in link["if"]
