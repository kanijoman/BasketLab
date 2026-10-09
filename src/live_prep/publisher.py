"""Publish the live preparation packages of the club's upcoming matches (issue #175).

``python -m src.live_prep.publisher --out <dir>`` finds the next matches of ``team_id`` in the competitions
of ``config/atlas_refresh.json``, builds one encrypted package per upcoming rival and writes
``<dir>/<team_id>/<rival_id>.bpkg`` plus ``<dir>/index.json``. The workflow ``live-packages.yml`` pushes that
directory to the ``live-packages`` branch, which the app reads through raw.githubusercontent.com.
Exit code 2 when the password (``PACKAGE_PASSWORD``, >= 8 characters) or the connection is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEFAULT_CONFIG = "config/package_publish.json"
MIN_PASSPHRASE = 8
INDEX_VERSION = 1
CALENDAR_WINDOW = 30  # matches asked to the calendar per collection before picking the nearest rivals


def load_config(path: Any = DEFAULT_CONFIG) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("team_id"):
        raise ValueError("config lacks: team_id")
    return {"team_id": str(data["team_id"]), "upcoming": int(data.get("upcoming", 3))}


def build_index(packages: List[Dict[str, Any]], now: Optional[str] = None) -> Dict[str, Any]:
    return {"v": INDEX_VERSION, "generated_at": now or datetime.now(timezone.utc).isoformat(), "packages": packages}


def _match_meta(match: Dict[str, Any]) -> Dict[str, Any]:
    return {k: match[k] for k in ("code", "start", "round", "home", "away")}


def _next_rivals(service: Any, collections: List[str], team_id: str, upcoming: int) -> List[tuple]:
    """``(collection, match)`` of the nearest match against each of the next ``upcoming`` rivals."""
    found = []
    for collection in collections:
        found += [(collection, m) for m in service.upcoming(collection, team_id, limit=CALENDAR_WINDOW)["matches"]
                  if m["status"] == "scheduled" and m.get("opponent")]
    found.sort(key=lambda item: item[1]["start"] or "")
    seen, chosen = set(), []
    for collection, match in found:
        if match["opponent"]["id"] not in seen:
            seen.add(match["opponent"]["id"])
            chosen.append((collection, match))
    return chosen[:upcoming]


def _remove_stale(team_dir: Path) -> None:
    for old in team_dir.glob("*.bpkg"):
        old.unlink()


def publish_all(db: Any, out: Any, passphrase: str, collections: List[str], team_id: str,
                service: Any = None, build: Optional[Callable[..., Any]] = None, upcoming: int = 3,
                errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Write the packages and the index; a rival whose package fails is reported in ``errors`` and skipped."""
    from src.live_prep.db_source import build_package_from_db
    from src.live_prep.package_crypto import encrypt_package
    from src.services.match_schedule_service import MatchScheduleService

    service = service or MatchScheduleService(db)
    build = build or build_package_from_db
    out = Path(out)
    team_dir = out / team_id
    team_dir.mkdir(parents=True, exist_ok=True)
    _remove_stale(team_dir)
    entries: List[Dict[str, Any]] = []
    for collection, match in _next_rivals(service, collections, team_id, upcoming):
        rival = match["opponent"]
        try:
            package = build(db, collection, team_id, rival["id"], competition_meta={"match": _match_meta(match)})
            content = json.dumps(encrypt_package(package.dumps(), passphrase), separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001 - one rival must not block the others
            if errors is not None:
                errors.append(f"{rival['id']} ({rival['name']}): {type(exc).__name__}: {exc}")
            continue
        (team_dir / f"{rival['id']}.bpkg").write_text(content, encoding="utf-8")
        entries.append({
            "team_id": team_id, "rival_id": rival["id"], "rival": rival["name"], "collection": collection,
            "match": _match_meta(match), "file": f"{team_id}/{rival['id']}.bpkg",
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(), "bytes": len(content.encode("utf-8")),
        })
    (out / "index.json").write_text(json.dumps(build_index(entries), ensure_ascii=False, indent=1), encoding="utf-8")
    return entries


def _collections() -> List[str]:
    """Collections of the competitions kept fresh by the Atlas refresh (single source of truth)."""
    from src.database import get_collection_name
    from src.services.atlas_refresh import load_config as load_refresh

    return [get_collection_name(e.competition_label, e.season_label, e.group_label) for e in load_refresh()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the encrypted live packages of the upcoming matches")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--out", default="live-packages")
    args = parser.parse_args(argv)
    passphrase = os.environ.get("PACKAGE_PASSWORD", "")
    if len(passphrase) < MIN_PASSPHRASE:
        print(f"PACKAGE_PASSWORD must have at least {MIN_PASSPHRASE} characters (GitHub secret)", file=sys.stderr)
        return 2
    if not os.environ.get("MONGODB_CONNECTION_STRING"):
        print("MONGODB_CONNECTION_STRING is not set (GitHub secret ATLAS_READ_URI / ATLAS_WRITE_URI)", file=sys.stderr)
        return 2
    config = load_config(args.config)
    from src.database import MongoDBHandler

    db = MongoDBHandler()
    if not db.is_connected():
        print("No se pudo conectar a la base de datos", file=sys.stderr)
        return 2
    errors: List[str] = []
    entries = publish_all(db, args.out, passphrase, _collections(), config["team_id"],
                          upcoming=config["upcoming"], errors=errors)
    lines = [f"# Paquetes live ({len(entries)})", ""]
    lines += [f"- {e['match']['start']} · {e['rival']} · {e['bytes'] // 1024} KB" for e in entries]
    lines += [f"- **Error**: {e}" for e in errors]
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
