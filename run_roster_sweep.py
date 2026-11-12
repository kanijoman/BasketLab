"""Entry point of the daily roster sweep (#905): ``python run_roster_sweep.py --out DIR [--seasons 2025,2024] [--budget N]``.

Asks the FEB for the roster of the teams of the archive (birth date, height, position, nationality, formation, full name) and merges what it answers into ``DIR`` (``rosters/<season>.json`` of the
private ``basketlab-archive-ext``; ``src/market/roster_run``): the current season whole every day, the closed seasons once, at most ``--budget`` teams of them per run (a first load of several
seasons is more than one run should hold; the next run goes on). The games come from the archive restored into an ephemeral Mongo (``MONGODB_CONNECTION_STRING``), only their team ids are read.
Exit code 1 when nothing answered at all (FEB down or the page changed: a red run is how that gets noticed), 2 without a connection.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

DEFAULT_BUDGET = 1500        # closed-season teams per run: about 40 minutes at one request per second and a half


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sweep the FEB rosters into the folder rosters/ of basketlab-archive-ext")
    parser.add_argument("--out", required=True, help="the rosters/ folder")
    parser.add_argument("--seasons", help="only these seasons (comma separated, the year they start in: 2025)")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="closed-season teams per run (the current season is always swept whole)")
    args = parser.parse_args(argv)

    from src.database.shared_handler import shared_handler
    from src.market.roster_run import sweep_into, teams_by_season
    from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue
    from src.services.derived_backfill import feb_collection_names

    handler = shared_handler()
    if not handler.is_connected():
        print("No se pudo conectar a la base de datos", file=sys.stderr)
        return 2
    db = handler.connection.client["BASKETBALL"]
    teams = teams_by_season(handler.connection, sorted(feb_collection_names(db)), load_catalogue(DEFAULT_CATALOGUE))
    started = time.time()
    seasons = [s.strip() for s in (args.seasons or "").split(",") if s.strip()]
    print(f"{sum(len(t) for t in teams.values())} teams in {len(teams)} seasons ({', '.join(sorted(teams, reverse=True))})", flush=True)
    summary = sweep_into(args.out, teams, seasons=seasons or None, budget=args.budget)
    print(f"asked {summary['planned']} teams, {summary['swept']} answered, {len(summary['missing'])} did not, {summary['left']} closed-season teams left for the next run, "
          f"files changed: {', '.join(summary['changed']) or 'none'} ({time.time() - started:.0f} s)")
    if summary["missing"]:
        print("did not answer (asked again next run): " + ", ".join(f"{s}/{t}" for s, t in summary["missing"][:40]) + (" ..." if len(summary["missing"]) > 40 else ""))
    return 1 if summary["planned"] and not summary["swept"] else 0


if __name__ == "__main__":
    sys.exit(main())
