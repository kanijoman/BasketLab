"""Command line and report of the win-probability calibration (issue #255): ``python -m src.live_prep.wp_cli``."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.live_core.config import RuleConfig

from .wp_eval import VARIANTS, collect_samples, compare, grid_search

DEFAULT_GRID = {"wp_sigma": [9.0, 10.5, 12.0, 13.5], "wp_n0": [30.0, 60.0, 120.0], "wp_home_adv": [0.0, 4.0, 8.0], "ff_beta": [0.0, 4.5, 9.0]}
NAMES = {"full": "Modelo completo", "prior_only": "Solo valor previo", "score_time": "Solo marcador y tiempo"}
MAX_GAP_POINTS = 5.0


def _fmt(value: Optional[float], digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def build_report(compared: Dict[str, Dict[str, Any]], ranked: Sequence[Dict[str, Any]], samples: Sequence[Dict[str, Any]],
                 cfg: RuleConfig, validation: Optional[Dict[str, Any]] = None) -> str:
    games = len({s["game"] for s in samples})
    full, lines = compared["full"], []
    lines += ["# Calibración de la probabilidad de victoria", "",
              f"{len(samples)} cortes de {games} partidos (ambos puntos de vista, cortes cada 5 min). Parámetros actuales: "
              f"`wp_sigma={cfg.wp_sigma}`, `wp_n0={cfg.wp_n0}`, `wp_home_adv={cfg.wp_home_adv}`, `ff_beta={cfg.ff_beta}`.", "",
              "## Variantes", "", "| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |", "|---|---|---|---|---|"]
    for variant in VARIANTS:
        c = compared[variant]
        lines.append(f"| {NAMES[variant]} | {_fmt(c['brier'])} | {_fmt(c['log_loss'])} | {_fmt(c['mae'], 2)} | {_fmt(c['max_gap'], 1)} |")
    beats = all((full["log_loss"] or 9) < (compared[v]["log_loss"] or 9) for v in ("prior_only", "score_time"))
    gap = full["max_gap"]
    ok = beats and gap is not None and gap <= MAX_GAP_POINTS
    lines += ["", f"**Criterio para mostrarla en la app** (mejor que «solo marcador y tiempo» y que «solo valor previo» y desvío por decil ≤ {MAX_GAP_POINTS:.0f} pts): "
              f"{'cumplido' if ok else 'NO cumplido'}.", "", "## Fiabilidad del modelo completo", "",
              "| Decil | n | P media | Frecuencia |", "|---|---|---|---|"]
    lines += [f"| {r['bin'] * 10}-{r['bin'] * 10 + 10} % | {r['n']} | {r['mean_p']:.3f} | {r['freq']:.3f} |" for r in full["reliability"]]
    lines += ["", "## Mejores parámetros (por log loss)", "", "| Parámetros | Log loss | Brier | MAE |", "|---|---|---|---|"]
    lines += [f"| {r['params']} | {_fmt(r['log_loss'])} | {_fmt(r['brier'])} | {_fmt(r['mae'], 2)} |" for r in ranked[:8]]
    if validation:
        lines += _validation_section(validation)
    return "\n".join(lines) + "\n"


def _validation_section(v: Dict[str, Any]) -> List[str]:
    """The best parameters of the grid, tried on a season that did not take part in choosing them."""
    lines = ["", "## Validación en una temporada aparte", "",
             f"{v['samples']} cortes de {v['games']} partidos que no se usaron para ajustar. Parámetros ajustados: `{v['params']}`.", "",
             "| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |", "|---|---|---|---|---|"]
    for label, compared in (("Parámetros por defecto", v["default"]), ("Parámetros ajustados", v["tuned"])):
        c = compared["full"]
        lines.append(f"| {label} (modelo completo) | {_fmt(c['brier'])} | {_fmt(c['log_loss'])} | {_fmt(c['mae'], 2)} | {_fmt(c['max_gap'], 1)} |")
    for variant in ("prior_only", "score_time"):
        c = v["default"][variant]
        lines.append(f"| {NAMES[variant]} | {_fmt(c['brier'])} | {_fmt(c['log_loss'])} | {_fmt(c['mae'], 2)} | {_fmt(c['max_gap'], 1)} |")
    return lines


def _validate(args: argparse.Namespace, ranked: Sequence[Dict[str, Any]], cfg: RuleConfig) -> Dict[str, Any]:
    from .eval_source import games_from_dir

    held_out = collect_samples(games_from_dir(args.validate_dir), cut_s=args.cut, min_prior_games=args.min_prior_games)
    tuned = dataclasses.replace(cfg, **ranked[0]["params"])
    return {"samples": len(held_out), "games": len({s["game"] for s in held_out}), "params": ranked[0]["params"],
            "default": compare(held_out, cfg), "tuned": compare(held_out, tuned)}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.live_prep.wp_cli", description="Calibrate the live win probability on finished games.")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--collection", help="MongoDB collection of a FEB competition")
    source.add_argument("--games-dir", action="append", metavar="DIR",
                        help="folder with the finished games of ONE season (*.json or *.json.gz); repeat it for several seasons "
                             "(each has its own priors; their samples are scored together)")
    p.add_argument("--validate-dir", metavar="DIR",
                   help="folder of a season NOT used to tune: the default and the best parameters are scored on it")
    p.add_argument("--min-prior-games", type=int, default=3, help="skip sides whose team has fewer earlier games")
    p.add_argument("--cut", type=int, default=300, help="seconds between the cuts")
    p.add_argument("--out", help="write the report to this file (it is always printed)")
    return p


def _samples(args: argparse.Namespace) -> List[Dict[str, Any]]:
    """The samples of every season asked for: one per folder, or the collection."""
    if args.games_dir:
        from .eval_source import games_from_dir

        return [s for folder in args.games_dir
                for s in collect_samples(games_from_dir(folder), cut_s=args.cut, min_prior_games=args.min_prior_games)]
    return collect_samples(_mongo_games(args), cut_s=args.cut, min_prior_games=args.min_prior_games)


def _mongo_games(args: argparse.Namespace):
    from .eval_source import games_from_mongo

    from src.database import MongoDBHandler

    handler = MongoDBHandler()
    if not handler.is_connected():
        raise RuntimeError("No se pudo conectar a la base de datos")
    return games_from_mongo(handler, args.collection)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        samples = _samples(args)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if not samples:
        print("Error: ningún partido con suficientes partidos previos", file=sys.stderr)
        return 2
    cfg = RuleConfig()
    ranked = grid_search(samples, DEFAULT_GRID, cfg)
    validation = _validate(args, ranked, cfg) if args.validate_dir else None
    text = build_report(compare(samples, cfg), ranked, samples, cfg, validation)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
