import sys, json, pathlib, datetime as dt
import os; sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from src.live_prep.package_builder import build_package
from src.live_prep.recording_report import merged_documents
from src.live_core.session import LiveSession

S = pathlib.Path(sys.argv[1]); REC = pathlib.Path(sys.argv[2])
OWN, RIVAL = "1008631", "1008898"
MATCH_START = dt.datetime(2026, 10, 10, 17, 0)
prior = []
for f in sorted((S/"games").glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    st = dt.datetime.strptime(d["HEADER"]["starttime"], "%d-%m-%Y - %H:%M")
    if st < MATCH_START: prior.append(d)
print("prior games:", len(prior))
pkg = build_package(prior, "LF_CHALLENGE", "2026/2027", OWN, RIVAL, {"match": {"code": "2524470"}})
(S/"package.json").write_text(pkg.dumps(), encoding="utf-8")
session = LiveSession(pkg.dumps())
print("meta:", session.meta["team"], "vs", session.meta["rival"])
rows = []; n = 0
for t, doc in merged_documents(REC):
    out = session.update(doc); n += 1
    snap = out["snapshot"]
    for a in out["alerts"]:
        rows.append({"poll_t": t, "elapsed": snap.get("elapsed"), "period": snap.get("period"), "remaining": snap.get("remaining"),
                     "score": snap.get("score"), "alert": a})
print("updates", n, "alerts", len(rows))
(S/"alerts.json").write_text(json.dumps(rows, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
import collections
print(collections.Counter((r["alert"]["id"], r["alert"]["severity"]) for r in rows))
