"""The crest and the photos of a team, published for the DOCX of the individual scouting (#717, 17a).

The FEB is replaced by a fake that answers images made here, counts what is asked of it and announces the size of each (a ``HEAD``): the publication must download what is new, keep what
did not change (the same size) and scrape the identity of a player once.
"""
import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from db_helpers import new_mock_db
from src.live_prep.package_scopes import open_sealed, scope_key
from src.live_prep.package_sealing import ScopedSealer
from src.local_data.images_export import (
    LOGO_HEIGHT, PHOTO_HEIGHT, Source, current_season_collections, reduce_logo, reduce_photo, seal_images, team_payload, team_sources)

COLLECTION = "PRIMERA_FEB_2026_2027_Liga_Regular_Unico"
MASTER = "a-master-secret-for-the-tests"


def png(width, height, colour=(200, 30, 30, 255)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (width, height), colour).save(out, format="PNG")
    return out.getvalue()


def jpeg(width, height) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (20, 90, 200)).save(out, format="JPEG")
    return out.getvalue()


class FakeFeb(Source):
    def __init__(self, images, identities=None, photos=None, crests=None):
        self.images, self.identities = dict(images), identities or {}
        self.photos, self.crests = photos or {}, crests or {}                      # FBCYL: the photo URL of a player uuid, the crest URL of a team id
        self.gets, self.heads, self.scrapes, self.lookups = [], [], [], []

    def get(self, url):
        self.gets.append(url)
        return self.images.get(url)

    def length(self, url):
        self.heads.append(url)
        return len(self.images[url]) if url in self.images else None

    def identity(self, team_id, player_id):
        self.scrapes.append((team_id, player_id))
        return self.identities.get(player_id, (None, None))

    def photo_url(self, uuid):
        self.lookups.append(("photo", uuid))
        return self.photos.get(uuid)

    def team_logo_url(self, team_id):
        self.lookups.append(("crest", team_id))
        return self.crests.get(str(team_id))


URLS = {"logo1": "https://img/logo1", "p11": "https://img/p11", "p12": "https://img/p12", "logo2": "https://img/logo2", "p21": "https://img/p21"}
IMAGES = {URLS["logo1"]: png(400, 400), URLS["p11"]: png(600, 800), URLS["p12"]: jpeg(300, 400), URLS["logo2"]: png(300, 300, (10, 10, 200, 255)), URLS["p21"]: jpeg(250, 350)}
IDENTITIES = {"11": ("05/03/1998", "198 cm"), "12": ("17/11/2001", "185 cm"), "21": (None, "190 cm")}


def games():
    def game(i):
        return {"_id": i, "HEADER": {"TEAM": [{"id": "1", "name": "ALFA", "logo": URLS["logo1"]}, {"id": "2", "name": "BRAVO", "logo": URLS["logo2"]}]},
                "BOXSCORE": {"TEAM": [
                    {"id": "1", "PLAYER": [{"id": "11", "no": "4", "name": "A. UNO", "logo": URLS["p11"]}, {"id": "12", "no": "7", "name": "B. DOS", "logo": URLS["p12"]}]},
                    {"id": "2", "PLAYER": [{"id": "21", "no": "9", "name": "C. TRES", "logo": URLS["p21"]}, {"id": "22", "no": "3", "name": "D. SIN FOTO", "logo": ""}]}]}}
    return [game(1), game(2)]


@pytest.fixture()
def collection():
    col = new_mock_db("v")[COLLECTION]
    col.insert_many(games())
    return col


def decode(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1])))


def test_a_photo_is_a_small_jpeg_on_white_and_a_crest_a_small_png_that_keeps_its_transparency():
    photo = reduce_photo(png(600, 800, (255, 0, 0, 0)))                                        # a PNG photo with transparency
    image = Image.open(io.BytesIO(photo))
    assert image.format == "JPEG" and image.height == PHOTO_HEIGHT and image.width == 150 and len(photo) < len(png(600, 800))
    assert image.convert("RGB").getpixel((5, 5)) == (255, 255, 255) or min(image.convert("RGB").getpixel((5, 5))) > 240          # transparent over white
    logo = Image.open(io.BytesIO(reduce_logo(png(400, 400, (10, 20, 30, 0)))))
    assert logo.format == "PNG" and logo.height == LOGO_HEIGHT and logo.mode == "RGBA" and logo.getpixel((5, 5))[3] == 0
    assert reduce_photo(b"not an image") is None and reduce_logo(b"") is None
    assert Image.open(io.BytesIO(reduce_photo(jpeg(80, 100)))).height == 100                    # a small one is not enlarged


