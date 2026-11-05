"""The jobs that READ the archive instead of Atlas (issue #724, step 4): the live packages and the rule evaluation.

Both used to read Atlas. Now they download the private archive, restore it into an ephemeral Mongo and read from there, through ONE composite action
(``.github/actions/restore-archive``) so that the key handling and the restore are written once. They never write the archive (that is ``archive-refresh.yml``), the live packages
wait for the refresh that saved it, and Atlas is no longer a fallback (retired in step 5).
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / ".github" / "actions" / "restore-archive" / "action.yml"


def _load(name):
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def _on(workflow):
    return workflow.get("on") or workflow.get(True)               # YAML 1.1 reads the key `on` as True


def _steps(workflow, job):
    return workflow["jobs"][job]["steps"]


def _named(workflow, job):
    return {s["name"]: s for s in _steps(workflow, job) if "name" in s}


class TestTheRestoreAction:
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    steps = {s["name"]: s for s in action["runs"]["steps"]}

    def test_it_is_a_composite_action_that_asks_for_the_deploy_key(self):
        assert self.action["runs"]["using"] == "composite"
        assert self.action["inputs"]["deploy-key"]["required"] is True
        assert {"collection", "mongo-uri"} <= set(self.action["inputs"])
        assert all(step["shell"] == "bash" for step in self.action["runs"]["steps"])

    def test_the_order_is_download_restore_index(self):
        names = [s["name"] for s in self.action["runs"]["steps"]]
        assert names == ["Download the archive", "Restore the archive into the ephemeral Mongo", "Create the team index"]

    def test_the_deploy_key_is_rebuilt_and_checked_before_it_is_used_regression(self):
        run = self.steps["Download the archive"]["run"]
        assert run.index("python -m src.local_data.ssh_key") < run.index("ssh-keygen -y -f") < run.index("run_archive.py pull")
        assert "ARCHIVE_DEPLOY_KEY" in run.split("ssh_key", 1)[1].split("exit 1", 1)[0]

    def test_it_only_reads_the_archive(self):
        text = ACTION.read_text(encoding="utf-8")
        assert "run_archive.py push" not in text and "run_archive.py dump" not in text

    def test_the_input_reaches_the_command_through_the_environment_not_the_script_text(self):
        step = self.steps["Restore the archive into the ephemeral Mongo"]
        assert "${{" not in step["run"], "an input interpolated into the script would allow command injection"
        assert step["env"]["COLLECTION"] == "${{ inputs.collection }}" and step["env"]["MONGODB_CONNECTION_STRING"] == "${{ inputs.mongo-uri }}"
        assert "--replace" in step["run"] and '--collection "$COLLECTION"' in step["run"]

    def test_the_team_index_comes_after_the_restore_on_the_same_database(self):
        step = self.steps["Create the team index"]
        assert "run_archive.py index" in step["run"] and step["env"]["MONGODB_CONNECTION_STRING"] == "${{ inputs.mongo-uri }}"


class TestLivePackages:
    wf = _load("live-packages.yml")
    steps = _named(wf, "publish")

    def test_it_waits_for_the_refresh_that_saved_the_archive_and_no_longer_for_atlas(self):
        runs = _on(self.wf)["workflow_run"]
        assert runs["workflows"] == ["Archive refresh"] and runs["types"] == ["completed"]
        assert "cancelled" in self.wf["jobs"]["publish"]["if"]                      # a red refresh does not stop the packages, a cancelled one does

    def test_it_restores_the_archive_with_the_shared_action_and_the_ephemeral_mongo_is_a_service(self):
        restore = self.steps["Restore the archive"]
        assert restore["uses"] == "./.github/actions/restore-archive" and restore["with"]["deploy-key"] == "${{ secrets.ARCHIVE_DEPLOY_KEY }}"
        assert restore["if"] == "github.event_name != 'pull_request'"                # pull requests only validate the entry points
        assert self.wf["jobs"]["publish"]["services"]["mongo"]["image"].startswith("mongo:")

    def test_the_order_is_restore_build_publish_and_a_failed_restore_stops_the_build(self):
        names = [s.get("name", "") for s in _steps(self.wf, "publish")]
        order = ["Restore the archive", "Build the packages", "Publish to the live-packages branch"]
        assert [names.index(n) for n in order] == sorted(names.index(n) for n in order)
        assert "continue-on-error" not in self.steps["Restore the archive"]

    def test_it_builds_from_the_ephemeral_mongo_and_never_from_atlas(self):
        build = self.steps["Build the packages"]["env"]["MONGODB_CONNECTION_STRING"]
        assert build == "${{ env.EPHEMERAL_MONGO }}"

    def test_it_never_writes_the_archive_and_the_pull_requests_validate_the_new_pieces(self):
        assert "run_archive.py push" not in (ROOT / ".github" / "workflows" / "live-packages.yml").read_text(encoding="utf-8")
        paths = _on(self.wf)["pull_request"]["paths"]
        assert ".github/actions/restore-archive/action.yml" in paths and "run_archive.py" in paths

    def test_the_job_has_room_for_the_restore_and_the_build(self):
        assert self.wf["jobs"]["publish"]["timeout-minutes"] >= 60


class TestRuleEvaluation:
    wf = _load("rule-evaluation.yml")
    steps = _named(wf, "evaluate")

    def test_it_restores_only_the_collection_it_evaluates_from_the_archive(self):
        restore = self.steps["Restore the archive"]
        assert restore["uses"] == "./.github/actions/restore-archive"
        assert restore["with"]["collection"] == "${{ inputs.collection }}" and restore["with"]["deploy-key"] == "${{ secrets.ARCHIVE_DEPLOY_KEY }}"

    def test_it_evaluates_from_the_ephemeral_mongo_and_never_from_atlas(self):
        names = [s.get("name", "") for s in _steps(self.wf, "evaluate")]
        assert names.index("Restore the archive") < names.index("Evaluate")
        mongo = self.steps["Evaluate"]["env"]["MONGODB_CONNECTION_STRING"]
        assert mongo == "${{ env.EPHEMERAL_MONGO }}"
        assert self.wf["jobs"]["evaluate"]["services"]["mongo"]["image"].startswith("mongo:")

    def test_it_stays_manual_and_never_writes_the_archive(self):
        assert list(_on(self.wf)) == ["workflow_dispatch"]
        assert "run_archive.py push" not in (ROOT / ".github" / "workflows" / "rule-evaluation.yml").read_text(encoding="utf-8")
