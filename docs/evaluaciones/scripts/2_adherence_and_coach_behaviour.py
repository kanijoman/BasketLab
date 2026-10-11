import sys, json, os, collections, statistics as st, pathlib
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from src.live_core.events import parse_line
S = pathlib.Path(sys.argv[1]) / "eval"
OWN, RIVAL, MATCH = "1008631", "1008898", "2524470"

def events(doc):
    evs = [e for e in (parse_line(l) for l in doc["PLAYBYPLAY"]["LINES"]) if e and not e.deleted]
    evs.sort(key=lambda e: (e.elapsed, e.num)); return evs

def at_boundary(e): return e.remaining in (0, 600) or e.remaining == (300 if e.period > 4 else 600)

def pts(evs, team, a, b): return sum(e.points for e in evs if e.team_id == team and a < e.elapsed <= b and e.points)

# ---------- A. adherence to this game's alerts ----------
doc = json.load(open(S/"games"/f"{MATCH}.json", encoding="utf-8"))
E = events(doc)
alerts = json.load(open(S/"alerts.json", encoding="utf-8"))
res = []
for r in alerts:
    a = r["alert"]; t0 = r["elapsed"]; ev = a.get("evidence", {}); row = {"t0": t0, "period": r["period"], "id": a["id"], "sev": a["severity"], "msg": a["message"]}
    if a["id"] in ("foul_trouble", "fatigue_high") and a.get("proposal"):
        p = a["proposal"][0]; out_id, in_id = p["out_id"], p["in_id"]
        for W in (180, 300):
            out_ev = [e for e in E if e.kind == "sub_out" and e.player_id == out_id and t0 < e.elapsed <= t0 + W]
            in_ev = [e for e in E if e.kind == "sub_in" and e.player_id == in_id and t0 < e.elapsed <= t0 + W]
            row[f"out_{W}"] = bool(out_ev); row[f"in_{W}"] = bool(in_ev)
            if out_ev and W == 300: row["t_out"] = out_ev[0].elapsed - t0
        row["player"] = p["out_name"]; row["proposed_in"] = p["in_name"]
        # who came in for him (first own sub_in within 5 s of his sub_out)
        outs = [e for e in E if e.kind == "sub_out" and e.player_id == out_id and e.elapsed > t0]
        if outs:
            o = outs[0]; ins = [e for e in E if e.kind == "sub_in" and e.team_id == OWN and abs(e.elapsed - o.elapsed) <= 3]
            row["replaced_by"] = [i.name for i in ins]
            row["out_at_boundary"] = at_boundary(o)
        pf_after = [e for e in E if e.kind == "foul" and e.player_id == out_id and e.elapsed > t0]
        row["fouls_after_alert"] = len(pf_after)
    elif a["id"] == "turnover_streak":
        row["timeout_60"] = any(e.kind == "timeout" and e.team_id == OWN and t0 < e.elapsed <= t0 + 120 for e in E)
        row["tov_next300"] = sum(1 for e in E if e.kind == "turnover" and e.team_id == OWN and t0 < e.elapsed <= t0 + 300)
        row["tov_prev300"] = sum(1 for e in E if e.kind == "turnover" and e.team_id == OWN and t0 - 300 < e.elapsed <= t0)
    elif a["id"] == "team_fouls_bonus":
        end = (r["period"]) * 600
        row["own_fouls_after_in_period"] = sum(1 for e in E if e.kind == "foul" and e.team_id == OWN and t0 < e.elapsed <= end)
    elif a["id"] in ("rival_foul_trouble", "rival_near_bonus"):
        row["own_fta_next300"] = sum(1 for e in E if e.kind == "ft" and e.team_id == OWN and t0 < e.elapsed <= t0 + 300)
        row["rival_fouls_next300"] = sum(1 for e in E if e.kind == "foul" and e.team_id == RIVAL and t0 < e.elapsed <= t0 + 300)
        row["own_fta_prev300"] = sum(1 for e in E if e.kind == "ft" and e.team_id == OWN and t0 - 300 < e.elapsed <= t0)
    elif a["id"] == "four_factors_lever":
        def efg(a_, b_, team):
            sh = [e for e in E if e.team_id == team and e.kind in ("fg2", "fg3") and a_ < e.elapsed <= b_]
            m = [e for e in sh if e.made]; return (round((len(m) + 0.5 * sum(1 for e in m if e.kind == "fg3")) / len(sh), 2), len(sh)) if sh else (None, 0)
        row["efg_before"] = efg(0, t0, OWN); row["efg_next300"] = efg(t0, t0 + 300, OWN)
    elif a["id"] in ("rival_hot_player", "rival_zone"):
        row["rival_pts_next300"] = pts(E, RIVAL, t0, t0 + 300); row["rival_pts_prev300"] = pts(E, RIVAL, t0 - 300, t0)
    res.append(row)
json.dump(res, open(S/"adherence.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)

# ---------- B. competition-wide coach behaviour (16 games) ----------
timeouts, vol_stints, foul_cases = [], [], []
for f in sorted((S/"games").glob("*.json")):
    d = json.load(open(f, encoding="utf-8")); evs = events(d); code = f.stem
    teams = [t["id"] for t in d["HEADER"]["TEAM"]] if isinstance(d["HEADER"].get("TEAM"), list) else []
    for e in evs:
        if e.kind == "timeout" and e.team_id:
            opp = [t for t in teams if t != e.team_id]; opp = opp[0] if opp else None
            timeouts.append({"game": code, "team": e.team_id, "elapsed": e.elapsed, "opp150": pts(evs, opp, e.elapsed - 150, e.elapsed), "own150": pts(evs, e.team_id, e.elapsed - 150, e.elapsed),
                             "opp300": pts(evs, opp, e.elapsed - 300, e.elapsed), "own300": pts(evs, e.team_id, e.elapsed - 300, e.elapsed),
                             "tov300": sum(1 for x in evs if x.kind == "turnover" and x.team_id == e.team_id and e.elapsed - 300 < x.elapsed <= e.elapsed)})
    # stint length at mid-period substitutions: track on-court time per player
    on = {}
    for e in evs:
        if e.kind == "sub_in" and e.player_id: on[e.player_id] = e.elapsed
        elif e.kind == "period_start": pass
        elif e.kind == "sub_out" and e.player_id in on:
            stint = e.elapsed - on.pop(e.player_id)
            if not at_boundary(e): vol_stints.append({"game": code, "team": e.team_id, "stint": stint, "period": e.period})
    # foul-trouble handling: when a player gets his 2nd PF in Q1-Q2 / 3rd in Q1-Q3 / 4th any, is he subbed within 120 s?
    for e in evs:
        if e.kind == "foul" and e.player_id and e.foul_type == "personal" and e.pf_count in (2, 3, 4):
            subbed = any(x.kind == "sub_out" and x.player_id == e.player_id and e.elapsed <= x.elapsed <= e.elapsed + 120 for x in evs)
            foul_cases.append({"game": code, "pf": e.pf_count, "period": e.period, "subbed_120": subbed})
json.dump({"timeouts": timeouts, "vol_stints": vol_stints, "foul_cases": foul_cases}, open(S/"coach.json", "w", encoding="utf-8"), indent=1)
print("timeouts", len(timeouts), "voluntary sub stints", len(vol_stints), "foul cases", len(foul_cases))
