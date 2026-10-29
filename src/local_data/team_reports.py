"""Team reports precomputed and sealed by scope (issue #638, class B of the local-first spike #327).

The first user (the staff) reads the analysis of its team and the scouting of its rivals; both are deterministic per team and week, so they
are computed here with the report service of the API, once per competition, and published as files that need no server. A report is sealed
once with a random key (``package_scopes``) and the key is wrapped for the scopes that may read it: access is the wraps, never a re-encryption.
A file is only rewritten when its report changed (sealing is random: rewriting all on every refresh would invalidate every cache).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from src.live_prep.package_sealing import Sealer
from src.local_data.export import file_name

MODES = ("own", "rival")
INDEX = "index.json"


def report_scopes(mode: str, team_id: str, team_ids: Sequence[str], collection: str) -> List[str]:
    """Who may read a report: its own team's analysis, the club itself; a rival scouting, every club of the competition (it is the scouting
    each of them asks for); both, the key of the competition. The levels and prices are decided later (#591): changing them is changing this."""
    competition = f"competicion:{collection}"
    if mode == "own":
        return [f"club:{team_id}", competition]
    return [competition] + [f"club:{t}" for t in team_ids]


class _Memo:
    """Reads of the season shared by every report of a competition (each would otherwise load the whole season again); callers get copies."""

    def __init__(self, target: Any) -> None:
        self._target, self._cache = target, {}

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        def call(*args: Any, **kwargs: Any) -> Any:
            key = (name, args, tuple(sorted(kwargs.items())))
            if key not in self._cache:
                self._cache[key] = attr(*args, **kwargs)
            return copy.deepcopy(self._cache[key])

        return call


def build_reports(handler: Any, collection: str) -> Iterator[Tuple[str, str, str, Dict[str, Any]]]:
    """``(team_id, team name, mode, report)`` for every team of the competition and both modes; the season is read once."""
    from src.services.team_report_service import TeamNotFoundError, TeamReportService
    from src.services.team_stats_service import TeamStatsService

    stats = _Memo(TeamStatsService(handler))
    pbp = _Memo(TeamReportService(handler, stats=stats))._load_pbp
    service = TeamReportService(handler, stats=stats, pbp=pbp)
    for team in stats.get_teams_with_ids(collection):
        for mode in MODES:
            try:
                yield str(team["id"]), team["name"], mode, service.build(collection, str(team["id"]), mode)
            except TeamNotFoundError:
                continue                                              # listed in a game but without stats: nothing to say about it


def _dump(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)


def publish_reports(handler: Any, collections: Sequence[str], out_dir: Path, sealer: Sealer, previous: Optional[Dict[str, Any]] = None,
                    on_collection: Optional[Callable[[str, int], None]] = None) -> Dict[str, Any]:
    """Write one sealed file per team and mode of each collection and ``index.json`` (returned); ``previous`` (default: the index already in
    ``out_dir``) lets an unchanged report keep its file. Files of reports that no longer exist are removed."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if previous is None and (out_dir / INDEX).is_file():
        previous = json.loads((out_dir / INDEX).read_text(encoding="utf-8"))
    old = {(e["collection"], e["team_id"], e["mode"]): e for e in (previous or {}).get("reports", [])}
    entries: List[Dict[str, Any]] = []
    for collection in collections:
        built = list(build_reports(handler, collection))
        team_ids = sorted({tid for tid, _n, _m, _r in built})
        for team_id, name, mode, report in built:
            plain = _dump(report)
            sha = hashlib.sha256(plain.encode("utf-8")).hexdigest()
            scopes = sealer.scopes_for(report_scopes(mode, team_id, team_ids, collection)) if hasattr(sealer, "scopes_for") else []
            file = file_name(f"{collection}|{mode}|{team_id}")
            kept = old.get((collection, team_id, mode))
            if kept and kept["sha256"] == sha and (out_dir / kept["file"]).is_file() and [w["scope"] for w in kept.get("wraps", [])] == scopes:
                entries.append(kept)
                continue
            envelope, extra = sealer.seal(plain, report_scopes(mode, team_id, team_ids, collection), compress=True)
            data = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
            (out_dir / file).write_bytes(data)
            entries.append({"collection": collection, "team_id": team_id, "team": name, "mode": mode, "file": file, "bytes": len(data), "sha256": sha, **extra})
        if on_collection:
            on_collection(collection, len(built))
    index = {"v": sealer.index_version, **sealer.index_extra(), "reports": entries}
    keep = {e["file"] for e in entries} | {INDEX}
    for stale in out_dir.glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
    (out_dir / INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return index
