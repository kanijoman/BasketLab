"""Capture the real answers of the public API of the Euroleague that the tests of its source read (#1038, D6a): ``python scripts/capture_euroleague_fixtures.py``.

Writes ``tests/fixtures/euroleague/*.json.gz``. Three answers per game, as the source asks for them (the box and bio of ``api-live.euroleague.net/v2``, the play by play and the shots of
``live.euroleague.net/api``), whole as they come. Lists are cut to the few entries the tests read. One request every 0.6 s: the API answers 429 (Cloudflare) from about 8 a second.
"""
import gzip
import json
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "euroleague"
V2 = "https://api-live.euroleague.net/v2/competitions"
LIVE = "https://live.euroleague.net/api"
PAUSE = 0.6
# name -> (competition, season code, game code): what each game is for
GAMES = {
    "E2025_1": ("E", "E2025", 1),          # Anadolu Efes - Maccabi Tel Aviv: a normal game of the regular season, the first of 2025/26
    "E2025_397": ("E", "E2025", 397),      # one overtime of 10 minutes (the second of the 17 of that season)
}
OTHERS = {"U": ("U2025", "a EuroCup game"), "J": ("JTA25", "a U18 Next Generation Tournament game (Abu Dhabi 2025/26)")}


def get(url: str) -> dict:
    time.sleep(PAUSE)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(request, timeout=60).read().decode("utf-8"))


def write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json.gz").write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), mtime=0))


def capture_game(name: str, competition: str, season: str, code: int) -> None:
    write(f"{name}.stats", get(f"{V2}/{competition}/seasons/{season}/games/{code}/stats"))
    write(f"{name}.pbp", get(f"{LIVE}/PlayByPlay?gamecode={code}&seasoncode={season}"))
    write(f"{name}.points", get(f"{LIVE}/Points?gamecode={code}&seasoncode={season}"))


def first_played(competition: str, season: str) -> dict:
    return next(g for g in get(f"{V2}/{competition}/seasons/{season}/games?limit=500")["data"] if g["played"])


def main() -> int:
    for name, (competition, season, code) in GAMES.items():
        capture_game(name, competition, season, code)
    for competition, (season, _) in OTHERS.items():
        game = first_played(competition, season)
        GAMES[f"{season}_{game['gameCode']}"] = (competition, season, game["gameCode"])
        capture_game(f"{season}_{game['gameCode']}", competition, season, game["gameCode"])
    played = get(f"{V2}/E/seasons/E2025/games?limit=500")["data"]
    pick = [g for g in played if g["gameCode"] in (1, 397, 406)]                       # a normal one, an overtime one and the final
    write("games_E2025", {"total": len(pick), "data": pick})
    upcoming = get(f"{V2}/E/seasons/E2026/games?limit=500")["data"]
    write("games_U2025", {"total": 1, "data": [g for g in get(f"{V2}/U/seasons/U2025/games?limit=500")["data"] if g["gameCode"] == GAMES["U2025_195"][2]]})
    write("games_E2026", {"total": 3, "data": [g for g in upcoming if g["played"]][:2] + [g for g in upcoming if not g["played"]][:1]})
    write("seasons_E", get(f"{V2}/E/seasons?limit=50"))
    write("seasons_J", get(f"{V2}/J/seasons?limit=100"))
    write("games_JTA25", get(f"{V2}/J/seasons/JTA25/games?limit=100"))
    print("captured:", ", ".join(sorted(p.name for p in OUT.iterdir())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
