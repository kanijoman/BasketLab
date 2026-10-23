"""The red proof (issue #542): the tests a branch adds or changes must FAIL against the source of its base.

CLAUDE.md asks for the failing test first (red → green); nothing checked it. This script takes the tests that differ from ``--base`` (``git diff base...HEAD -- tests/``),
runs them in a throw-away worktree of the base with the NEW tests copied over, and says whether at least one fails (a failure, or a test that cannot even be collected because
the feature is not in the base). If every new test already passes on the base it proves nothing about the change.

``python scripts/red_proof.py [--base origin/main] [--repo .] [--strict]``: informative by default (exit 0); with ``--strict`` exit 1 when there is no red proof
(including a change without tests). It writes a markdown summary to ``$GITHUB_STEP_SUMMARY`` when it is set. Standard library only.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

PYTEST_NO_TESTS = 5


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def changed_tests(repo: Path, base: str) -> List[str]:
    """Test files (``tests/test_*.py``) added or modified since ``base``, existing in the working tree."""
    names = _git(repo, "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", "tests").split()
    return sorted(n for n in names if Path(n).name.startswith("test_") and n.endswith(".py") and (repo / n).exists())


def run_on_base(repo: Path, base: str, files: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    """Run ``files`` on the source of ``base`` (a detached worktree outside the repository) with the tests of the branch copied over it."""
    tmp = Path(tempfile.mkdtemp(prefix="red-proof-"))
    work = tmp / "base"
    try:
        _git(repo, "worktree", "add", "--detach", str(work), base)
        shutil.copytree(repo / "tests", work / "tests", dirs_exist_ok=True)       # the new tests, and the helpers they use
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(work), str(work / "src")])}
        return subprocess.run([sys.executable, "-m", "pytest", *files, "-q", "--no-cov", "-p", "no:cacheprovider", "--override-ini=addopts=", "-x", "--tb=no", "-rfE"],
                              cwd=work, capture_output=True, text=True, encoding="utf-8", env=env)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(work)], cwd=repo, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def _failing_lines(output: str) -> List[str]:
    return [line.strip() for line in output.splitlines() if line.startswith(("FAILED", "ERROR"))]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="The tests of a branch must fail on the source of its base.")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--strict", action="store_true", help="exit 1 when there is no red proof")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()

    files = changed_tests(repo, args.base)
    if not files:
        lines = ["## Prueba de rojo", "", f"Este cambio no cambia tests respecto de `{args.base}`: no hay prueba de rojo (si corrige un bug, falta su test de regresión)."]
        ok = False
    else:
        result = run_on_base(repo, args.base, files)
        failing = _failing_lines(result.stdout)
        ok = result.returncode not in (0, PYTEST_NO_TESTS)
        if ok:
            lines = ["## Prueba de rojo: RED", "", f"Con el código de `{args.base}` fallan los tests nuevos o modificados ({len(files)} ficheros):", ""] + [f"- `{line}`" for line in failing[:10]]
        else:
            lines = ["## Prueba de rojo: SIN PRUEBA DE ROJO", "", f"Todos los tests nuevos o modificados ({', '.join(files)}) **ya pasan** con el código de `{args.base}`: no demuestran el cambio. "
                     "Un test de bug debe fallar sin el arreglo (regla TDD de CLAUDE.md)."]
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0 if ok or not args.strict else 1


if __name__ == "__main__":
    sys.exit(main())
