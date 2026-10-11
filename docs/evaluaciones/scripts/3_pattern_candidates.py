import sys, json, os, collections, statistics as st, pathlib
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from src.live_core.events import parse_line
S = pathlib.Path(sys.argv[1]) / "eval"; OWN, RIVAL = "1008631", "1008898"
def events(doc): return sorted([e for e in (parse_line(l) for l in doc["PLAYBYPLAY"]["LINES"]) if e and not e.deleted], key=lambda e: (e.elapsed, e.num))
def pts(evs, team, a, b): return sum(e.points for e in evs if e.team_id == team and a < e.elapsed <= b and e.points)
doc = json.load(open(S/"games/2524470.json", encoding="utf-8")); E = events(doc)
mm = lambda s: f"{int(s)//60}:{int(s)%60:02d}"
# (c) own timeouts context
print("== own timeouts context (León)")
for e in E:
    if e.kind == "timeout":
        t = e.elapsed; opp = RIVAL if e.team_id == OWN else OWN
        print(("OWN " if e.team_id == OWN else "RIV "), f"Q{e.period} {mm(e.remaining)}", "opp150", pts(E, opp, t-150, t), "own150", pts(E, e.team_id, t-150, t), "tov300", sum(1 for x in E if x.kind=="turnover" and x.team_id==e.team_id and t-300<x.elapsed<=t), "last 5 own-team events:", [x.kind for x in E if x.elapsed<=t and x.team_id==e.team_id][-4:])
# (a) own scoring droughts (no FG/FT made)
sc = [e.elapsed for e in E if e.team_id == OWN and e.points]
gaps = sorted([(b - a, a) for a, b in zip([0] + sc, sc + [2400])], reverse=True)[:5]
print("\n== own longest droughts (s, from):", [(g, mm(a)) for g, a in gaps])
rsc = [e.elapsed for e in E if e.team_id == RIVAL and e.points]
print("rival longest droughts:", [(g, mm(a)) for g, a in sorted([(b - a, a) for a, b in zip([0] + rsc, rsc + [2400])], reverse=True)[:3]])
# (b) lineup segments
on = {OWN: set(), RIVAL: set()}; seg_start = 0; segs = []
def close(t, key, a_for, a_ag): segs.append((key, t))
cur = {}; lineup_t0 = {OWN: 0, RIVAL: 0}
# build on-court via sub events, starters = sub_in at elapsed 0 (FEB logs starters as sub_in at 0)
timeline = [e for e in E if e.kind in ("sub_in", "sub_out") and e.team_id == OWN]
members = set(); last_t = 0; last_s = (0, 0); rows = []
def score_at(t): return (pts(E, OWN, -1, t), pts(E, RIVAL, -1, t))
last_score = (0, 0)
for e in timeline:
    if e.elapsed != last_t and len(members) == 5 and e.elapsed > last_t:
        s = score_at(e.elapsed); rows.append((frozenset(members), last_t, e.elapsed, s[0]-last_score[0], s[1]-last_score[1])); last_score = s; last_t = e.elapsed
    elif e.elapsed != last_t: last_t = e.elapsed; last_score = score_at(e.elapsed)
    (members.add if e.kind == "sub_in" else members.discard)(e.player_id)
agg = collections.defaultdict(lambda: [0, 0, 0])
for m, a, b, f, g in rows: agg[m][0] += b - a; agg[m][1] += f; agg[m][2] += g
names = {}
for e in E:
    if e.player_id: names[e.player_id] = e.name
print("\n== León lineups (>=240 s on court)")
for m, (sec, f, g) in sorted(agg.items(), key=lambda kv: kv[1][1] - kv[1][2]):
    if sec >= 240: print(mm(sec), f"{f}-{g} ({f-g:+d})", sorted((names.get(p, p) or "?").split()[-1] for p in m))
# (d) run-rule simulation over all games and coaches
print("\n== run-rule simulation (all 16 games, both teams)")
G = []
for f in sorted((S/"games").glob("*.json")):
    d = json.load(open(f, encoding="utf-8")); ev = events(d); teams = [t["id"] for t in d["HEADER"]["TEAM"]]
    G.append((ev, teams))
for thr, win, mode in [(8, 150, "unanswered"), (6, 150, "net"), (8, 150, "net"), (10, 180, "net"), (8, 240, "net"), (10, 240, "net")]:
    trig = 0; hit = 0; to_total = 0; to_hit = 0
    for ev, teams in G:
        for team in teams:
            opp = [t for t in teams if t != team][0]
            tos = [e.elapsed for e in ev if e.kind == "timeout" and e.team_id == team]
            to_total += len(tos); last = -999
            fired = []
            for e in ev:
                if e.team_id == opp and e.points and e.elapsed - last >= win:
                    o = pts(ev, opp, e.elapsed - win, e.elapsed); w = pts(ev, team, e.elapsed - win, e.elapsed)
                    ok = (o >= thr and w == 0) if mode == "unanswered" else (o - w >= thr)
                    if ok: fired.append(e.elapsed); last = e.elapsed
            trig += len(fired)
            hit += sum(1 for t in fired if any(t <= x <= t + 120 for x in tos))
            to_hit += sum(1 for x in tos if any(t <= x <= t + 120 for t in fired))
    print(f"{mode:<10} >={thr} in {win}s: fires {trig/32:.1f}/team-game, followed by own timeout in 120s: {hit/trig:.0%} | timeouts covered: {to_hit}/{to_total} ({to_hit/to_total:.0%})")
