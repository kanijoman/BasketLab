"""The sections whose code changed, computed in parallel (#945).

A change of the code that every section shares (``src/database``, the formulas of ``live_core``) recomputes every section of every competition: on 16/11/2026 lineups and IN/OUT
of the 366 competitions were 100 of the 118 minutes of the run, one after the other, on a runner with 4 cores, and the publication did not fit in its time (#944). Every
competition is independent, so ``publish_web_data`` hands the sections that will be computed whatever the data (their code changed, or the previous publication never saw them)
to a runner before publishing the competitions, and seals each one as it arrives; what changes because of new games (a few competitions) is computed as before, in series.

``in_processes`` is the runner of ``run_web_data.py``: ``spawn`` processes (a clean interpreter, no database client inherited from this one: a pymongo client must not cross a
fork), each with its own handler (``shared_handler``, from the same environment). The tests run the publication with a runner in their own process (their database is there).
"""
from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from multiprocessing import get_context
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

Task = Tuple[str, str]                                           # (competition, section)
Payload = Optional[Dict[str, Any]]                               # what the exporter says; None: nothing to publish
Computed = Tuple[Task, Payload, float]                           # and what it cost, in seconds
Runner = Callable[[List[Task]], Iterable[Computed]]


def changed_code(names: Sequence[str], sections: Sequence[str], versions: Mapping[str, str], remembered: Mapping[str, Dict[str, Any]]) -> List[Task]:
    """The sections that will be computed whatever the data: those whose code (``versions``) is not the one the previous publication remembers of the competition (``remembered``,
    empty when its memory is not to be trusted), or of a competition it never published. When the code is the same, whether they are computed depends on the data, as before."""
    tasks: List[Task] = []
    for name in names:
        old = (remembered.get(name) or {}).get("versions") or {}
        tasks += [(name, section) for section in sections if section in versions and old.get(section) != versions[section]]
    return tasks


def _from_the_shared_handler(task: Task) -> Payload:
    from src.database.shared_handler import shared_handler
    from src.local_data.sections import section_payload

    name, section = task
    handler = shared_handler()
    return section_payload(section, handler, handler.connection.client["BASKETBALL"], name)


def _timed(compute: Callable[[Task], Payload], task: Task) -> Computed:
    started = time.time()
    return task, compute(task), time.time() - started


def in_processes(workers: int, compute: Callable[[Task], Payload] = _from_the_shared_handler) -> Runner:
    """A runner of the tasks in ``workers`` processes; the results come as they are done. A task that fails stops the rest (what has not started is cancelled) and fails the
    publication, as it would in series: nothing is published half done (``web-data.yml`` publishes only after a successful build)."""
    def run(tasks: List[Task]) -> Iterator[Computed]:
        if not tasks:
            return
        pool = ProcessPoolExecutor(max_workers=max(1, min(workers, len(tasks))), mp_context=get_context("spawn"))
        try:
            pending = {pool.submit(_timed, compute, task) for task in tasks}
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)     # each one as soon as it is done (a failure too): the payloads are not held until the end
                for future in done:
                    yield future.result()
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
    return run


def precompute(tasks: List[Task], runner: Runner, seal: Callable[[Task, Payload], Optional[Dict[str, Any]]],
               on_section: Optional[Callable[[str, str, float, bool], None]]) -> Dict[Task, Optional[Dict[str, Any]]]:
    """The entry of every task, sealed as its payload arrives (the payload is not kept: only the entry), and what each cost to ``on_section``."""
    entries: Dict[Task, Optional[Dict[str, Any]]] = {}
    for task, payload, seconds in runner(tasks):
        entries[task] = seal(task, payload)
        if on_section:
            on_section(task[0], task[1], seconds, False)
    return entries
