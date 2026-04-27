import json

with open("coverage.json") as f:
    cov = json.load(f)

files = []
for path, data in cov["files"].items():
    short = path.replace("src\\", "").replace("src/", "")
    pct = data["summary"]["percent_covered"]
    missing = data["summary"]["missing_lines"]
    stmts = data["summary"]["num_statements"]
    files.append((pct, stmts, missing, short))

files.sort()
print(f"{'Module':<55} {'Stmts':>6} {'Miss':>6} {'Cover':>7}")
print("-" * 80)
for pct, stmts, miss, name in files:
    if pct < 30:
        mark = "  <-- LOW"
    elif pct < 60:
        mark = "  <-- MED"
    else:
        mark = ""
    print(f"{name:<55} {stmts:>6} {miss:>6} {pct:>6.0f}%{mark}")

totals = cov["totals"]
covered = totals["covered_lines"]
num_stmts = totals["num_statements"]
pct_total = totals["percent_covered"]
print()
print(f"TOTAL: {pct_total:.1f}%  ({covered}/{num_stmts} statements)")
