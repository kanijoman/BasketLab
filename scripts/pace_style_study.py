"""The pace of each team by its possessions (#938): ``python scripts/pace_style_study.py DIR [--out FILE]``, over the dump of ``scripts/web_data_dump.py``.

From the published per-possession CSV (duration, origin and end of every possession of every game with play-by-play), two things the walk-forward evaluation of the projection cannot see:

- **Duration × origin**: what a possession scores by how long it lasted and how it started, per family. It is the groundwork of the causal study (#942): a fast possession after a made
  basket is a choice of the team, after a steal it is given, so «fast possessions score more» does not say that playing faster scores more.
- **The style of each team**: how long its possessions last, how many are fast (≤ 8 s, the buckets of the possessions page), what the fast and the rest score, how long its possessions after a
  made basket last (its chosen pace) and how long the rivals' possessions last against it; and whether each of those is the team's own: the correlation, over the teams of a season, of the
  value from its odd games with the one from its even games (Spearman-Brown for the whole season). Near 0 it is noise, near 1 a trait of the team.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

BUCKETS = ("rápida", "media", "lenta")
FAST_MAX, MEDIUM_MAX = 8, 16
ORIGINS = {"saque_fondo": "tras canasta o tiros libres", "rebote_defensivo": "tras rebote defensivo", "recuperacion": "tras robo",
           "violacion": "tras pérdida sin robo", "saque_inicial_periodo": "inicio de periodo"}
STYLE_METRICS = ("avg_duration", "fast_share", "ppp_fast", "ppp_rest", "avg_duration_after_basket", "rival_avg_duration")
STYLE_NAMES = {"avg_duration": "duración media (s)", "fast_share": "% de rápidas", "ppp_fast": "puntos por posesión rápida", "ppp_rest": "puntos por posesión no rápida",
               "avg_duration_after_basket": "duración tras canasta (s)", "rival_avg_duration": "duración de las del rival (s)"}


@dataclass(frozen=True)
class Possession:
    game: str
    team: str
    rival: str
    origin: str
    duration: int
    ending: str
    points: int
    controversial: bool


def read_possessions(text: str) -> List[Possession]:
    """Every possession of the published CSV (``possession_export_service``)."""
    return [Possession(game=r["ID_Partido"], team=r["Equipo_ID"], rival=r["Rival_ID"], origin=r["Origen_posesion"], duration=int(r["Duracion_posesion"]),
                       ending=r["Tipo_finalizacion"], points=int(r["Puntos_obtenidos"]), controversial=r.get("Controversial_Possession") in ("1", "True", "true"))
            for r in csv.DictReader(io.StringIO(text))]


def bucket_of(duration: int) -> str:
    return BUCKETS[0] if duration <= FAST_MAX else BUCKETS[1] if duration <= MEDIUM_MAX else BUCKETS[2]


def _mean(xs: Sequence[float]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def origin_duration(possessions: Iterable[Possession]) -> List[Dict[str, object]]:
    """Per origin and bucket of duration: possessions, their share within the origin and the points per possession."""
    cells: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for p in possessions:
        cells[(p.origin, bucket_of(p.duration))].append(p.points)
    totals: Dict[str, int] = defaultdict(int)
    for (origin, _), points in cells.items():
        totals[origin] += len(points)
    return [{"origin": origin, "bucket": bucket, "possessions": len(points), "share": len(points) / totals[origin], "ppp": sum(points) / len(points)}
            for (origin, bucket), points in sorted(cells.items(), key=lambda kv: (kv[0][0], BUCKETS.index(kv[0][1])))]


def style_of(own: Sequence[Possession], against: Sequence[Possession]) -> Dict[str, Optional[float]]:
    """The style of a team over some games: its possessions (``own``) and those of its rivals against it (``against``)."""
    fast = [p for p in own if p.duration <= FAST_MAX]
    rest = [p for p in own if p.duration > FAST_MAX]
    return {"avg_duration": _mean([p.duration for p in own]), "fast_share": len(fast) / len(own) if own else None,
            "ppp_fast": _mean([p.points for p in fast]), "ppp_rest": _mean([p.points for p in rest]),
            "avg_duration_after_basket": _mean([p.duration for p in own if p.origin == "saque_fondo"]), "rival_avg_duration": _mean([p.duration for p in against])}


def styles_by_half(possessions: Sequence[Possession]) -> Dict[str, Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]]:
    """The style of each team in its odd and in its even games (its games in the order of their ids)."""
    games_of: Dict[str, List[str]] = defaultdict(list)
    for p in possessions:
        if p.game not in games_of[p.team]:
            games_of[p.team].append(p.game)
    out = {}
    for team, games in games_of.items():
        ordered = sorted(games)
        halves = (set(ordered[1::2]), set(ordered[0::2]))
        out[team] = tuple(style_of([p for p in possessions if p.team == team and p.game in half], [p for p in possessions if p.rival == team and p.game in half]) for half in halves)
    return out


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Pearson's correlation; None when one of the two does not vary."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def reliability(possessions: Sequence[Possession]) -> Dict[str, Optional[float]]:
    """Per style metric, the correlation over the teams of the odd half with the even half."""
    halves = styles_by_half(possessions)
    out = {}
    for metric in STYLE_METRICS:
        pairs = [(odd[metric], even[metric]) for odd, even in halves.values() if odd[metric] is not None and even[metric] is not None]
        out[metric] = pearson([a for a, _ in pairs], [b for _, b in pairs])
    return out


def _fmt(x: Optional[float], digits: int = 2) -> str:
    return "—" if x is None else f"{x:.{digits}f}".replace(".", ",")


def _table(head: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def report(competitions: List[Tuple[str, str, List[Possession]]]) -> str:
    families = [("Masculina", "M"), ("Femenina", "F")]
    parts = ["## Duración y origen de las posesiones",
             "Puntos por posesión según cómo empezó (origen) y cuánto duró (rápida ≤ 8 s, media 8-16 s, lenta > 16 s), sin las posesiones dudosas del CSV."]
    for label, g in families:
        mine = [p for _, gender, ps in competitions if gender == g for p in ps]
        if mine:
            parts += [f"### {label}", _table(["Origen", "Duración", "Posesiones", "% del origen", "Puntos por posesión"],
                                              [[ORIGINS.get(c["origin"], c["origin"]), c["bucket"], c["possessions"], _fmt(100 * c["share"], 1), _fmt(c["ppp"], 3)] for c in origin_duration(mine)])]
    rel = [(name, gender, reliability(ps)) for name, gender, ps in competitions]
    parts += ["## Estilo propio de cada equipo",
              "Correlación, entre los equipos de cada temporada, del valor con sus partidos impares y con sus partidos pares; entre paréntesis, la de la temporada entera (Spearman-Brown, 2r / (1 + r)).",
              _table(["Competición", *[STYLE_NAMES[m] for m in STYLE_METRICS]], [[name, *[_fmt(r[m]) for m in STYLE_METRICS]] for name, _, r in rel])]
    for label, g in families:
        values = {m: [r[m] for _, gender, r in rel if gender == g and r[m] is not None] for m in STYLE_METRICS}
        if any(values.values()):
            means = {m: _mean(v) for m, v in values.items()}
            parts.append(f"**{label}** (media): " + " · ".join(f"{STYLE_NAMES[m]} {_fmt(x)} ({_fmt(2 * x / (1 + x) if x is not None and x > -1 else None)})" for m, x in means.items()))
    return "\n\n".join(parts) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="The pace of each team by its possessions (per-possession CSV of scripts/web_data_dump.py)")
    parser.add_argument("dir")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    base = Path(args.dir)
    index = json.loads((base / "index.json").read_text(encoding="utf-8"))
    competitions = [(e["name"], e.get("gender") or "M", [p for p in read_possessions((base / e["possession_csv"]).read_text(encoding="utf-8")) if not p.controversial])
                    for e in index["collections"] if e.get("possession_csv")]
    text = "# El ritmo de cada equipo por sus posesiones\n\n" + report(competitions)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