def test_the_sources_of_a_team_are_read_from_the_last_game_and_those_without_players_are_left_out(collection):
    teams = team_sources(collection)
    assert sorted(teams) == ["1", "2"] and teams["1"]["name"] == "ALFA" and teams["1"]["logo"] == URLS["logo1"]
    assert teams["2"]["players"]["22"]["photo"] is None and teams["1"]["players"]["11"] == {"name": "A. UNO", "no": "4", "photo": URLS["p11"]}


def test_the_first_publication_downloads_everything_and_scrapes_the_identity_of_every_player(collection):
    feb = FakeFeb(IMAGES, IDENTITIES)
    payload = team_payload(COLLECTION, "1", team_sources(collection)["1"], {}, feb)
    assert sorted(feb.gets) == sorted([URLS["logo1"], URLS["p11"], URLS["p12"]]) and feb.heads == [] and sorted(feb.scrapes) == [("1", "11"), ("1", "12")]
    assert decode(payload["logo"]).height == LOGO_HEIGHT and decode(payload["players"]["11"]["photo"]).format == "JPEG"
    assert payload["players"]["11"] | {"photo": None} == {"name": "A. UNO", "no": "4", "photo": None, "birth_date": "05/03/1998", "height": "198 cm"}
    assert payload["sources"]["players"]["11"] == {"url": URLS["p11"], "size": len(IMAGES[URLS["p11"]])}


def test_the_next_one_only_asks_the_size_of_what_it_has_and_downloads_nothing_if_it_is_the_same_regression(collection):
    """Bug it prevents: downloading ~300 photos on every publication (the FEB honours no conditional request, so the size of a HEAD is the only cheap sign of a change)."""
    first = team_payload(COLLECTION, "1", team_sources(collection)["1"], {}, FakeFeb(IMAGES, IDENTITIES))
    feb = FakeFeb(IMAGES, IDENTITIES)
    again = team_payload(COLLECTION, "1", team_sources(collection)["1"], first, feb)
    assert again == first and feb.gets == [] and feb.scrapes == []
    assert sorted(feb.heads) == sorted([URLS["logo1"], URLS["p11"], URLS["p12"]])


def test_an_image_whose_size_changed_a_new_player_and_a_new_photo_url_are_downloaded_and_nothing_else(collection):
    first = team_payload(COLLECTION, "1", team_sources(collection)["1"], {}, FakeFeb(IMAGES, IDENTITIES))
    changed = {**IMAGES, URLS["p11"]: png(600, 801, (10, 200, 10, 255))}                                         # the FEB replaced the photo of 11
    feb = FakeFeb(changed, IDENTITIES)
    sources = team_sources(collection)["1"]
    sources["players"]["13"] = {"name": "E. NUEVO", "no": "1", "photo": "https://img/p13"}   # a signing
    sources["players"]["12"]["photo"] = "https://img/p12b"                                    # a new URL for 12
    feb.images.update({"https://img/p13": jpeg(200, 300), "https://img/p12b": jpeg(220, 320)})
    again = team_payload(COLLECTION, "1", sources, first, feb)
    assert sorted(feb.gets) == sorted([URLS["p11"], "https://img/p13", "https://img/p12b"]) and feb.scrapes == [("1", "13")]
    assert again["players"]["11"]["photo"] != first["players"]["11"]["photo"] and again["logo"] == first["logo"]


def test_what_cannot_be_had_is_left_out_without_failing_and_is_asked_again_next_time(collection):
    feb = FakeFeb({URLS["logo1"]: IMAGES[URLS["logo1"]], URLS["p12"]: b"corrupt"}, {})
    payload = team_payload(COLLECTION, "1", team_sources(collection)["1"], {}, feb)
    assert payload["logo"] and payload["players"]["11"]["photo"] is None and payload["players"]["12"]["photo"] is None       # missing, and not an image
    assert payload["players"]["11"]["birth_date"] is None
    feb2 = FakeFeb(IMAGES, IDENTITIES)
    healed = team_payload(COLLECTION, "1", team_sources(collection)["1"], payload, feb2)
    assert healed["players"]["11"]["photo"] and URLS["p11"] in feb2.gets and URLS["logo1"] not in feb2.gets


