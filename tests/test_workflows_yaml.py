"""Every GitHub Actions workflow must be valid YAML (an unquoted ': ' in a step name broke
live-vectors.yml: "mapping values are not allowed here")."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_valid_yaml_with_jobs(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and data.get("jobs"), f"{path.name} has no jobs"
    for name, job in data["jobs"].items():
        assert "runs-on" in job, f"{path.name}: job {name} has no runs-on"
        for step in job.get("steps", []):
            assert "uses" in step or "run" in step, f"{path.name}: step without uses/run: {step}"


def test_workflows_were_found():
    assert len(WORKFLOWS) >= 3


def _steps(workflow: str):
    data = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    return [s for job in data["jobs"].values() for s in job.get("steps", [])]


def _steps_of_job(workflow: str, job: str):
    data = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    return data["jobs"][job].get("steps", [])


class TestRenderDeployHooks:
    """A missing deploy-hook secret must not fail the pipeline (curl: "URL rejected: Malformed input")."""

    def _deploy_steps(self):
        return [s for s in _steps("ci.yml") if "Render deploy hook" in s.get("name", "")]

    def test_api_and_scraper_have_their_own_hook(self):
        names = " ".join(s["name"] for s in self._deploy_steps())
        assert "api" in names.lower() and "scraper" in names.lower()

    def test_empty_secret_is_skipped_with_a_warning_instead_of_failing_regression(self):
        for step in self._deploy_steps():
            script = step["run"]
            assert '[ -z "$HOOK" ]' in script and "::warning" in script and "exit 0" in script
            assert "secrets." not in script, "the secret must come through env, not be interpolated in the script"
            assert "HOOK" in step["env"]

    def test_hooks_use_distinct_secrets(self):
        secrets = {s["env"]["HOOK"] for s in self._deploy_steps()}
        assert len(secrets) == len(self._deploy_steps()) >= 2


class TestLiveAndroidReleases:
    def _text(self):
        return (ROOT / ".github" / "workflows" / "live-android.yml").read_text(encoding="utf-8")

    def test_versioned_release_is_a_prerelease_so_it_is_never_the_repo_latest(self):
        """make_latest:false is not enough (GitHub falls back to the newest release);
        a prerelease is never considered "latest"."""
        steps = [s for s in _steps("live-android.yml") if "softprops" in str(s.get("uses", ""))]
        assert steps and steps[0]["with"]["prerelease"] in (True, "true")

    def test_a_stable_moving_release_serves_the_newest_apk(self):
        text = self._text()
        assert "live-android-latest" in text and "basketlab-live.apk" in text
        assert "--prerelease" in text


class TestFebCanaryWorkflow:
    def _data(self):
        return yaml.safe_load((ROOT / ".github" / "workflows" / "feb-canary.yml").read_text(encoding="utf-8"))

    def test_runs_daily_and_on_demand(self):
        on = self._data()[True]  # PyYAML parses the bare key `on` as boolean True
        assert on["schedule"][0]["cron"] and "workflow_dispatch" in on

    def test_drift_opens_one_labelled_issue_not_one_per_run(self):
        text = (ROOT / ".github" / "workflows" / "feb-canary.yml").read_text(encoding="utf-8")
        assert "--label canary" in text and "gh issue comment" in text and "gh issue create" in text
        assert "github.event_name != 'pull_request'" in text

    def test_unreachable_feb_is_retried_and_does_not_open_a_drift_issue(self):
        text = (ROOT / ".github" / "workflows" / "feb-canary.yml").read_text(encoding="utf-8")
        assert "for attempt in 1 2 3" in text
        assert "outputs.code == '1'" in text  # only drift (1) creates an issue, not "unreachable" (2)

    def test_needs_only_the_scraper_dependencies(self):
        text = (ROOT / ".github" / "workflows" / "feb-canary.yml").read_text(encoding="utf-8")
        assert "requests beautifulsoup4 cachetools tenacity" in text and "requirements.txt" not in text



class TestFebRecorderWorkflow:
    def _path(self):
        return ROOT / ".github" / "workflows" / "feb-record.yml"

    def _data(self):
        return yaml.safe_load(self._path().read_text(encoding="utf-8"))

    def test_a_cheap_planner_runs_every_few_minutes_and_on_demand(self):
        on = self._data()[True]
        assert on["schedule"][0]["cron"].startswith("*/15") and "workflow_dispatch" in on
        assert {"codes", "teams", "competition"} <= set(on["workflow_dispatch"]["inputs"])
        assert "pull_request" in on  # the planner is exercised on PRs

    def test_recorder_jobs_come_from_the_plan_matrix_one_per_match(self):
        job = self._data()["jobs"]["record"]
        assert job["needs"] == "plan" and "fromJSON(needs.plan.outputs.matrix)" in job["strategy"]["matrix"]
        assert job["strategy"]["fail-fast"] is False

    def test_each_match_is_recorded_once_even_if_triggered_twice(self):
        job = self._data()["jobs"]["record"]
        assert "matrix.code" in job["concurrency"]["group"] and job["concurrency"]["cancel-in-progress"] is False
        record = next(s for s in job["steps"] if s.get("name") == "Record")
        assert "--skip-if-finished" in record["run"]

    def test_the_recording_and_report_are_uploaded_even_if_the_recorder_fails(self):
        steps = self._data()["jobs"]["record"]["steps"]
        upload = next(s for s in steps if "upload-artifact" in str(s.get("uses", "")))
        assert upload["if"] == "always()" and upload["with"]["retention-days"] >= 30
        assert next(s for s in steps if s.get("name") == "Report")["if"] == "always()"

    def test_each_match_snapshots_its_own_calendar(self):
        steps = self._data()["jobs"]["record"]["steps"]
        record = next(s for s in steps if s.get("name") == "Record")
        assert record["env"]["CALENDAR"] == "${{ matrix.calendar }}" and "--calendar" in record["run"]

    def test_the_job_is_long_enough_for_a_whole_match(self):
        assert self._data()["jobs"]["record"]["timeout-minutes"] >= 240

    def test_only_the_scraper_dependencies_are_installed(self):
        assert "requests beautifulsoup4 cachetools tenacity" in self._path().read_text(encoding="utf-8")


class TestRecorderWorkflowBudget:
    """Issue #205: the record job sleeps until kick-off, so wait + recording must fit in the job timeout."""

    @staticmethod
    def _workflow():
        return yaml.safe_load((ROOT / ".github" / "workflows" / "feb-record.yml").read_text(encoding="utf-8"))

    def test_the_job_timeout_covers_the_planner_window_plus_the_longest_recording(self):
        import re

        from src.live_prep.recorder import PLAN_BEFORE

        job = self._workflow()["jobs"]["record"]
        record_step = next(s for s in job["steps"] if s.get("name") == "Record")
        max_minutes = int(re.search(r"--max-minutes\s+(\d+)", record_step["run"]).group(1))
        wait = PLAN_BEFORE.total_seconds() / 60
        assert job["timeout-minutes"] >= wait + max_minutes + 3  # + set-up
        assert job["timeout-minutes"] <= 360  # GitHub-hosted runners stop at 6 h

    def test_the_planner_also_runs_after_each_atlas_refresh(self):
        triggers = self._workflow()[True]  # YAML reads the key `on` as True
        assert triggers["workflow_run"]["workflows"] == ["Atlas refresh"]
        assert "completed" in triggers["workflow_run"]["types"]
        assert "schedule" in triggers and "workflow_dispatch" in triggers


