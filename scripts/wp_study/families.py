"""Other families of models (issue #567): a Bayesian state-space prior of the teams, boosting, a neural network, and the structural model of the app calibrated per family."""
from __future__ import annotations

import pickle
from typing import Any, Dict, List, Sequence, Tuple

from .samples import BASE, GAME, brier, cross_val, decile_gap, log_loss, matrix


def _chains(folders: Sequence[str]) -> Dict[str, List[str]]:
    """The seasons of each competition, oldest first (a folder is ``<competition>/<season>``)."""
    chains: Dict[str, List[str]] = {}
    for folder in folders:
        chains.setdefault(folder.rsplit("/", 1)[0], []).append(folder)
    return {k: sorted(v, key=lambda f: f.rsplit("/", 1)[1]) for k, v in chains.items()}


def dynamic_prior(folders: Sequence[str], rho: float = 0.6, p0: float = 60.0, q_season: float = 20.0, q_game: float = 0.3, noise: float = 144.0,
                  carry: bool = True) -> Dict[Tuple[str, str], Dict[str, float]]:
    """A Bayesian state-space (Kalman) rating of every team, in points per game, BEFORE each game: it starts from the previous season (shrunk by ``rho``), updates
    with every result according to how sure it is of each team (variance), and drifts a little during the season. Pure Python: what the publisher could compute.
    FEB gives a team a NEW id every season: the season is carried by the ``teamCode`` of the header (the same club team), and ``carry=False`` starts every season
    from zero (to measure what the carry adds). ``{(folder, game code): {team id: rating}}``."""
    from src.live_prep.eval_source import games_from_dir, parse_starttime

    out: Dict[Tuple[str, str], Dict[str, float]] = {}
    for chain in _chains(folders).values():
        mean: Dict[str, float] = {}
        var: Dict[str, float] = {}
        home_sum, home_n = 3.0 * 20, 20
        for folder in chain:
            if not carry:
                mean, var = {}, {}
            for team in mean:                                          # a new season: regress to the average, less sure
                mean[team] *= rho
                var[team] = rho * rho * var[team] + q_season
            played = []
            for game in games_from_dir(folder):
                teams = (game.get("HEADER") or {}).get("TEAM") or []
                try:
                    ids, pts = [str(t["id"]) for t in teams], [int(t["pts"]) for t in teams]
                    keys = [str(t.get("teamCode") or t["id"]) for t in teams]          # the same team from one season to the next
                except (KeyError, TypeError, ValueError):
                    continue
                if len(ids) == 2 and any(pts):
                    played.append((parse_starttime(game), str(game.get("_id") or (game.get("HEADER") or {}).get("game_code")), ids, keys, pts[0] - pts[1]))
            played.sort(key=lambda g: (g[0] is None, g[0] or 0, g[1]))
            for _, code, (id_h, id_a), (h, a), margin in played:
                for t in (h, a):
                    mean.setdefault(t, 0.0)
                    var.setdefault(t, p0)
                out[(folder, code)] = {id_h: mean[h], id_a: mean[a]}
                innov = margin - (mean[h] - mean[a] + home_sum / home_n)
                s_ = var[h] + var[a] + noise
                kh, ka = var[h] / s_, var[a] / s_
                mean[h] += kh * innov
                mean[a] -= ka * innov
                var[h], var[a] = var[h] * (1 - kh) + q_game, var[a] * (1 - ka) + q_game
                home_sum, home_n = home_sum + margin, home_n + 1
    return out


