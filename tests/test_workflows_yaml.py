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
