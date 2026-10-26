"""Report of a FBCYL recording (issue #444): is anything served WHILE the match is played? ``python -m src.live_prep.fbcyl_recording_report recordings/fbcyl-...``

The verdict reads the readings of the moves endpoint against the calendar: if the number of moves grows over several readings before the calendar says the match is played, FBCYL
publishes during the game (GO for the live feed, #446); if it stays at 0 and jumps to the final figure when the match ends, it is a post-match feed (NO-GO: FBCYL stays for analysis
after the match). Standard library only.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

MIN_DISTINCT = 3          # distinct non-empty counts before the end that make it a live feed


def _read(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _when(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _finished_at(calendar: List[Dict[str, Any]]) -> Optional[datetime]:
    return next((_when(c["t"]) for c in calendar if (c.get("row") or {}).get("state") == "1"), None)


def readings(folder: Path) -> List[Dict[str, Any]]:
    """The successful readings of the moves endpoint: ``{t, n}`` in order."""
    return [{"t": _when(p["t"]), "n": p["n_moves"]} for p in _read(folder / "polls.jsonl") if p.get("endpoint") == "moves" and p.get("status") == 200 and "n_moves" in p]


def verdict(folder: Path) -> Dict[str, Any]:
    folder = Path(folder)
    moves, calendar = readings(folder), _read(folder / "calendar.jsonl")
    if not moves:
        return {"live": None, "reason": "no se leyó ningún movimiento: el partido no llegó a tener datos mientras se grababa", "final": 0, "before_end": []}
    ended = _finished_at(calendar)
    final = max(r["n"] for r in moves)
    before_end = [r["n"] for r in moves if ended is None or r["t"] < ended]
    distinct = sorted({n for n in before_end if n > 0})
    if len(distinct) >= MIN_DISTINCT and distinct[0] <= 0.8 * final:
        return {"live": True, "reason": f"los movimientos crecen durante el partido: {len(distinct)} lecturas distintas antes del final (de {distinct[0]} a {distinct[-1]} de {final})",
                "final": final, "before_end": before_end}
    return {"live": False, "reason": f"los movimientos aparecen de golpe: {max(before_end, default=0)} antes de que el calendario diga que el partido terminó y {final} al final",
            "final": final, "before_end": before_end}


def report(folder: Path) -> str:
    folder = Path(folder)
    result, calendar = verdict(folder), _read(folder / "calendar.jsonl")
    rows = [c["row"] for c in calendar if c.get("row")]
    live_seen = next((_when(c["t"]).strftime("%H:%M:%S") for c in calendar if (c.get("row") or {}).get("isLive")), None)
    ended = _finished_at(calendar)
    first_data = next((r for r in readings(folder) if r["n"] > 0), None)
    lines = [f"# Grabación FBCYL: {folder.name}", ""]
    lines.append("**GO**: FBCYL publica durante el partido." if result["live"] else ("**NO-GO**: " + ("FBCYL no publica durante el partido." if result["live"] is False else "sin datos.")))
    lines += ["", f"- {result['reason']}.", f"- Movimientos finales: {result['final']}.",
              f"- Primera lectura con movimientos: {first_data['t'].strftime('%H:%M:%S') if first_data else 'ninguna'}.",
              f"- El calendario marcó «en directo»: {live_seen or 'nunca'}; partido jugado: {ended.strftime('%H:%M:%S') if ended else 'no visto'}.",
              f"- Filas del calendario guardadas: {len(rows)}; lecturas de movimientos: {len(readings(folder))}."]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    args = (argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        print("usage: python -m src.live_prep.fbcyl_recording_report <recording folder>", file=sys.stderr)
        return 2
    print(report(Path(args[0])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
