"""``src.live_core`` runs on the tablet (Pyodide): standard library only.

It must import with pymongo and numpy unavailable and must never pull in
``src.database`` / ``src.services`` (their ``__init__`` import repositories eagerly).
Run in a subprocess so transitive imports are checked too.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent(
    """
    import importlib, pkgutil, sys

    BLOCKED = ("pymongo", "numpy", "scipy", "pandas", "sklearn", "requests", "bs4", "fastapi")

    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in BLOCKED:
                raise ImportError(f"{name} is blocked in this test")

    sys.meta_path.insert(0, _Block())

    import src.live_core as core
    for m in pkgutil.walk_packages(core.__path__, core.__name__ + "."):
        importlib.import_module(m.name)

    bad = [m for m in sys.modules
           if m.split(".")[0] in BLOCKED or m in ("src.database", "src.services", "src.live_prep")]
    assert not bad, f"forbidden modules imported: {bad}"
    print("OK")
    """
)


def test_live_core_imports_with_only_the_standard_library():
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert result.returncode == 0, result.stderr[-1000:]
    assert "OK" in result.stdout
