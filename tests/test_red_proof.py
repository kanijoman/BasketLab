"""The red proof (issue #542): the tests a pull request adds or changes must FAIL against the source of its base, or they prove nothing about the change.

``scripts/red_proof.py`` turns the TDD rule of CLAUDE.md (write the failing test first) into a check. The tests run it on a small git repository built for the case.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import red_proof  # noqa: E402

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=GIT_ENV)


def write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


@pytest.fixture()
def repo(tmp_path):
    """``main`` has a buggy ``add`` and a test file that passes; the branch ``work`` is where each case builds its change."""
    git(tmp_path, "init", "-q", "-b", "main")
    write(tmp_path, "src/calc.py", "def add(a, b):\n    return a - b      # the bug\n")
    write(tmp_path, "tests/test_old.py", "def test_old():\n    assert True\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def commit(repo, message="change"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def prove(repo, *extra):
    return red_proof.main(["--repo", str(repo), "--base", "main", *extra])


def test_a_regression_test_that_fails_on_the_base_is_a_red_proof(repo, capsys):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    write(repo, "tests/test_calc.py", "from src.calc import add\n\n\ndef test_add_adds():\n    assert add(2, 3) == 5\n")
    commit(repo, "fix add")
    assert prove(repo) == 0
    out = capsys.readouterr().out
    assert "RED" in out and "test_add_adds" in out


def test_a_new_test_that_passes_on_the_base_proves_nothing_and_says_so(repo, capsys):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    write(repo, "tests/test_calc.py", "def test_trivial():\n    assert 1 + 1 == 2\n")
    commit(repo, "fix add")
    assert prove(repo) == 0                         # informative by default
    assert "SIN PRUEBA DE ROJO" in capsys.readouterr().out
    assert prove(repo, "--strict") == 1             # and it can be made to fail


def test_a_change_without_tests_is_reported_not_failed_unless_it_is_asked_to(repo, capsys):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    commit(repo, "fix add without a test")
    assert prove(repo) == 0
    assert "no cambia tests" in capsys.readouterr().out
    assert prove(repo, "--strict") == 1


def test_a_test_of_a_feature_that_does_not_exist_yet_is_red_too(repo, capsys):
    write(repo, "src/feature.py", "def double(x):\n    return 2 * x\n")
    write(repo, "tests/test_feature.py", "from src.feature import double\n\n\ndef test_double():\n    assert double(4) == 8\n")
    commit(repo, "feature")
    assert prove(repo) == 0
    assert "RED" in capsys.readouterr().out         # the module is not in the base: the test cannot even be collected there


def test_the_branch_is_left_as_it_was(repo):
    write(repo, "src/calc.py", "def add(a, b):\n    return a + b\n")
    write(repo, "tests/test_calc.py", "from src.calc import add\n\n\ndef test_add_adds():\n    assert add(2, 3) == 5\n")
    commit(repo)
    before = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    prove(repo)
    after = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert before == after == ""
    assert not list(Path(repo).glob(".red-proof*"))
