"""Pack a recording (``recordings/<match>/``) into one small replayable file (issue #174).

``python -m src.live_prep.recording_pack recordings/2524470 -o tests/recordings/2524470.rec.json.gz``

The recorder keeps every body that changed (58 MB for one match); the play-by-play is append-only, so each
line is stored once with the frame it first appeared in (see ``src/live_core/recorded_feed.py`` for the layout
and the player). Per-endpoint 404 windows of the middle of the match are kept too.
"""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.live_core.recorded_feed import ENDPOINTS, FORMAT_VERSION
from src.live_core.replay import _ROSTER_FIELDS, _TEAM_FIELDS
from src.live_prep.recording_report import _read_polls, merged_documents

Docs = List[Tuple[str, Dict[str, Any]]]


def _seconds(iso: str, start: datetime) -> float:
    return round((datetime.fromisoformat(iso) - start).total_seconds(), 3)


def _slim_base(doc: Dict[str, Any]) -> Dict[str, Any]:
    """The part of a document that does not change over the match, without box-score statistics."""
    return {
        "HEADER": json.loads(json.dumps(doc["HEADER"])),
        "BOXSCORE": {"TEAM": [
            {**{k: team[k] for k in _TEAM_FIELDS if k in team},
             "PLAYER": [{k: p[k] for k in _ROSTER_FIELDS if k in p} for p in team.get("PLAYER", [])]}
            for team in doc["BOXSCORE"]["TEAM"]]},
        "PLAYBYPLAY": {k: v for k, v in (doc.get("PLAYBYPLAY") or {}).items() if k != "LINES"},
        "SHOTCHART": {**{k: v for k, v in (doc.get("SHOTCHART") or {}).items() if k not in ("SHOTS", "TEAM")}, "TEAM": []},
    }


def _pack_lines(docs: Docs) -> List[Dict[str, Any]]:
    entries: Dict[str, Dict[str, Any]] = {}
    for frame, (_, doc) in enumerate(docs):
        seen = set()
        for line in doc["PLAYBYPLAY"]["LINES"]:
            num = str(line["num"])
            seen.add(num)
            entry = entries.get(num)
            if entry is None:
                entries[num] = {"f": frame, "l": line, "_cur": line}
                continue
            entry.pop("r", None)
            if line != entry["_cur"]:
                entry.setdefault("fix", []).append([frame, line])
                entry["_cur"] = line
        for num, entry in entries.items():
            if num not in seen and "r" not in entry:
                entry["r"] = frame
    final_order = [str(line["num"]) for line in docs[-1][1]["PLAYBYPLAY"]["LINES"]]
    ordered = [entries[n] for n in final_order]
    for num, entry in entries.items():  # lines removed before the end: keep them where their number belongs
        if num not in final_order:
            position = next((i for i, e in enumerate(ordered) if int(e["l"]["num"]) < int(num)), len(ordered))
            ordered.insert(position, entry)
    return [{k: v for k, v in entry.items() if k != "_cur"} for entry in ordered]


def _pack_shots(docs: Docs) -> List[Dict[str, Any]]:
    entries: Dict[str, Dict[str, Any]] = {}
    for frame, (_, doc) in enumerate(docs):
        now = {json.dumps(s, sort_keys=True): s for s in (doc.get("SHOTCHART") or {}).get("SHOTS") or []}
        for key, shot in now.items():
            entries.setdefault(key, {"f": frame, "s": shot}).pop("r", None)
        for key, entry in entries.items():
            if key not in now and "r" not in entry:
                entry["r"] = frame
    final = [json.dumps(s, sort_keys=True) for s in (docs[-1][1].get("SHOTCHART") or {}).get("SHOTS") or []]
    return [entries[k] for k in final] + [e for k, e in entries.items() if k not in final]


def _pack_gaps(polls: List[Dict[str, Any]], start: datetime) -> Dict[str, List[List[float]]]:
    """404 windows per endpoint after its first answer: [first failing poll, first poll that answered again)."""
    gaps: Dict[str, List[List[float]]] = {}
    for endpoint in ENDPOINTS:
        own = [p for p in polls if p.get("endpoint") == endpoint]
        first_ok = next((i for i, p in enumerate(own) if p.get("status") == 200), None)
        if first_ok is None:
            continue
        opened: Optional[float] = None
        for poll in own[first_ok:]:
            t = _seconds(poll["t"], start)
            if poll.get("status") != 200 and opened is None:
                opened = t
            elif poll.get("status") == 200 and opened is not None:
                gaps.setdefault(endpoint, []).append([opened, t])
                opened = None
        if opened is not None:
            gaps.setdefault(endpoint, []).append([opened, _seconds(own[-1]["t"], start)])
    return gaps


def pack_recording(directory: Any) -> Dict[str, Any]:
    directory = Path(directory)
    polls = _read_polls(directory) if (directory / "polls.jsonl").exists() else []
    if not polls:
        raise ValueError(f"{directory} has no polls.jsonl: not a recording")
    docs = list(merged_documents(directory))
    if not docs:
        raise ValueError(f"{directory} has no complete document (boxscore + keyfacts + shotchart)")
    start = datetime.fromisoformat(polls[0]["t"])
    meta_path = directory / "meta.json"
    match = json.loads(meta_path.read_text(encoding="utf-8")).get("match_code") if meta_path.exists() else directory.name

    frames = []
    for iso, doc in docs:
        header = doc["HEADER"]
        frames.append({"t": _seconds(iso, start), "h": {
            "status": str(header.get("status")), "statusText": header.get("statusText"),
            "quarter": header.get("quarter"), "time": header.get("time"),
            "pts": {str(t["id"]): int(t.get("pts") or 0) for t in header.get("TEAM", [])}}})
    return {"v": FORMAT_VERSION, "match": str(match), "started": start.isoformat(), "base": _slim_base(docs[-1][1]),
            "lines": _pack_lines(docs), "shots": _pack_shots(docs), "frames": frames, "gaps": _pack_gaps(polls, start)}


def write_pack(directory: Any, out: Any) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(pack_recording(directory), ensure_ascii=False, separators=(",", ":"))
    out.write_bytes(gzip.compress(text.encode("utf-8"), 9))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pack a recording into one small replayable file")
    parser.add_argument("directory")
    parser.add_argument("-o", "--out", required=True)
    args = parser.parse_args(argv)
    path = write_pack(args.directory, args.out)
    print(f"{path} ({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
