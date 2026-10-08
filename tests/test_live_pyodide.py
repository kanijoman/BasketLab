"""Run the shared vectors inside real Pyodide (needs Node and ``npm ci`` in tests/pyodide).

Skipped when Node or the installed ``pyodide`` package is missing; the CI workflow
``live-vectors.yml`` always runs it. This is the check that the engine keeps working in the
runtime the Android app uses (Python compiled to WebAssembly).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

RUNNER_DIR = Path(__file__).resolve().parent / "pyodide"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not (RUNNER_DIR / "node_modules" / "pyodide").exists(),
    reason="needs Node and `npm ci` in tests/pyodide",
)


def _run(env_extra=None):
    import os

    return subprocess.run(
        ["node", "run_vectors.mjs"], cwd=RUNNER_DIR, capture_output=True, text=True, timeout=300,
        env={**os.environ, **(env_extra or {})},
    )


def test_pyodide_reproduces_every_vector_of_the_python_reference():
    result = _run()
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1500:]
    assert "vectors identical to the Python reference" in result.stdout


def test_the_runner_really_fails_on_a_wrong_expectation(tmp_path):
    import json

    vectors = json.loads((RUNNER_DIR.parent / "live_vectors" / "vectors.json").read_text(encoding="utf-8"))
    vectors["expected"]["engine"]["checkpoints"][0]["digests"]["snapshot"] = "0" * 64
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text(json.dumps(vectors), encoding="utf-8")
    result = _run({"VECTORS_PATH": str(corrupt)})
    assert result.returncode == 1 and "FAILED" in result.stderr
