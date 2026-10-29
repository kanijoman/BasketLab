"""What the refresh publishes for the web (#328, #640): the ``web-data`` branch, read through a static host with no server.

``index.json`` is the manifest (the only file that keeps its name): ``schema`` of the contract, ``v`` and ``open_key`` of the sealing (same index as
the live packages), the ``rows`` of each competition (the contract of ``export``) and, per competition, the index of its ``reports`` (``team_reports``).
Everything but the manifest is sealed by scope and named after the hash of its content, so a file never changes in place: a client holding an older
manifest finds either the old file or a 404, never a mix. The previous publication in ``out_dir`` is the base of the next one: what did not change
keeps its bytes (sealing is random), what is no longer referenced is removed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.live_prep.package_sealing import Sealer
from src.live_prep.publisher import VERCEL_GUARD
from src.local_data.export import export_collection, file_name
from src.local_data.team_reports import seal_file, seal_reports

SCHEMA = 1
INDEX = "index.json"
ROWS, REPORTS = "rows/", "reports/"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _read(path: Path) -> Optional[Dict[str, Any]]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return manifest if manifest.get("schema") == SCHEMA else None


def _write_if_changed(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def _previous_reports(out_dir: Path, manifest: Optional[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]:
    """The entries of the reports already published, by ``(collection, team_id, mode)``."""
    old: Dict[Any, Dict[str, Any]] = {}
    for entry in (manifest or {}).get("reports", []):
        try:
            index = json.loads((out_dir / entry["file"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for report in index.get("reports", []):
            old[(entry["collection"], report["team_id"], report["mode"])] = {**report, "collection": entry["collection"]}
    return old


def _publish_rows(db: Any, collection: str, out_dir: Path, sealer: Sealer, kept: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = export_collection(db[collection], collection)
    fields = seal_file(out_dir, f"{collection}", _json(payload), [f"competicion:{collection}"], sealer, kept, ROWS)
    return {"collection": collection, "league": payload["league"], "games": payload["games"], **fields}


def _publish_report_index(handler: Any, collection: str, out_dir: Path, sealer: Sealer, old: Dict[Any, Dict[str, Any]]) -> Dict[str, Any]:
    """Seal the reports of a competition and write their index (plain: the wraps are not secret), named after its hash."""
    reports = [{k: v for k, v in e.items() if k != "collection"} for e in seal_reports(handler, collection, out_dir, sealer, old, REPORTS)]
    data = (_json({"collection": collection, "reports": reports}) + "\n").encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    file = REPORTS + file_name(f"{collection}|index|{sha[:12]}")
    _write_if_changed(out_dir / file, data)
    return {"collection": collection, "teams": len({r["team_id"] for r in reports}), "file": file, "bytes": len(data), "sha256": sha}


def _referenced(out_dir: Path, manifest: Dict[str, Any]) -> set:
    files = {INDEX, "frontend/vercel.json"}
    for entry in manifest["rows"]:
        files.add(entry["file"])
    for entry in manifest["reports"]:
        files.add(entry["file"])
        files.update(r["file"] for r in json.loads((out_dir / entry["file"]).read_text(encoding="utf-8"))["reports"])
    return files


def publish_web_data(handler: Any, out_dir: Path, sealer: Sealer, collections: Iterable[str], keep_others: bool = False,
                     on_collection: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Write the artifacts of ``collections`` and the manifest (returned). With ``keep_others`` the competitions of the previous publication that are
    not in ``collections`` stay as they were (a partial refresh); otherwise the directory mirrors ``collections``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    db = handler.connection.client["BASKETBALL"]
    names = list(collections)
    previous = _read(out_dir / INDEX)
    old_reports = _previous_reports(out_dir, previous)
    rows = {e["collection"]: e for e in (previous or {}).get("rows", []) if keep_others and e["collection"] not in names}
    reports = {e["collection"]: e for e in (previous or {}).get("reports", []) if keep_others and e["collection"] not in names}
    kept_rows = {e["collection"]: e for e in (previous or {}).get("rows", [])}
    for name in names:
        rows[name] = _publish_rows(db, name, out_dir, sealer, kept_rows.get(name))
        reports[name] = _publish_report_index(handler, name, out_dir, sealer, old_reports)
        if on_collection:
            on_collection(name)
    manifest = {"schema": SCHEMA, "v": sealer.index_version, **sealer.index_extra(),
                "rows": [rows[n] for n in sorted(rows)], "reports": [reports[n] for n in sorted(reports)]}
    _write_if_changed(out_dir / "frontend" / "vercel.json", json.dumps(VERCEL_GUARD, indent=1).encode("utf-8"))
    _write_if_changed(out_dir / INDEX, (_json(manifest) + "\n").encode("utf-8"))
    keep = _referenced(out_dir, manifest)
    for folder in (ROWS, REPORTS):
        for stale in (out_dir / folder).glob("*.json"):
            if f"{folder}{stale.name}" not in keep:
                stale.unlink()
    return manifest
