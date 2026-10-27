"""The red proof (issues #542, #610): the tests a branch adds or changes must FAIL against the source of its base.

CLAUDE.md asks for the failing test first (red → green); nothing checked it. This script takes the tests that differ from ``--base`` in each suite (pytest in
``tests/``, vitest in the web ``frontend/`` and in the live app ``apps/live-android/``), runs them in a throw-away worktree of the base with the tests of the
branch copied over, and says whether at least one fails (a failure, or a test that cannot even be collected because the feature is not in the base). If every
new test already passes on the base it proves nothing about the change. A vitest suite borrows the ``node_modules`` of the branch (``npm ci`` first); without
them it is reported as not run.

``python scripts/red_proof.py [--base origin/main] [--repo .] [--strict] [--needs]``: informative by default (exit 0); with ``--strict`` exit 1 when there is no
red proof (including a code change without tests; a change of documentation only needs none). ``--needs`` only prints ``<suite>=true|false`` for the suites with
new tests (for ``$GITHUB_OUTPUT``: the CI installs only those). It writes a markdown summary to ``$GITHUB_STEP_SUMMARY`` when it is set. Standard library only.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

PYTEST_NO_TESTS = 5
RED, GREEN, NOT_RUN = "red", "green", "not-run"
DOCS = re.compile(r".+\.md|docs/.+")


@dataclass(frozen=True)
class Suite:
    key: str
    label: str
    root: str       # its workspace, relative to the repository ("" for pytest)
    tests: str      # regex of its test files (repository paths); the vitest ones mirror ``include`` in ``<root>/vite.config.ts``
    helpers: str    # regex of the other files the tests use, copied from the branch too


SUITES = (
    Suite("python", "Python", "", r"tests/(.+/)?test_[^/]*\.py", r"tests/.+"),
    Suite("web", "Web", "frontend", r"frontend/src/.+\.(test|spec)\.tsx?", r"frontend/src/test/.+"),
    Suite("app", "App live", "apps/live-android", r"apps/live-android/(src/.+\.test\.tsx?|scripts/.+\.test\.mjs)",
          r"apps/live-android/src/(test-setup\.ts|test/.+|.+TestKit\.tsx?)"),
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def suite_of(path: str) -> Optional[str]:
    """The key of the suite ``path`` (a repository path) is a test file of, or None."""
    return next((s.key for s in SUITES if re.fullmatch(s.tests, path)), None)


def changed_tests(repo: Path, base: str) -> Dict[str, List[str]]:
    """Test files added or modified since ``base`` and existing in the working tree, by suite key (a suite without any is left out)."""
    changed: Dict[str, List[str]] = {}
    for name in sorted(_git(repo, "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD").splitlines()):
        key = suite_of(name)
        if key and (repo / name).exists():
            changed.setdefault(key, []).append(name)
    return changed


def only_docs(repo: Path, base: str) -> bool:
    names = _git(repo, "diff", "--name-only", f"{base}...HEAD").splitlines()
    return bool(names) and all(DOCS.fullmatch(n) for n in names)


def _missing(repo: Path, suite: Suite) -> Optional[str]:
    """Why a vitest suite cannot run here, or None."""
    if not suite.root:
        return None
    if shutil.which("npm") is None:
        return "falta `npm` en el sistema"
    if not (repo / suite.root / "node_modules").is_dir():
        return f"falta `npm ci` en `{suite.root}` (no hay `node_modules`)"
    return None


def _copy_tests(repo: Path, work: Path, suite: Suite, tracked: Sequence[str]) -> None:
    """The tests and test helpers of the branch over the base: the new tests, and what they use."""
    for name in tracked:
        if (re.fullmatch(suite.tests, name) or re.fullmatch(suite.helpers, name)) and (repo / name).is_file():
            (work / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, work / name)


def _link(target: Path, link: Path) -> Path:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:                                         # Windows without the symlink privilege: a junction needs none
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    return link


def _unlink(link: Path) -> None:
    """Remove the link only, never what it points to; it raises rather than let the worktree removal reach the target."""
    try:
        os.unlink(link)
    except OSError:
        os.rmdir(link)


def _run_suite(work: Path, suite: Suite, files: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    if not suite.root:
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(work), str(work / "src")])}
        cmd = [sys.executable, "-m", "pytest", *files, "-q", "--no-cov", "-p", "no:cacheprovider", "--override-ini=addopts=", "-x", "--tb=no", "-rfE"]
        return subprocess.run(cmd, cwd=work, capture_output=True, text=True, encoding="utf-8", env=env)
    relative = [f[len(suite.root) + 1:] for f in files]
    env = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0"}
    return subprocess.run([shutil.which("npm"), "run", "test:run", "--", *relative], cwd=work / suite.root,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def _failing_lines(output: str) -> List[str]:
    return [s for s in (line.strip() for line in output.splitlines()) if s.startswith(("FAIL", "ERROR"))]


def run_on_base(repo: Path, base: str, changed: Dict[str, List[str]]) -> Dict[str, Tuple[str, List[str]]]:
    """Run the changed tests of each suite on the source of ``base`` (a detached worktree outside the repository): ``(RED|GREEN|NOT_RUN, details)`` by suite key."""
    tmp = Path(tempfile.mkdtemp(prefix="red-proof-")).resolve()      # a real path: from a Windows short one (MANUEL~1) vite cannot find the setup files
    work = tmp / "base"
    links: List[Path] = []
    outcomes: Dict[str, Tuple[str, List[str]]] = {}
    try:
        _git(repo, "worktree", "add", "--detach", str(work), base)
        tracked = _git(repo, "ls-files").splitlines()
        for suite in (s for s in SUITES if s.key in changed):
            missing = _missing(repo, suite)
            if missing:
                outcomes[suite.key] = (NOT_RUN, [missing])
                continue
            _copy_tests(repo, work, suite, tracked)
            if suite.root:
                links.append(_link(repo / suite.root / "node_modules", work / suite.root / "node_modules"))
            result = _run_suite(work, suite, changed[suite.key])
            red = result.returncode not in (0, PYTEST_NO_TESTS)
            outcomes[suite.key] = (RED, _failing_lines(result.stdout + result.stderr)) if red else (GREEN, [])
    finally:
        for link in links:
            _unlink(link)                                   # first: removing the worktree must never reach the node_modules of the branch
        subprocess.run(["git", "worktree", "remove", "--force", str(work)], cwd=repo, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return outcomes


def _summary(base: str, changed: Dict[str, List[str]], outcomes: Dict[str, Tuple[str, List[str]]]) -> Tuple[bool, List[str]]:
    statuses = [status for status, _ in outcomes.values()]
    verdict = "RED" if RED in statuses else "SIN EJECUTAR" if set(statuses) == {NOT_RUN} else "SIN PRUEBA DE ROJO"
    lines = [f"## Prueba de rojo: {verdict}", "", f"Tests nuevos o modificados, ejecutados con el código de `{base}`:", ""]
    texts = {RED: "RED (fallan)", GREEN: "ya pasan: no demuestran el cambio", NOT_RUN: "sin ejecutar"}
    for suite in (s for s in SUITES if s.key in changed):
        status, details = outcomes[suite.key]
        n = len(changed[suite.key])
        lines.append(f"- **{suite.label}** ({n} fichero{'s' if n != 1 else ''}): {texts[status]}")
        lines += [f"  - `{d}`" for d in details[:10]]
    if RED not in statuses:
        lines += ["", "Un test de bug debe fallar sin el arreglo (regla TDD de CLAUDE.md)."]
    return RED in statuses, lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="The tests of a branch must fail on the source of its base.")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--strict", action="store_true", help="exit 1 when there is no red proof")
    parser.add_argument("--needs", action="store_true", help="only print <suite>=true|false for the suites with new tests (for $GITHUB_OUTPUT)")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()

    changed = changed_tests(repo, args.base)
    if args.needs:
        print("\n".join(f"{s.key}={'true' if s.key in changed else 'false'}" for s in SUITES))
        return 0
    if changed:
        ok, lines = _summary(args.base, changed, run_on_base(repo, args.base, changed))
    elif only_docs(repo, args.base):
        ok, lines = True, ["## Prueba de rojo: solo documentación", "", f"Este cambio solo toca documentación respecto de `{args.base}`: no necesita prueba de rojo."]
    else:
        ok, lines = False, ["## Prueba de rojo", "", f"Este cambio no cambia tests respecto de `{args.base}`: no hay prueba de rojo (si corrige un bug, falta su test de regresión)."]
    text = "\n".join(lines)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")            # the vitest lines carry symbols (❯, ×) a Windows console cannot encode
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0 if ok or not args.strict else 1


if __name__ == "__main__":
    sys.exit(main())
