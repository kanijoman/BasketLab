"""The CI of a pull request has to be fast (issue #741): a backend run of 12-15 minutes made every integration wait for it.

These guards fix the cheap measures of the first step: a newer push cancels the run of the previous commit of the same pull request (never a run of ``main``, whose deploy waits for
it), the slowest tests are reported on every run and the tests of a module are no longer pinned to one worker.

Step 2: the suite is split into SHARES that run as parallel jobs (``pytest-split`` with the stored durations of ``.test_durations``); a final job keeps the name ``Backend (pytest)`` that the ruleset
of ``main`` requires, passes only if every share passed, and on ``main`` combines the coverage of the shares and applies the gate (82 %).
"""
from pathlib import Path

import sys

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from store_missing_durations import coverage_message, missing_modules  # noqa: E402

CI = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
SHARD = CI["jobs"]["backend-shard"]
PYTEST_STEPS = [s for s in SHARD["steps"] if "python -m pytest" in s.get("run", "")]


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


ROOT = WORKFLOWS.parent.parent
JOBS = CI["jobs"]
SHARES = 4


def test_the_ruleset_checks_still_exist_by_name():
    names = {job["name"] for job in JOBS.values()}
    assert {"Backend (pytest)", "Frontend (vitest + type-check)"} <= names                # required by the ruleset of main: renaming them leaves every pull request waiting forever


def test_the_suite_runs_in_parallel_shares_and_every_share_asks_for_its_own_group():
    assert SHARD["strategy"]["matrix"]["group"] == list(range(1, SHARES + 1)) and SHARD["strategy"]["fail-fast"] is False
    for step in PYTEST_STEPS:
        assert f"--splits {SHARES}" in step["run"] and "--group ${{ matrix.group }}" in step["run"] and "--durations-path .test_durations" in step["run"] and "--splitting-algorithm least_duration" in step["run"]    # the default chunks are contiguous: the heavy modules would pile up in one share


def test_the_stored_durations_cover_the_modules_of_the_suite():
    modules = {path.name for path in (ROOT / "tests").glob("test_*.py")}
    missing = missing_modules(ROOT)
    covered = 1 - len(missing) / len(modules)
    assert covered >= 0.95, coverage_message(missing, covered)      # the message names the modules and the command that calibrates only them (#866)


def test_the_gate_job_keeps_the_required_name_and_fails_if_a_share_fails():
    gate = JOBS["test-backend"]
    assert gate["name"] == "Backend (pytest)" and gate["needs"] == "backend-shard" and "always()" in gate["if"]
    check = next(s for s in gate["steps"] if "needs.backend-shard.result" in s.get("run", ""))
    assert "success" in check["run"] and "exit 1" in check["run"]                         # a skipped or cancelled share must not count as a pass


def test_the_coverage_of_the_shares_is_combined_and_gated_only_when_it_is_measured():
    steps = SHARD["steps"]
    measured = [s for s in steps if "--cov=src" in s.get("run", "")]
    unmeasured = [s for s in steps if "python -m pytest" in s.get("run", "") and "--cov" not in s["run"]]
    assert len(measured) == 1 and len(unmeasured) == 1
    assert measured[0]["env"]["COVERAGE_FILE"] == ".coverage.share${{ matrix.group }}" and "--cov-fail-under" not in measured[0]["run"]   # one share cannot meet the gate alone
    upload = next(s for s in steps if "upload-artifact" in str(s.get("uses", "")))
    assert upload["with"]["include-hidden-files"] is True and upload["with"]["name"] == "coverage-${{ matrix.group }}"
    report = next(s for s in JOBS["test-backend"]["steps"] if "coverage report" in s.get("run", ""))
    assert "coverage combine" in report["run"] and "--fail-under=82" in report["run"]


def test_a_manual_run_can_check_the_coverage_path_before_it_reaches_main():
    assert "workflow_dispatch" in CI[True]


def test_the_split_tool_is_a_dev_dependency():
    assert "pytest-split" in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
