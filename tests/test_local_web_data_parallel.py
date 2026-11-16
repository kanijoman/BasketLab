"""The sections whose code changed, computed in parallel (#945).

A change of the code that every section shares recomputes every section of every competition: on 16/11/2026 lineups and IN/OUT of the 366 competitions were 100 of the 118 minutes of
the run, one after the other, on a runner with 4 cores, and the publication did not fit in its time (#944). Each competition is independent: with a runner (``in_processes``) the
sections whose code changed are computed in other processes and sealed as they arrive, and the publication is the same as in series. What changes because of new games is still
computed in series (a few competitions), and without a runner nothing changes.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import web_data_parallel_fakes as fakes  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data import web_data  # noqa: E402
from src.local_data.parallel_sections import in_processes  # noqa: E402
from src.local_data.web_data import CACHED, SECTIONS, publish_web_data  # noqa: E402
from tests.test_local_web_data import FBCYL, FEB, MASTER, cheap_lineups, handler  # noqa: E402,F401  (fixtures)
from tests.test_local_web_data_cache import calls, cheap_exporters  # noqa: E402,F401  (fixtures)


class InProcess:
    """A runner that computes in this process (the test database is in it) and gives the results back to front, as processes that finish in any order would; it remembers what it was asked."""

    def __init__(self, handler):
        self.handler, self.asked = handler, []

    def __call__(self, tasks):
        self.asked.append(sorted(tasks))
        db = self.handler.connection.client["BASKETBALL"]
        for name, section in reversed(list(tasks)):
            yield (name, section), web_data.section_payload(section, self.handler, db, name), 0.5


def _publish(handler, out, runner=None):
    return publish_web_data(handler, out, ScopedSealer(MASTER), [FEB, FBCYL], sections_runner=runner)


def _published(manifest):
    """What a publication says of every file, but the random part of the sealing (the bytes and the wraps): the file is named after the hash of its content."""
    return {s: sorted((e["collection"], e["file"], e["sha256"]) for e in manifest.get(s, [])) for s in ["rows", *SECTIONS]}


def test_with_a_runner_the_publication_is_the_same_as_in_series(handler, tmp_path):
    runner = InProcess(handler)
    in_series, in_parallel = _publish(handler, tmp_path / "series"), _publish(handler, tmp_path / "parallel", runner)
    assert _published(in_parallel) == _published(in_series)
    assert runner.asked == [sorted((name, s) for name in (FEB, FBCYL) for s in CACHED)], "a first publication computes every section: all of them go to the runner"
    assert any(in_parallel[s] for s in CACHED)


def test_only_the_sections_whose_code_changed_go_to_the_runner_and_new_games_are_computed_in_series(handler, tmp_path, calls, monkeypatch):
    runner = InProcess(handler)
    _publish(handler, tmp_path, runner)
    calls[:] = []
    _publish(handler, tmp_path, runner)
    assert runner.asked[-1] == [] and calls == [], "nothing changed: nothing is computed, in parallel or in series"

    real = web_data.section_versions
    monkeypatch.setattr(web_data, "section_versions", lambda modules: {**real(modules), "lineups": "new-code"})
    calls[:] = []
    _publish(handler, tmp_path, runner)
    assert runner.asked[-1] == [(FBCYL, "lineups"), (FEB, "lineups")], "the code of one section changed: that section of every competition, in parallel"

    handler.connection.client["BASKETBALL"][FEB].delete_one({})        # a game of one competition changed (here, gone): its data, not the code
    calls[:] = []
    _publish(handler, tmp_path, runner)
    assert runner.asked[-1] == []
    assert {c for _, c in calls} == {FEB}, "the competition with news is computed as before, in series"


def test_the_sections_computed_by_the_runner_are_told_with_what_each_cost(handler, tmp_path):
    seen = []
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB], sections_runner=InProcess(handler), on_section=lambda *said: seen.append(said))
    told = [s for s in seen if s[1] in CACHED]
    assert sorted(s[1] for s in told) == sorted(CACHED), "every section is told once, not again when the competition is published"
    assert all(s[2] == 0.5 and s[3] is False for s in told)


# ------------------------------------------------------------------------------------------------------- the processes
def test_in_processes_computes_every_task_in_other_processes_and_says_what_each_cost():
    tasks = [(f"C{i}", section) for i in range(4) for section in ("lineups", "inout")]
    results = list(in_processes(2, compute=fakes.who_computes)(tasks))
    assert sorted(task for task, _payload, _seconds in results) == sorted(tasks)
    assert all(payload["task"] == list(task) for task, payload, _seconds in results)
    assert all(payload["pid"] != os.getpid() for _task, payload, _seconds in results), "computed in other processes"
    assert all(seconds >= 0 for _task, _payload, seconds in results)


def test_in_processes_with_nothing_to_compute_starts_no_process():
    assert list(in_processes(4, compute=fakes.who_computes)([])) == []


def test_a_section_that_fails_in_a_process_fails_the_publication():
    tasks = [("C0", "lineups"), *[(f"C{i}", "inout") for i in range(6)]]
    with pytest.raises(RuntimeError, match="C0: the lineups exporter failed"):
        list(in_processes(2, compute=fakes.fails_on_lineups)(tasks))


def test_the_entry_point_computes_in_processes_only_when_it_is_asked_to(handler, tmp_path, monkeypatch):
    """Without ``--workers`` it publishes in series, as before: a process of its own would not see the database of the tests (nor should it open the one of the environment)."""
    import run_web_data
    from src.local_data import parallel_sections

    monkeypatch.setenv("PACKAGE_MASTER_KEY", MASTER)
    made = []
    monkeypatch.setattr(parallel_sections, "in_processes", lambda workers: made.append(workers) or InProcess(handler))
    quiet = ["--collection", FEB, "--no-images", "--no-calendar", "--no-scouting"]
    assert run_web_data.main(["--out", str(tmp_path / "series"), *quiet]) == 0
    assert made == []
    assert run_web_data.main(["--out", str(tmp_path / "parallel"), "--workers", "3", *quiet]) == 0
    assert made == [3]
    assert run_web_data.main(["--out", str(tmp_path / "one"), "--workers", "1", *quiet]) == 0
    assert made == [3], "one worker is in series: no processes"
