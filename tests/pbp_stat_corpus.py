"""Corpus of play-by-play actions to pin down how the IN/OUT and the lineup calculators count them (issue #200, block 6 of #452).

``python tests/pbp_stat_corpus.py`` regenerates ``tests/fixtures/inout_lineup_golden.json.gz`` from the CURRENT code: do it only when a counting rule is
changed on purpose (a refactor must leave the file as it is). Both calculators read the same actions with rules that differ in small ways (which
words count as a miss, which sources count a steal…); the golden file is what says which differences are deliberate, case by case.
"""
from __future__ import annotations

import gzip
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Tuple
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLDEN = Path(__file__).parent / "fixtures" / "inout_lineup_golden.json.gz"
TEAM, OPP = "A", "B"

FEB_TEXTS = [
    "", "Tiro de 2 anotado", "Tiro de 2 fallado", "Canasta de 2", "Canasta de 2 fallada", "Tiro de 3 anotado", "Tiro de 3 fallado", "Triple",
    "Canasta de 3", "Triple fallado", "Tiro de 1 anotado", "Tiro libre anotado", "Tiro libre fallado", "Tiro libre falla", "Tiro de 2 falla",
    "Asistencia", "Robo de balón", "Recupera", "Tapón", "Tapon", "Pérdida de balón", "Perdida", "Falta personal", "Rebote defensivo", "Rebote ofensivo",
    "Rebote", "Tiempo muerto",
]
FEB_TYPES = ["", "shoot", "fthrow", "rebound", "assist", "steal", "recovery", "block", "turnover", "lose", "foul"]
FEB_LP4 = [None, "0", "1"]
FEB_LP6 = [None, "2", "3"]
FBCYL_MOVES = [
    "", "Canasta de 2", "canasta de 2", "Intento fallado de 2", "intento fallado de 2", "Canasta de 3", "Intento fallado de 3", "Canasta de 1",
    "Tiro libre anotado", "Intento fallado de 1", "Pérdida", "pérdida", "Falta personal", "Personal", "personal", "Falta", "Asistencia", "asistencia",
    "Robo", "robo", "Tapón", "tapón", "Tapon", "Rebote defensivo", "Rebote ofensivo", "Rebote", "rebote", "Entra al campo", "Mate", "Mate fuera",
]
CONTEXT_SHOTS = [None, ("shoot", "Tiro de 2 fallado", TEAM), ("shoot", "Tiro de 2 fallado", OPP), ("fthrow", "Tiro libre anotado", TEAM), ("", "Canasta de 2", OPP)]


def feb_actions() -> Iterator[Dict[str, Any]]:
    for text, typ, lp4, lp6, team in itertools.product(FEB_TEXTS, FEB_TYPES, FEB_LP4, FEB_LP6, (TEAM, OPP)):
        if typ not in ("shoot", "fthrow") and (lp4 is not None or lp6 is not None) and typ != "rebound":
            continue                                       # the log params only matter for shots; keep the corpus small
        action: Dict[str, Any] = {"idTeam": team, "text": text, "action": typ}
        if lp4 is not None:
            action["logParam4"] = lp4
        if lp6 is not None:
            action["logParam6"] = lp6
        yield action


def fbcyl_actions() -> Iterator[Dict[str, Any]]:
    for move, team in itertools.product(FBCYL_MOVES, (TEAM, OPP)):
        yield {"idTeam": team, "move": move}


def _shot(ctx: Tuple[str, str, str] | None) -> Dict[str, Any] | None:
    return None if ctx is None else {"idTeam": ctx[2], "action": ctx[0], "text": ctx[1]}


def _nonzero(stats: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in sorted(stats.items()) if v}


def _key(*parts: Any) -> str:
    return json.dumps(parts, ensure_ascii=False, sort_keys=True)


def _inout():
    from src.database.inout_calculator import InOutStatsCalculator
    return InOutStatsCalculator(MagicMock())


def _lineup(is_fbcyl: bool):
    from src.database.lineup_stats_calculator import LineupStatsCalculator
    analyzer = MagicMock()
    analyzer.is_fbcyl = is_fbcyl
    return LineupStatsCalculator(analyzer)


def _empty(calc) -> Dict[str, int]:
    return calc._empty_stats()


