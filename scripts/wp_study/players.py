"""The individual experiment (issue #567): who is on court. Adjusted plus-minus ratings from earlier games, and whether the fives on court predict what comes."""
from __future__ import annotations

import math
import pickle
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .samples import features, log_loss


STINT_S = 30


def lineup_pass(folder: str) -> Dict[str, Any]:
    """Replays the games of a folder keeping WHO IS ON COURT: rows of ``STINT_S`` seconds (home five, away five, margin gained by the home team, seconds) for the ratings, and the
    two fives at every cut of 300 s for the evaluation. ``{game id: {...}}`` in date order."""
    from src.live_core.engine import LiveEngine
    from src.live_prep.eval_feed import finished_game_polls
    from src.live_prep.eval_source import game_code, games_from_dir

    out: Dict[str, Any] = {}
    for order, game in enumerate(games_from_dir(folder)):
        ids = [str(t["id"]) for t in game["HEADER"]["TEAM"]]
        if len(ids) != 2:
            continue
        engine, rows, cuts, state, snap = LiveEngine(), [], {}, None, None
        for poll in finished_game_polls(game, latency_s=0.0, poll_s=10.0):
            snap = engine.update(poll.doc)
            fives = {tid: sorted(pid for pid, p in snap["players"].items() if p["team_id"] == tid and p["on_court"]) for tid in ids}
            if not all(len(f) == 5 for f in fives.values()):
                continue
            now = snap["elapsed"]
            margin = snap["score"].get(ids[0], 0) - snap["score"].get(ids[1], 0)
            if state is None:
                state = (now, margin, (fives[ids[0]], fives[ids[1]]))
            elif now - state[0] >= STINT_S:
                rows.append((state[2][0], state[2][1], margin - state[1], now - state[0]))
                state = (now, margin, (fives[ids[0]], fives[ids[1]]))
            cut = (now // 300) * 300
            if 0 < cut < 2400 and cut not in cuts:
                cuts[cut] = fives
        box = {pid: {"team": p["team_id"], "min": p["minutes"], "pts": p["pts"], "pf": p["pf"], **p["stats"]} for pid, p in (snap or {}).get("players", {}).items()}   # the box score of the game: the prior of a rating
        out[str(game_code(game))] = {"order": order, "teams": ids, "rows": rows, "cuts": cuts, "box": box}
    return out


def collect_lineups(folders: Sequence[str], out: str) -> None:
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lineup_pass, folders))
    data = dict(zip(folders, results))
    for folder, games in data.items():
        print(f"{folder}: {len(games)} games, {sum(len(g['rows']) for g in games.values())} stint rows", flush=True)
    with open(out, "wb") as fh:
        pickle.dump(data, fh)


