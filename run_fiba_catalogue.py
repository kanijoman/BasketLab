"""Add the FIBA events to the catalogue, paused (#887): ``python run_fiba_catalogue.py --year 2025 [--year 2026 ...] [--dry-run]``.

Asks the public site of FIBA (the event page of each candidate: the youth EuroBasket championships of both sexes, the U19 World Cup and the absolute EuroBasket, ``src/external/fiba_catalogue``), one request every 2 s,
and appends to ``config/competitions.json`` an entry, ``active: false``, for every event that exists and lists games. What is already in the file is not touched (the file is written as it was: two spaces, accents as
they are, so the diff has only what was added) and nothing is turned on: setting ``active: true`` on an entry is what makes the daily refresh of the external sources start loading it. Exit code 1 if an event
failed to answer (what could be added is added; run it again). See docs/OPERATIONS.md.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main(argv: Optional[List[str]] = None, client: Any = None, today: Optional[str] = None) -> int:
    from src.external.fiba_catalogue import new_entries
    from src.external.fiba_client import FibaClient
    from src.services.competition_catalogue import DEFAULT_CATALOGUE

    parser = argparse.ArgumentParser(description="Add the FIBA events to the catalogue, paused")
    parser.add_argument("--year", type=int, action="append", default=[], help="a year (the one of the event) of the national-team events; repeatable")
    parser.add_argument("--club-season", type=int, action="append", default=[], help="a season of the club competitions (EuroLeague Women, EuroCup Women), the year it starts in (2025 is 2025/26); repeatable")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    parser.add_argument("--dry-run", action="store_true", help="say what would be added and write nothing")
    args = parser.parse_args(argv)
    if not args.year and not args.club_season:
        parser.error("give at least one --year or --club-season")
    path = Path(args.catalogue)
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries, report = new_entries(client or FibaClient(), raw.get("competitions", []), args.year, today or date.today().strftime("%d/%m/%Y"), club_seasons=args.club_season)
    for entry in entries:
        print(f"{'would add' if args.dry_run else 'adds'}: {entry['fiba']['event']} ({entry['note']})")
    for key in ("already", "empty", "missing"):
        if report[key]:
            print(f"{key}: {', '.join(report[key])}")
    for slug, reason in report["failed"].items():
        print(f"FAILED: {slug}: {reason}")
    if entries and not args.dry_run:
        raw["competitions"] = [*raw.get("competitions", []), *entries]
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
