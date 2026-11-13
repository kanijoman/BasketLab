"""Regenerate ``web_data/``: a REAL publication of ``publish_web_data`` over the small leagues of the fixtures (#328, #639).

The contract between the exporter (Python) and the browser (WebCrypto): the web tests (``frontend/src/webdata``) read the manifest, open the sealed
rows and reports with the open key the manifest publishes, and must find what the exporter produced. Sealing is random, so the directory is
committed and only regenerated on demand (``python tests/local_vectors/generate_web_data.py``); ``test_local_vectors.py`` checks that it still
opens and says what the exporter says today. The secret is public on purpose: these are fixtures.
"""
import copy
import json
import base64
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import mongomock
import pymongo

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(Path(__file__).resolve().parent)]

import fbcyl_games  # noqa: E402
import games  # noqa: E402

from src.api import deps  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.calendar_export import CalendarSource  # noqa: E402
from src.local_data.competition_gender import competition_genders  # noqa: E402
from src.services.competition_category import competition_categories  # noqa: E402
from src.local_data.images_export import Source  # noqa: E402
from src.local_data.web_data import publish_web_data  # noqa: E402
from src.scraper.calendar_parser import CalendarMatch  # noqa: E402
from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue  # noqa: E402
from src.services.scouting_rival_service import ScoutingRivalService  # noqa: E402

OUT = Path(__file__).resolve().parent / "web_data"
SECRET = "vector-master-secret-for-the-web-tests"
FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1\u00aa_FASE-GRUPO_A-1_2026_"


def fixture_handler():
    """A handler over a mongomock database with both leagues (the real ``deps._create_handler`` with the client swapped)."""
    pymongo.MongoClient = mongomock.MongoClient
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    db[FEB].insert_many(games.build_games())
    db[FBCYL].insert_many(fbcyl_games.build_games())
    return handler


SAMPLE = ROOT / "src" / "JSON_samples" / "feb_game.json"
SAMPLE_TEAMS = {"982047": "101", "981204": "102"}                           # the two teams of the sample game, as two teams of the fixture league


def _unwrap(node):
    """The sample stores its numbers as Mongo extended JSON (``{"$numberInt": "3"}``)."""
    if isinstance(node, dict):
        if len(node) == 1 and next(iter(node)) in ("$numberInt", "$numberLong"):
            return int(next(iter(node.values())))
        if len(node) == 1 and next(iter(node)) == "$oid":
            return next(iter(node.values()))
        return {k: _unwrap(v) for k, v in node.items()}
    return [_unwrap(v) for v in node] if isinstance(node, list) else node


def scouting_games() -> tuple:
    """Three games of the real sample (the league's) and one for the cup, with its two teams renamed to teams of the fixture league."""
    text = SAMPLE.read_text(encoding="utf-8")
    for old, new in SAMPLE_TEAMS.items():
        text = text.replace(old, new)
    sample = _unwrap(json.loads(text))

    def dated(start, code):
        game = copy.deepcopy(sample)
        game["HEADER"]["starttime"], game["_id"] = start, code
        return game

    return [dated("10-10-2025 - 17:00", 9001), dated("17-10-2025 - 17:00", 9002)], [dated("14-10-2025 - 20:00", 9101)]


