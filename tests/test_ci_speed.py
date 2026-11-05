"""The CI of a pull request has to be fast (issue #741): a backend run of 12-15 minutes made every integration wait for it.

These guards fix the cheap measures of the first step: a newer push cancels the run of the previous commit of the same pull request (never a run of ``main``, whose deploy waits for
it), the slowest tests are reported on every run (they seed the split of the suite in the next step) and the tests of a module are no longer pinned to one worker.
"""
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
CI = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
PYTEST_STEPS = [s for s in CI["jobs"]["test-backend"]["steps"] if "python -m pytest" in s.get("run", "")]


def test_a_newer_push_to_a_pull_request_cancels_the_previous_run_but_never_a_run_of_main():
    concurrency = CI["concurrency"]
    assert "github.ref" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


def test_the_two_pytest_commands_report_the_slowest_tests():
    assert len(PYTEST_STEPS) == 2                       # pull requests (no coverage) and main (coverage gate)
    for step in PYTEST_STEPS:
        assert "--durations=30" in step["run"] and "--durations-min=1" in step["run"]


def test_the_tests_are_spread_by_stealing_work_not_pinned_to_a_worker_by_module():
    for step in PYTEST_STEPS:
        assert "--dist worksteal" in step["run"] and "loadscope" not in step["run"]