def benchmark(paths: Sequence[str]) -> str:
    import dataclasses
    import time as _time
    import zlib

    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    from src.live_core.config import RuleConfig
    from src.live_prep.wp_eval import forecast

    samples = [s_ for path in paths for s_ in pickle.load(open(path, "rb"))]
    league = np.array(["masculinas" if "/men/" in s_["source"].replace("\\", "/") else "femeninas" for s_ in samples])
    y = np.array([int(s_["won"]) for s_ in samples])
    g = np.array([f"{s_['source']}:{s_['game']}" for s_ in samples])
    started = _time.time()
    dyn = dynamic_prior(sorted({s_["source"] for s_ in samples}))
    dyn_diff = np.array([dyn.get((s_["source"], s_["game"]), {}).get(s_["team"], 0.0) - dyn.get((s_["source"], s_["game"]), {}).get(s_["rival"], 0.0) for s_ in samples])
    X_base, X_all = matrix(samples, BASE), matrix(samples, BASE + GAME)
    X_dyn = np.column_stack([X_base, dyn_diff])
    X_all_dyn = np.column_stack([X_all, dyn_diff])
    cfg = RuleConfig()
    results: Dict[str, Any] = {"A. Modelo de la app (estructural)": np.array([forecast(s_, cfg, "full")["p"] for s_ in samples])}

    # A2: the same structural model with its spread (wp_sigma) fitted per family of competitions, on half of the games and scored on the other half
    sigmas = [10.0, 12.0, 14.0, 16.0, 18.0]
    by_sigma = {sg: np.array([forecast(s_, dataclasses.replace(cfg, wp_sigma=sg), "full")["p"] for s_ in samples]) for sg in sigmas}
    half = np.array([zlib.crc32(x.encode()) % 2 for x in g])          # a stable half of the games (hash() changes with every run)
    p_a2 = np.zeros(len(y))
    chosen = {}
    for fam in sorted(set(league)):
        for fold in (0, 1):
            train, test = (league == fam) & (half != fold), (league == fam) & (half == fold)
            best = min(sigmas, key=lambda sg: log_loss(by_sigma[sg][train], y[train]))
            chosen[(fam, fold)] = best
            p_a2[test] = by_sigma[best][test]
    results["A2. Estructural con la dispersión ajustada por familia de competiciones"] = p_a2

    logit = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000))  # noqa: E731
    results["D. Logística: marcador, tiempo y valor previo"] = cross_val(samples, X_base, y, g, logit)
    results["K. Logística + valor previo bayesiano dinámico (Kalman, con la temporada anterior)"] = cross_val(samples, X_dyn, y, g, logit)
    monotone = [1, 1] + [0] * (X_all_dyn.shape[1] - 2)                                  # more margin never lowers the chance of winning
    boost = lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.03, max_iter=400, min_samples_leaf=200, l2_regularization=2.0,  # noqa: E731
                                                   monotonic_cst=monotone, early_stopping=True, random_state=0)
    results["F2. Árboles potenciados (monótonos, regularizados) con todo + Kalman"] = cross_val(samples, X_all_dyn, y, g, boost)
    mlp = lambda: make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-2, early_stopping=True, max_iter=400, random_state=0))  # noqa: E731
    results["N. Red neuronal (32-16) con todo + Kalman"] = cross_val(samples, X_all_dyn, y, g, mlp)

    games = len(set(g))
    lines = [f"{len(y)} cortes de {games} partidos ({int((league == 'femeninas').sum())} de ligas femeninas y {int((league == 'masculinas').sum())} de masculinas), validación cruzada por partido.", "",
             "| Modelo | Log loss | Brier | Desvío máx. por decil | Log loss femeninas | Log loss masculinas |", "|---|---|---|---|---|---|"]
    for name, p in results.items():
        fem, mas = league == "femeninas", league == "masculinas"
        lines.append(f"| {name} | {log_loss(p, y):.4f} | {brier(p, y):.4f} | {decile_gap(p, y):.1f} pp | {log_loss(p[fem], y[fem]):.4f} | {log_loss(p[mas], y[mas]):.4f} |")
    lines += ["", "Dispersión elegida (`wp_sigma`, puntos) por familia y mitad: " + ", ".join(f"{fam} {fold}: {sg:.0f}" for (fam, fold), sg in sorted(chosen.items())) + f" (actual: {cfg.wp_sigma:.0f}).",
              "", "Por tramo del partido (log loss):", "", "| Minutos | " + " | ".join(n.split(".")[0] for n in results) + " |", "|---|" + "---|" * len(results)]
    elapsed = np.array([s_["snap"]["elapsed"] for s_ in samples])
    for lo, hi in ((0, 600), (600, 1200), (1200, 1800), (1800, 2400)):
        m_ = (elapsed >= lo) & (elapsed < hi)
        lines.append(f"| {lo // 60}-{hi // 60} | " + " | ".join(f"{log_loss(p[m_], y[m_]):.4f}" for p in results.values()) + " |")
    # paired bootstrap by game of the best alternatives against the app
    keys = list(results)
    index: Dict[str, List[int]] = {}
    for i, x in enumerate(g):
        index.setdefault(x, []).append(i)
    ids_ = list(index)
    rng = np.random.default_rng(0)
    pick_sets = [rng.integers(0, len(ids_), len(ids_)) for _ in range(500)]

    def per_game_loss(p):
        p = np.clip(p, 1e-4, 1 - 1e-4)
        loss = -(y * np.log(p) + (1 - y) * np.log(1 - p))
        return np.array([loss[index[k]].sum() for k in ids_]), np.array([len(index[k]) for k in ids_])

    base_loss, size = per_game_loss(results[keys[0]])
    lines += ["", "Diferencia de log loss frente al modelo de la app (negativo = mejor), con intervalo 95 % por partidos:", "", "| Modelo | Diferencia | IC 95 % |", "|---|---|---|"]
    for name in keys[1:]:
        loss, _ = per_game_loss(results[name])
        diff = loss - base_loss
        boot = [diff[pk].sum() / size[pk].sum() for pk in pick_sets]
        lines.append(f"| {name} | {diff.sum() / size.sum():+.4f} | {np.percentile(boot, 2.5):+.4f} a {np.percentile(boot, 97.5):+.4f} |")
    lines += ["", f"({_time.time() - started:.0f} s)"]
    return "\n".join(lines)


