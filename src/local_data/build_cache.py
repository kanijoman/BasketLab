"""What the last publication was made of (#700), so a refresh computes only the competitions that changed.

``build-cache.json`` sits in the publication next to the manifest and holds, per competition, a fingerprint of its inputs (the sha of its sealed rows and of its derived
figures) and the sections that had something to publish, plus the version of the code that made them. It has hashes only, nothing readable. A competition whose fingerprint
and code are the same reuses its sealed files; anything else (new or corrected game, new code, a missing or unreadable memory, a file that is gone) is computed again.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

CACHE = "build-cache.json"
_SRC = Path(__file__).resolve().parent.parent
_OUT_OF_THE_BUILD = {"api"}          # the routers do not shape a published file (the exporters call the same service functions the routers do)


def code_version() -> str:
    """The hash of the Python of ``src`` that can shape a published file: any change in it makes the next publication compute everything again (the safe side)."""
    digest = hashlib.sha256()
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC)
        if relative.parts[0] in _OUT_OF_THE_BUILD or "__pycache__" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:16]


def fingerprint(rows_sha: str, derived_sha: Optional[str]) -> str:
    return hashlib.sha256(f"{rows_sha}|{derived_sha or ''}".encode("utf-8")).hexdigest()


def load(out_dir: Path) -> Dict[str, Any]:
    """The memory of the previous publication; empty when it is missing or is not what this code writes."""
    try:
        data = json.loads((Path(out_dir) / CACHE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"code": None, "competitions": {}}
    if not isinstance(data, dict) or not isinstance(data.get("competitions"), dict):
        return {"code": None, "competitions": {}}
    return {"code": data.get("code"), "competitions": {k: v for k, v in data["competitions"].items() if isinstance(v, dict)}}


def save(out_dir: Path, code: str, competitions: Dict[str, Dict[str, Any]]) -> bytes:
    return (json.dumps({"code": code, "competitions": {k: competitions[k] for k in sorted(competitions)}}, indent=1) + "\n").encode("utf-8")
