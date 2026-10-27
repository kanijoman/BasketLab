"""The red proof (issue #542): the tests a pull request adds or changes must FAIL against the source of its base, or they prove nothing about the change.

``scripts/red_proof.py`` turns the TDD rule of CLAUDE.md (write the failing test first) into a check. The tests run it on a small git repository built for the case.
Since #610 it also runs the vitest tests of the web (``frontend/``) and of the live app (``apps/live-android/``); here the app runs a tiny fake of vitest
that lives in its ``node_modules``, so the backend CI needs no ``npm ci`` (only ``node`` and ``npm``).
"""
import fnmatch
import itertools
import os
import re
import shutil
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


def test_a_change_of_documentation_only_needs_no_red_proof(repo, capsys):
    write(repo, "docs/evaluaciones/informe.md", "# Informe\n")
    write(repo, "README.md", "BasketLab\n")
    commit(repo, "docs")
    assert prove(repo, "--strict") == 0             # nothing to prove, not a code change without its test
    assert "solo documentación" in capsys.readouterr().out


@pytest.mark.parametrize("files, needs", [
    (["frontend/src/pages/Teams.test.tsx", "apps/live-android/src/ui/App.test.tsx"], {"python": "false", "web": "true", "app": "true"}),
    (["frontend/src/lib/x.spec.ts", "tests/test_calc.py"], {"python": "true", "web": "true", "app": "false"}),
    (["apps/live-android/scripts/sync.test.mjs"], {"python": "false", "web": "false", "app": "true"}),
    # Playwright and the code itself are not vitest tests
    (["frontend/e2e/smoke.spec.ts", "apps/live-android/e2e/layout.spec.ts", "apps/live-android/src/ui/App.tsx"], {"python": "false", "web": "false", "app": "false"}),
])
def test_it_says_which_suites_have_new_tests_so_the_ci_installs_only_those(repo, capsys, files, needs):
    for rel in files:
        write(repo, rel, "// x\n")
    commit(repo)
    assert prove(repo, "--needs") == 0
    printed = dict(line.split("=") for line in capsys.readouterr().out.split())
    assert printed == needs


# ── The live app (vitest): a fake vitest in its node_modules ─────────────────
# Like the real one it needs its root to be a real path: from a Windows short path (C:\Users\MANUEL~1\...\Temp) vite cannot find the setup files and every
# suite fails before running, a false red (#610).
FAKE_VITEST = """\
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { realpathSync } from 'node:fs';
if (realpathSync.native(process.cwd()) !== process.cwd()) { console.log(' FAIL  setup > the root is not a real path'); process.exit(1); }
let failed = 0;
for (const file of process.argv.slice(2)) {
  try { await import(pathToFileURL(resolve(file)).href); console.log(` ✓ ${file}`); }
  catch (e) { failed++; console.log(` FAIL  ${file} > ${e.message}`); }
}
process.exit(failed ? 1 : 0);
"""
APP = "apps/live-android"
needs_npm = pytest.mark.skipif(shutil.which("npm") is None, reason="needs node and npm")


@pytest.fixture()
def app_repo(repo):
    """The base of ``repo`` plus a live app whose ``add`` has the bug, with its ``node_modules`` installed (ignored by git, as in the real repository)."""
    git(repo, "checkout", "-q", "main")
    write(repo, ".gitignore", "node_modules/\n")
    write(repo, f"{APP}/package.json", '{"name": "app", "private": true, "scripts": {"test:run": "node node_modules/fake-vitest/cli.mjs"}}\n')
    write(repo, f"{APP}/scripts/calc.mjs", "export const add = (a, b) => a - b;   // the bug\n")
    commit(repo, "app")
    git(repo, "checkout", "-q", "work")
    git(repo, "merge", "-q", "--ff-only", "main")
    write(repo, f"{APP}/node_modules/fake-vitest/cli.mjs", FAKE_VITEST)
    return repo


def fix_the_app(repo, test_body="if (add(2, 3) !== 5) throw new Error('add adds');\n"):
    write(repo, f"{APP}/scripts/calc.mjs", "export const add = (a, b) => a + b;\n")
    write(repo, f"{APP}/scripts/calc.test.mjs", "import { add } from './calc.mjs';\n" + test_body)
    commit(repo, "fix add in the app")


@needs_npm
def test_an_app_regression_test_that_fails_on_the_base_is_a_red_proof(app_repo, capsys):
    fix_the_app(app_repo)
    assert prove(app_repo, "--strict") == 0
    out = capsys.readouterr().out
    assert "RED" in out and "App live" in out and "add adds" in out


@needs_npm
def test_an_app_test_that_passes_on_the_base_proves_nothing(app_repo, capsys):
    fix_the_app(app_repo, test_body="if (1 + 1 !== 2) throw new Error('arithmetic');\n")
    assert prove(app_repo, "--strict") == 1
    assert "SIN PRUEBA DE ROJO" in capsys.readouterr().out


@needs_npm
def test_one_suite_that_fails_on_the_base_is_enough_and_the_summary_says_which(app_repo, capsys):
    fix_the_app(app_repo)
    write(app_repo, "tests/test_trivial.py", "def test_trivial():\n    assert True\n")
    commit(app_repo, "a python test that proves nothing")
    assert prove(app_repo, "--strict") == 0
    out = capsys.readouterr().out
    assert out.startswith("## Prueba de rojo: RED")
    assert re.search(r"Python.*ya pasan", out) and re.search(r"App live.*RED", out)


@needs_npm
def test_the_node_modules_of_the_branch_survive_and_the_branch_is_left_as_it_was(app_repo):
    fix_the_app(app_repo)
    prove(app_repo)
    assert (app_repo / APP / "node_modules" / "fake-vitest" / "cli.mjs").read_text(encoding="utf-8") == FAKE_VITEST
    assert subprocess.run(["git", "status", "--porcelain"], cwd=app_repo, capture_output=True, text=True).stdout == ""


def test_without_npm_ci_the_app_tests_are_not_run_and_it_says_so(app_repo, capsys):
    shutil.rmtree(app_repo / APP / "node_modules")
    fix_the_app(app_repo)
    assert prove(app_repo, "--strict") == 1         # not run is not a red proof
    out = capsys.readouterr().out
    assert "sin ejecutar" in out and "npm ci" in out


# ── The suites follow the `include` of each vitest config ────────────────────
def _vitest_globs(config: Path):
    """The ``include`` globs of a vite config, braces expanded and ``**/`` folded (``fnmatch``'s ``*`` already crosses directories)."""
    include = re.search(r"include:\s*\[([^\]]*)\]", config.read_text(encoding="utf-8")).group(1)
    globs = []
    for glob in re.findall(r"'([^']+)'", include):
        parts = re.split(r"\{([^}]*)\}", glob)
        for combo in itertools.product(*[p.split(",") if i % 2 else [p] for i, p in enumerate(parts)]):
            globs.append("".join(combo).replace("**/", ""))
    return globs


@pytest.mark.parametrize("suite, workspace", [("web", "frontend"), ("app", "apps/live-android")])
def test_the_suites_take_exactly_the_files_vitest_runs(suite, workspace):
    globs = _vitest_globs(ROOT / workspace / "vite.config.ts")
    tracked = subprocess.run(["git", "ls-files", workspace], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for path in tracked:
        runs = any(fnmatch.fnmatch(path[len(workspace) + 1:], g) for g in globs)
        assert (red_proof.suite_of(path) == suite) == runs, path