def corpus() -> Dict[str, Any]:
    """Every case and what the current code does with it: {case key: nonzero stats (or points / last shot)}."""
    out: Dict[str, Any] = {}
    io = _inout()
    lf, lc = _lineup(False), _lineup(True)

    for action in itertools.chain(feb_actions(), fbcyl_actions()):
        out[_key("io.points", action)] = list(io._extract_points_from_action(action))

    for action, ctx, last in itertools.product(feb_actions(), CONTEXT_SHOTS, (None, TEAM, OPP)):
        prev = _shot(ctx)
        lines = [action] + ([prev] if prev else [])
        text = action.get("text", "")
        target = _io_stats(io)
        new_last = io._process_feb_action(action, text.upper(), action.get("action", ""), action["idTeam"], TEAM, target, 0, lines, last)
        out[_key("io.feb", action, ctx, last)] = [_nonzero(target), new_last]

    for action in fbcyl_actions():
        target = _io_stats(io)
        io._process_fbcyl_move(action, action["move"], action["idTeam"], TEAM, target, 0, [action])
        out[_key("io.fbcyl", action)] = _nonzero(target)

    for action, ctx in itertools.product(feb_actions(), CONTEXT_SHOTS):
        prev = _shot(ctx)
        actions = [action] + ([prev] if prev else [])
        out[_key("io.list", action, ctx)] = _nonzero(io._calculate_stats_from_actions(actions, TEAM, OPP))

    for calc, actions, label in ((lf, feb_actions(), "lineup.feb"), (lc, fbcyl_actions(), "lineup.fbcyl")):
        for action, last in itertools.product(actions, (None, TEAM, OPP)):
            stats = _empty(calc)
            calc._process_action(action, TEAM, stats, last)
            out[_key(label, action, last)] = _nonzero(stats)

    for action, ctx in itertools.product(feb_actions(), CONTEXT_SHOTS):
        prev = _shot(ctx)
        stats = _empty(lf)
        lf._process_actions_with_context(([prev] if prev else []) + [action], TEAM, stats)
        out[_key("lineup.feb.seq", action, ctx)] = _nonzero(stats)
    for action, ctx in itertools.product(fbcyl_actions(), CONTEXT_SHOTS):
        prev = _shot(ctx)
        fb_prev = None if prev is None else {"idTeam": prev["idTeam"], "move": {"shoot": "Intento fallado de 2", "fthrow": "Tiro libre anotado", "": "Canasta de 2"}[prev["action"]]}
        stats = _empty(lc)
        lc._process_actions_with_context(([fb_prev] if fb_prev else []) + [action], TEAM, stats)
        out[_key("lineup.fbcyl.seq", action, ctx)] = _nonzero(stats)

    out.update(real_game())
    return out


def real_game() -> Dict[str, Any]:
    """A whole FBCYL match from ``fbcyl_game_ok``: the IN/OUT of every player and the lineups of 3 and 5 of each team, through the real analyzer and extractor."""
    from src.database.inout_calculator import InOutStatsCalculator
    from src.database.lineup_extractor import LineupExtractor
    from src.database.lineup_stats_calculator import LineupStatsCalculator
    from src.database.playbyplay_analyzer import PlayByPlayAnalyzer

    with gzip.open(Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz", "rt", encoding="utf-8") as f:
        game = json.load(f)
    analyzer = PlayByPlayAnalyzer(game, True)
    extractor = LineupExtractor(analyzer)
    io, lineups = InOutStatsCalculator(analyzer), LineupStatsCalculator(analyzer)
    teams: Dict[str, set] = {}
    for move in analyzer.lines:
        if move.get("move") == "Entra al campo":
            teams.setdefault(str(move["idTeam"]), set()).add(str(move["licenseId"]))
    out: Dict[str, Any] = {}
    for team, players in sorted(teams.items()):
        for player in sorted(players):
            res = io.calculate_in_out_stats(player, team)
            out[_key("io.game", team, player)] = {side: _nonzero(stats) for side, stats in res.items()}
        for size in (5, 3):
            for lineup in sorted(extractor.get_lineup_combinations(team, size), key=sorted)[:6]:
                res = lineups.calculate_lineup_stats_single_game(analyzer, extractor, team, lineup)
                res["players"] = sorted(res["players"])
                out[_key("lineup.game", team, sorted(lineup))] = res
    return out


def _io_stats(io) -> Dict[str, int]:
    """The empty IN/OUT bucket: today a local function of ``calculate_in_out_stats``, so it is taken from the lineup twin until it is shared."""
    return _empty(_lineup(False))


def write_golden() -> int:
    data = corpus()
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    GOLDEN.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))     # mtime=0: the same bytes every time
    return len(data)


def read_golden() -> Dict[str, Any]:
    with gzip.open(GOLDEN, "rt", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    print(write_golden(), "cases written to", GOLDEN)
