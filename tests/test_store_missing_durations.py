"""Issue #866: when the stored durations stop covering the test modules, the failure names the modules and one command calibrates only them.

The guard of ``test_ci_speed`` fails a pull request that has nothing to do with it when the new modules of several pull requests add up: the fix must be a command of two minutes, not a
recalibration of the whole suite (``--store-durations`` merges with the file, so the old values stay).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from store_missing_durations import coverage_message, missing_modules, recalibrate_command  # noqa: E402


def tree(tmp_path, modules, stored):
    (tmp_path / "tests").mkdir()
    for name in modules:
        (tmp_path / "tests" / name).write_text("", encoding="utf-8")
    (tmp_path / ".test_durations").write_text(json.dumps({f"tests/{m}::test_x": 1.0 for m in stored}), encoding="utf-8")
    return tmp_path


def test_the_modules_without_stored_duration_are_the_missing_ones(tmp_path):
    root = tree(tmp_path, ["test_a.py", "test_b.py", "test_c.py", "conftest.py", "helper.py"], ["test_a.py"])
    assert missing_modules(root) == ["test_b.py", "test_c.py"]


def test_nothing_is_missing_when_every_module_is_stored(tmp_path):
    assert missing_modules(tree(tmp_path, ["test_a.py"], ["test_a.py", "test_gone.py"])) == []     # a stored module that was deleted is not missing


def test_the_command_calibrates_only_the_missing_modules_and_merges_into_the_file(tmp_path):
    command = recalibrate_command(["test_b.py", "test_c.py"])
    assert "--store-durations --durations-path=.test_durations" in command and "--clean-durations" not in command
    assert "tests/test_b.py" in command and "tests/test_c.py" in command and "tests/test_a.py" not in command


def test_the_failure_of_the_ci_guard_says_which_modules_and_how_to_fix_them():
    message = coverage_message(["test_b.py"], 0.9)
    assert "test_b.py" in message and "store_missing_durations" in message


def test_the_command_really_stores_the_missing_module_and_keeps_the_rest(tmp_path):
    """Run for real on a small tree: the new module gets its entry and the stored one keeps its value."""
    from store_missing_durations import main

    root = tree(tmp_path, ["test_old.py"], ["test_old.py"])
    (root / "tests" / "test_new.py").write_text("def test_it():\n    assert True\n", encoding="utf-8")
    assert main([], root) == 0
    stored = json.loads((root / ".test_durations").read_text(encoding="utf-8"))
    assert stored["tests/test_old.py::test_x"] == 1.0 and any(key.startswith("tests/test_new.py::") for key in stored)
    assert missing_modules(root) == []
