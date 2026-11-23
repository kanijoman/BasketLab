"""Capture the real answers of ESPN that the tests of the NCAA source read (#888, D4): ``python scripts/capture_ncaa_fixtures.py``.

Writes ``tests/fixtures/ncaa/*.json.gz``. The list of conferences of a season is kept as it comes. The standings of a season (6,7 MB each, mostly logos, links and stats nobody reads) are cut to what
``src/external/ncaa_page`` reads: the conferences and, in each, the id and name of its teams. Two seasons on purpose: 2025/26 and 2026/27, between which 27 teams changed conference (the realignments of
the summer of 2026), the real case #966 asks for. ESPN answers 403 to a user agent that names a bot: the plain ``Mozilla/5.0`` is what the client sends too.
"""
import gzip
import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "ncaa"
SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/{sex}-college-basketball"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/basketball/{sex}-college-basketball/standings?group=50&level=2&season={season}"
SEASONS = (2026, 2027)                       # the ESPN season is the year it ends in: 2026 is 2025/26
# the games the tests of the source read, whole as ESPN gives them (``summary``): what each one is for
GAMES = {
    "game_mens_401829197": ("mens", "401829197"),         # Gonzaga at Washington State: a normal men's game, two halves
    "game_mens_ot_401812120": ("mens", "401812120"),      # UMBC at Bryant: one overtime
    "game_mens_nond1_401823428": ("mens", "401823428"),   # RIT at Buffalo: the visitor is not a Division I team (no conference)
    "game_womens_401825641": ("womens", "401825641"),     # Villanova at UConn: a normal women's game, four quarters
    "game_womens_ot_401827769": ("womens", "401827769"),  # Coppin State at Maryland Eastern Shore: an overtime of the women's game
    "game_womens_nond1_401817303": ("womens", "401817303"),   # Claflin at East Tennessee State: a visitor that is not Division I
    "game_womens_noplays_401830444": ("womens", "401830444"),  # Wyoming at San Diego State: the play by play comes EMPTY (0 plays) while the box is complete (51 and 70 points)
}
SCOREBOARDS = {"scoreboard_mens_20260115": ("mens", "20260115"), "scoreboard_womens_20260115": ("womens", "20260115"), "scoreboard_mens_20251115": ("mens", "20251115")}      # 15/11: early season, with Division I teams that host others that are not


def get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(request, timeout=60).read().decode("utf-8"))


def trimmed_standings(data: dict) -> dict:
    return {"children": [{"id": c["id"], "name": c["name"], "abbreviation": c.get("abbreviation"), "shortName": c.get("shortName"), "isConference": c.get("isConference"),
                          "standings": {"entries": [{"team": {"id": e["team"]["id"], "displayName": e["team"]["displayName"]}} for e in c["standings"]["entries"]]}}
                         for c in data["children"]]}


def trimmed_scoreboard(data: dict) -> dict:
    """The events of a day as far as the reader goes: the game, its status and date and, for each side, its team with the conference it plays in, the score and where it plays."""
    events = []
    for e in data["events"]:
        c = e["competitions"][0]
        events.append({"id": e["id"], "date": e["date"], "status": {"type": {"name": e["status"]["type"]["name"]}, "period": e["status"].get("period")},
                       "competitions": [{"neutralSite": c.get("neutralSite"), "conferenceCompetition": c.get("conferenceCompetition"), "playByPlayAvailable": c.get("playByPlayAvailable"),
                                         "competitors": [{"homeAway": x["homeAway"], "score": x.get("score"), "team": {k: x["team"].get(k) for k in ("id", "displayName", "conferenceId")}}
                                                         for x in c["competitors"]]}]})
    return {"events": events}


def write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json.gz").write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), mtime=0))


def main() -> int:
    for sex in ("mens", "womens"):
        for season in SEASONS:
            write(f"conferences_{sex}_{season}", get(SITE.format(sex=sex) + f"/scoreboard/conferences?season={season}"))
            write(f"standings_{sex}_{season}", trimmed_standings(get(STANDINGS.format(sex=sex, season=season))))
    for name, (sex, event) in GAMES.items():
        write(name, get(SITE.format(sex=sex) + f"/summary?event={event}"))
    for name, (sex, day) in SCOREBOARDS.items():
        write(name, trimmed_scoreboard(get(SITE.format(sex=sex) + f"/scoreboard?dates={day}&groups=50&limit=400")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