class TestRuleEvaluation:
    """The rule evaluator workflow (issue #238) runs by hand, reads Atlas read-only and always uploads its report."""

    def _data(self):
        return yaml.safe_load((ROOT / ".github" / "workflows" / "rule-evaluation.yml").read_text(encoding="utf-8"))

    def test_it_runs_only_by_hand_and_asks_for_the_collection(self):
        on = self._data()[True]
        assert list(on) == ["workflow_dispatch"]
        inputs = on["workflow_dispatch"]["inputs"]
        assert inputs["collection"]["required"] is True and {"team", "min_prior_games"} <= set(inputs)

    def test_inputs_reach_the_command_through_the_environment_not_the_script_text(self):
        step = next(s for s in _steps("rule-evaluation.yml") if s.get("name") == "Evaluate")
        assert "${{" not in step["run"], "an input interpolated into the script would allow command injection"
        assert step["env"]["COLLECTION"] == "${{ inputs.collection }}"
        assert "ATLAS_READ_URI" in step["env"]["MONGODB_CONNECTION_STRING"]   # read-only user first

    def test_the_committed_recordings_replace_the_simulated_feed_of_their_match(self):
        step = next(s for s in _steps("rule-evaluation.yml") if s.get("name") == "Evaluate")
        assert "tests/recordings/*.rec.json.gz" in step["run"] and "--recording" in step["run"]

    def test_the_report_is_uploaded_even_if_the_evaluation_fails(self):
        upload = next(s for s in _steps("rule-evaluation.yml") if "upload-artifact" in str(s.get("uses", "")))
        assert upload["if"] == "${{ !cancelled() }}" and upload["with"]["path"] == "rule-evaluation/"


