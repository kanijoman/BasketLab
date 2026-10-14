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


def engine_version(root: Optional[Union[str, Path]] = None) -> str:
    """Eight hex characters identifying the ``*.py`` modules of ``root`` (by default, this package)."""
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(base.glob("*.py"), key=lambda p: p.name):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()[:_LENGTH]
