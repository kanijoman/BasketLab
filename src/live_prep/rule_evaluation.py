"""Evaluate the live alert rules on the competition's games: ``python -m src.live_prep.rule_evaluation``.

Every game is replayed "as live" (``eval_feed``) from the point of view of BOTH teams, with the package each team
would have had before that game (``SeasonAccumulator``: only earlier games, those that start together do not see each
other), through the very same engine as the app. Each alert is then labelled with what the coach did (``eval_labels``)
and measured (``eval_metrics``); coach behaviour comes from the same games (``eval_coach``). Several configurations
(``rules_off`` and thresholds) can be compared on identical games, and recordings of real matches replace the
simulated feed of their game.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig, unknown_rule_ids
from src.live_core.engine import LiveEngine
from src.live_core.vectors import to_jsonable

from .eval_coach import game_behaviour, simulate_run_rule
from .eval_feed import finished_game_polls, recording_polls, timing_mode
from .eval_labels import Actions, LabelConfig, label_alert, outcome_of
from .eval_source import game_code, merge_recordings, same_start_groups
from .package_builder import SeasonAccumulator

FIXED_CREATED_AT = "1970-01-01T00:00:00Z"   # a fixed date: two runs over the same games give the same packages
# (points, window in s, mode) of the "rival run" rule to simulate on the finished games
RUN_SPECS: Tuple[Tuple[int, int, str], ...] = (
    (8, 150, "unanswered"), (6, 150, "net"), (8, 150, "net"), (10, 180, "net"), (8, 240, "net"), (10, 240, "net"),
)


@dataclass(frozen=True)
class ConfigSpec:
    name: str
    overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evaluation:
    rows: List[Dict[str, Any]] = field(default_factory=list)         # one per alert, per configuration
    team_games: List[Dict[str, Any]] = field(default_factory=list)   # one per team-game evaluated
    coach: List[Dict[str, Any]] = field(default_factory=list)        # coach behaviour of every game
    simulation: List[Dict[str, Any]] = field(default_factory=list)   # the run rule with other thresholds
    configs: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


def validate_config(spec: ConfigSpec) -> None:
    """Reject settings and rule ids the engine does not know (the engine itself would silently ignore them)."""
    known = {f.name for f in dataclasses.fields(RuleConfig)}
    problems = [f"unknown setting {k!r}" for k in sorted(set(spec.overrides) - known)]
    problems += [f"unknown rule {r!r}" for r in unknown_rule_ids(spec.overrides.get("rules_off") or [])]
    if problems:
        raise ValueError(f"Configuration {spec.name!r}: " + ", ".join(problems))


def _teams(game: Dict[str, Any]) -> List[Tuple[str, str]]:
    return [(str(t["id"]), (t.get("name") or str(t["id"])).strip()) for t in (game.get("HEADER") or {}).get("TEAM", [])]


def _alert_row(a: Dict[str, Any], snap: Dict[str, Any], shown: int, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {**ctx, "elapsed": snap["elapsed"], "shown": max(shown, snap["elapsed"]),
            "period": snap["period"], "remaining": snap["remaining"], "id": a["id"], "key": a["key"],
            "severity": a["severity"], "category": a["category"], "message": a["message"],
            "evidence": a["evidence"], "proposal": a["proposal"]}


class _Evaluator:
    def __init__(self, configs: Sequence[ConfigSpec], recordings: Dict[str, Any], collection: str, season: str,
                 team: Optional[str], latency_s: float, poll_s: float, min_prior: int, labels: LabelConfig,
                 roster: Optional[Dict[str, Dict[str, Any]]] = None,
                 roster_source: Optional[Callable[[str], Optional[Dict[str, Dict[str, Any]]]]] = None) -> None:
        self.configs, self.recordings, self.collection, self.season = configs, recordings, collection, season
        self.team, self.latency_s, self.poll_s, self.min_prior, self.labels = team, latency_s, poll_s, min_prior, labels
        self.acc = SeasonAccumulator()
        self.roster, self.roster_source = roster, roster_source
        self.rosters: Dict[str, Dict[str, Dict[str, Any]]] = {}   # team id -> its players, each team asked for at most once
        self.finished: List[Tuple[Actions, Tuple[str, str]]] = []   # every game, for the simulation of the run rule
        self.out = Evaluation(configs=[c.name for c in configs])

    def roster_for(self, *team_ids: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """The roster rows of these teams (the given table first, then FEB once per team), or None without any (issue #278)."""
        table: Dict[str, Dict[str, Any]] = {}
        for tid in dict.fromkeys(team_ids):
            if tid not in self.rosters:
                rows = {pid: e for pid, e in (self.roster or {}).items() if str(e.get("team_id")) == tid}
                if not rows and self.roster_source is not None:
                    rows = self.roster_source(tid) or {}
                self.rosters[tid] = rows
            table.update(self.rosters[tid])
        return table or None

    def _perspectives(self, code: str, ids: List[str]) -> List[Tuple[str, str, int, ConfigSpec, AdviceEngine]]:
        out = []
        for own, rival in ((ids[0], ids[1]), (ids[1], ids[0])):
            prior = self.acc.played(own)
            if (self.team and own != self.team) or prior < self.min_prior:
                continue
            package = self.acc.to_package(self.collection, self.season, own, rival, {"match": {"code": code}}, FIXED_CREATED_AT,
                                          roster=self.roster_for(own, rival))
            for spec in self.configs:
                configured = dataclasses.replace(package, rule_config={**package.rule_config, **spec.overrides})
                out.append((own, rival, prior, spec, AdviceEngine.from_package(configured)))
        return out

    def play(self, game: Dict[str, Any]) -> None:
        ids = [tid for tid, _ in _teams(game)]
        if len(ids) != 2:
            return
        code, actions = game_code(game), Actions.from_game(game)
        self.out.coach.append(game_behaviour(actions, (ids[0], ids[1])))
        self.finished.append((actions, (ids[0], ids[1])))
        perspectives = self._perspectives(code, ids)
        if not perspectives:
            return
        feed = self.recordings.get(code)
        timing = "recording" if feed is not None else timing_mode(game)
        polls = recording_polls(feed, self.poll_s) if feed is not None else finished_game_polls(game, self.latency_s, self.poll_s)
        rows, count, engine = [], 0, LiveEngine()
        for poll in polls:
            count += 1
            snap = engine.update(poll.doc)
            shown = poll.shown_elapsed if poll.shown_elapsed is not None else snap["elapsed"]
            for own, rival, prior, spec, advice in perspectives:
                ctx = {"game": code, "team": own, "rival": rival, "config": spec.name, "prior": prior, "poll_t": poll.t}
                rows += [_alert_row(a, snap, shown, ctx) for a in to_jsonable(advice.evaluate(snap))]
        for row in rows:
            row.update(label_alert(row, actions, self.labels))
            row["outcome"] = outcome_of(row, actions, self.labels)
        self.out.rows += rows
        end = max((e.elapsed for e in actions.events), default=0)
        for own, rival, prior in sorted({(o, r, p) for o, r, p, _, _ in perspectives}, key=lambda x: ids.index(x[0])):
            self.out.team_games.append({"game": code, "team": own, "rival": rival, "prior": prior, "duration_s": end,
                                        "timing": timing, "polls": count, "timeouts": actions.timeouts(own)})


def evaluate(
    games: Iterable[Dict[str, Any]],
    configs: Optional[Sequence[ConfigSpec]] = None,
    recordings: Optional[Dict[str, Any]] = None,
    *,
    collection: str = "FEB",
    season: str = "",
    team: Optional[str] = None,
    latency_s: float = 40.0,
    poll_s: float = 10.0,
    min_prior_games: int = 0,
    label_cfg: Optional[LabelConfig] = None,
    progress: Optional[Callable[[int], None]] = None,
    roster: Optional[Dict[str, Dict[str, Any]]] = None,
    roster_source: Optional[Callable[[str], Optional[Dict[str, Dict[str, Any]]]]] = None,
) -> Evaluation:
    """Replay ``games`` (in date order; ``eval_source`` gives them so) and return the alerts, labels and coach data.

    ``configs``: the first one is the baseline. ``team``: evaluate only that team's side (everybody still feeds the
    season). ``min_prior_games``: skip sides whose team has fewer earlier games (its baselines would be noise).

    ``roster`` (a table player id -> {team_id, formacion, ...}) and/or ``roster_source`` (team id -> its roster, asked at most once per
    team) give the packages the FEB roster, without which the illegal-lineup rule is off (issue #278). It is the CURRENT roster: an
    approximation that is valid for the season in progress.
    """
    configs = list(configs or [ConfigSpec("base")])
    for spec in configs:
        validate_config(spec)
    recordings = dict(recordings or {})
    run = _Evaluator(configs, recordings, collection, season, team, latency_s, poll_s, min_prior_games, label_cfg or LabelConfig(), roster, roster_source)
    source = merge_recordings(games, recordings) if recordings else games
    done = 0
    for group in same_start_groups(source):
        for game in group:   # all of them before any is learned: games that start together do not see each other
            run.play(game)
        for game in group:
            run.acc.add_game(game)
        done += len(group)
        if progress:
            progress(done)
    run.out.simulation = simulate_run_rule([a for a, _ in run.finished], [p for _, p in run.finished], RUN_SPECS)
    run.out.params = {"latency_s": latency_s, "poll_s": poll_s, "min_prior_games": min_prior_games, "team": team,
                      "follow_s": run.labels.follow_s, "games": done,
                      "roster": ({"players": sum(len(r) for r in run.rosters.values()), "teams": sum(1 for r in run.rosters.values() if r)}
                                 if roster or roster_source else None),
                      "formation_min": {c.name: c.overrides.get("formation_min_on_court", RuleConfig().formation_min_on_court) for c in configs}}
    return run.out


def attach_feedback(rows: List[Dict[str, Any]], exports: Iterable[Dict[str, Any]], baseline: str) -> int:
    """Join the staff's exported verdicts to the alerts of the baseline configuration by match code and key.

    Marks the rows of those matches (``feedback`` True, ``verdict`` None when the staff did not answer) and returns
    how many exported entries matched no alert (the app and the evaluator did not emit the same alerts).
    """
    verdicts: Dict[Tuple[str, str], Optional[str]] = {}
    for export in exports:
        context = str(export.get("context") or "")
        if not context.startswith(("live:", "demo:")):
            continue
        code = context.split(":", 1)[1]
        for entry in export.get("entries") or []:
            verdicts[(code, str(entry.get("key")))] = entry.get("verdict")
    codes = {code for code, _ in verdicts}
    seen = set()
    for row in rows:
        if row["config"] != baseline or row["game"] not in codes:
            continue
        row["feedback"] = True
        row["verdict"] = verdicts.get((row["game"], row["key"]))
        seen.add((row["game"], row["key"]))
    return len(set(verdicts) - seen)


def main(argv: Optional[List[str]] = None) -> int:
    """``python -m src.live_prep.rule_evaluation`` (the command line lives in ``eval_cli``)."""
    from .eval_cli import main as cli

    return cli(argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())