def test_a_player_without_a_photo_url_has_no_photo_and_no_download(collection):
    feb = FakeFeb(IMAGES, IDENTITIES)
    payload = team_payload(COLLECTION, "2", team_sources(collection)["2"], {}, feb)
    assert payload["players"]["22"]["photo"] is None and sorted(feb.gets) == sorted([URLS["logo2"], URLS["p21"]])
    assert payload["players"]["21"]["birth_date"] is None and payload["players"]["21"]["height"] == "190 cm"


def test_only_the_competitions_of_the_newest_season_of_each_league_are_published():
    names = ["PRIMERA_FEB_2025_2026_Liga_Regular_Unico", "PRIMERA_FEB_2026_2027_Liga_Regular_Unico", "COPA_ESPANA_2026_2027_FASE_DE_GRUPOS_A", "COPA_ESPANA_2025_2026_Play-offs_Final",
             "FBCYL_1ª_FASE-GRUPO_A-1_2026_", "FBCYL_1ª_FASE-GRUPO_A-1_2025_", "SEGUNDA_FEB_2026_2027_Liga_Regular_A", "SIN_TEMPORADA"]
    assert current_season_collections(names) == {"PRIMERA_FEB_2026_2027_Liga_Regular_Unico", "COPA_ESPANA_2026_2027_FASE_DE_GRUPOS_A", "SEGUNDA_FEB_2026_2027_Liga_Regular_A", "FBCYL_1ª_FASE-GRUPO_A-1_2026_"}
    assert current_season_collections(["FBCYL_X_2025_"]) == {"FBCYL_X_2025_"}                      # FBCYL's season is the single year: its newest does not depend on FEB's
    assert current_season_collections([]) == set()


FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
FB_URLS = {"crest101": "https://cdn/crest101.png", "ph1": "https://s3/ph1.jpg", "ph2": "https://s3/ph2.jpg"}
FB_IMAGES = {FB_URLS["crest101"]: png(300, 300), FB_URLS["ph1"]: jpeg(300, 400), FB_URLS["ph2"]: jpeg(260, 360)}


@pytest.fixture()
def fbcyl():
    """Two FBCYL games: a uuid is the stable key of a player (his ``actorId`` changes from game to game) and some appearances come without it."""
    col = new_mock_db("f")[FBCYL]

    def game(i, actor):
        return {"uuid": f"g{i}", "stats": {"teams": [
            {"teamIdIntern": 900 + i, "teamIdExtern": 101, "name": "ALFA ", "players": [
                {"uuid": "u1", "actorId": actor, "name": "A. UNO", "dorsal": "4"}, {"uuid": "u2", "actorId": actor + 1, "name": "B. DOS", "dorsal": "7"},
                {"uuid": None, "actorId": actor + 2, "name": "C. SIN UUID", "dorsal": "9"}]},
            {"teamIdIntern": 950 + i, "teamIdExtern": 102, "name": "BRAVO", "players": [{"uuid": "u3", "actorId": actor + 5, "name": "D. TRES", "dorsal": "1"}]}]}}
    col.insert_many([game(1, 10), game(2, 20)])
    return col


def test_fbcyl_sources_are_read_from_the_stats_by_uuid_and_those_without_uuid_are_left_out(fbcyl):
    teams = team_sources(fbcyl)
    assert sorted(teams) == ["101", "102"] and teams["101"]["name"] == "ALFA" and teams["101"]["logo"] is None and teams["101"]["fbcyl"] is True
    assert teams["101"]["players"] == {"u1": {"name": "A. UNO", "no": "4", "photo": None}, "u2": {"name": "B. DOS", "no": "7", "photo": None}}


