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


FLOAT_DIGITS = 9                                                  # the sums of a season differ in the 14th decimal with the order of the games


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, FLOAT_DIGITS)
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(v) for v in value]
    return value


def _dump(report: Dict[str, Any]) -> str:
    return json.dumps(_rounded(report), ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)


def seal_file(out_dir: Path, stem: str, plain: str, scopes: Sequence[str], sealer: Sealer, kept: Optional[Dict[str, Any]], subdir: str = "") -> Dict[str, Any]:
    """Seal ``plain`` into ``<stem>.<sha256 of plain>.json`` for ``scopes`` and return the index fields of the file (``file``, ``bytes``,
    ``sha256``, the wraps). The name carries the hash of the content, so it never changes in place; ``kept`` (the entry of the previous publication)
    keeps the same bytes when nothing changed, because sealing is random and rewriting it would invalidate every cache."""
    sha = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    file = subdir + file_name(f"{stem}|{sha[:12]}")                  # relative to ``out_dir``; ``subdir`` ends with "/"
    wanted = sealer.scopes_for(scopes) if hasattr(sealer, "scopes_for") else []
    if kept and kept["sha256"] == sha and kept["file"] == file and (out_dir / file).is_file() and [w["scope"] for w in kept.get("wraps", [])] == wanted:
        return {k: kept[k] for k in ("file", "bytes", "sha256", "wraps") if k in kept}
    envelope, extra = sealer.seal(plain, scopes, compress=True)
    data = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    (out_dir / file).parent.mkdir(parents=True, exist_ok=True)
    (out_dir / file).write_bytes(data)
    return {"file": file, "bytes": len(data), "sha256": sha, **extra}


def seal_reports(handler: Any, collection: str, out_dir: Path, sealer: Sealer, old: Dict[Any, Dict[str, Any]], subdir: str = "") -> List[Dict[str, Any]]:
    """The sealed files of every report of one competition (``old``: the previous entries by ``(collection, team_id, mode)``) and their entries."""
    built = list(build_reports(handler, collection))
    team_ids = sorted({tid for tid, _n, _m, _r in built})
    entries = []
    for team_id, name, mode, report in built:
        fields = seal_file(out_dir, f"{collection}|{mode}|{team_id}", _dump(report), report_scopes(mode, team_id, team_ids, collection), sealer,
                           old.get((collection, team_id, mode, None)), subdir)
        entries.append({"collection": collection, "team_id": team_id, "team": name, "mode": mode, **fields})
    return entries


def publish_reports(handler: Any, collections: Sequence[str], out_dir: Path, sealer: Sealer, previous: Optional[Dict[str, Any]] = None,
                    on_collection: Optional[Callable[[str, int], None]] = None) -> Dict[str, Any]:
    """Write one sealed file per team and mode of each collection and ``index.json`` (returned); ``previous`` (default: the index already in
    ``out_dir``) lets an unchanged report keep its file. Files of reports that no longer exist are removed."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if previous is None and (out_dir / INDEX).is_file():
        previous = json.loads((out_dir / INDEX).read_text(encoding="utf-8"))
    old = {(e["collection"], e["team_id"], e["mode"], e.get("scope")): e for e in (previous or {}).get("reports", [])}
    entries: List[Dict[str, Any]] = []
    for collection in collections:
        built = seal_reports(handler, collection, out_dir, sealer, old)
        entries.extend(built)
        if on_collection:
            on_collection(collection, len(built))
    index = {"v": sealer.index_version, **sealer.index_extra(), "reports": entries}
    keep = {e["file"] for e in entries} | {INDEX}
    for stale in out_dir.glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
    (out_dir / INDEX).write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return index
