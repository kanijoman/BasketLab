"""One-off: rebuild tests/recordings/<code>.package.json (the package of a recorded demo match) with the CURRENT package schema.

    PYTHONPATH=".;src" python tests/recordings/make_package.py 2524470 [F|M]

Needs MongoDB (the competition of the match) and FEB's website (the rosters). It keeps the teams, the competition metadata and the
creation date of the existing package and rebuilds the tables from the games played BEFORE the match, so it is what the staff
would have had. The gender (``F``/``M``) goes in its ``rule_config``: the win probability is calibrated per family (#567), and a package that does not say it gets the generic values. Run it whenever the package schema grows (issue #315); tests/test_live_demo_package.py fails when it is stale.
"""
import sys
from datetime import datetime
from pathlib import Path

from src.database import MongoDBHandler
from src.live_core.package import PreparationPackage
from src.live_prep.eval_source import games_from_mongo, parse_starttime
from src.live_prep.package_builder import build_package
from src.live_prep.roster_fetcher import fetch_rosters

ROOT = Path(__file__).resolve().parent


def main(code: str, gender: str = "") -> None:
    path = ROOT / f"{code}.package.json"
    old = PreparationPackage.loads(path.read_text(encoding="utf-8"))
    match = (old.competition_meta or {}).get("match") or {}
    start = datetime.fromisoformat(match["start"])
    handler = MongoDBHandler()
    names = handler.repository.connection.db.list_collection_names()
    collection = old.collection if old.collection in names else next(n for n in names if n.startswith(old.collection[:12]))
    games = [g for g in games_from_mongo(handler, collection) if (parse_starttime(g) or start) < start]
    roster = fetch_rosters([old.team["id"], old.rival["id"]])
    package = build_package(games, collection, old.season, old.team["id"], old.rival["id"], competition_meta=old.competition_meta,
                            created_at=old.created_at, roster=roster, rule_config={**old.rule_config, **({"gender": gender} if gender else {})} or None)
    path.write_text(package.dumps(), encoding="utf-8")
    print(f"{path.name}: {len(games)} games before the match, roster of {len(roster or {})} players, tables {sorted(package.tables)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2524470", sys.argv[2] if len(sys.argv) > 2 else "")
