"""The PBP parsing code lives in the DB-free ``src.pbp`` package.

The live-game runtime must be importable without MongoDB, but ``src.database`` and
``src.services`` eagerly import repositories (-> pymongo). The parsers were therefore
extracted to ``src.pbp``; the old locations keep re-exporting the *same objects* so
existing imports (``src.database...``, ``src.services...`` and the legacy un-prefixed
``database...`` / ``services...`` paths used by some tests) keep working.
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


@pytest.mark.parametrize(
    "old_module, new_module, names",
    [
        ("src.database.playbyplay_core", "src.pbp.playbyplay_core", ["PlayByPlayAnalyzer"]),
        ("src.database._pbp_event_helpers", "src.pbp.event_helpers",
         ["get_timestamp", "ft_sequence_info", "is_missed_fg", "is_turnover", "is_rebound"]),
        ("src.services.possession_core", "src.pbp.possession_core",
         ["extract_possession_rows", "order_possession_moves", "count_quality_pbp_metrics",
          "is_tab_evaluated_possession"]),
    ],
)
def test_old_paths_reexport_the_same_objects(old_module, new_module, names):
    import importlib

    old, new = importlib.import_module(old_module), importlib.import_module(new_module)
    for name in names:
        assert getattr(old, name) is getattr(new, name), f"{old_module}.{name} is not shared"


def test_legacy_unprefixed_paths_still_work():
    """Some tests import without the ``src.`` prefix (``src`` dir on sys.path)."""
    src_dir = str(ROOT / "src")
    sys.path.insert(0, src_dir)
    try:
        from services.possession_core import extract_possession_rows as legacy
        from database._pbp_event_helpers import get_timestamp as legacy_ts
    finally:
        sys.path.remove(src_dir)
    from src.pbp.event_helpers import get_timestamp
    from src.pbp.possession_core import extract_possession_rows

    assert callable(legacy) and callable(legacy_ts)
    assert legacy_ts is get_timestamp
    assert legacy is extract_possession_rows
