"""What the processes of ``tests/test_local_web_data_parallel.py`` compute (#945): top-level functions, so that a spawned process can import them by name."""
import os
import time


def who_computes(task):
    """The process that computed ``task``, and the task back."""
    return {"pid": os.getpid(), "task": list(task)}


def fails_on_lineups(task):
    """A section that breaks (an exporter that raises), and the rest slow enough to be still running."""
    if task[1] == "lineups":
        raise RuntimeError(f"{task[0]}: the lineups exporter failed")
    time.sleep(0.2)
    return {"task": list(task)}
