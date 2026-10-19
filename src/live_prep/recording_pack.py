"""Pack a recording (``recordings/<match>/``) into one small replayable file (issue #174).

``python -m src.live_prep.recording_pack recordings/2524470 -o tests/recordings/2524470.rec.json.gz``

The recorder keeps every body that changed (58 MB for one match); the play-by-play is append-only, so each
line is stored once with the frame it first appeared in (see ``src/live_core/recorded_feed.py`` for the layout
and the player; the packing itself is ``src/live_core/recording_builder.py``, shared with the app, which records the feed it follows).
Per-endpoint 404 windows of the middle of the match are kept too.
"""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.live_core.recorded_feed import ENDPOINTS
from src.live_core.recording_builder import RecordingBuilder
from src.live_prep.recording_report import _read_polls, merged_documents

Docs = List[Tuple[str, Dict[str, Any]]]


def _seconds(iso: str, start: datetime) -> float:
    return round((datetime.fromisoformat(iso) - start).total_seconds(), 3)


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

    builder = RecordingBuilder(str(match), start.isoformat())
    for iso, doc in docs:
        builder.add(_seconds(iso, start), doc)
    data = builder.pack()
    data["gaps"] = _pack_gaps(polls, start)         # per-endpoint 404 windows, from the poll log
    return data


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
