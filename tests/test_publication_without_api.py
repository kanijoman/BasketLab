"""Publishing the data does not depend on the API server (issue #334, towards a repository without a hosted API).

Before: ``run_web_data.py`` and ``run_local_reports.py`` took their database handler from ``src.api.deps``, the exporter of IN/OUT called the FastAPI function of the players router, and
``src.database.connection`` read the failure classifier from ``src.api.db_health``: deleting or moving the server would have broken the publication. The pieces now live under
``src/database`` and ``src/services``; the API imports them, never the other way round.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# everything the publication, the exporters and the data layer are made of: none of it may import the server
NOT_THE_SERVER = ["run_web_data.py", "run_local_reports.py", "run_local_export.py", "run_refresh.py", "run_archive.py", "run_package_publish.py", "run_backfill_derived.py",
                  "src/database", "src/services", "src/local_data", "src/live_prep", "src/live_core", "src/utils"]


def _python_files():
    for entry in NOT_THE_SERVER:
        path = ROOT / entry
        yield from ([path] if path.is_file() else sorted(path.rglob("*.py")))


def _imports_of_the_server(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))      # some files carry a BOM
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (node.module == "src.api" or node.module.startswith("src.api.")):
            yield node.lineno
        elif isinstance(node, ast.Import):
            yield from (node.lineno for alias in node.names if alias.name == "src.api" or alias.name.startswith("src.api."))


def test_nothing_the_publication_is_made_of_imports_the_server():
    found = [f"{path.relative_to(ROOT)}:{line}" for path in _python_files() for line in _imports_of_the_server(path)]
    assert not found, found


def test_the_server_uses_the_shared_handler_and_the_classifier_of_the_data_layer():
    from src.api import db_health, deps
    from src.database import db_health as shared_health
    from src.database.shared_handler import shared_handler

    assert deps._create_handler is shared_handler                    # one handler per process, whoever asks (conftest clears it through the server's name)
    assert db_health.classify_db_error is shared_health.classify_db_error


def test_the_in_out_analysis_of_a_player_is_a_service_and_the_endpoint_gives_what_it_gives(monkeypatch):
    from src.api.routers.players import get_inout_analysis
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
    assert len(answer["on"]) > 3 and len(answer["off"]) > 1
    assert get_inout_analysis("C", "7", object()) == answer and calls == [("C", "7"), ("C", "7")]


@pytest.mark.parametrize("path", ["src/api/deps.py"])
def test_the_server_still_has_its_own_dependency_module(path):
    assert (ROOT / path).exists()
