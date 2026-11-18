"""The reconciliation report of the FIBA source (#887, D3a): ``python scripts/fiba_reconciliation_report.py [--out FILE]`` over the real pages of ``tests/fixtures/fiba``.

For every game: the page is read (``fiba_page``), converted to the canonical document (``fiba_canonical``) and its play-by-play compared with the official box of the page (``market.box_reconciliation``: the nine core
statistics and the information ones, per team-game). And the minutes, which that comparison does not count yet (#963): worked out from the substitutions and the starting five of the page and compared with the official
ones of every player. The report is what ``docs/evaluaciones/2026-11-18_fiba-cuadre.md`` quotes; ``tests/test_fiba_reconciliation_report.py`` keeps the numbers honest.
"""
import argparse
import gzip
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from src.external.fiba_canonical import to_canonical  # noqa: E402
from src.external.fiba_page import parse_game  # noqa: E402
from src.market.box_reconciliation import CORE_STATS, UNCHECKED, reconcile_game, summarize  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "fiba"
GAMES = ["125809", "125803", "125812", "125859", "123004", "123043"]


def load(name: str) -> Dict[str, Any]:
    return parse_game(gzip.decompress((FIXTURES / f"{name}.flight.gz").read_bytes()).decode("utf-8"))


def _seconds(clock: str) -> int:
    minutes, _, seconds = (clock or "0:0").partition(":")
    return int(minutes) * 60 + int(seconds or 0)


def played(player: Dict[str, Any]) -> bool:
    """Whether a player took part: the flag of the page or minutes on the clock. The flag alone is not reliable: a player can be marked as not played with a minute and a quarter in the official box (game 125803)."""
    return bool(player["stats"].get("HasPlayed")) or _seconds(player["stats"].get("TP")) > 0


def length_of(game: Dict[str, Any]) -> int:
    """The length of the game in seconds: four quarters of 10 minutes and every overtime of 5."""
    return sum(600 if period.startswith("Q") else 300 for period in game["periods"])


def minutes_from_substitutions(game: Dict[str, Any], team: Dict[str, Any]) -> Dict[int, int]:
    """Seconds on court of every player of ``team``: the starting five of the page and its substitutions. A substitution is either one event that names who comes in (``player``) and who goes out (``player2``)
    or two, one for each; the lineup at the end of a period is the one that starts the next."""
    on = {p["person_id"] for p in team["players"] if p["stats"].get("Starter")}
    total = {p["person_id"]: 0 for p in team["players"]}
    for period in game["periods"]:
        remaining = 600 if period.startswith("Q") else 300
        for event in (e for e in game["events"] if e["period"] == period and e["code"] == "SUBST" and e["team"] == team["org_id"]):
            now = _seconds(event["clock"])
            for person in on:
                total[person] += remaining - now
            remaining = now
            if event["player2"] is not None:
                on.discard(event["player2"])
                on.add(event["player"])
            else:
                (on.add if event["in"] == "IN" else on.discard)(event["player"])
        for person in on:
            total[person] += remaining
    return total


def team_minutes() -> Dict[str, Dict[str, int]]:
    """Per team-game: the seconds worked out, the official ones and the length of the game (five players are on court at every moment)."""
    out = {}
    for name in GAMES:
        game = load(name)
        for team in game["teams"]:
            worked = minutes_from_substitutions(game, team)
            out[f"{name} {team['code']}"] = {"got": sum(worked.values()), "official": sum(_seconds(p["stats"].get("TP")) for p in team["players"] if played(p)), "length": length_of(game)}
    return out


def build_summary() -> Dict[str, Any]:
    results, detail, gaps = [], [], []
    for name in GAMES:
        game = load(name)
        doc = to_canonical(game)
        results.append(reconcile_game(doc))
        detail.append({"game": name, "competition": game["competition"]["name"], "teams": f"{game['teams'][0]['name']} - {game['teams'][1]['name']}",
                       "score": f"{game['teams'][0]['score']}-{game['teams'][1]['score']}", "periods": len(game["periods"]), "events": len(game["events"]),
                       "players": sum(1 for t in game["teams"] for p in t["players"] if played(p))})
        for team in game["teams"]:
            worked = minutes_from_substitutions(game, team)
            gaps += [abs(worked[p["person_id"]] - _seconds(p["stats"]["TP"])) for p in team["players"] if played(p)]
    summary = summarize(results)
    return {"games": summary["games"], "team_games": summary["games"] * 2, "reliable": summary["reliable"], "unreliable": summary["unreliable"], "stats": summary["stats"], "detail": detail,
            "minutes": {"player_games": len(gaps), "exact": sum(1 for g in gaps if g == 0), "within_2_s": sum(1 for g in gaps if g <= 2), "worst_s": max(gaps)}, "unchecked": summary["unchecked"]}


def render(summary: Dict[str, Any]) -> str:
    """The report in Spanish, in markdown."""
    lines: List[str] = [f"Cuadre de la jugada a jugada con la caja oficial de la ficha: **{summary['games']} partidos** ({summary['team_games']} equipo-partido), {summary['reliable']} fiables.", "",
                        "| Partido | Competición | Marcador | Periodos | Eventos | Jugadores |", "| --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {d['game']} {d['teams']} | {d['competition']} | {d['score']} | {d['periods']} | {d['events']} | {d['players']} |" for d in summary["detail"]]
    lines += ["", "| Estadística | Equipo-partido que cuadran | Tipo |", "| --- | --- | --- |"]
    for stat, entry in summary["stats"].items():
        lines.append(f"| {stat} | {entry['match']} de {entry['checked']} | {'central' if stat in CORE_STATS else 'informativa'} |")
    m = summary["minutes"]
    lines += ["", f"Minutos (calculados desde las sustituciones y el quinteto inicial de la ficha): **{m['player_games']} jugador-partido**, {m['exact']} exactos y {m['within_2_s']} a 2 s o menos de la caja oficial (el peor, {m['worst_s']} s).", "",
              "Sin comprobar: " + ", ".join(summary["unchecked"] or UNCHECKED) + " en `reconcile_game` (#963; aquí medido aparte) y el mapa de tiro (FIBA da las coordenadas; falta llevarlas a las zonas del motor)."]
    return "\n".join(lines) + "\n"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Reconciliation report of the FIBA fixtures")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    text = render(build_summary())
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
