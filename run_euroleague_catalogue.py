"""Add the Euroleague competitions to the catalogue, paused (#1038): ``python run_euroleague_catalogue.py [--dry-run]``.

Asks the public API of the Euroleague (the seasons of the EuroLeague, the EuroCup and the U18 Next Generation Tournament, ``src/external/euroleague_catalogue``; no key) and appends to
``config/competitions.json`` an entry, ``active: false``, for every season since 2017/18 (2019/20 the U18 ones) that exists and lists games. What is already in the file is not touched (the file is written as it
was: two spaces, accents as they are, so the diff has only what was added) and nothing is turned on: setting ``active: true`` on an entry is what makes the daily refresh of the external sources start loading it
(``run_catalogue_activate.py --season 2025 --league euroleague``). Exit code 1 if a season failed to answer (what could be added is added; run it again).
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
    from src.external.euroleague_catalogue import new_entries
    from src.external.euroleague_client import EuroleagueClient
    from src.services.competition_catalogue import DEFAULT_CATALOGUE

    parser = argparse.ArgumentParser(description="Add the Euroleague competitions to the catalogue, paused")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    parser.add_argument("--dry-run", action="store_true", help="say what would be added and write nothing")
    args = parser.parse_args(argv)
    path = Path(args.catalogue)
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries, report = new_entries(client or EuroleagueClient(), raw.get("competitions", []), today or date.today().strftime("%d/%m/%Y"))
    for entry in entries:
        print(f"{'would add' if args.dry_run else 'adds'}: {entry['note']}")
    for key in ("already", "empty"):
        if report[key]:
            print(f"{key}: {', '.join(report[key])}")
    for season, reason in report["failed"].items():
        print(f"FAILED: season {season}: {reason}")
    if entries and not args.dry_run:
        raw["competitions"] = [*raw.get("competitions", []), *entries]
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
