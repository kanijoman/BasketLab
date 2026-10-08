"""The PBP parsing code lives in the DB-free ``src.pbp`` package.

The live-game runtime must be importable without MongoDB, but ``src.database`` and
``src.services`` eagerly import repositories (-> pymongo). The parsers therefore live
in ``src.pbp``; the old re-export shims were removed (issue #114).
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

BLOCK_AND_IMPORT = textwrap.dedent(
    """
    import sys

    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name == "pymongo" or name.startswith("pymongo."):
                raise ImportError("pymongo is blocked in this test")

    sys.meta_path.insert(0, _Block())
    import src.pbp.playbyplay_core, src.pbp.event_helpers, src.pbp.possession_core
    bad = [m for m in sys.modules if m in ("pymongo", "src.database", "src.services")]
    assert not bad, f"DB-bound modules were imported: {bad}"
    print("OK")
    """
)


def test_pbp_package_imports_without_database():
    result = subprocess.run(
        [sys.executable, "-c", BLOCK_AND_IMPORT],
        cwd=ROOT, capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert "OK" in result.stdout


OLD_MODULES = [
    ("src/database/playbyplay_core.py", "database.playbyplay_core"),
    ("src/database/_pbp_event_helpers.py", "database._pbp_event_helpers"),
    ("src/services/possession_core.py", "services.possession_core"),
]


@pytest.mark.parametrize("path, _dotted", OLD_MODULES)
def test_old_shim_files_are_gone(path, _dotted):
    assert not (ROOT / path).exists()


def test_nothing_imports_the_old_module_paths():
    """Everything must import ``src.pbp.*`` (the shims were removed, issue #114)."""
    import re

    pattern = re.compile(
        r"(database|services)\.(playbyplay_core|_pbp_event_helpers|possession_core)"
    )
    offenders = []
    for base in ("src", "tests"):
        for p in (ROOT / base).rglob("*.py"):
            if p.name == Path(__file__).name:
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                if re.match(r"\s*(from|import)\s", line) and pattern.search(line):
                    offenders.append(f"{p.relative_to(ROOT)}: {line.strip()}")
    assert offenders == []
