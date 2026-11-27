"""The API is gone and nothing depends on it (epic #1199, after issue #334): publishing the data never needed a server.

Before #334 ``run_web_data.py`` and ``run_local_reports.py`` took their database handler from ``src.api.deps``, the exporter of IN/OUT called the FastAPI function of the players router and
``src.database.connection`` read the failure classifier from ``src.api.db_health``. The pieces live under ``src/database`` and ``src/services`` and the server was removed in #1199: this guard
keeps it that way (no module of the repository names ``src.api``, and no server is left to import).
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["src", "scripts", "run_web_data.py", "run_local_reports.py", "run_local_export.py", "run_refresh.py", "run_archive.py", "run_package_publish.py", "run_backfill_derived.py", "tests"]


def _python_files():
    for entry in SOURCES:
        path = ROOT / entry
        yield from ([path] if path.is_file() else sorted(p for p in path.rglob("*.py") if "__pycache__" not in p.parts))


def _imports_of_the_server(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))      # some files carry a BOM
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (node.module == "src.api" or node.module.startswith("src.api.")):
            yield node.lineno
        elif isinstance(node, ast.Import):
            yield from (node.lineno for alias in node.names if alias.name == "src.api" or alias.name.startswith("src.api."))


def test_no_module_of_the_repository_imports_the_server():
    found = [f"{path.relative_to(ROOT)}:{line}" for path in _python_files() for line in _imports_of_the_server(path) if path != Path(__file__).resolve()]
    assert not found, found


@pytest.mark.parametrize("path", ["src/api", "run_api.py", "tests/e2e_web/serve_api.py"])
def test_the_server_is_gone(path):
    assert not (ROOT / path).exists()


def test_the_in_out_analysis_of_a_player_is_a_service(monkeypatch):
    from src.services.inout_service import inout_analysis

    calls = []

    class _Service:
        def __init__(self, db):
            pass

        def get_in_out_analysis(self, collection, player_id):
            calls.append((collection, player_id))
            return {"in": {"points_for": 10, "fga_2": 4, "fgm_2": 2}, "out": {"points_for": 8}}

    monkeypatch.setattr("src.services.inout_service.PlayerStatsService", _Service)
    answer = inout_analysis(object(), "C", "7")

    assert set(answer) == {"on", "off"} and "in" not in answer      # the legacy keys are renamed and each block carries the advanced metrics
    assert len(answer["on"]) > 3 and len(answer["off"]) > 1 and calls == [("C", "7")]