def test_fbcyl_asks_the_esb_for_the_crest_and_for_the_photo_of_each_uuid_and_has_no_identity_to_scrape(fbcyl):
    feb = FakeFeb(FB_IMAGES, photos={"u1": FB_URLS["ph1"], "u2": FB_URLS["ph2"]}, crests={"101": FB_URLS["crest101"]})
    payload = team_payload(FBCYL, "101", team_sources(fbcyl)["101"], {}, feb)
    assert sorted(feb.lookups) == [("crest", "101"), ("photo", "u1"), ("photo", "u2")] and feb.scrapes == []
    assert decode(payload["logo"]).height == LOGO_HEIGHT and decode(payload["players"]["u1"]["photo"]).format == "JPEG"
    assert payload["players"]["u1"] == {"name": "A. UNO", "no": "4", "photo": payload["players"]["u1"]["photo"], "birth_date": None, "height": None}
    assert payload["sources"]["players"]["u2"] == {"url": FB_URLS["ph2"], "size": len(FB_IMAGES[FB_URLS["ph2"]])}


def test_fbcyl_the_next_publication_asks_again_where_the_photo_is_but_downloads_only_what_changed_regression(fbcyl):
    """The ESB is the only place that says which photo a uuid has now, so it is asked every time; the image is downloaded only if its size changed."""
    first = team_payload(FBCYL, "101", team_sources(fbcyl)["101"], {}, FakeFeb(FB_IMAGES, photos={"u1": FB_URLS["ph1"], "u2": FB_URLS["ph2"]}, crests={"101": FB_URLS["crest101"]}))
    changed = {**FB_IMAGES, FB_URLS["ph1"]: png(300, 401, (10, 200, 10, 255))}
    feb = FakeFeb(changed, photos={"u1": FB_URLS["ph1"], "u2": "https://s3/ph2-new.jpg"}, crests={"101": FB_URLS["crest101"]})
    feb.images["https://s3/ph2-new.jpg"] = jpeg(100, 140)
    again = team_payload(FBCYL, "101", team_sources(fbcyl)["101"], first, feb)
    assert sorted(feb.gets) == sorted([FB_URLS["ph1"], "https://s3/ph2-new.jpg"]) and feb.scrapes == []
    assert again["logo"] == first["logo"] and again["players"]["u1"]["photo"] != first["players"]["u1"]["photo"]


def test_fbcyl_a_player_without_photo_and_a_team_without_crest_are_left_blank_without_failing(fbcyl):
    payload = team_payload(FBCYL, "101", team_sources(fbcyl)["101"], {}, FakeFeb(FB_IMAGES, photos={"u1": FB_URLS["ph1"]}))
    assert payload["logo"] is None and payload["players"]["u2"]["photo"] is None and payload["players"]["u1"]["photo"]


def test_each_team_is_sealed_for_the_competition_and_the_clubs_and_an_unchanged_team_keeps_its_bytes(collection, tmp_path):
    sealer = ScopedSealer(MASTER, open_access=False)
    feb = FakeFeb(IMAGES, IDENTITIES)
    entries = seal_images(collection, COLLECTION, tmp_path, sealer, {}, "images/", feb)
    assert [(e["team_id"], e["mode"]) for e in entries] == [("1", "images"), ("2", "images")] and all(e["file"].startswith("images/") for e in entries)
    scopes = {w["scope"] for w in entries[0]["wraps"]}
    assert scopes == {f"competicion:{COLLECTION}", "club:1", "club:2"}
    opened = json.loads(open_sealed(json.loads((tmp_path / entries[0]["file"]).read_text(encoding="utf-8")), entries[0]["wraps"], {f"competicion:{COLLECTION}": scope_key(MASTER, f"competicion:{COLLECTION}")}))
    assert opened["team"] == "ALFA" and opened["players"]["11"]["birth_date"] == "05/03/1998"
    bytes_before = {e["file"]: (tmp_path / e["file"]).read_bytes() for e in entries}
    again = FakeFeb(IMAGES, IDENTITIES)
    old = {(e["collection"], e["team_id"], "images", None): e for e in entries}
    second = seal_images(collection, COLLECTION, tmp_path, sealer, old, "images/", again)
    assert again.gets == [] and again.scrapes == [] and [e["file"] for e in second] == [e["file"] for e in entries]
    assert all((tmp_path / e["file"]).read_bytes() == bytes_before[e["file"]] for e in second)          # sealing is random: the same file, not a new seal
    assert Path(tmp_path / entries[0]["file"]).stat().st_size < 60_000
