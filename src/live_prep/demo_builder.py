"""Demo matches made from finished games (issue #441, epic #435): a recording the app replays as if it were live, and its package.

``python -m src.live_prep.demo_builder --collection <collection> --team <team id> [--code <match code>] [--out tests/recordings]``

``recording_pack`` only packs what the CI recorder saved from a LIVE match, so a team that has not played live yet had no demo for the beta
testers. Here a finished game of MongoDB becomes the same pack (``recorded_feed`` format): the polls the app would have received with FEB's
latency (``eval_feed.finished_game_polls``) plus a last frame with the finished game. The package is built from ONLY the games played before
that match, which is what the staff would have had. Without ``--code`` the match is chosen with the rule evaluator: the one where the team
gets the most different kinds of alerts after some history. Needs MongoDB; the roster comes from FEB's website (``--no-roster`` skips it).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.live_core.recording_builder import RecordingBuilder

from .eval_feed import GAME_CLOCK, finished_game_polls, timing_mode
from .eval_source import game_code, parse_starttime
from .package_builder import build_package

QUIET = ("info",)   # severities that do not make a match interesting to watch
MIN_PRIOR = 3


def _started(game: Dict[str, Any], first_t: float) -> str:
    if timing_mode(game) == GAME_CLOCK:
        start = parse_starttime(game)
        return (start or datetime(1970, 1, 1)).replace(tzinfo=timezone.utc).isoformat()
    return datetime.fromtimestamp(first_t, timezone.utc).isoformat()


def build_recording(game: Dict[str, Any], latency_s: float = 40.0, poll_s: float = 10.0) -> Dict[str, Any]:
    """The pack (``RecordedFeed`` format) of a finished game: the polls the app would have received, then the finished game itself."""
    polls = list(finished_game_polls(game, latency_s, poll_s))
    if not polls:
        raise ValueError(f"Game {game_code(game) or '?'} has no play-by-play: it cannot be a demo")
    builder = RecordingBuilder(game_code(game), _started(game, polls[0].t))
    for poll in polls:
        builder.add(round(poll.t - polls[0].t, 3), poll.doc)
    builder.add(round(polls[-1].t - polls[0].t + poll_s, 3), game)    # the match ends: status finished, final score, every line
    return builder.pack()


def _match_meta(game: Dict[str, Any]) -> Dict[str, Any]:
    teams = [{"id": str(t["id"]), "name": (t.get("name") or str(t["id"])).strip()} for t in game["HEADER"]["TEAM"]]
    start = parse_starttime(game)
    return {"code": game_code(game), "start": start.strftime("%Y-%m-%dT%H:%M") if start else None,
            "round": (game["HEADER"].get("round") or None), "home": teams[0], "away": teams[1]}


def wants_roster(collection: str, no_roster: bool) -> bool:
    """FEB's roster (who is a "formación" player) only exists for FEB collections."""
    from src.utils.collection_utils import is_fbcyl

    return not no_roster and not is_fbcyl(collection)


def build_demo_package(games: Iterable[Dict[str, Any]], match: Dict[str, Any], collection: str, season: str, team_id: str, rival_id: str,
                       roster: Optional[Dict[str, Dict[str, Any]]] = None, rule_config: Optional[Dict[str, Any]] = None,
                       created_at: Optional[str] = None):
    """The package of ``team_id`` against ``rival_id`` built with the games played BEFORE ``match`` (``match`` is not among them)."""
    start = parse_starttime(match)
    before = [g for g in games if game_code(g) != game_code(match) and (start is None or (parse_starttime(g) or start) < start)]
    meta: Dict[str, Any] = {"match": _match_meta(match)}
    if (match.get("HEADER") or {}).get("source") == "fbcyl":
        meta["data_quality"] = "experimental"      # FBCYL's play-by-play is annotated by the clubs: errors the feed does not fix (DATA_FORMATS)
    return build_package(before, collection, season, team_id, rival_id, competition_meta=meta,
                         created_at=created_at or (start or datetime.now()).strftime("%Y-%m-%dT%H:%M:%SZ"), roster=roster, rule_config=rule_config)


def best_match(evaluation: Any, team_id: str, min_prior: int = MIN_PRIOR) -> str:
    """Code of the game most worth showing: the most different alert ids beyond information, among those with at least ``min_prior`` earlier games
    (or the most history the team has, when it has less); a tie goes to the latest."""
    games = [g for g in evaluation.team_games if g["team"] == team_id]
    if not games:
        raise ValueError(f"No games of the team {team_id} were evaluated")
    need = min(min_prior, max(g["prior"] for g in games))      # a team with less history than that is shown with the most it has
    seasoned = [g for g in games if g["prior"] >= need]
    kinds: Dict[str, set] = {}
    for row in evaluation.rows:
        if row["team"] == team_id and row["severity"] not in QUIET:
            kinds.setdefault(str(row["game"]), set()).add(row["id"])
    order = {g["game"]: n for n, g in enumerate(games)}
    return max((g["game"] for g in seasoned), key=lambda code: (len(kinds.get(code, ())), order[code]))


def write_demo(out: Any, code: str, recording: Dict[str, Any], package: Any) -> List[Path]:
    """``<code>.rec.json.gz`` and ``<code>.package.json``: what ``scripts/sync-engine.mjs`` bundles in the app."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rec, pkg = out / f"{code}.rec.json.gz", out / f"{code}.package.json"
    rec.write_bytes(gzip.compress(json.dumps(recording, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
    pkg.write_text(package.dumps(), encoding="utf-8")
    return [rec, pkg]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a demo match (recording + package) from a finished game of MongoDB")
    parser.add_argument("--collection", required=True)
    parser.add_argument("--team", required=True, help="team id whose point of view the demo has")
    parser.add_argument("--code", help="match code (default: the most interesting one, chosen with the rule evaluator)")
    parser.add_argument("--out", default="tests/recordings")
    parser.add_argument("--no-roster", action="store_true", help="do not ask FEB for the roster (the formation rule is then off; FBCYL never has one)")
    args = parser.parse_args(argv)

    from src.database import MongoDBHandler

    from .eval_source import games_from_mongo
    from .rule_evaluation import evaluate

    handler = MongoDBHandler()
    games = list(games_from_mongo(handler, args.collection))
    code = args.code or best_match(evaluate(games, collection=args.collection, team=args.team, min_prior_games=0), args.team)
    match = next((g for g in games if game_code(g) == str(code)), None)
    if match is None:
        print(f"Game {code} is not in {args.collection}", file=sys.stderr)
        return 1
    ids = [str(t["id"]) for t in match["HEADER"]["TEAM"]]
    if args.team not in ids:
        print(f"Team {args.team} does not play game {code}", file=sys.stderr)
        return 1
    rival = next(i for i in ids if i != args.team)
    roster = None
    if wants_roster(args.collection, args.no_roster):
        from .roster_fetcher import fetch_rosters

        roster = fetch_rosters([args.team, rival])
    season = str(match.get("_season") or args.collection)
    package = build_demo_package(games, match, args.collection, season, args.team, rival, roster=roster)
    files = write_demo(args.out, str(code), build_recording(match), package)
    print(f"{code}: {' + '.join(f.name for f in files)} (games before: {package.baselines['sample_games']['league']}, roster: {len(roster or {})} players)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
