"""Analysis of a FEB live recording (see ``recorder``): the facts issue #118 needs.

``python -m src.live_prep.recording_report <recording dir> [--replay]`` prints a Markdown report:
status timeline (404 -> LIVE -> FINISHED), how often the play-by-play really changes (cadence),
how late events arrive (``LogTimeUtc`` vs the poll that first saw them), token renewals and HTTP
errors, and - with ``--replay`` - whether ``LiveEngine`` digests the real live documents and how
long an update takes.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


def _read_polls(directory: Path) -> List[Dict[str, Any]]:
    path = directory / "polls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    return {"n": len(values), "median": round(statistics.median(ordered), 2),
            "p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 2), "max": round(ordered[-1], 2)}


def _parse_utc(text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(text.replace("T", " ")[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _status_timeline(polls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for p in polls:
        status = p.get("game_status")
        if p["endpoint"] == "boxscore" and status and status not in seen:
            seen.add(status)
            out.append({"status": status, "t": p["t"], "mono": p["mono"]})
    return out


def _cadence_and_delay(polls: List[Dict[str, Any]]) -> Tuple[int, List[float], List[float]]:
    """Seconds between play-by-play changes, and event delay (poll time - LogTimeUtc of the newest event)."""
    changes, delays, last_lines, last_stamp = [], [], 0, None
    stamps: List[float] = []
    for p in polls:
        if p["endpoint"] != "keyfacts" or p.get("status") != 200 or "pbp_lines" not in p:
            continue
        if p["pbp_lines"] > last_lines:
            stamps.append(p["mono"])
            stamp = _parse_utc(p.get("last_log_utc", ""))
            polled = datetime.fromisoformat(p["t"])
            if stamp and stamp != last_stamp:
                delays.append(round((polled - stamp).total_seconds(), 2))
            last_stamp = stamp or last_stamp
            last_lines = p["pbp_lines"]
    cadence = [round(b - a, 2) for a, b in zip(stamps, stamps[1:])]
    return len(stamps), cadence, delays


def merged_documents(directory: Path) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Rebuild full match documents from the stored bodies (BoxScore + ShotChart + KeyFacts)."""
    directory = Path(directory)
    polls = _read_polls(directory)
    files = sorted((directory / "bodies").glob("*.json.gz")) if (directory / "bodies").exists() else []
    changed = [p for p in polls if p.get("changed") and p.get("status") == 200]
    current: Dict[str, Dict[str, Any]] = {}
    for poll, file in zip(changed, files):
        current[poll["endpoint"]] = json.loads(gzip.decompress(file.read_bytes()))
        if poll["endpoint"] == "shotchart" or not {"boxscore", "keyfacts", "shotchart"} <= set(current):
            continue
        doc = copy.deepcopy(current["boxscore"])
        doc["PLAYBYPLAY"] = copy.deepcopy(current["keyfacts"].get("PLAYBYPLAY") or {})
        doc["SHOTCHART"] = copy.deepcopy(current["shotchart"].get("SHOTCHART") or {})
        yield poll["t"], doc


def _replay(directory: Path) -> Dict[str, Any]:
    from src.live_core.engine import LiveEngine

    engine, times, error = LiveEngine(), [], None
    last = None
    for _, doc in merged_documents(directory):
        started = time.perf_counter()
        try:
            engine.update(doc)
        except Exception as exc:  # noqa: BLE001 - a crash on real live data IS the finding
            error = f"{type(exc).__name__}: {exc}"
            break
        times.append((time.perf_counter() - started) * 1000)
        last = doc
    result: Dict[str, Any] = {"updates": len(times), "crashed": error is not None, "error": error,
                              "max_ms": round(max(times), 1) if times else 0.0,
                              "median_ms": round(statistics.median(times), 1) if times else 0.0}
    if last is not None and str((last.get("HEADER") or {}).get("status")) == "3":
        from src.live_prep.canary import check_totals_for_final_document

        result["final_invariant_errors"] = check_totals_for_final_document(last)
    return result


