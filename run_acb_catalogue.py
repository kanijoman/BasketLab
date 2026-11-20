"""Add the ACB editions to the catalogue, paused (#886): ``python run_acb_catalogue.py [--dry-run]``.

Asks the API of ACB (the editions of the Liga Endesa and the clubs of each, ``src/external/acb_catalogue``; the key is read from the public JavaScript of the site on each run and never written) and appends to
``config/competitions.json`` an entry, ``active: false``, for every edition since 2019/20 that exists and lists clubs. What is already in the file is not touched (the file is written as it was: two spaces,
accents as they are, so the diff has only what was added) and nothing is turned on: setting ``active: true`` on an entry is what makes the daily refresh of the external sources start loading it. Exit code 1 if
an edition failed to answer (what could be added is added; run it again). The legal risk of using ACB is open (docs/evaluaciones/2026-11-20_acb-spike-886.md).
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
    from src.external.acb_catalogue import new_entries
    from src.external.acb_client import AcbClient
    from src.services.competition_catalogue import DEFAULT_CATALOGUE

    parser = argparse.ArgumentParser(description="Add the ACB editions to the catalogue, paused")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    parser.add_argument("--dry-run", action="store_true", help="say what would be added and write nothing")
    args = parser.parse_args(argv)
    path = Path(args.catalogue)
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries, report = new_entries(client or AcbClient(), raw.get("competitions", []), today or date.today().strftime("%d/%m/%Y"))
    for entry in entries:
        print(f"{'would add' if args.dry_run else 'adds'}: edition {entry['acb']['edition_id']} ({entry['note']})")
    for key in ("already", "empty", "missing"):
        if report[key]:
            print(f"{key}: {', '.join(str(i) for i in report[key])}")
    for edition, reason in report["failed"].items():
        print(f"FAILED: edition {edition}: {reason}")
    if entries and not args.dry_run:
        raw["competitions"] = [*raw.get("competitions", []), *entries]
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
