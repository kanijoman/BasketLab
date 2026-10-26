"""The samples of the study (issue #567): the replay of finished games at cuts of 5 minutes, the variables the models read and the metrics."""
from __future__ import annotations

import math
import pickle
from typing import Any, Dict, List, Sequence


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
