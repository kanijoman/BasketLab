"""Link the players of an external source to the persons of FEB (#885): ``python run_identity_links.py --ext DIR [--source fiba]`` or ``--source fbcyl --archive DIR --ext DIR`` (#978).

Reads the games of ``DIR/<source>/*.jsonl.gz`` (the archive of the external sources, ``basketlab-archive-ext``) and the FEB rosters of ``DIR/rosters/`` (``run_roster_sweep.py``), links them by date of birth and
name (``src/market/identity_link``) and writes ``DIR/links/<source>.json``: the links sorted, no timestamp, so a repeated run changes no byte. Prints how many are linked and how many go to review.

FBCYL has no date of birth: its games and the FEB ones come from ``--archive`` (the private ``basketlab-archive``), the sex of the FEB competitions and the category of the FBCYL ones from the catalogue
(``--catalogue``) and the full name and birth of the FEB persons from ``DIR/rosters/``; the link is by name key, sex, category and the club or the full name with a birth that fits.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def _games(folder: Path) -> Iterator[Dict[str, Any]]:
    for path in sorted(folder.glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def _archive_games(folder: Path, fbcyl: bool) -> Iterator[Dict[str, Any]]:
    """The games of the archive of FEB and FBCYL: the collections ``FBCYL_*`` (``fbcyl``) or all the others."""
    for path in sorted(folder.glob("*.jsonl.gz")):
        if path.name.startswith("COLLECTION_META") or path.name.startswith("FBCYL_") != fbcyl:
            continue
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def main(argv: Optional[List[str]] = None) -> int:
    from src.market.identity_link import external_players, fbcyl_age_groups, fbcyl_players, feb_genders, feb_persons, link_fbcyl, link_players
    from src.market.roster_store import read_rosters
    from src.services.competition_catalogue import DEFAULT_CATALOGUE

    parser = argparse.ArgumentParser(description="Link the players of an external source to FEB")
    parser.add_argument("--ext", required=True, help="folder of the external archive (it has <source>/ and rosters/)")
    parser.add_argument("--source", default="fiba")
    parser.add_argument("--archive", help="folder of the archive of FEB and FBCYL (for --source fbcyl)")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE, help="the catalogue of competitions (sex of the FEB ones, category of the FBCYL ones)")
    args = parser.parse_args(argv)
    root = Path(args.ext)
    if args.source == "fbcyl":
        if not args.archive or not Path(args.archive).is_dir():
            print("--source fbcyl needs --archive with the games of FEB and FBCYL")
            return 1
        folder, catalogue = Path(args.archive), json.loads(Path(args.catalogue).read_text(encoding="utf-8"))["competitions"]
        persons = feb_persons(_archive_games(folder, False), rosters=read_rosters(root / "rosters"), genders=feb_genders(catalogue))
        links = link_fbcyl(persons, fbcyl_players(_archive_games(folder, True), fbcyl_age_groups(catalogue)))
    elif not (root / args.source).is_dir():
        print(f"no archive of {args.source} in {root}")
        return 1
    else:
        links = link_players(read_rosters(root / "rosters"), external_players(_games(root / args.source)))
    out = root / "links"
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{args.source}.json"
    text = json.dumps({"format": 1, "source": args.source, "links": links}, ensure_ascii=False, indent=1) + "\n"
    if not target.is_file() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")
    print(f"{args.source}: {sum(1 for l in links if l['status'] == 'linked')} linked, {sum(1 for l in links if l['status'] == 'review')} to review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