class TestDeployJob:
    """Issue #269: an older run still waiting for Render must not fail when a newer deploy arrives."""

    def _job(self):
        return yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))["jobs"]["deploy-backend"]

    def test_a_newer_deploy_cancels_the_run_that_is_still_waiting(self):
        concurrency = self._job()["concurrency"]
        assert concurrency["cancel-in-progress"] is True and concurrency["group"]

    def test_the_job_may_wait_as_long_as_the_check_does(self):
        assert self._job()["timeout-minutes"] >= 50

    def test_the_check_can_ask_github_whether_a_newer_commit_contains_ours(self):
        step = next(s for s in self._job()["steps"] if "Post-deploy check" in s.get("name", ""))
        assert step["env"]["GITHUB_TOKEN"] == "${{ github.token }}"


class TestAppVersionAndUpdate:
    """Issues #226 and #227: the app knows its version and finds out about a newer APK through latest.json."""

    def _steps(self):
        data = yaml.safe_load((ROOT / ".github" / "workflows" / "live-android.yml").read_text(encoding="utf-8"))
        return data["jobs"]["apk"]["steps"]

    def _step(self, name):
        return next(s for s in self._steps() if s.get("name", "").startswith(name))

    def test_the_version_is_fixed_before_the_web_build_so_the_web_build_carries_it(self):
        names = [s.get("name", "") for s in self._steps()]
        assert names.index("Version") < next(i for i, n in enumerate(names) if n.startswith("Build the web app"))
        run = self._step("Version")["run"]
        for variable in ("APP_VERSION_NAME", "APP_VERSION_CODE", "VITE_APP_VERSION", "VITE_APP_BUILD", "VITE_BUILT_AT"):
            assert variable in run

    def test_the_build_number_is_the_workflow_run_number_which_only_grows(self):
        assert "github.run_number" in self._step("Version")["run"]

    def test_latest_json_says_what_the_app_needs_to_compare_and_to_download(self):
        run = self._step("Name the APK")["run"]
        for field in ("version:", "versionCode:", "apk:", "built_at:", "dist-apk/latest.json"):
            assert field in run
        assert "releases/download/live-android-latest/basketlab-live.apk" in run

    def test_the_fixed_latest_release_publishes_latest_json_next_to_the_apk(self):
        run = self._step("Update the stable")["run"]
        assert "dist-apk/basketlab-live.apk dist-apk/latest.json" in run

    def test_the_app_reads_latest_json_from_the_url_this_workflow_publishes(self):
        source = (ROOT / "apps" / "live-android" / "src" / "about" / "update.ts").read_text(encoding="utf-8")
        assert "releases/download/live-android-latest/latest.json" in source


