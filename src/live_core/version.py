"""The version of the engine (issue #226): a short hash of its own sources (standard library only).

The About screen of the app shows it and the diagnostics carry it, so a report says which engine ran. It is not a number to remember to raise:
it changes when any module of ``live_core`` changes (and when one is added or renamed), it is the same under pytest and in Pyodide on the
tablet, and the line endings of the checkout do not change it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Union

_LENGTH = 8

# What a match kept on the tablet (a finished match, a recording) was saved under (issue #562). Raise it, here AND in the app (feed/replayCompat.ts), when a change of the engine
# makes the replay of an older saved match unreliable (a duration, a lineup, a score read differently): the app warns about the matches kept under an older number and offers to delete them.
# It is not the hash above: that one changes with every edit and would flag every saved match every week. 1: until 0.4.0 (they carry no number); 2: 0.4.1 (duration of a replay, scores read from the header).
REPLAY_COMPAT = 2


def engine_version(root: Optional[Union[str, Path]] = None) -> str:
    """Eight hex characters identifying the ``*.py`` modules of ``root`` (by default, this package)."""
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(base.glob("*.py"), key=lambda p: p.name):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()[:_LENGTH]
