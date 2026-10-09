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
