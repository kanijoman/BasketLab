"""Command line of the rule evaluator (``python -m src.live_prep.rule_evaluation``)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.live_core.recorded_feed import RecordedFeed

from .eval_report import build_report

DEFAULT_OUT = "rule-evaluation"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.live_prep.rule_evaluation",
        description="Replay the competition's games as live, from both teams, through the alert engine and measure "
                    "every rule: alerts, duplicates, follow-up by the coach, outcome and coach behaviour.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--collection", help="MongoDB collection of a FEB competition (needs MONGODB_CONNECTION_STRING)")
    source.add_argument("--games-dir", help="folder with finished games as FEB documents (*.json or *.json.gz)")
    p.add_argument("--recording", action="append", default=[], metavar="FILE",
                   help="packed recording (*.rec.json.gz) replayed instead of the simulated feed of its match; repeatable")
    p.add_argument("--team", help="evaluate only this team's side (every team still feeds the season)")
    p.add_argument("--config", action="append", default=[], metavar="FILE",
                   help='JSON with {"name": ..., "rule_config": {...}} (or just the settings) to compare with the stock '
                        "configuration, which is always the baseline; repeatable")
    p.add_argument("--feedback", action="append", default=[], metavar="FILE", help="export of the app's feedback; repeatable")
    p.add_argument("--roster", action="store_true",
                   help="ask FEB for the roster of every team once (the current one) so the illegal-lineup rule can be measured")
    p.add_argument("--roster-file", metavar="FILE",
                   help="JSON with the roster ({player id: {team_id, formacion, ...}}, what a package carries in tables.roster): "
                        "no network; combined with --roster, FEB is asked only for the teams the file does not cover")
    p.add_argument("--season", default="", help="season label of the packages (default: read from the collection)")
    p.add_argument("--latency", type=float, default=40.0, help="seconds from FEB logging a line to the app seeing it")
    p.add_argument("--poll", type=float, default=10.0, help="seconds between the app's polls")
    p.add_argument("--follow-window", type=int, default=120, help="seconds after an alert that still count as following it")
    p.add_argument("--min-prior-games", type=int, default=3, help="skip sides whose team has fewer earlier games")
    p.add_argument("--out", default=DEFAULT_OUT, help="output folder (evaluation.json, alerts.jsonl, report.md)")
    return p


def _read_config(path: str):
    from .rule_evaluation import ConfigSpec

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: a configuration is a JSON object")
    overrides = data["rule_config"] if isinstance(data.get("rule_config"), dict) else {k: v for k, v in data.items() if k != "name"}
    return ConfigSpec(str(data.get("name") or Path(path).name.split(".")[0]), overrides)


def _read_roster(path: str) -> Dict[str, Dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path}: the roster file is not valid JSON ({exc})") from exc
    if not isinstance(data, dict) or not all(isinstance(v, dict) and v.get("team_id") is not None for v in data.values()):
        raise ValueError(f"{path}: a roster is a JSON object {{player id: {{team_id, formacion, ...}}}} (the package's tables.roster)")
    return data


def _roster_source(enabled: bool):
    """Ask FEB for one team's roster (one attempt; a team that fails is simply left without roster)."""
    if not enabled:
        return None
    from . import roster_fetcher

    return lambda team_id: roster_fetcher.fetch_team_roster(team_id)


def _configs(paths: List[str]):
    from .rule_evaluation import ConfigSpec, validate_config

    specs = [ConfigSpec("base")] + [_read_config(p) for p in paths]
    names = [s.name for s in specs]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ValueError(f"Two configurations are called {dup[0]!r} (the stock one is always «base»): rename one")
    for spec in specs:
        validate_config(spec)
    return specs


def _games(args: argparse.Namespace):
    from .eval_source import games_from_dir, games_from_mongo

    if args.games_dir:
        return games_from_dir(args.games_dir), args.season
    from src.database import MongoDBHandler
    from .db_source import season_of

    handler = MongoDBHandler()
    if not handler.is_connected():
        raise RuntimeError("No se pudo conectar a la base de datos")
    mongo = handler.repository.connection.get_collection(args.collection)
    return games_from_mongo(handler, args.collection), args.season or season_of(mongo, args.collection)


def _write(out: Path, ev: Any, data: Dict[str, Any], text: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    with open(out / "alerts.jsonl", "w", encoding="utf-8") as fh:
        for row in ev.rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    (out / "report.md").write_text(text, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    from .eval_labels import LabelConfig
    from .rule_evaluation import attach_feedback, evaluate

    args = _parser().parse_args(argv)
    try:
        configs = _configs(args.config)
        recordings = {feed.match: feed for feed in (RecordedFeed.load(p) for p in args.recording)}
        exports = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.feedback]
        roster = _read_roster(args.roster_file) if args.roster_file else None
        games, season = _games(args)
        ev = evaluate(
            games, configs, recordings, collection=args.collection or "FEB", season=season, team=args.team,
            latency_s=args.latency, poll_s=args.poll, min_prior_games=args.min_prior_games,
            label_cfg=LabelConfig(follow_s=args.follow_window), roster=roster, roster_source=_roster_source(args.roster),
            progress=lambda n: print(f"{n} partidos...", file=sys.stderr) if n % 10 == 0 else None)
    except (ValueError, OSError, RuntimeError, NotImplementedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    unmatched = attach_feedback(ev.rows, exports, baseline=ev.configs[0]) if exports else 0
    if unmatched:
        print(f"{unmatched} entradas de feedback sin alerta en la evaluación (¿otro partido o configuración?)", file=sys.stderr)
    data, text = build_report(ev)
    data["unmatched_feedback"] = unmatched
    _write(Path(args.out), ev, data, text)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0
