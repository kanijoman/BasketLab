"""The full scouting of the rival, sealed by scope and published in ``web-data`` (issue #638).

For each team of the competitions scouted ``ScoutingRivalService.build_scopes`` gives up to three reports (``liga``, ``copa``, ``todo``); each is sealed once
and its key wrapped for who may read a rival report (``team_reports.report_scopes``: every club of the competition and the competition itself).
Which competitions: the ones where a club of interest plays in the latest season (the club of the publisher config and the ``clubs`` of its catalog):
a scouting costs about ten seconds per team, so the three hundred senior teams are not scouted unless the list grows on purpose.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from src.live_prep.package_sealing import Sealer
from src.live_prep.scouting_scopes import _database, _feb_collections, is_cup, season_of
from src.local_data.team_reports import _dump, _Memo, report_scopes, seal_file


def interest_clubs(config: Optional[Dict[str, Any]] = None) -> Set[str]:
    """The ids of the clubs whose rivals are scouted: the club of the publisher and the ``clubs`` of every competition of its catalog."""
    if config is None:
        from src.live_prep.publisher import load_config

        config = load_config()
    clubs = {str(config["team_id"])} if config.get("team_id") else set()
    for competition in config.get("competitions", []):
        clubs |= {str(c) for c in competition.get("clubs") or []}
    return clubs


def scouting_collections(handler: Any, clubs: Iterable[str]) -> List[str]:
    """The league collections of the latest season where one of ``clubs`` plays, in name order (cups are scouted through the leagues of their teams)."""
    names = [n for n in _feb_collections(handler) if not is_cup(n) and season_of(n)]
    if not names:
        return []
    latest = max(season_of(n) for n in names)
    wanted = {str(c) for c in clubs}
    database = _database(handler)
    return [n for n in names if season_of(n) == latest and wanted & {str(t) for t in database[n].distinct("HEADER.TEAM.id")}]


def _default_service(handler: Any) -> Any:
    from src.services.scouting_rival_service import ScoutingRivalService
    from src.services.team_report_service import TeamReportService
    from src.services.team_stats_service import TeamStatsService

    stats = _Memo(TeamStatsService(handler))                    # the season is read once for every team of the competition
    return ScoutingRivalService(handler, stats=stats, report_service=TeamReportService(handler, stats=stats))


def seal_scouting(handler: Any, collection: str, out_dir: Any, sealer: Sealer, old: Dict[Any, Dict[str, Any]], subdir: str,
                  service_factory: Optional[Callable[[Any], Any]] = None, on_team: Optional[Callable[[str, str], None]] = None) -> List[Dict[str, Any]]:
    """The sealed scouting of every team of ``collection`` and the entries of its files (``mode: scouting`` and its ``scope``); ``old`` are the previous
    entries by ``(collection, team_id, mode, scope)``, so that an unchanged one keeps its bytes. A team without games with play-by-play has none."""
    from src.services.team_report_service import TeamNotFoundError

    service = (service_factory or _default_service)(handler)
    names = service.teams(collection)
    ids = sorted(names)
    entries: List[Dict[str, Any]] = []
    for team_id in ids:
        try:
            reports = service.build_scopes(collection, team_id)
        except (ValueError, TeamNotFoundError):
            continue                                            # listed in a game but never seen with play-by-play: nothing to scout
        for scope in sorted(reports):
            fields = seal_file(Path(out_dir), f"{collection}|scouting|{scope}|{team_id}", _dump(reports[scope]),
                               report_scopes("rival", team_id, ids, collection), sealer, old.get((collection, team_id, "scouting", scope)), subdir)
            entries.append({"collection": collection, "team_id": team_id, "team": names[team_id], "mode": "scouting", "scope": scope, **fields})
        if on_team:
            on_team(collection, team_id)
    return entries
