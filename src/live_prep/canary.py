"""FEB format canary (issue #136).

The live engine depends on the exact shape of FEB's data. This canary downloads a FINISHED
game from FEB every day and checks, before a live match does, that

1. **schema**: every field the engine reads (HEADER, BOXSCORE, PLAYBYPLAY, SHOTCHART) is still
   there with the same types, compared with a committed reference document (new fields are
   only reported);
2. **invariants**: the engine still reproduces the official numbers (final score, personal
   fouls, shooting totals) and the live session replays the whole game.

CLI: ``python -m src.live_prep.canary [--match CODE ...] [--reference FILE]``.
Exit codes: 0 all good, 1 drift or broken invariant, 2 FEB could not be reached/returned nothing
(inconclusive: no issue should be opened for it).

Limits: it sees finished games only; the in-progress feed (status, refresh, token life) still
needs a real live match (issue #118).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.live_core.engine import LiveEngine
from src.live_core.session import LiveSession
from src.live_core.vectors import unwrap_extended_json

SECTIONS = ("HEADER", "BOXSCORE", "PLAYBYPLAY", "SHOTCHART")
DEFAULT_MATCHES = ("2477341",)  # a finished LF Challenge game; its document is the committed reference
DEFAULT_REFERENCE = Path(__file__).resolve().parents[2] / "src" / "JSON_samples" / "feb_game.json"
FINISHED = "3"
REPLAY_CHECKPOINTS = (300, 900, 1500, 2100, 2400)

_TYPES = {str: "str", bool: "bool", int: "int", float: "float", type(None): "null"}


# --- schema ---------------------------------------------------------------------------------

def _walk(node: Any, path: str, out: Dict[str, Set[str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _walk(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, f"{path}[]", out)
        out.setdefault(path + "[]", set())
    else:
        out.setdefault(path, set()).add(_TYPES.get(type(node), type(node).__name__))


def signature(doc: Dict[str, Any]) -> Dict[str, Set[str]]:
    """path -> set of value types, for the sections the engine uses (lists collapse to ``[]``)."""
    out: Dict[str, Set[str]] = {}
    for section in SECTIONS:
        if section in doc:
            _walk(doc[section], section, out)
    return out


def compare_signatures(reference: Dict[str, Set[str]], live: Dict[str, Set[str]]) -> Dict[str, list]:
    missing = sorted(p for p in reference if p not in live and not _empty_container(p, reference))
    type_changes: List[Tuple[str, List[str], List[str]]] = []
    for path in sorted(set(reference) & set(live)):
        ref_t, live_t = reference[path], live[path]
        if ref_t and live_t and not live_t <= ref_t:
            type_changes.append((path, sorted(ref_t), sorted(live_t)))
    new = sorted(p for p in live if p not in reference)
    return {"missing": missing, "type_changes": type_changes, "new": new}


def _empty_container(path: str, reference: Dict[str, Set[str]]) -> bool:
    """A list that is empty in the reference carries no element paths to compare."""
    return path.endswith("[]") and not reference[path] and not any(p.startswith(path + ".") for p in reference)


# --- invariants -----------------------------------------------------------------------------

def _int(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _check_header(doc: Dict[str, Any]) -> List[str]:
    header = doc.get("HEADER") or {}
    errors = []
    if str(header.get("status")) != FINISHED:
        errors.append(f"El partido no está finalizado (status={header.get('status')!r}): no sirve como canario")
    if len(header.get("TEAM") or []) != 2:
        errors.append("HEADER.TEAM no tiene exactamente 2 equipos")
    return errors


def _check_totals(snapshot: Dict[str, Any], doc: Dict[str, Any]) -> List[str]:
    errors = []
    header_pts = {str(t["id"]): _int(t.get("pts")) for t in doc["HEADER"]["TEAM"]}
    for tid, pts in header_pts.items():
        if snapshot["score"].get(tid) != pts:
            errors.append(f"Marcador final distinto en el equipo {tid}: motor {snapshot['score'].get(tid)} vs oficial {pts}")
    for team in doc["BOXSCORE"]["TEAM"]:
        tid, total = str(team["id"]), team.get("TOTAL") or {}
        stats = snapshot["teams"][tid]["stats"]
        for name, ours, theirs in (("triples", stats["fg3m"], "p3m"), ("tiros de 2", stats["fg2m"], "p2m"),
                                   ("tiros libres", stats["ftm"], "p1m")):
            if ours != _int(total.get(theirs)):
                errors.append(f"Anotados en {name} distintos en el equipo {tid}: motor {ours} vs oficial {_int(total.get(theirs))}")
        for player in team.get("PLAYER", []):
            ours = snapshot["players"].get(str(player.get("id")))
            if ours and ours["pf"] != _int(player.get("pf")):
                errors.append(f"Faltas de {player.get('name', player.get('id'))} distintas: motor {ours['pf']} vs oficial {_int(player.get('pf'))}")
    return errors


def _check_replay(doc: Dict[str, Any]) -> List[str]:
    """Build a one-game package and replay the game through the live session."""
    from src.live_prep.package_builder import build_package

    ids = [str(t["id"]) for t in doc["HEADER"]["TEAM"]]
    package = build_package([doc], "CANARY", "canary", ids[0], ids[1], created_at="2000-01-01T00:00:00Z")
    session = LiveSession(package.dumps())
    session.load_replay(doc)
    for elapsed in REPLAY_CHECKPOINTS:
        session.replay(elapsed)
    return []


def check_invariants(doc: Dict[str, Any]) -> List[str]:
    """Human-readable violations (empty list = the engine reproduces the official game)."""
    errors = _check_header(doc)
    lines = (doc.get("PLAYBYPLAY") or {}).get("LINES")
    if not isinstance(lines, list) or not lines:
        return errors + ["El play-by-play está vacío o no es una lista"]
    try:
        snapshot = LiveEngine().update(doc)
        errors += _check_totals(snapshot, doc)
        errors += _check_replay(doc)
    except Exception as exc:  # noqa: BLE001 - a crash IS the finding
        errors.append(f"El motor live falló con este documento: {type(exc).__name__}: {exc}")
    return errors


# --- report ---------------------------------------------------------------------------------

@dataclass
class CanaryReport:
    match_code: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def markdown(self) -> str:
        lines = [f"# Canario FEB: partido {self.match_code or '(sin código)'} — {'OK' if self.ok else 'FALLO'}"]
        if self.errors:
            lines += ["", "## Errores"] + [f"- {e}" for e in self.errors]
        if self.warnings:
            lines += ["", "## Avisos"] + [f"- {w}" for w in self.warnings]
        if self.ok and not self.warnings:
            lines += ["", "El formato de FEB coincide con la referencia y el motor reproduce el partido oficial."]
        return "\n".join(lines)


def run_checks(live: Dict[str, Any], reference: Dict[str, Any], match_code: str = "") -> CanaryReport:
    report = CanaryReport(match_code=match_code)
    drift = compare_signatures(signature(reference), signature(live))
    report.errors += [f"Campo desaparecido: {p}" for p in drift["missing"]]
    report.errors += [f"Tipo cambiado en {p}: {a} -> {b}" for p, a, b in drift["type_changes"]]
    report.warnings += [f"Campo nuevo: {p}" for p in drift["new"]]
    report.errors += check_invariants(live)
    return report


# --- CLI ------------------------------------------------------------------------------------

def fetch_match(code: str) -> Optional[Dict[str, Any]]:
    """Download a match document exactly as the scraper stores it (needs network)."""
    import requests

    # the scraper still imports some helpers un-prefixed (``utils...``): put ``src`` on the path
    src_dir = str(Path(__file__).resolve().parents[1])
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from src.scraper.api_client import FEBApiClient
    from src.scraper.token_manager import TokenManager
    from src.scraper.web_client import WebClient

    client = FEBApiClient(TokenManager(), WebClient())
    return client.fetch_boxscore(code, requests.Session())


def main(argv: Optional[List[str]] = None, fetch: Callable[[str], Optional[Dict[str, Any]]] = fetch_match) -> int:
    parser = argparse.ArgumentParser(description="FEB data format canary")
    parser.add_argument("--match", action="append", help="FEB match code (repeatable)")
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE), help="reference game document (JSON)")
    args = parser.parse_args(argv)
    reference = unwrap_extended_json(json.loads(Path(args.reference).read_text(encoding="utf-8")))

    sections: List[str] = []
    exit_code = 0
    for code in args.match or list(DEFAULT_MATCHES):
        try:
            doc = fetch(code)
        except Exception as exc:  # noqa: BLE001 - network / FEB outage: inconclusive
            sections.append(f"# Canario FEB: partido {code} — NO CONCLUYENTE\n\nNo se pudo descargar de FEB: {exc}")
            exit_code = max(exit_code, 2) if exit_code != 1 else 1
            continue
        if not doc:
            sections.append(f"# Canario FEB: partido {code} — NO CONCLUYENTE\n\nFEB no devolvió datos para el partido.")
            exit_code = max(exit_code, 2) if exit_code != 1 else 1
            continue
        report = run_checks(unwrap_extended_json(doc), reference, code)
        sections.append(report.markdown())
        if not report.ok:
            exit_code = 1
    text = "\n\n".join(sections)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