class TestWeeklyAndroidRelease:
    """Issue #279: every Friday morning the app is published with everything integrated since the last release."""

    def _data(self):
        return yaml.safe_load((ROOT / ".github" / "workflows" / "live-android-release.yml").read_text(encoding="utf-8"))

    def _steps(self):
        return self._data()["jobs"]["release"]["steps"]

    def _step(self, name):
        return next(s for s in self._steps() if s.get("name", "").startswith(name))

    def test_it_runs_on_friday_morning_and_by_hand(self):
        on = self._data()[True]
        assert on["schedule"] == [{"cron": "0 7 * * 5"}]          # 09:00 in Madrid in summer time, 08:00 in winter
        inputs = on["workflow_dispatch"]["inputs"]
        assert inputs["version"]["required"] is False and inputs["force"]["type"] == "boolean"

    def test_it_may_start_other_workflows_and_ask_for_generated_notes(self):
        """Regression: the generate-notes API answers 403 (Resource not accessible by integration) with
        ``contents: read``; it needs ``contents: write`` even though it creates nothing. The workflow itself
        never pushes, tags or releases (live-android.yml does)."""
        assert self._data()["permissions"] == {"contents": "write", "actions": "write"}
        script = "\n".join(s.get("run", "") for s in self._steps())
        assert "git push" not in script and "gh release create" not in script

    def test_two_runs_never_overlap(self):
        concurrency = self._data()["concurrency"]
        assert concurrency["group"] == "live-android-release" and concurrency["cancel-in-progress"] is False

    def test_it_sees_every_tag_and_the_history_since_the_last_release(self):
        checkout = next(s for s in self._steps() if "actions/checkout" in str(s.get("uses", "")))
        assert checkout["with"]["fetch-depth"] == 0

    def test_the_decision_comes_from_the_tested_script_and_inputs_reach_it_through_the_environment(self):
        step = self._step("Decide")
        assert "scripts/live_android_release.py" in step["run"] and "${{" not in step["run"]
        assert step["env"]["FORCED_VERSION"] == "${{ inputs.version }}"

    def test_it_only_publishes_when_the_script_says_so(self):
        assert self._step("Release notes")["if"] == "steps.decide.outputs.release == 'true'"
        assert "steps.decide.outputs.release == 'true'" in self._step("Publish")["if"]

    def test_a_dry_run_shows_the_decision_and_the_notes_but_publishes_nothing(self):
        assert self._data()[True]["workflow_dispatch"]["inputs"]["dry_run"]["type"] == "boolean"
        assert "inputs.dry_run" in self._step("Publish")["if"]
        preview = self._step("Preview")
        assert "inputs.dry_run" in preview["if"] and "GITHUB_STEP_SUMMARY" in preview["run"] and "${{" not in preview["run"]
        assert "gh workflow run" not in preview["run"]

    def test_the_build_is_started_with_the_version_and_the_notes_as_inputs_of_the_android_workflow(self):
        run = self._step("Publish")["run"]
        assert "gh workflow run live-android.yml" in run
        for name in ("version=", "notes=", "release_body="):
            assert name in run

    def test_the_run_summary_says_what_was_decided(self):
        assert "GITHUB_STEP_SUMMARY" in self._step("Decide")["run"]


