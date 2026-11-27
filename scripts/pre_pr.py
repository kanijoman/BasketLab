"""The checks before opening a pull request, in one command (CLAUDE.md, «Checklist previa al PR»).

``python scripts/pre_pr.py [--base origin/main]`` runs them and exits 1 if one that blocks fails; ``--hook`` is the way the harness calls it: it reads the JSON of the tool call
on stdin, does nothing unless the command is ``gh pr create``, and stops it with exit code 2 (what the harness reads as a stop, with stderr shown to the agent).

Blocking (deterministic): not on main, rebased on the base, ruff clean, ``tests/test_docs_consistency.py``. Warnings (they inform, never stop): uncommitted changes (the red proof
compares COMMITS) and the red proof itself. Standard library only; the tests are ``tests/test_pre_pr.py``.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
_QUOTED = re.compile(r"""'[^']*'|"[^"]*\"""")
_PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b")


@dataclass(frozen=True)
class Result:
    name: str
    blocking: bool
    ok: bool
    detail: str


def _run(repo: Path, *cmd: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")


def is_rebased(repo: Path, base: str) -> bool:
    """Does the branch contain the tip of ``base`` (nothing came into the base after the branch was cut)?"""
    return _run(repo, "git", "merge-base", "--is-ancestor", base, "HEAD").returncode == 0


def targets_pr_create(payload: str) -> bool:
    """Is the tool call of the hook ``gh pr create``? Text inside quotes (a commit message that names it) does not count; a payload that cannot be read never says yes."""
    try:
        command = (json.loads(payload).get("tool_input") or {}).get("command")
    except (ValueError, AttributeError):
        return False
    return isinstance(command, str) and bool(_PR_CREATE.search(_QUOTED.sub("", command)))


def verdict(results: Sequence[Result]) -> Tuple[int, List[str]]:
    lines = [f"{'ok ' if r.ok else ('FALLA' if r.blocking else 'aviso')}  {r.name}{(': ' + r.detail) if r.detail and not r.ok else ''}" for r in results]
    return (1 if any(r.blocking and not r.ok for r in results) else 0), lines


def exit_code_for(code: int, hook: bool) -> int:
    """The harness stops a tool call on exit code 2; 1 is only an error it shows and ignores."""
    return 2 if code and hook else code


def _branch(repo: Path) -> Result:
    name = _run(repo, "git", "branch", "--show-current").stdout.strip()
    return Result("rama de trabajo", True, name not in ("", "main", "master"), f"estás en «{name or 'HEAD suelto'}»: una rama por PR (CLAUDE.md, Flujo git)")


def _rebase(repo: Path, base: str) -> Result:
    remote, _, branch = base.partition("/")
    if branch:
        _run(repo, "git", "fetch", "-q", remote, branch)
    return Result(f"rebase sobre {base}", True, is_rebased(repo, base), f"la rama no contiene {base}: git fetch && git rebase {base}")


def _command_check(repo: Path, name: str, blocking: bool, *cmd: str) -> Result:
    done = _run(repo, *cmd)
    return Result(name, blocking, done.returncode == 0, (done.stdout + done.stderr).strip().splitlines()[-1] if (done.stdout + done.stderr).strip() else "")


def _clean_tree(repo: Path) -> Result:
    dirty = _run(repo, "git", "status", "--porcelain").stdout.strip()
    return Result("todo commiteado", False, not dirty, "hay cambios sin commit: la prueba de rojo compara commits, no el árbol de trabajo")


def _red_proof(repo: Path, base: str) -> Result:
    out = _run(repo, sys.executable, "scripts/red_proof.py", "--base", base).stdout
    return Result("prueba de rojo", False, "Prueba de rojo: GREEN" not in out and "no hay prueba de rojo" not in out, "los tests nuevos pasan con el código de la base: no prueban el cambio (python scripts/red_proof.py)")


def checks(repo: Path, base: str) -> List[Callable[[], Result]]:
    py = sys.executable
    return [
        lambda: _branch(repo),
        lambda: _rebase(repo, base),
        lambda: _command_check(repo, "ruff", True, py, "-m", "ruff", "check", "--no-cache"),
        lambda: _command_check(repo, "docs coherentes", True, py, "-m", "pytest", "-q", "--no-cov", "tests/test_docs_consistency.py"),
        lambda: _clean_tree(repo),
        lambda: _red_proof(repo, base),
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--hook", action="store_true", help="called by the harness: reads the tool call on stdin and acts only on gh pr create")
    args = parser.parse_args(argv)
    if args.hook and not targets_pr_create(sys.stdin.read()):
        return 0
    code, lines = verdict([check() for check in checks(ROOT, args.base)])
    print("\n".join(lines), file=sys.stderr if args.hook and code else sys.stdout)
    return exit_code_for(code, args.hook)


if __name__ == "__main__":
    sys.exit(main())
