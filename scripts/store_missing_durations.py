"""Calibrate the CI split for the test modules that have no stored duration (issue #866).

``.test_durations`` balances the shares of the backend (``pytest-split``); ``tests/test_ci_speed.py`` fails when it covers less than 95 % of the test modules. The cure is not to recalibrate the
whole suite (~6 min): ``--store-durations`` MERGES into the file, so running only the missing modules adds their entries and leaves the rest as it was.

    python scripts/store_missing_durations.py          # runs the missing modules and stores their durations
    python scripts/store_missing_durations.py --list   # only names them
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
DURATIONS = ".test_durations"


def missing_modules(root: Path = ROOT) -> List[str]:
    """The ``test_*.py`` modules of ``tests/`` with no entry in ``.test_durations`` (a stored module that no longer exists is not missing)."""
    stored = json.loads((root / DURATIONS).read_text(encoding="utf-8"))
    stored_modules = {key.split("::")[0].split("/")[-1] for key in stored}
    return sorted(p.name for p in (root / "tests").glob("test_*.py") if p.name not in stored_modules)


def recalibrate_command(modules: List[str]) -> str:
    return "python -m pytest --no-cov -q -n auto --store-durations --durations-path=.test_durations " + " ".join(f"tests/{m}" for m in modules)


def coverage_message(modules: List[str], covered: float) -> str:
    """What the guard of the CI says when the stored durations cover too little of the suite."""
    shown = ", ".join(modules[:12]) + (f" and {len(modules) - 12} more" if len(modules) > 12 else "")
    return (f"the stored durations cover {covered:.1%} of the test modules (95 % needed); missing: {shown}. "
            f"Run `python scripts/store_missing_durations.py` (it stores only those modules and merges into .test_durations), or: {recalibrate_command(modules)}")


def main(argv: List[str], root: Path = ROOT) -> int:
    modules = missing_modules(root)
    if not modules:
        print("every test module has stored durations")
        return 0
    print("missing:", ", ".join(modules))
    if "--list" in argv:
        return 0
    command = recalibrate_command(modules).split()
    return subprocess.call([sys.executable, *command[1:]], cwd=root)      # the interpreter that runs this script: it has pytest-split and xdist


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