class TestAndroidWorkflowManualRelease:
    """Issue #279: a tag created with GITHUB_TOKEN does not start other workflows, so the weekly workflow dispatches this one."""

    def _data(self):
        return yaml.safe_load((ROOT / ".github" / "workflows" / "live-android.yml").read_text(encoding="utf-8"))

    def _steps(self):
        return self._data()["jobs"]["apk"]["steps"]

    def _step(self, name):
        return next(s for s in self._steps() if s.get("name", "").startswith(name))

    def test_it_can_be_started_by_hand_or_by_the_weekly_workflow_with_a_version(self):
        inputs = self._data()[True]["workflow_dispatch"]["inputs"]
        assert inputs["version"]["required"] is True
        assert {"notes", "release_body"} <= set(inputs)
        assert "tags" in self._data()[True]["push"], "pushing a tag by hand keeps working"

    def test_the_version_comes_from_the_input_only_on_main_and_only_if_it_looks_like_a_version(self):
        step = self._step("Version")
        assert step["env"]["DISPATCH_VERSION"] == "${{ inputs.version }}"
        assert "${{ inputs" not in step["run"], "inputs must not be pasted into the script"
        assert "refs/heads/main" in step["run"] and "[0-9]+" in step["run"]

    def test_the_build_number_still_comes_from_the_run_number_of_this_workflow_so_it_only_grows(self):
        """A lower versionCode than the installed one would make Android refuse the update."""
        assert "github.run_number" in self._step("Version")["run"]

    def test_both_releases_are_published_for_a_tag_and_for_a_manual_run(self):
        for name in ("Publish a GitHub Release", "Update the stable"):
            condition = self._step(name)["if"]
            assert "refs/tags/live-android-v" in condition and "workflow_dispatch" in condition

    def test_a_manual_run_creates_the_tag_at_the_commit_that_was_built(self):
        with_ = self._step("Publish a GitHub Release")["with"]
        assert "live-android-v{0}" in with_["tag_name"] and "inputs.version" in with_["tag_name"]
        assert with_["target_commitish"] == "${{ github.sha }}" and with_["prerelease"] is True
        assert "inputs.release_body" in with_["body"]

    def test_the_notes_of_the_update_notice_come_from_the_environment(self):
        step = self._step("Name the APK")
        assert step["env"]["NOTES"] == "${{ inputs.notes }}"
        assert "${{ inputs" not in step["run"] and "$NOTES" in step["run"]


class TestBackendTestsRunInParallel:
    """The backend tests were the bottleneck of every integration (8 min in one process on a 4-CPU runner).

    They run with pytest-xdist; the coverage gate (70 %) only on main, so a pull request does not pay the tracing cost.
    ``python -m pytest`` (not the bare command) keeps the repo root on ``sys.path`` for ``from tests.x import y`` in the workers.
    """

    def _test_steps(self):
        steps = _steps_of_job("ci.yml", "test-backend")
        return [s for s in steps if "pytest" in s.get("run", "")]

    def test_every_pytest_step_is_parallel_and_keeps_the_root_on_the_path(self):
        steps = self._test_steps()
        assert steps, "the backend job must run pytest"
        for step in steps:
            assert "python -m pytest" in step["run"] and "-n auto" in step["run"] and "--dist loadscope" in step["run"], step["name"]

    def test_the_coverage_gate_runs_only_on_main_and_everything_else_runs_without_it(self):
        with_cov = [s for s in self._test_steps() if "--cov-fail-under=70" in s["run"]]
        without = [s for s in self._test_steps() if "--cov" not in s["run"]]
        assert len(with_cov) == 1 and len(without) == 1
        assert with_cov[0]["if"] == "github.ref == 'refs/heads/main'"
        assert without[0]["if"] == "github.ref != 'refs/heads/main'"

    def test_xdist_is_installed_for_the_job(self):
        assert "pytest-xdist" in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")


class TestRuleEvaluationRoster:
    """Issue #278: the evaluation can ask FEB for the rosters (``roster``) or read a file of the repository (``roster_file``), so the
    illegal-lineup rule is measured. Inputs reach the script only through the environment."""

    def _data(self):
        return yaml.safe_load((ROOT / ".github" / "workflows" / "rule-evaluation.yml").read_text(encoding="utf-8"))

    def _step(self):
        return next(s for s in _steps("rule-evaluation.yml") if s.get("name") == "Evaluate")

    def test_it_has_the_two_optional_inputs(self):
        inputs = self._data()[True]["workflow_dispatch"]["inputs"]
        assert inputs["roster"]["type"] == "boolean" and inputs["roster"]["required"] is False
        assert inputs["roster_file"]["type"] == "string" and inputs["roster_file"]["required"] is False

    def test_the_inputs_reach_the_script_by_the_environment_and_become_the_flags(self):
        step = self._step()
        assert step["env"]["ROSTER"] == "${{ inputs.roster }}" and step["env"]["ROSTER_FILE"] == "${{ inputs.roster_file }}"
        assert "${{ inputs" not in step["run"]
        assert "--roster-file" in step["run"] and '"$ROSTER_FILE"' in step["run"] and "--roster" in step["run"]