def structural(paths: Sequence[str]) -> str:
    """The structural model of the app, calibrated per family of competitions (spread, home court, weight of the prior), with the season-to-date prior or with the
    Bayesian (Kalman) prior. Half of the games choose the parameters and the other half scores them, and the other way round."""
    import dataclasses
    import itertools
    import zlib

    import numpy as np

    from src.live_core.config import RuleConfig
    from src.live_prep.wp_eval import forecast

    samples = [s_ for path in paths for s_ in pickle.load(open(path, "rb"))]
    league = np.array(["masculinas" if "/men/" in s_["source"].replace("\\", "/") else "femeninas" for s_ in samples])
    y = np.array([int(s_["won"]) for s_ in samples])
    g = np.array([f"{s_['source']}:{s_['game']}" for s_ in samples])
    half = np.array([zlib.crc32(x.encode()) % 2 for x in g])
    folders = sorted({s_["source"] for s_ in samples})

    def with_prior(dyn):
        out = []
        for s_ in samples:
            r = dyn.get((s_["source"], s_["game"]), {})
            pace = float(s_["baselines"].get("pace_per_40") or 70.0)
            out.append({**s_, "baselines": {**s_["baselines"], "net_rtg_prior": (r.get(s_["team"], 0.0) - r.get(s_["rival"], 0.0)) * 100.0 / pace}})   # per 100 possessions
        return out

    kalman = with_prior(dynamic_prior(folders, carry=False))                 # every season from zero
    kalman_carry = with_prior(dynamic_prior(folders, carry=True))            # from the previous season (same teamCode), shrunk
    cfg = RuleConfig()
    grid = list(itertools.product([12.0, 14.0, 16.0, 18.0], [2.0, 4.0, 6.0], [240.0, 480.0, 960.0]))

    def calibrated(pool):
        preds = {k: np.array([forecast(s_, dataclasses.replace(cfg, wp_sigma=k[0], wp_home_adv=k[1], wp_n0=k[2]), "full")["p"] for s_ in pool]) for k in grid}
        p, chosen = np.zeros(len(y)), {}
        for fam in sorted(set(league)):
            for fold in (0, 1):
                train, test = (league == fam) & (half != fold), (league == fam) & (half == fold)
                chosen[(str(fam), fold)] = min(grid, key=lambda k: log_loss(preds[k][train], y[train]))
                p[test] = preds[chosen[(str(fam), fold)]][test]
        return p, chosen

    p_season, c_season = calibrated(samples)
    p_kalman, c_kalman = calibrated(kalman)
    p_carry, c_carry = calibrated(kalman_carry)
    app = np.array([forecast(s_, cfg, "full")["p"] for s_ in samples])
    fem, mas, early = league == "femeninas", league == "masculinas", np.array([s_["snap"]["elapsed"] < 600 for s_ in samples])
    lines = ["| Modelo | Log loss | Femeninas | Masculinas | Primeros 10 min | Desvío máx. por decil |", "|---|---|---|---|---|---|"]
    for name, p in (("A. App (parámetros actuales)", app), ("A3. Estructural calibrado por familia", p_season), ("A4. A3 + valor previo bayesiano (Kalman, cada temporada de cero)", p_kalman),
                    ("A5. A3 + valor previo bayesiano con la temporada anterior", p_carry)):
        lines.append(f"| {name} | {log_loss(p, y):.4f} | {log_loss(p[fem], y[fem]):.4f} | {log_loss(p[mas], y[mas]):.4f} | {log_loss(p[early], y[early]):.4f} | {decile_gap(p, y):.1f} pp |")
    lines += ["", f"Parámetros elegidos (`wp_sigma`, `wp_home_adv`, `wp_n0`) por familia y mitad: A3 {c_season}; A4 {c_kalman}; A5 {c_carry}.", ""]
    index: Dict[str, List[int]] = {}
    for i, x in enumerate(g):
        index.setdefault(x, []).append(i)
    ids_ = list(index)
    rng = np.random.default_rng(0)

    def per_game(p):
        p = np.clip(p, 1e-4, 1 - 1e-4)
        loss = -(y * np.log(p) + (1 - y) * np.log(1 - p))
        return np.array([loss[index[k]].sum() for k in ids_]), np.array([len(index[k]) for k in ids_])

    (la, n), (l3, _), (l4, _), (l5, _) = per_game(app), per_game(p_season), per_game(p_kalman), per_game(p_carry)
    for name, d in (("A3 − app", l3 - la), ("A4 − app", l4 - la), ("A5 − app", l5 - la), ("A4 − A3", l4 - l3), ("A5 − A4", l5 - l4)):
        boot = [d[k].sum() / n[k].sum() for k in (rng.integers(0, len(ids_), len(ids_)) for _ in range(500))]
        lines.append(f"- {name}: {d.sum() / n.sum():+.4f} (IC 95 % por partidos {np.percentile(boot, 2.5):+.4f} a {np.percentile(boot, 97.5):+.4f})")
    return "\n".join(lines)
