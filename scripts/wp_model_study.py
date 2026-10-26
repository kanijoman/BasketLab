"""Study of the models behind the win probability and its levers (issue #567): does a model with more information beat the one in the app?

``python scripts/wp_model_study.py collect --out samples.pkl DIR [DIR ...]`` replays the finished games of each folder (ONE season of ONE competition per folder: every folder has its own priors) and
keeps, at a cut every 5 minutes and from both sides, what the engine knows: score, clock, the team stats of both teams, fouls, timeouts, the last five minutes and the package baselines.
``python scripts/wp_model_study.py fit samples.pkl`` compares, with cross-validation BY GAME (a game never is in train and test), the structural model of the app with logistic and boosted models that
read more, and prints the contribution of each group of variables (the base of the levers). Research tool, not part of the product: it needs scikit-learn.
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(extra))

RECENT_S = 300


def rich_trim(snap: Dict[str, Any]) -> Dict[str, Any]:
    """What ``wp_eval`` keeps of a snapshot plus what the models of the study read (fouls, timeouts used, points of the last five minutes)."""
    now = snap["elapsed"]
    recent: Dict[str, int] = {tid: 0 for tid in snap["teams"]}
    for event in snap.get("log", []):
        if event[2] == "pts" and event[0] > now - RECENT_S and event[1] in recent:
            recent[event[1]] += event[3]
    return {"score": dict(snap["score"]), "elapsed": now, "home_id": snap.get("home_id"),
            "teams": {tid: {"stats": dict(t["stats"]), "fouls": t.get("fouls_game", 0), "timeouts": len(t.get("timeouts", [])), "recent": recent[tid]} for tid, t in snap["teams"].items()}}


def collect(folders: Sequence[str], out: str) -> None:
    from src.live_prep import wp_eval
    from src.live_prep.eval_source import games_from_dir

    wp_eval._trimmed = rich_trim                                    # the replay keeps more than the calibration needs
    samples: List[Dict[str, Any]] = []
    for folder in folders:
        found = wp_eval.collect_samples(games_from_dir(folder), cut_s=300, min_prior_games=3)
        for s in found:
            s["source"] = folder
        print(f"{folder}: {len({s['game'] for s in found})} games, {len(found)} samples", flush=True)
        samples += found
    with open(out, "wb") as fh:
        pickle.dump(samples, fh)
    print(f"{len(samples)} samples -> {out}")


# --- a stronger prior: opponent-adjusted ratings from the margins of the games played before (ridge regression of the margin on the two teams) -----------------

def prior_ratings(folder: str, ridge: float = 4.0) -> Dict[str, Dict[str, float]]:
    """``{game code: {team id: rating in points per game}}`` with ONLY the games that started earlier (a team is worth what it did against those it faced, not its raw average)."""
    import numpy as np

    from src.live_prep.eval_source import games_from_dir, parse_starttime

    played = []
    for game in games_from_dir(folder):
        teams = (game.get("HEADER") or {}).get("TEAM") or []
        try:
            ids, pts = [str(t["id"]) for t in teams], [int(t["pts"]) for t in teams]
        except (KeyError, TypeError, ValueError):
            continue
        if len(ids) == 2 and any(pts):
            played.append({"code": str(game.get("_id") or (game.get("HEADER") or {}).get("game_code")), "start": parse_starttime(game), "ids": ids, "margin": pts[0] - pts[1]})
    out: Dict[str, Dict[str, float]] = {}
    for game in played:
        before = [g for g in played if g["start"] is not None and game["start"] is not None and g["start"] < game["start"]]
        teams = sorted({t for g in before for t in g["ids"]})
        if len(before) < 6 or not teams:
            out[game["code"]] = {}
            continue
        col = {t: i for i, t in enumerate(teams)}
        A = np.zeros((len(before), len(teams) + 1))
        y = np.zeros(len(before))
        for i, g in enumerate(before):
            A[i, col[g["ids"][0]]], A[i, col[g["ids"][1]]], A[i, -1], y[i] = 1.0, -1.0, 1.0, g["margin"]      # the last column is the home court
        penalty = ridge * np.eye(len(teams) + 1)
        penalty[-1, -1] = 0.0
        beta = np.linalg.solve(A.T @ A + penalty, A.T @ y)
        out[game["code"]] = {t: float(beta[col[t]]) for t in teams}
    return out


# --- features ---------------------------------------------------------------------------------------------------------------------------------

BASE = ["margin", "z", "frac_left", "home", "prior_net", "pace_prior"]
FACTORS = ["efg", "tov", "orb", "ftr"]
GAME = (["poss"] + [f"d_{f}" for f in FACTORS] + [f"own_{f}" for f in FACTORS] + [f"rival_{f}" for f in FACTORS]
        + ["recent_net", "fouls_own", "fouls_rival", "timeouts_own", "timeouts_rival", "pts_per_poss_own", "pts_per_poss_rival"])
GROUPS = {
    "marcador y tiempo": ["margin", "z", "frac_left"],
    "valor previo (equipos + campo)": ["home", "prior_net", "pace_prior"],
    "ritmo": ["poss"],
    "tiro (acierto efectivo)": ["d_efg", "own_efg", "rival_efg"],
    "balón (pérdidas)": ["d_tov", "own_tov", "rival_tov"],
    "rebote ofensivo": ["d_orb", "own_orb", "rival_orb"],
    "tiros libres": ["d_ftr", "own_ftr", "rival_ftr"],
    "racha (últimos 5 min)": ["recent_net"],
    "faltas y tiempos muertos": ["fouls_own", "fouls_rival", "timeouts_own", "timeouts_rival"],
    "eficiencia por posesión": ["pts_per_poss_own", "pts_per_poss_rival"],
}


def features(sample: Dict[str, Any]) -> Dict[str, float]:
    from src.live_core.four_factors import FourFactorsModel, possessions

    snap, own, rival, base = sample["snap"], sample["team"], sample["rival"], sample["baselines"]
    margin = snap["score"][own] - snap["score"][rival]
    frac = max(0, 2400 - snap["elapsed"]) / 2400
    home = snap.get("home_id")
    ff = FourFactorsModel(own, rival, base).evaluate(snap) or {}
    fo, fr, diffs = ff.get("factors_own") or {}, ff.get("factors_rival") or {}, ff.get("diffs") or {}
    t_own, t_rival = snap["teams"][own], snap["teams"][rival]
    poss_own, poss_rival = possessions(t_own["stats"]), possessions(t_rival["stats"])
    row = {"margin": margin, "z": margin / math.sqrt(max(frac, 0.02)), "frac_left": frac, "home": 1.0 if home == own else -1.0 if home == rival else 0.0,
           "prior_net": float(base.get("net_rtg_prior", 0.0)), "pace_prior": float(base.get("pace_per_40") or 70.0), "poss": (poss_own + poss_rival) / 2,
           "recent_net": t_own["recent"] - t_rival["recent"], "fouls_own": t_own["fouls"], "fouls_rival": t_rival["fouls"],
           "timeouts_own": t_own["timeouts"], "timeouts_rival": t_rival["timeouts"],
           "pts_per_poss_own": t_own["stats"]["pts"] / poss_own if poss_own else 0.0, "pts_per_poss_rival": t_rival["stats"]["pts"] / poss_rival if poss_rival else 0.0}
    for f in FACTORS:
        row[f"d_{f}"], row[f"own_{f}"], row[f"rival_{f}"] = diffs.get(f, 0.0), fo.get(f, 0.0), fr.get(f, 0.0)
    return row


def matrix(samples: Sequence[Dict[str, Any]], names: Sequence[str]):
    import numpy as np

    rows = [features(s) for s in samples]
    return np.array([[r[n] for n in names] for r in rows], dtype=float)


# --- evaluation -------------------------------------------------------------------------------------------------------------------------------

def log_loss(p, y):
    import numpy as np

    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(p, y):
    import numpy as np

    return float(np.mean((p - y) ** 2))


def decile_gap(p, y, min_n: int = 400) -> float:
    import numpy as np

    gaps = []
    for k in range(10):
        m = (p >= k / 10) & (p < (k + 1) / 10 + (1e-9 if k == 9 else 0))
        if m.sum() >= min_n:
            gaps.append(abs(float(y[m].mean() - p[m].mean())) * 100)
    return max(gaps, default=float("nan"))


def cross_val(samples: Sequence[Dict[str, Any]], X, y, groups, make_model) -> Any:
    import numpy as np
    from sklearn.model_selection import GroupKFold

    p = np.zeros(len(y))
    for train, test in GroupKFold(n_splits=5).split(X, y, groups):
        model = make_model()
        model.fit(X[train], y[train])
        p[test] = model.predict_proba(X[test])[:, 1]
    return p


def fit(path: str) -> str:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    from src.live_core.config import RuleConfig
    from src.live_prep.wp_eval import forecast

    samples = pickle.load(open(path, "rb"))
    y = np.array([int(s["won"]) for s in samples])
    groups = np.array([f"{s['source']}:{s['game']}" for s in samples])
    cfg, lines = RuleConfig(), []
    ratings = {folder: prior_ratings(folder) for folder in sorted({s["source"] for s in samples})}
    srs = np.array([ratings[s["source"]].get(s["game"], {}).get(s["team"], 0.0) - ratings[s["source"]].get(s["game"], {}).get(s["rival"], 0.0) for s in samples])
    names_all = BASE + GAME
    X_all, X_base = matrix(samples, names_all), matrix(samples, BASE)
    X_srs = np.column_stack([matrix(samples, ["margin", "z", "frac_left", "home"]), srs])
    X_both = np.column_stack([X_base, srs])
    results: Dict[str, Any] = {}
    for variant, label in (("full", "A. Modelo de la app (estructural, valor previo + cuatro factores)"), ("prior_only", "B. Solo valor previo"), ("score_time", "C. Solo marcador y tiempo")):
        results[label] = np.array([forecast(s, cfg, variant)["p"] for s in samples])
    logit = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))  # noqa: E731
    boost = lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0, random_state=0)  # noqa: E731
    results["D. Logística con marcador, tiempo y valor previo"] = cross_val(samples, X_base, y, groups, logit)
    results["G. Logística con marcador, tiempo y valor previo ajustado por rival (ridge)"] = cross_val(samples, X_srs, y, groups, logit)
    results["H. Logística con los dos valores previos"] = cross_val(samples, X_both, y, groups, logit)
    results["E. Logística con toda la información"] = cross_val(samples, X_all, y, groups, logit)
    results["F. Árboles potenciados con toda la información"] = cross_val(samples, X_all, y, groups, boost)
    games = len(set(groups))
    lines += [f"{len(samples)} cortes de {games} partidos ({len(set(s['source'] for s in samples))} carpetas), validación cruzada por partido (5 grupos).", "",
              "| Modelo | Log loss | Brier | Mayor desvío por decil (≥ 400 cortes) |", "|---|---|---|---|"]
    for label, p in results.items():
        lines.append(f"| {label} | {log_loss(p, y):.4f} | {brier(p, y):.4f} | {decile_gap(p, y):.1f} pp |")
    # by stage of the game
    lines += ["", "Log loss por tramo del partido:", "", "| Minutos jugados | " + " | ".join(l.split('.')[0] for l in results) + " |", "|---|" + "---|" * len(results)]
    elapsed = np.array([s["snap"]["elapsed"] for s in samples])
    for lo, hi in ((0, 600), (600, 1200), (1200, 1800), (1800, 2400)):
        m = (elapsed >= lo) & (elapsed < hi)
        lines.append(f"| {lo // 60}-{hi // 60} ({int(m.sum())}) | " + " | ".join(f"{log_loss(p[m], y[m]):.4f}" for p in results.values()) + " |")
    # contribution of each group (logistic E, standardised) and permutation importance (trees F)
    model = logit()
    model.fit(X_all, y)
    coef = model[-1].coef_[0]
    index = {n: i for i, n in enumerate(names_all)}
    lines += ["", "Peso de cada grupo de variables en la logística con toda la información (suma de |coeficiente tipificado| del grupo, y el signo de cada variable):", "",
              "| Grupo | Peso | Variables (coeficiente) |", "|---|---|---|"]
    for group, cols in GROUPS.items():
        lines.append(f"| {group} | {sum(abs(coef[index[c]]) for c in cols):.2f} | " + ", ".join(f"{c} {coef[index[c]]:+.2f}" for c in cols) + " |")
    trees = boost()
    trees.fit(X_all, y)
    imp = permutation_importance(trees, X_all, y, n_repeats=5, random_state=0, scoring="neg_log_loss")
    lines += ["", "Importancia por permutación en los árboles (caída de log loss al barajar el grupo; mayor = más usado):", "", "| Grupo | Importancia |", "|---|---|"]
    for group, cols in GROUPS.items():
        lines.append(f"| {group} | {sum(imp.importances_mean[index[c]] for c in cols):.4f} |")
    return "\n".join(lines)


def persistence(path: str) -> str:
    """Do the stats of the game predict what happens in the NEXT five minutes? (the base a lever needs: a deficit that persists is worth correcting, one that is luck is not).

    Target: margin gained by the side in the next cut (300 s) per 100 possessions-equivalent (here: points). Baseline: prior of the matchup, home court and the score; then the
    four-factor differentials of the last five minutes and of the whole game so far. Cross-validated R2 by game, and the standardised coefficient of each factor."""
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import GroupKFold

    from src.live_core.four_factors import differentials, factors

    samples = pickle.load(open(path, "rb"))
    by_side: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for s_ in samples:
        by_side.setdefault((s_["source"], s_["game"], s_["team"]), []).append(s_)
    rows, target, groups = [], [], []
    for key, cuts in by_side.items():
        cuts.sort(key=lambda c: c["cut"])
        for a, b in zip(cuts, cuts[1:]):
            if b["cut"] - a["cut"] != 300:
                continue
            own, rival = a["team"], a["rival"]
            win_own = {k: b["snap"]["teams"][own]["stats"][k] - a["snap"]["teams"][own]["stats"][k] for k in a["snap"]["teams"][own]["stats"]}
            win_rival = {k: b["snap"]["teams"][rival]["stats"][k] - a["snap"]["teams"][rival]["stats"][k] for k in a["snap"]["teams"][rival]["stats"]}
            prev = [c for c in cuts if c["cut"] < a["cut"]]
            if not prev:
                continue
            last = prev[-1]                                   # the five minutes BEFORE the cut a: what is known when the lever would be said
            before_own = {k: a["snap"]["teams"][own]["stats"][k] - last["snap"]["teams"][own]["stats"][k] for k in a["snap"]["teams"][own]["stats"]}
            before_rival = {k: a["snap"]["teams"][rival]["stats"][k] - last["snap"]["teams"][rival]["stats"][k] for k in a["snap"]["teams"][rival]["stats"]}
            recent = differentials(before_own, before_rival)
            attack, defence = factors(before_own, before_rival), factors(before_rival, before_own)       # the five minutes before, split: what we did / what the rival did
            season = differentials(a["snap"]["teams"][own]["stats"], a["snap"]["teams"][rival]["stats"])
            f = features(a)
            rows.append([f["prior_net"], f["home"], f["margin"], f["frac_left"]] + [recent[k] for k in FACTORS] + [season[k] for k in FACTORS]
                        + [attack[k] for k in FACTORS] + [defence[k] for k in FACTORS])
            target.append((b["snap"]["score"][own] - b["snap"]["score"][rival]) - (a["snap"]["score"][own] - a["snap"]["score"][rival]))
            groups.append(f"{key[0]}:{key[1]}")
    X, y, g = np.array(rows), np.array(target, dtype=float), np.array(groups)
    sets = {"valor previo + campo + marcador": list(range(4)), "+ factores de los 5 min anteriores": list(range(8)), "+ factores de todo el partido": list(range(4)) + list(range(8, 12)), "todo": list(range(12)), "ataque y defensa por separado (5 min anteriores)": list(range(4)) + list(range(12, 20))}
    lines = [f"{len(y)} tramos de 5 minutos de {len(set(g))} partidos (cada lado cuenta; el objetivo es el margen que gana el equipo en los 5 min siguientes).", "",
             "| Variables | R² (validación cruzada por partido) |", "|---|---|"]
    for name, cols in sets.items():
        pred = np.zeros(len(y))
        for train, test in GroupKFold(n_splits=5).split(X, y, g):
            mu, sd = X[train][:, cols].mean(0), X[train][:, cols].std(0) + 1e-9
            model = Ridge(alpha=1.0).fit((X[train][:, cols] - mu) / sd, y[train])
            pred[test] = model.predict((X[test][:, cols] - mu) / sd)
        lines.append(f"| {name} | {1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2):.4f} |")
    mu, sd = X.mean(0), X.std(0) + 1e-9
    coef = Ridge(alpha=1.0).fit((X - mu) / sd, y).coef_
    names = ["valor previo", "campo", "marcador", "tiempo restante"] + [f"5 min: {f}" for f in FACTORS] + [f"partido: {f}" for f in FACTORS] + [f"ataque 5 min: {f}" for f in FACTORS] + [f"defensa 5 min (del rival): {f}" for f in FACTORS]
    lines += ["", "Coeficiente tipificado (puntos de margen en los 5 min siguientes por desviación típica de la variable):", "", "| Variable | Coeficiente |", "|---|---|"]
    lines += [f"| {n} | {c:+.3f} |" for n, c in zip(names, coef)]
    return "\n".join(lines)


# --- the individual study (who is on court) ----------------------------------------------------------------------------------------------------

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
        engine, rows, cuts, state = LiveEngine(), [], {}, None
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
        out[str(game_code(game))] = {"order": order, "teams": ids, "rows": rows, "cuts": cuts}
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


def ratings(games: Dict[str, Any], codes: Sequence[str], ridge: float = 2000.0) -> Dict[str, float]:
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
    beta = lsqr(diags(sw) @ A, np.array(y) * sw, damp=math.sqrt(ridge))[0]
    return {pid: float(beta[i]) for pid, i in players.items()}


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
        before = lineups.get(folder.replace("/2025", "/2024")) if folder.endswith("/2025") else None
        if before:                                                       # the previous season of the same competition: the players are mostly the same
            pool = {**{f"p:{c}": g_ for c, g_ in before.items()}, **games}
            rate_carry = ratings(pool, [f"p:{c}" for c in before] + train)
        else:
            rate_carry = rate
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
                f = features(a)
                rows.append([f["prior_net"], f["home"], f["margin"], f["frac_left"], strength(five_o) - strength(five_r), strength(five_o), strength(five_r), carried(five_o) - carried(five_r), 1.0 if before else 0.0])
                target.append((b["snap"]["score"][own] - b["snap"]["score"][rival]) - (a["snap"]["score"][own] - a["snap"]["score"][rival]))
                wins.append(int(a["won"]))
                groups.append(f"{folder}:{game}")
    X, y, w, g = np.array(rows), np.array(target, dtype=float), np.array(wins), np.array(groups)
    lines = [f"{len(y)} tramos de 5 minutos de {len(set(g))} partidos de la parte posterior de cada temporada (el 60 % de partidos más antiguo de cada carpeta calcula los ratings; estos no se han visto).", "",
             "Fiabilidad de los ratings (correlación entre los calculados con los partidos pares y los impares del tramo de entrenamiento, jugadores presentes en ambos):", "",
             "| Carpeta | Jugadores | Correlación |", "|---|---|---|"]
    lines += [f"| {f.split('historical_games/')[-1][-22:]} | {n} | {r:+.2f} |" for f, n, r in reliability]
    sets = {"valor previo + campo + marcador (equipo)": [0, 1, 2, 3], "+ calidad de los quintetos en pista (propio − rival)": [0, 1, 2, 3, 4], "+ los dos quintetos por separado": [0, 1, 2, 3, 5, 6]}
    lines += ["", "Margen de los 5 min siguientes (R², validación cruzada por partido):", "", "| Variables | R² |", "|---|---|"]
    for name, cols in sets.items():
        pred = np.zeros(len(y))
        for tr, te in GroupKFold(n_splits=5).split(X, y, g):
            mu, sd = X[tr][:, cols].mean(0), X[tr][:, cols].std(0) + 1e-9
            pred[te] = Ridge(alpha=1.0).fit((X[tr][:, cols] - mu) / sd, y[tr]).predict((X[te][:, cols] - mu) / sd)
        lines.append(f"| {name} | {1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2):.4f} |")
    with_before = X[:, 8] == 1.0
    if with_before.any():
        lines += ["", f"Solo las carpetas con la temporada anterior de la misma competición ({int(with_before.sum())} tramos): ratings de esa temporada y del 60 % antiguo de la actual.", "",
                  "| Variables | R² |", "|---|---|"]
        Xs, ys, gs = X[with_before], y[with_before], g[with_before]
        for name, cols_ in (("equipo (valor previo + campo + marcador)", [0, 1, 2, 3]), ("+ quintetos con ratings de la temporada actual", [0, 1, 2, 3, 4]),
                            ("+ quintetos con ratings que incluyen la temporada anterior", [0, 1, 2, 3, 7])):
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



def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Study of the models of the win probability (#567)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True)
    c.add_argument("folders", nargs="+")
    f = sub.add_parser("fit")
    f.add_argument("samples")
    q = sub.add_parser("persistence")
    q.add_argument("samples")
    cl = sub.add_parser("collect-lineups")
    cl.add_argument("--out", required=True)
    cl.add_argument("folders", nargs="+")
    ind = sub.add_parser("individual")
    ind.add_argument("samples")
    ind.add_argument("lineups")
    args = parser.parse_args(argv)
    if args.cmd == "collect":
        collect(args.folders, args.out)
    elif args.cmd == "collect-lineups":
        collect_lineups(args.folders, args.out)
    elif args.cmd == "individual":
        print(individual(args.samples, args.lineups))
    elif args.cmd == "persistence":
        print(persistence(args.samples))
    else:
        print(fit(args.samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
