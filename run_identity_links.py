"""Link the players of an external source to the persons of FEB (#885): ``python run_identity_links.py --ext DIR [--source fiba]``.

Reads the games of ``DIR/<source>/*.jsonl.gz`` (the archive of the external sources, ``basketlab-archive-ext``) and the FEB rosters of ``DIR/rosters/`` (``run_roster_sweep.py``), links them by date of birth and
name (``src/market/identity_link``) and writes ``DIR/links/<source>.json``: the links sorted, no timestamp, so a repeated run changes no byte. Prints how many are linked and how many go to review.
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


def main(argv: Optional[List[str]] = None) -> int:
    from src.market.identity_link import external_players, link_players
    from src.market.roster_store import read_rosters

    parser = argparse.ArgumentParser(description="Link the players of an external source to FEB")
    parser.add_argument("--ext", required=True, help="folder of the external archive (it has <source>/ and rosters/)")
    parser.add_argument("--source", default="fiba")
    args = parser.parse_args(argv)
    root = Path(args.ext)
    if not (root / args.source).is_dir():
        print(f"no archive of {args.source} in {root}")
        return 1
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
