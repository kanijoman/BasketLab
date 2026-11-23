"""Two jobs write to the same repository, ``basketlab-archive-ext`` (issue #1068): the sources of ``archive-ext-refresh`` (one job each, in parallel) and ``talent-rosters``.

Real failure of 23/11/2026: the first batch of NCAA worked for 34 minutes and its final ``git push`` was rejected (``fetch first``): FIBA, which takes two minutes, had pushed to the same branch in the
meantime and the clone of NCAA was behind. Each job only touches ITS folder, so there is nothing to conflict: the push has to integrate what the others wrote and try again, and a push that is refused
for good has to say so. These tests run the REAL script of each step of the workflow against a local repository that another job has already written to.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="the scripts of the steps are bash")

# (workflow, job, step, the folder it commits, what the expression ``matrix.source`` is replaced with)
STEPS = [("archive-ext-refresh", "refresh", "Save the archive of the source", "ncaa"), ("talent-rosters", None, "Save the rosters", "rosters")]


def script_of(workflow: str, job, step: str, folder: str) -> str:
    data = yaml.safe_load((WORKFLOWS / f"{workflow}.yml").read_text(encoding="utf-8"))
    jobs = data["jobs"]
    steps = (jobs[job] if job else next(iter(jobs.values())))["steps"]
    run = next(s["run"] for s in steps if s.get("name") == step)
    return run.replace("${{ matrix.source }}", folder)


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True,
                          env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": __import__("os").environ["PATH"], "HOME": str(cwd)})


@pytest.fixture
def repo(tmp_path):
    """A remote with one commit, the clone the job has (``archive-ext``, behind) and a second clone of another job."""
    remote = tmp_path / "remote.git"
    git("init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    git("clone", "-q", str(remote), "archive-ext", cwd=work)
    seed = work / "archive-ext"
    (seed / "README").write_text("archive", encoding="utf-8")
    git("add", "README", cwd=seed)
    git("commit", "-q", "-m", "seed", cwd=seed)
    git("push", "-q", "origin", "HEAD:main", cwd=seed)
    other = tmp_path / "other"
    git("clone", "-q", str(remote), str(other), cwd=tmp_path)
    return {"remote": remote, "work": work, "job": seed, "other": other, "tmp": tmp_path}


def other_job_writes(repo, folder="fiba"):
    other = repo["other"]
    (other / folder).mkdir(exist_ok=True)
    (other / folder / "status.json").write_text('{"source": "%s"}' % folder, encoding="utf-8")
    git("add", folder, cwd=other)
    git("commit", "-q", "-m", folder, cwd=other)
    git("push", "-q", "origin", "HEAD:main", cwd=other)


def run_step(repo, script, pause="0"):
    return subprocess.run([BASH, "-e", "-c", script], cwd=repo["work"], capture_output=True, text=True,
                          env={"PATH": __import__("os").environ["PATH"], "HOME": str(repo["work"]), "PUSH_RETRY_PAUSE": pause, "GIT_TERMINAL_PROMPT": "0"})


def remote_files(repo):
    check = repo["tmp"] / "check"
    shutil.rmtree(check, ignore_errors=True)
    git("clone", "-q", str(repo["remote"]), str(check), cwd=repo["tmp"])
    return sorted(str(p.relative_to(check)).replace("\\", "/") for p in check.rglob("*") if p.is_file() and ".git" not in p.parts)


@pytest.mark.parametrize("workflow,job,step,folder", STEPS)
def test_a_job_whose_clone_is_behind_integrates_what_the_other_wrote_and_pushes(repo, workflow, job, step, folder):
    """The failure of the day: another job pushed to the branch while this one worked."""
    script = script_of(workflow, job, step, folder)
    (repo["job"] / folder).mkdir()
    (repo["job"] / folder / "status.json").write_text('{"state": "ok"}', encoding="utf-8")
    other_job_writes(repo, "fiba")
    done = run_step(repo, script)
    assert done.returncode == 0, done.stderr
    assert remote_files(repo) == ["README", "fiba/status.json", f"{folder}/status.json"]


@pytest.mark.parametrize("workflow,job,step,folder", STEPS)
def test_when_nobody_wrote_in_between_it_pushes_as_it_always_did(repo, workflow, job, step, folder):
    script = script_of(workflow, job, step, folder)
    (repo["job"] / folder).mkdir()
    (repo["job"] / folder / "status.json").write_text("{}", encoding="utf-8")
    assert run_step(repo, script).returncode == 0 and f"{folder}/status.json" in remote_files(repo)


@pytest.mark.parametrize("workflow,job,step,folder", STEPS)
def test_nothing_changed_means_no_commit_and_no_push(repo, workflow, job, step, folder):
    script = script_of(workflow, job, step, folder)
    (repo["job"] / folder).mkdir()
    done = run_step(repo, script)
    assert done.returncode == 0 and remote_files(repo) == ["README"]


@pytest.mark.parametrize("workflow,job,step,folder", STEPS)
def test_two_writes_in_a_row_both_end_up_in_the_archive(repo, workflow, job, step, folder):
    """The other job writes twice while this one works (it can happen with several sources): still no conflict, each one has its own folder."""
    script = script_of(workflow, job, step, folder)
    (repo["job"] / folder).mkdir()
    (repo["job"] / folder / "status.json").write_text("{}", encoding="utf-8")
    other_job_writes(repo, "fiba")
    other_job_writes(repo, "acb")
    assert run_step(repo, script).returncode == 0
    assert remote_files(repo) == ["README", "acb/status.json", "fiba/status.json", f"{folder}/status.json"]


@pytest.mark.parametrize("workflow,job,step,folder", STEPS)
def test_a_push_that_is_refused_for_good_fails_the_job_after_a_few_attempts_and_says_why(repo, workflow, job, step, folder):
    """A repository that keeps refusing (a rule, a key without write access) must not be hidden nor loop for ever."""
    hook = repo["remote"] / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'refused by the test' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    script = script_of(workflow, job, step, folder)
    (repo["job"] / folder).mkdir()
    (repo["job"] / folder / "status.json").write_text("{}", encoding="utf-8")
    done = run_step(repo, script)
    assert done.returncode != 0 and "attempt" in (done.stdout + done.stderr) and len(re.findall(r"attempt \d", done.stdout + done.stderr)) >= 3
    assert remote_files(repo) == ["README"]
