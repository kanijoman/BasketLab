"""Publish the live preparation packages of the club's upcoming matches (issue #175).

``python -m src.live_prep.publisher --out <dir>`` finds the next matches of ``team_id`` in the competitions
of ``config/atlas_refresh.json``, builds one encrypted package per upcoming rival and writes
``<dir>/<team_id>/<rival_id>.bpkg`` plus ``<dir>/index.json``. The workflow ``live-packages.yml`` pushes that
directory to the ``live-packages`` branch, which the app reads through raw.githubusercontent.com.
With ``"rounds": true`` (the default) it also writes, for EVERY competition kept fresh by the Atlas refresh, one compressed encrypted
bundle with the packages of all the matches of its next round (``rounds/<collection>__r<round>.bpkgz``, see ``round_packages``) and lists
them under ``rounds`` in the index (issues #286, #172); an app that predates it only reads ``packages``.
Exit code 2 when the password (``PACKAGE_PASSWORD``, >= 8 characters) or the connection is missing.
The config's ``access`` chooses how it is encrypted (issue #410, ``package_sealing``): ``legacy`` (password, what the apps in the field read)
or ``scoped`` (open to the beta with a key in the index, paid scopes for later; index v2).
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .package_sealing import Sealer, as_sealer, make_sealer

DEFAULT_CONFIG = "config/package_publish.json"
MIN_PASSPHRASE = 8
INDEX_VERSION = 1
ACCESS_MODES = ("legacy", "scoped")
DEFAULT_ACCESS = {"mode": "legacy", "open": True, "monthly": False, "scopes": []}
CALENDAR_WINDOW = 30  # matches asked to the calendar per collection before picking the nearest rivals


def load_config(path: Any = DEFAULT_CONFIG) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("team_id"):
        raise ValueError("config lacks: team_id")
    access = {**DEFAULT_ACCESS, **(data.get("access") or {})}
    if access["mode"] not in ACCESS_MODES:
        raise ValueError(f"access.mode must be one of {ACCESS_MODES}")
    access = {"mode": access["mode"], "open": bool(access["open"]), "monthly": bool(access["monthly"]), "scopes": [str(s) for s in access["scopes"]]}
    return {"team_id": str(data["team_id"]), "upcoming": int(data.get("upcoming", 3)), "rounds": bool(data.get("rounds", True)), "access": access}


def build_index(packages: List[Dict[str, Any]], now: Optional[str] = None, rounds: Optional[List[Dict[str, Any]]] = None,
                club_team_id: Optional[str] = None, sealer: Optional[Sealer] = None) -> Dict[str, Any]:
    version = sealer.index_version if sealer else INDEX_VERSION
    index: Dict[str, Any] = {"v": version, "generated_at": now or datetime.now(timezone.utc).isoformat(), **(sealer.index_extra() if sealer else {}),
                             "packages": packages}
    if rounds is not None:
        index.update({"rounds": rounds, "club_team_id": club_team_id})
    return index


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


# The branch is served by raw.githubusercontent.com, not by Vercel; its Git integration would otherwise try (and fail,
# the project's root directory is ``frontend``) to build it on every publish. ``frontend/vercel.json`` makes that
# directory exist and switches the branch's deployments off.
VERCEL_GUARD = {"git": {"deploymentEnabled": False}}


def _write_vercel_guard(out: Path) -> None:
    guard = out / "frontend"
    guard.mkdir(parents=True, exist_ok=True)
    (guard / "vercel.json").write_text(json.dumps(VERCEL_GUARD, indent=1), encoding="utf-8")


def _remove_stale(team_dir: Path) -> None:
    for old in team_dir.glob("*.bpkg"):
        old.unlink()


def publish_all(db: Any, out: Any, passphrase: Any, collections: List[str], team_id: str,
                service: Any = None, build: Optional[Callable[..., Any]] = None, upcoming: int = 3,
                errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Write the packages and the index; a rival whose package fails is reported in ``errors`` and skipped."""
    from src.live_prep.db_source import build_package_from_db
    from src.live_prep.roster_fetcher import fetch_rosters
    from src.services.match_schedule_service import MatchScheduleService

    sealer = as_sealer(passphrase)
    service = service or MatchScheduleService(db)
    build = build or functools.partial(build_package_from_db, roster_source=fetch_rosters)
    out = Path(out)
    team_dir = out / team_id
    team_dir.mkdir(parents=True, exist_ok=True)
    _remove_stale(team_dir)
    entries: List[Dict[str, Any]] = []
    for collection, match in _next_rivals(service, collections, team_id, upcoming):
        rival = match["opponent"]
        try:
            package = build(db, collection, team_id, rival["id"], competition_meta={"match": _match_meta(match)})
            envelope, extra = sealer.seal(package.dumps(), [f"club:{team_id}", f"competicion:{collection}"])
            content = json.dumps(envelope, separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001 - one rival must not block the others
            if errors is not None:
                errors.append(f"{rival['id']} ({rival['name']}): {type(exc).__name__}: {exc}")
            continue
        (team_dir / f"{rival['id']}.bpkg").write_text(content, encoding="utf-8")
        entries.append({
            "team_id": team_id, "rival_id": rival["id"], "rival": rival["name"], "collection": collection,
            "match": _match_meta(match), "file": f"{team_id}/{rival['id']}.bpkg",
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(), "bytes": len(content.encode("utf-8")), **extra,
        })
    _write_vercel_guard(out)
    (out / "index.json").write_text(json.dumps(build_index(entries, sealer=sealer), ensure_ascii=False, indent=1), encoding="utf-8")
    return entries


def publish_round_bundles(db: Any, out: Any, passphrase: Any, collections: List[str], team_id: str, service: Any = None,
                          build: Optional[Callable[..., Any]] = None, errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """One bundle per competition with every match of its next round; a competition that fails is reported in ``errors`` and skipped."""
    from src.live_prep.roster_fetcher import fetch_rosters
    from src.live_prep.round_packages import ROUNDS_DIR, build_round_packages_from_db, publish_rounds
    from src.services.match_schedule_service import MatchScheduleService

    service = service or MatchScheduleService(db)
    build = build or functools.partial(build_round_packages_from_db, roster_source=fetch_rosters)
    out = Path(out)
    for old in (out / ROUNDS_DIR).glob("*.bpkgz"):
        old.unlink()
    entries: List[Dict[str, Any]] = []
    for collection in collections:
        try:
            upcoming = service.next_round(collection)
            if not upcoming["matches"]:
                continue
            built = build(db, collection, upcoming["matches"], club_team_id=team_id)
            entries.append(publish_rounds(out, passphrase, collection, upcoming["round"], built, team_id))
        except Exception as exc:  # noqa: BLE001 - one competition must not block the others
            if errors is not None:
                errors.append(f"{collection}: {type(exc).__name__}: {exc}")
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
    config = load_config(args.config)
    try:
        sealer = make_sealer(config["access"], os.environ)
    except ValueError as exc:
        print(f"{exc} (GitHub secret)", file=sys.stderr)
        return 2
    if not os.environ.get("MONGODB_CONNECTION_STRING"):
        print("MONGODB_CONNECTION_STRING is not set (GitHub secret ATLAS_READ_URI / ATLAS_WRITE_URI)", file=sys.stderr)
        return 2
    from src.database import MongoDBHandler

    db = MongoDBHandler()
    if not db.is_connected():
        print("No se pudo conectar a la base de datos", file=sys.stderr)
        return 2
    errors: List[str] = []
    entries = publish_all(db, args.out, sealer, _collections(), config["team_id"],
                          upcoming=config["upcoming"], errors=errors)
    rounds: List[Dict[str, Any]] = []
    if config["rounds"]:
        rounds = publish_round_bundles(db, args.out, sealer, _collections(), config["team_id"], errors=errors)
        (Path(args.out) / "index.json").write_text(
            json.dumps(build_index(entries, rounds=rounds, club_team_id=config["team_id"], sealer=sealer), ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# Paquetes live ({len(entries)})", ""]
    lines += [f"- {e['match']['start']} · {e['rival']} · {e['bytes'] // 1024} KB" for e in entries]
    lines += ["", f"## Jornadas completas ({len(rounds)})", ""]
    lines += [f"- {r['collection']} · jornada {r['round']} · {len(r['matches'])} partidos · {r['bytes'] // 1024} KB" for r in rounds]
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