def summarize(directory: Path, replay: bool = False) -> Dict[str, Any]:
    directory = Path(directory)
    polls = _read_polls(directory)
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8")) if (directory / "meta.json").exists() else {}
    box = [p for p in polls if p["endpoint"] == "boxscore"]
    first_200 = next((p for p in box if p.get("status") == 200), None)
    n_changes, cadence, delays = _cadence_and_delay(polls)
    summary: Dict[str, Any] = {
        "match_code": meta.get("match_code", directory.name), "polls": len(polls),
        "finished": any(p.get("game_status") == "3" for p in box),
        "first_200_t": first_200["t"] if first_200 else None,
        "not_started_polls": sum(1 for p in box if p.get("status") == 404 and (not first_200 or p["mono"] < first_200["mono"])),
        "status_timeline": _status_timeline(polls),
        "http_status": dict(Counter(str(p.get("status")) if p.get("status") else "error" for p in polls)),
        "errors": sum(1 for p in polls if p.get("error")),
        "token_renewals": sum(1 for p in polls if p.get("renewed_token")),
        "pbp_changes": n_changes, "cadence_s": _stats(cadence), "event_delay_s": _stats(delays),
        "response_ms": _stats([p["ms"] for p in polls if p.get("ms") is not None]),
        "bodies": len(list((directory / "bodies").glob("*.json.gz"))) if (directory / "bodies").exists() else 0,
    }
    cal = directory / "calendar.jsonl"
    if cal.exists():
        kinds = [json.loads(line)["row"] for line in cal.read_text(encoding="utf-8").splitlines() if line.strip()]
        summary["calendar_rows"] = [r for i, r in enumerate(kinds) if i == 0 or r != kinds[i - 1]]
    if replay:
        summary["engine"] = _replay(directory)
    return summary


def to_markdown(s: Dict[str, Any]) -> str:
    out = [f"# Grabación FEB {s['match_code']}", ""]
    out.append(f"- Peticiones: {s['polls']} · cuerpos distintos guardados: {s['bodies']} · errores: {s['errors']} · "
               f"renovaciones de token: {s['token_renewals']} · HTTP: {s['http_status']}")
    out.append(f"- Finalizado: {'sí' if s['finished'] else 'no'} · primer 200: {s['first_200_t']} · "
               f"sondeos antes de empezar (404): {s['not_started_polls']}")
    for t in s["status_timeline"]:
        out.append(f"  - estado `{t['status']}` visto por primera vez a las {t['t']}")
    c, d = s["cadence_s"], s["event_delay_s"]
    out.append(f"- Cadencia real de cambios del play-by-play ({s['pbp_changes']} cambios): mediana {c['median']} s · "
               f"p95 {c['p95']} s · máx {c['max']} s")
    out.append(f"- Retraso de los eventos (hora de la petición - `LogTimeUtc`): mediana {d['median']} s · p95 {d['p95']} s "
               f"· máx {d['max']} s (n={d['n']})")
    r = s["response_ms"]
    out.append(f"- Tiempo de respuesta de FEB: mediana {r['median']} ms · p95 {r['p95']} ms")
    if s.get("calendar_rows"):
        out.append("- Fila del partido en el calendario a lo largo del tiempo: " + " → ".join(
            json.dumps(r, ensure_ascii=False)[:90] for r in s["calendar_rows"]))
    if "engine" in s:
        e = s["engine"]
        out.append(f"- Motor live sobre los documentos reales: {e['updates']} actualizaciones, "
                   f"{'**FALLÓ: ' + str(e['error']) + '**' if e['crashed'] else 'sin errores'}, "
                   f"mediana {e['median_ms']} ms, máx {e['max_ms']} ms")
        for err in e.get("final_invariant_errors", []):
            out.append(f"  - invariante roto en el documento final: {err}")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Report on a FEB live recording")
    parser.add_argument("directory")
    parser.add_argument("--replay", action="store_true", help="feed the recorded documents to LiveEngine")
    args = parser.parse_args(argv)
    text = to_markdown(summarize(Path(args.directory), replay=args.replay))
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
