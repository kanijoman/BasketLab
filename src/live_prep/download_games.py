"""Download a FEB competition's games to a local folder (issue #301): ``python -m src.live_prep.download_games``.

One ``<match code>.json.gz`` per game with play-by-play, the very document the scraper would store in MongoDB (boxscore,
play-by-play and shot chart), so ``games_from_dir`` feeds the evaluators (``rule_evaluation --games-dir``,
``wp_cli --games-dir``) without a database. A run can be repeated or interrupted: games already in the folder are not
downloaded again. Without play-by-play a game is of no use to the engine and is not kept.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

LF_CHALLENGE_URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"
DEFAULT_DELAY_S = 0.5   # between matches: the website is somebody else's


def _scraper() -> Any:
    from src.scraper import FEBWebScraper

    return FEBWebScraper()


def _has_pbp(doc: Dict[str, Any]) -> bool:
    return bool((doc.get("PLAYBYPLAY") or {}).get("LINES"))


def _selected(groups: Sequence[Any], wanted: Optional[Sequence[str]]) -> List[Any]:
    """Groups whose label contains any of ``wanted`` (case-insensitive); all of them without a filter."""
    if not wanted:
        return list(groups)
    return [g for g in groups if any(w.lower() in g[0].lower() for w in wanted)]


def _save(path: Path, doc: Dict[str, Any], code: str) -> None:
    doc.setdefault("_id", code)
    path.write_bytes(gzip.compress(json.dumps(doc, ensure_ascii=False).encode("utf-8")))


def download_season(scraper: Any, url: str, season: str, out_dir: Path, groups: Optional[Sequence[str]] = None,
                    delay_s: float = 0.0, log: Any = None) -> Dict[str, Any]:
    """Save every game with play-by-play of one season (``season`` is the dropdown value, e.g. ``2025``) into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Any] = {"season": season, "groups": [], "saved": 0, "skipped": 0, "no_pbp": 0, "missing": 0, "errors": 0}
    chosen = _selected(scraper.get_groups_for_season(url, season), groups)
    if not chosen:
        return result
    _, session = scraper.get_page_content(season)
    for label, value in chosen:
        result["groups"].append(label)
        for code in scraper.get_matches(season, value, season, session, url=url):
            path = out_dir / f"{code}.json.gz"
            if path.exists():
                result["skipped"] += 1
                continue
            try:
                doc = scraper.fetch_boxscore(code, session)
            except Exception as exc:  # noqa: BLE001 - one broken match must not stop a season
                result["errors"] += 1
                if log:
                    log(f"  {code}: {exc}")
                continue
            if not doc:
                result["missing"] += 1     # not played yet, or the website has nothing
            elif not _has_pbp(doc):
                result["no_pbp"] += 1
            else:
                _save(path, doc, str(code))
                result["saved"] += 1
            if delay_s:
                time.sleep(delay_s)
        if log:
            log(f"  {label}: {result['saved']} guardados, {result['skipped']} ya estaban")
    return result


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.live_prep.download_games",
                                description="Download the games of a FEB competition to a folder of *.json.gz.")
    p.add_argument("--url", default=LF_CHALLENGE_URL, help="calendar page of the competition (default: LF Challenge)")
    p.add_argument("--season", action="append", required=True, metavar="YEAR",
                   help="season dropdown value, the year it starts (2025 = 2025/2026); repeatable, one subfolder each")
    p.add_argument("--out", required=True, help="folder to write into")
    p.add_argument("--groups", action="append", metavar="TEXT",
                   help="only groups whose name contains TEXT (e.g. regular, play-off); repeatable; default all")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY_S, help="seconds between matches")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    scraper = _scraper()
    total = 0
    for season in args.season:
        print(f"Temporada {season}", file=sys.stderr)
        result = download_season(scraper, args.url, season, Path(args.out) / season, args.groups, args.delay,
                                 lambda msg: print(msg, file=sys.stderr))
        total += result["saved"]
        print(json.dumps(result, ensure_ascii=False))
    print(f"{total} partidos nuevos", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
