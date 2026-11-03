"""The refresh of the archive without Atlas (issue #724, step 3): ONE workflow brings the games up to date and is the ONLY writer of the private archive.

Before, ``web-data.yml`` did both things (scraped into its ephemeral Mongo, built the web data for an hour and saved the archive at the end) and was triggered by the Atlas refresh. A
long job that also writes the archive cannot share it with a second writer (the push replaces the last commit), and a refresh that waits behind an hour-long publication is a
refresh that does not happen. So the scrape and the save live in ``archive-refresh.yml`` (minutes) and ``web-data.yml`` only restores the archive and builds from it.
"""
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(workflow):
    return workflow.get("on") or workflow.get(True)               # YAML 1.1 reads the key `on` as True


def _runs(workflow):
    return "\n".join(step.get("run", "") for job in workflow["jobs"].values() for step in job["steps"])


def _step(workflow, name):
    return next(step for job in workflow["jobs"].values() for step in job["steps"] if step.get("name", "").startswith(name))


class TestTheRefresh:
    wf = _load("archive-refresh.yml")

    def test_it_runs_on_its_own_schedule_by_hand_and_validates_on_pull_requests(self):
        triggers = _triggers(self.wf)
        assert triggers["schedule"] and "workflow_dispatch" in triggers and "pull_request" in triggers
        assert "only" in triggers["workflow_dispatch"]["inputs"]                  # the first load of a competition is heavy: by hand and one at a time
        assert "config/competitions.json" in triggers["pull_request"]["paths"]

    def test_it_restores_the_archive_scrapes_the_active_competitions_of_the_catalogue_fills_derived_and_saves(self):
        runs = _runs(self.wf)
        order = [runs.index(s) for s in ("run_archive.py pull", "run_archive.py load --src archive --replace", "run_atlas_refresh.py --config config/competitions.json",
                                         "run_backfill_derived.py", "run_archive.py dump --out archive --no-shrink", "run_archive.py push")]
        assert order == sorted(order)

    def test_a_failed_scrape_does_not_stop_the_save_but_leaves_the_run_red(self):
        scrape = _step(self.wf, "Scrape")
        assert scrape.get("continue-on-error") is True and scrape["id"] == "scrape"
        save, fail = _step(self.wf, "Save the archive"), _step(self.wf, "Fail")
        assert "cancelled()" in save["if"]                                        # the new games are worth keeping even if the scrape reported a problem
        assert "steps.scrape.outcome == 'failure'" in fail["if"] and "exit 1" in fail["run"]
        steps = [s.get("name", "") for s in self.wf["jobs"]["refresh"]["steps"]]
        assert steps.index(save["name"]) < steps.index(fail["name"])              # and the red comes after the save

    def test_two_refreshes_never_run_at_once_and_a_running_one_is_not_cancelled(self):
        assert self.wf["concurrency"]["cancel-in-progress"] is False and self.wf["concurrency"]["group"] == "archive-refresh"

    def test_the_job_has_room_for_a_heavy_first_load(self):
        assert self.wf["jobs"]["refresh"]["timeout-minutes"] >= 60

    def test_it_only_reads_the_repository_and_writes_the_archive_through_its_own_key(self):
        assert self.wf["permissions"] == {"contents": "read"}
        assert "ARCHIVE_DEPLOY_KEY" in str(self.wf)


class TestTheSingleWriter:
    def test_only_the_refresh_pushes_the_archive(self):
        writers = [p.name for p in WORKFLOWS.glob("*.yml") if "run_archive.py push" in p.read_text(encoding="utf-8")]
        assert writers == ["archive-refresh.yml"]

    def test_the_publication_restores_the_archive_and_builds_from_it_without_scraping_or_saving(self):
        web = _load("web-data.yml")
        runs = _runs(web)
        assert "run_archive.py load --src archive --replace" in runs and "run_web_data.py" in runs
        assert "run_atlas_refresh.py --config" not in runs and "run_backfill_derived.py" not in runs and "run_archive.py dump" not in runs

    def test_the_publication_waits_for_the_refresh_and_no_longer_for_the_atlas_one(self):
        runs = _triggers(_load("web-data.yml"))["workflow_run"]
        assert runs["workflows"] == ["Archive refresh"] and runs["types"] == ["completed"]

    def test_a_red_refresh_does_not_stop_the_publication_but_a_cancelled_one_does(self):
        condition = _load("web-data.yml")["jobs"]["publish"]["if"]
        assert "cancelled" in condition


class TestTheGuardsOfTheWriter:
    """The job rewrites the only copy of the games (#646): what ``web-data.yml`` guarded when it was the writer is guarded here."""

    steps = {s["name"]: s for s in _load("archive-refresh.yml")["jobs"]["refresh"]["steps"] if "name" in s}

    def test_the_archive_is_saved_only_after_a_complete_restore_and_never_with_fewer_games(self):
        save = self.steps["Save the archive"]
        assert "steps.restore.outcome == 'success'" in save["if"] and "!cancelled()" in save["if"]
        assert "--no-shrink" in save["run"]

    def test_a_failed_download_or_restore_stops_everything_that_would_use_the_empty_database(self):
        assert self.steps["Restore the archive into the ephemeral Mongo"]["if"] == "steps.pull.outcome == 'success'"
        assert "steps.restore.outcome == 'success'" in self.steps["Scrape the new games"]["if"]
        assert "steps.restore.outcome == 'success'" in self.steps["Fill DERIVED in the games"]["if"]
        assert "continue-on-error" not in self.steps["Restore the archive into the ephemeral Mongo"]       # a red restore must turn the run red

    def test_everything_works_on_the_ephemeral_mongo_and_nothing_touches_atlas(self):
        wf = _load("archive-refresh.yml")
        assert wf["jobs"]["refresh"]["services"]["mongo"]["image"].startswith("mongo:")
        for name in ("Restore the archive into the ephemeral Mongo", "Scrape the new games", "Fill DERIVED in the games", "Save the archive"):
            assert "EPHEMERAL_MONGO" in self.steps[name]["env"]["MONGODB_CONNECTION_STRING"]
        assert "secrets.ATLAS" not in (WORKFLOWS / "archive-refresh.yml").read_text(encoding="utf-8")

    def test_the_deploy_key_is_rebuilt_and_checked_before_it_is_used_regression(self):
        run = self.steps["Download the archive"]["run"]
        assert "python -m src.local_data.ssh_key" in run and "ssh-keygen -y -f" in run
        assert run.index("python -m src.local_data.ssh_key") < run.index("ssh-keygen -y -f") < run.index("run_archive.py pull")
        assert "ARCHIVE_DEPLOY_KEY" in run.split("ssh_key", 1)[1].split("exit 1", 1)[0]
