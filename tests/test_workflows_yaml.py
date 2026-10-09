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