def ratings(games: Dict[str, Any], codes: Sequence[str], ridge: float = 2000.0, prior: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Adjusted plus-minus of every player (points per 40 minutes above the average player), ridge-regularised, from the rows of the games in ``codes`` only."""
    import numpy as np
    from scipy.sparse import csr_matrix, diags
    from scipy.sparse.linalg import lsqr

    players: Dict[str, int] = {}
    data, ri, ci, y, w = [], [], [], [], []
    for code in codes:
        for home, away, delta, seconds in games[code]["rows"]:
            r = len(y)
            for pid, sign in [(p, 1.0) for p in home] + [(p, -1.0) for p in away]:
                data.append(sign)
                ri.append(r)
                ci.append(players.setdefault(pid, len(players)))
            y.append(delta / seconds * 2400)               # per 40 minutes
            w.append(seconds)
    if not y:
        return {}
    A = csr_matrix((data, (ri, ci)), shape=(len(y), len(players)))
    sw = np.sqrt(np.array(w, dtype=float))
    mu = np.array([(prior or {}).get(pid, 0.0) for pid in players])           # shrink towards what the box score says of the player, not towards zero
    beta = lsqr(diags(sw) @ A, (np.array(y) - A @ mu) * sw, damp=math.sqrt(ridge))[0]
    return {pid: float(mu[i] + beta[i]) for pid, i in players.items()}


BOX = ["pts", "ast", "orb", "drb", "stl", "blk", "tov", "pf", "fga", "fta"]


def box_prior(games: Dict[str, Any], codes: Sequence[str], ridge: float, min_minutes: float = 60.0) -> Dict[str, float]:
    """A prior rating from the box score alone: the plain ratings are regressed on the per-40 box of the players with minutes, and applied to every player."""
    import numpy as np
    from sklearn.linear_model import Ridge

    total: Dict[str, Dict[str, float]] = {}
    for code in codes:
        for pid, b in (games[code].get("box") or {}).items():
            row = total.setdefault(pid, {"min": 0.0, **{k: 0.0 for k in BOX}})
            row["min"] += b["min"] / 60
            for k in ("pts", "ast", "orb", "drb", "stl", "blk", "tov", "pf"):
                row[k] += b.get(k, 0)
            row["fga"] += b.get("fg2a", 0) + b.get("fg3a", 0)
            row["fta"] += b.get("fta", 0)
    plain = ratings(games, codes, ridge)
    pids = [p_ for p_, r in total.items() if r["min"] >= min_minutes and p_ in plain]        # enough minutes for the plain rating to say something
    if len(pids) < 30:
        return {}
    per40 = lambda r: [r[k] / r["min"] * 40 for k in BOX]  # noqa: E731
    X = np.array([per40(total[p_]) for p_ in pids])
    y = np.array([plain[p_] for p_ in pids])
    w = np.array([total[p_]["min"] for p_ in pids])
    mu, sd = X.mean(0), X.std(0) + 1e-9
    model = Ridge(alpha=10.0).fit((X - mu) / sd, y, sample_weight=w)
    return {p_: float(model.predict(((np.array([per40(r)]) - mu) / sd))[0]) for p_, r in total.items() if r["min"] >= 8}


def individual(samples_path: str, lineups_path: str) -> str:
    import numpy as np
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    samples, lineups = pickle.load(open(samples_path, "rb")), pickle.load(open(lineups_path, "rb"))
    rows, target, wins, groups, reliability = [], [], [], [], []
    by_side: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for s_ in samples:
        by_side.setdefault((s_["source"], s_["game"], s_["team"]), []).append(s_)
    for folder, games in lineups.items():
        codes = sorted(games, key=lambda c: games[c]["order"])
        cut = int(len(codes) * 0.6)
        train, test = codes[:cut], set(codes[cut:])
        rate = ratings(games, train)
        rate_box = ratings(games, train, prior=box_prior(games, train, 2000.0))
        parent, season = folder.rsplit("/", 1)
        earlier = sorted(f for f in lineups if f.rsplit("/", 1)[0] == parent and f.rsplit("/", 1)[1] < season)          # every earlier season of the same competition
        if earlier:                                                      # the players are mostly the same from one season to the next
            pool = {f"{k}:{c}": g_ for k, f in enumerate(earlier) for c, g_ in lineups[f].items()} | games
            rate_carry = ratings(pool, [f"{k}:{c}" for k, f in enumerate(earlier) for c in lineups[f]] + train)
            used = [f"{k}:{c}" for k, f in enumerate(earlier) for c in lineups[f]] + train
            rate_carry_box = ratings(pool, used, prior=box_prior(pool, used, 2000.0))
        else:
            rate_carry, rate_carry_box = rate, rate_box
        before = bool(earlier)
        half = ratings(games, train[::2]), ratings(games, train[1::2])
        common = [p for p in half[0] if p in half[1]]
        if len(common) > 20:
            reliability.append((folder, len(common), float(np.corrcoef([half[0][p] for p in common], [half[1][p] for p in common])[0, 1])))
        for (source, game, team), cuts in by_side.items():
            if source != folder or game not in test or game not in games:
                continue
            cuts.sort(key=lambda c: c["cut"])
            info = games[game]["cuts"]
            for a, b in zip(cuts, cuts[1:]):
                if b["cut"] - a["cut"] != 300 or a["cut"] not in info:
                    continue
                own, rival = a["team"], a["rival"]
                five_o, five_r = info[a["cut"]].get(own, []), info[a["cut"]].get(rival, [])
                if len(five_o) != 5 or len(five_r) != 5:
                    continue
                strength = lambda ps: sum(rate.get(p, 0.0) for p in ps)               # a player never seen is worth the average  # noqa: E731
                carried = lambda ps: sum(rate_carry.get(p, 0.0) for p in ps)  # noqa: E731
                boxed = lambda ps: sum(rate_box.get(p, 0.0) for p in ps)  # noqa: E731
                carried_box = lambda ps: sum(rate_carry_box.get(p, 0.0) for p in ps)  # noqa: E731
                f = features(a)
                rows.append([f["prior_net"], f["home"], f["margin"], f["frac_left"], strength(five_o) - strength(five_r), strength(five_o), strength(five_r), carried(five_o) - carried(five_r), 1.0 if before else 0.0, boxed(five_o) - boxed(five_r), carried_box(five_o) - carried_box(five_r)])
                target.append((b["snap"]["score"][own] - b["snap"]["score"][rival]) - (a["snap"]["score"][own] - a["snap"]["score"][rival]))
                wins.append(int(a["won"]))
                groups.append(f"{folder}:{game}")
    X, y, w, g = np.array(rows), np.array(target, dtype=float), np.array(wins), np.array(groups)
    lines = [f"{len(y)} tramos de 5 minutos de {len(set(g))} partidos de la parte posterior de cada temporada (el 60 % de partidos más antiguo de cada carpeta calcula los ratings; estos no se han visto).", "",
             "Fiabilidad de los ratings (correlación entre los calculados con los partidos pares y los impares del tramo de entrenamiento, jugadores presentes en ambos):", "",
             "| Carpeta | Jugadores | Correlación |", "|---|---|---|"]
    lines += [f"| {f.split('historical_games/')[-1][-22:]} | {n} | {r:+.2f} |" for f, n, r in reliability]
    sets = {"valor previo + campo + marcador (equipo)": [0, 1, 2, 3], "+ calidad de los quintetos en pista (propio − rival)": [0, 1, 2, 3, 4], "+ los dos quintetos por separado": [0, 1, 2, 3, 5, 6], "+ quintetos con valor previo de la estadística individual": [0, 1, 2, 3, 9]}
    lines += ["", "Margen de los 5 min siguientes (R², validación cruzada por partido):", "", "| Variables | R² |", "|---|---|"]
    for name, cols in sets.items():
        pred = np.zeros(len(y))
        for tr, te in GroupKFold(n_splits=5).split(X, y, g):
            mu, sd = X[tr][:, cols].mean(0), X[tr][:, cols].std(0) + 1e-9
            pred[te] = Ridge(alpha=1.0).fit((X[tr][:, cols] - mu) / sd, y[tr]).predict((X[te][:, cols] - mu) / sd)
        lines.append(f"| {name} | {1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2):.4f} |")
    with_before = X[:, 8] == 1.0
    if with_before.any():
        lines += ["", f"Solo las carpetas con alguna temporada anterior de la misma competición ({int(with_before.sum())} tramos): ratings de esa temporada y del 60 % antiguo de la actual.", "",
                  "| Variables | R² |", "|---|---|"]
        Xs, ys, gs = X[with_before], y[with_before], g[with_before]
        for name, cols_ in (("equipo (valor previo + campo + marcador)", [0, 1, 2, 3]), ("+ quintetos con ratings de la temporada actual", [0, 1, 2, 3, 4]),
                            ("+ quintetos con ratings que incluyen las temporadas anteriores", [0, 1, 2, 3, 7]),
                            ("+ ídem con valor previo de la estadística individual", [0, 1, 2, 3, 10])):
            pred = np.zeros(len(ys))
            for tr, te in GroupKFold(n_splits=5).split(Xs, ys, gs):
                mu_, sd_ = Xs[tr][:, cols_].mean(0), Xs[tr][:, cols_].std(0) + 1e-9
                pred[te] = Ridge(alpha=1.0).fit((Xs[tr][:, cols_] - mu_) / sd_, ys[tr]).predict((Xs[te][:, cols_] - mu_) / sd_)
            lines.append(f"| {name} | {1 - np.sum((ys - pred) ** 2) / np.sum((ys - ys.mean()) ** 2):.4f} |")
    cols = [0, 1, 2, 3, 4]
    mu, sd = X[:, cols].mean(0), X[:, cols].std(0) + 1e-9
    coef = Ridge(alpha=1.0).fit((X[:, cols] - mu) / sd, y).coef_
    lines += ["", "Coeficientes tipificados (puntos de margen en 5 min por desviación típica): " + ", ".join(f"{n} {c:+.3f}" for n, c in zip(["valor previo", "campo", "marcador", "tiempo", "quinteto propio − rival"], coef)) + ".", "",
              "Probabilidad de ganar (log loss, validación cruzada por partido):", "", "| Variables | Log loss |", "|---|---|"]
    z = np.column_stack([X[:, 2] / np.sqrt(np.maximum(X[:, 3], 0.02)), X[:, 1], X[:, 0]])
    preds: List[Any] = []
    for name, extra in (("marcador, tiempo, campo y valor previo", None), ("+ calidad de los quintetos en pista", X[:, 4])):
        Z = z if extra is None else np.column_stack([z, extra])
        p = np.zeros(len(w))
        for tr, te in GroupKFold(n_splits=5).split(Z, w, g):
            p[te] = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(Z[tr], w[tr]).predict_proba(Z[te])[:, 1]
        lines.append(f"| {name} | {log_loss(p, w):.4f} |")
        preds.append(p)
    # paired bootstrap by game of the difference in log loss: is the gain more than noise?
    games = sorted(set(g))
    index = {game: np.where(g == game)[0] for game in games}
    loss = lambda p_: -(w * np.log(np.clip(p_, 1e-4, 1 - 1e-4)) + (1 - w) * np.log(np.clip(1 - p_, 1e-4, 1 - 1e-4)))  # noqa: E731
    gain = loss(preds[0]) - loss(preds[1])
    per_game = np.array([gain[index[game]].sum() for game in games])
    size = np.array([len(index[game]) for game in games])
    rng = np.random.default_rng(0)
    boot = [per_game[pick].sum() / size[pick].sum() for pick in (rng.integers(0, len(games), len(games)) for _ in range(1000))]
    # the coefficient of the quality of the fives, with the games as the unit of resampling
    coefs = []
    for pick in (rng.integers(0, len(games), len(games)) for _ in range(300)):
        rows_ = np.concatenate([index[games[k]] for k in pick])
        mu_, sd_ = X[rows_][:, cols].mean(0), X[rows_][:, cols].std(0) + 1e-9
        coefs.append(Ridge(alpha=1.0).fit((X[rows_][:, cols] - mu_) / sd_, y[rows_]).coef_[4])
    lines += ["", f"Coeficiente del quinteto propio − rival con intervalo 95 % por partidos: {coef[4]:+.3f} ({np.percentile(coefs, 2.5):+.3f} a {np.percentile(coefs, 97.5):+.3f})."]
    lines += ["", f"Mejora del log loss con los quintetos: {per_game.sum() / size.sum():+.4f} (intervalo 95 % por partidos: {np.percentile(boot, 2.5):+.4f} a {np.percentile(boot, 97.5):+.4f})."]
    return "\n".join(lines)
