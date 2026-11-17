"""The code is free of what pyflakes finds (#955): imports and variables that nothing uses, f-strings without a placeholder, names that are not defined, a function hidden by another.

Only the ``F`` rules of ``ruff.toml``: no style, no formatting. It runs with the suite, so a pull request that leaves an unused import fails like any other test. ``ruff`` is in ``requirements-dev.txt``.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ruff(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "ruff", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)   # utf-8: the default of Windows (cp1252) cannot read the paths


def test_the_code_has_no_pyflakes_findings():
    pytest.importorskip("ruff", reason="ruff is a development dependency (requirements-dev.txt)")
    run = _ruff("check", "--output-format", "json", "--no-cache")
    assert run.returncode in (0, 1), run.stderr
    found = [f"{Path(f['filename']).relative_to(ROOT).as_posix()}:{f['location']['row']} {f['code']} {f['message']}" for f in json.loads(run.stdout)]
    assert found == [], f"{len(found)} findings; `ruff check --fix` solves most:\n" + "\n".join(found[:40])


def test_an_unused_import_is_caught_regression(tmp_path):
    """The check is not a no-op: a file with an unused import and a variable nobody reads is reported by the same configuration."""
    pytest.importorskip("ruff", reason="ruff is a development dependency (requirements-dev.txt)")
    bad = tmp_path / "bad.py"
    bad.write_text("import os\n\n\ndef f():\n    unused = 1\n    return 2\n", encoding="utf-8")
    run = _ruff("check", "--config", str(ROOT / "ruff.toml"), "--output-format", "json", "--no-cache", str(bad))
    assert {f["code"] for f in json.loads(run.stdout)} == {"F401", "F841"}
