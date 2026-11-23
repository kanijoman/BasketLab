"""Add the NCAA D1 competitions to the catalogue, paused (#888, #966): ``python run_ncaa_catalogue.py --season 2025 [--season 2024 ...] [--dry-run]``.

Asks ESPN (``src/external/ncaa_catalogue``) for the conferences of each season (the year it STARTS in: 2025 is 2025/26) and sex, and adds to ``config/competitions.json`` an entry, ``active: false``,
for each conference that is not in the file yet. What is already there is not touched (the file is written with the accents as they are, so the diff has only what was added) and nothing is turned
on: setting ``active: true`` is what makes the daily refresh of the external sources start with it. Exit code 1 when a sex could not be read (what could be added is added; run it again).
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
    from src.external.ncaa_catalogue import new_entries
    from src.external.ncaa_client import NcaaClient
    from src.services.competition_catalogue import DEFAULT_CATALOGUE

    parser = argparse.ArgumentParser(description="Add the NCAA D1 competitions to the catalogue, paused")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    parser.add_argument("--season", type=int, action="append", required=True, help="the year the season starts in (2025 is 2025/26); repeat it for several")
    parser.add_argument("--dry-run", action="store_true", help="say what would be added and write nothing")
    args = parser.parse_args(argv)
    path = Path(args.catalogue)
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries, report = new_entries(client or NcaaClient(), raw.get("competitions", []), today or date.today().strftime("%d/%m/%Y"), sorted(set(args.season)))
    print(f"{'would add' if args.dry_run else 'adds'}: {len(entries)} entries ({len(report['already'])} already in the catalogue)")
    for gender, reason in report["failed"].items():
        print(f"FAILED: {gender}: {reason}")
    if entries and not args.dry_run:
        raw["competitions"] = [*raw.get("competitions", []), *entries]
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