def fixture_scouting_service(handler):
    """The scouting service over those games (mongomock cannot run the pipeline that sorts the real ones by date)."""
    league, cup = scouting_games()

    class Stats:
        def get_teams_with_ids(self, collection):
            return [{"id": "101", "name": "ALPHA"}, {"id": "102", "name": "BRAVO"}]

        def load_season_data(self, collection):
            return {"team_stats": []}

    class Report:
        def build(self, collection, team_id, mode="own"):
            return {"profile": ["Perfil de prueba."], "training": [], "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}

    count = SimpleNamespace(count_documents=lambda query: 3)
    return ScoutingRivalService(SimpleNamespace(repository=SimpleNamespace(connection=SimpleNamespace(get_collection=lambda name: count))),
                                stats=Stats(), report_service=Report(), games=lambda h, c: iter(league), gender_of=lambda c: "",
                                extra_games=lambda h, c, t: {"copa": iter(cup)}, levels_of=lambda h, c: {})


class FixtureFeb(Source):
    """The FEB of the fixtures: a crest and a photo made here (the fixture games have no photo URL, so every player gets the same small one) and an identity for everyone."""

    # fixed bytes, not encoded here: the size of a PNG depends on the zlib of the machine and the sealed fixture records it
    PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAASwAAAEsCAYAAAB5fY51AAAD80lEQVR4nO3UQQ3AIADAQIYQhE3xXIEFfkuTOwV99VnvtwdAwPw7AOCWYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBWQYFpBhWECGYQEZhgVkGBaQYVhAhmEBGYYFZBgWkGFYQIZhARmGBYyKAxipBJcf2MvYAAAAAElFTkSuQmCC")

    def get(self, url):
        return self.PNG

    def length(self, url):
        return len(self.PNG)

    def identity(self, team_id, player_id):
        return "05/03/2000", "190 cm"

    def photo_url(self, uuid):                      # FBCYL: the ESB says where the photo of a uuid is
        return f"https://fixture.test/photo/{uuid}"

    def team_logo_url(self, team_id):
        return f"https://fixture.test/crest/{team_id}"


class FixtureCalendar(CalendarSource):
    """The federations of the fixtures (#842): the FEB calendar is the 12 games of the league as results (the code is the game's ``_id``) plus six still to play; the FBCYL one has the shape of the ESB rows
    (a played match carries its ``universallyid`` and kick-off too) with four still to play. Nobody asks the live API: no status."""

    PENDING = [("101", "102"), ("103", "104"), ("101", "103"), ("102", "104"), ("101", "104"), ("102", "103")]

    def feb(self, handler, collection):
        done = []
        for i, game in enumerate(games.build_games()):
            home, away = game["HEADER"]["TEAM"]
            done.append(CalendarMatch(code=str(game["_id"]), kind="result", round_index=i // 2 + 1, home_id=home["id"], home_name=home["name"], away_id=away["id"], away_name=away["name"],
                                      score=f"{home['pts']}-{away['pts']}"))
        names = {t["id"]: t["name"] for g in games.build_games() for t in g["HEADER"]["TEAM"]}
        todo = [CalendarMatch(code=str(9101 + i), kind="scheduled", round_index=7 + i // 2, home_id=h, home_name=names[h], away_id=a, away_name=names[a], start=f"2026-12-{12 + i // 2 * 7:02d}T{18 + i % 2 * 2}:00")
                for i, (h, a) in enumerate(self.PENDING)]
        return done + todo

    def fbcyl_rows(self, group_id):
        rows = []
        for i, game in enumerate(fbcyl_games.build_games()):
            home, away = game["stats"]["teams"][:2]
            rows.append({"idMatch": str(200 + i), "universallyid": game["_id"], "round": str(i // 2 + 1), "state": "1", "tiedAllowed": "0", "matchDay": f"2026-10-{3 + i:02d} 12:30:00",
                         "idLocalTeam": str(home["teamIdExtern"]), "idVisitorTeam": str(away["teamIdExtern"]), "nameLocalTeam": home["name"], "nameVisitorTeam": away["name"],
                         "localScore": str(home["data"]["score"]), "visitorScore": str(away["data"]["score"])})
        ids = [str(t["teamIdExtern"]) for t in fbcyl_games.build_games()[0]["stats"]["teams"]] + ["34003", "34004"]
        for i in range(4):
            home, away = ids[i % 4], ids[(i + 1) % 4]
            rows.append({"idMatch": str(300 + i), "universallyid": f"{i + 1:024x}", "round": str(7 + i // 2), "state": "0", "tiedAllowed": "0", "matchDay": f"2026-12-{5 + i // 2 * 7:02d} 12:30:00",
                         "idLocalTeam": home, "idVisitorTeam": away, "nameLocalTeam": f"T{home}", "nameVisitorTeam": f"T{away}", "localScore": None, "visitorScore": None})
        return rows


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    handler = fixture_handler()
    manifest = publish_web_data(handler, OUT, ScopedSealer(SECRET, open_access=True), [FEB, FBCYL], scouting=[FEB],
                                scouting_service=fixture_scouting_service, image_source=FixtureFeb(),
                                calendar_source=FixtureCalendar(), fbcyl_groups={FBCYL: "7298"},
                                genders=competition_genders(handler, [FEB, FBCYL], load_catalogue(DEFAULT_CATALOGUE)),
                                categories=competition_categories([FEB, FBCYL], load_catalogue(DEFAULT_CATALOGUE)))
    print("wrote", OUT, sum(1 for p in OUT.rglob("*") if p.is_file()), "files,", len(manifest["rows"]), "competitions")


if __name__ == "__main__":
    main()
