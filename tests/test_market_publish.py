"""The Talent publication (B2, #878): one sealed file per competition and season with a row per player, team and competition, and a manifest of its own.

Same guarantees as ``web-data`` (#328, #640): nothing readable is published (rows are sealed, access is the wraps of the index), a name carries the hash of its content so it never changes in
place, and an unchanged competition keeps its bytes (sealing is random). The data are the games of the local-first test league and its FBCYL twin."""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.market.contract import validate_talent_manifest  # noqa: E402
from src.market.publish import publish_talent_data  # noqa: E402

LF2 = "L_F_-2_2025_2026_Liga_Regular_B"
CHALLENGE = "LF_CHALLENGE_2025_2026_Liga_Regular_Único"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
MASTER = "a-master-secret-for-the-tests"
CATALOGUE = [
    {"competition": "L.F.-2", "league": "feb", "level": 3, "gender": "F", "active": True, "packages": True},
    {"competition": "LF CHALLENGE", "league": "feb", "level": 2, "gender": "F", "active": True, "packages": True},
    {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-1", "season_value": "2026", "season_label": "2026", "note": "Primera Nacional Femenina, grupo A-1", "active": True,
     "fbcyl": {"competition_id": "7298", "category": "1129", "gender": "F", "territory": "1"}},
]
META = {LF2: ("L.F.-2", "Liga Regular · B"), CHALLENGE: ("LF CHALLENGE", "Liga Regular · Único")}


@pytest.fixture()
def connection(monkeypatch):
    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    from src.api import deps

    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    for name in (LF2, CHALLENGE):
        db[name].insert_many(games.build_games())
        label, group = META[name]
        db["COLLECTION_META"].insert_one({"_id": name, "league": "FEB", "competition_label": label, "season_value": "2025", "season_label": "2025/2026", "group_label": group})
    db[FBCYL].insert_many(fbcyl_games.build_games())
    yield handler.connection
    deps._create_handler.cache_clear()


def _manifest(out):
    return json.loads((out / "index.json").read_text(encoding="utf-8"))


def _open(out, entry, scope="talent"):
    envelope = json.loads((out / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], {scope: scope_key(MASTER, scope)}))


def _publish(connection, out, names=(LF2, CHALLENGE, FBCYL), sealer=None, **kw):
    return publish_talent_data(connection, out, sealer or ScopedSealer(MASTER, open_access=False), list(names), CATALOGUE, **kw)


def _tree(out):
    return {str(p.relative_to(out)).replace("\\", "/"): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def _by(manifest, competition):
    return next(e for e in manifest["competitions"] if e["competition"] == competition)


def test_one_file_per_competition_and_season_and_a_manifest_that_satisfies_the_contract(connection, tmp_path):
    manifest = _publish(connection, tmp_path)
    validate_talent_manifest(manifest)
    assert manifest == _manifest(tmp_path)
    assert [e["key"] for e in manifest["competitions"]] == ["fbcyl|1129-1|2026", "feb|lf2|2025", "feb|lfchallenge|2025"]          # sorted by key: a fixed order
    assert {e["gender"] for e in manifest["competitions"]} == {"F"} and _by(manifest, "L.F.-2")["level"] == 3 and _by(manifest, "Primera Nacional Femenina")["league"] == "fbcyl"


def test_competitions_are_never_mixed_even_with_the_same_teams_and_players(connection, tmp_path):
    """LF2 and LF Challenge hold the same games here: if they were put together every figure would double."""
    manifest = _publish(connection, tmp_path)
    a, b = _open(tmp_path, _by(manifest, "L.F.-2")), _open(tmp_path, _by(manifest, "LF CHALLENGE"))
    strip = lambda rows: [{k: v for k, v in r.items() if k != "groups"} for r in rows]               # only the label of the group differs between the two
    assert strip(a["rows"]) == strip(b["rows"]) and len(a["rows"]) == _by(manifest, "L.F.-2")["players"] and a["competition"]["competition"] == "L.F.-2"
    assert next(r for r in a["rows"] if r["person_id"] == "feb:10100")["games"] == 6                    # six games, not twelve


def test_a_row_has_the_totals_the_context_figures_the_profile_and_the_bio(connection, tmp_path):
    roster = [{"person_id": "feb:10100", "season": "2025", "team_id": "101", "name": "ANA PRUEBA UNO", "birth": "2004-05-06", "height": 178, "position": "Base",
               "nationality": "ESPAÑA", "formacion": True, "dorsal": 7}]
    manifest = _publish(connection, tmp_path, roster_rows=roster)
    row = next(r for r in _open(tmp_path, _by(manifest, "L.F.-2"))["rows"] if r["person_id"] == "feb:10100")
    assert (row["team_id"], row["games"], row["pts"], row["usage_pct"], row["orating"], row["pie"]) == ("101", 6, 61, 21.5, 113.5, 7.67)        # the numbers of the Players page vectors
    assert row["per40"]["pts"] > 0 and set(row["role"]) >= {"orb40", "usage40"} and 0 <= row["pct"]["pts"] <= 100 and row["eligible"] is True
    assert (row["birth"], row["height"], row["position"], row["full_name"]) == ("2004-05-06", 178, "Base", "ANA PRUEBA UNO")


def test_fbcyl_is_a_competition_of_its_own_with_its_minutes_in_seconds_and_no_bio(connection, tmp_path):
    entry = _by(_publish(connection, tmp_path), "Primera Nacional Femenina")
    rows = _open(tmp_path, entry)["rows"]
    row = next(r for r in rows if r["person_id"] == "fbcyl:34001-00")
    assert row["minutes"] % 60 == 0 and row["minutes"] > 0 and row["birth"] is None and row["height"] is None and entry["players"] == len(rows)


def test_the_rows_are_sealed_for_the_talent_scope_and_the_open_key_opens_them_only_while_the_beta_is_open(connection, tmp_path):
    closed = _publish(connection, tmp_path / "closed")
    assert [w["scope"] for w in closed["competitions"][0]["wraps"]] == ["talent"] and "open_key" not in _manifest(tmp_path / "closed")
    with pytest.raises(Exception):
        _open(tmp_path / "closed", closed["competitions"][0], "club:101")
    opened = _publish(connection, tmp_path / "open", sealer=ScopedSealer(MASTER, open_access=True))
    assert opened["open_key"] and [w["scope"] for w in opened["competitions"][0]["wraps"]] == ["abierto", "talent"]


def test_a_second_run_keeps_every_byte_and_a_corrected_game_changes_only_its_competition(connection, tmp_path):
    two = (LF2, CHALLENGE)
    _publish(connection, tmp_path, names=two)
    before = _tree(tmp_path)
    _publish(connection, tmp_path, names=two)
    assert _tree(tmp_path) == before
    db = connection.client["BASKETBALL"]
    game = db[CHALLENGE].find_one({})
    game["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["pts"] = "99"
    db[CHALLENGE].replace_one({"_id": game["_id"]}, game)
    _publish(connection, tmp_path, names=two)
    after = _tree(tmp_path)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert {k for k in changed if k.startswith("players/")} and all("lfchallenge" in k for k in changed if k.startswith("players/")) and "index.json" in changed
    assert sum(1 for k in after if k.startswith("players/")) == 2                       # the old file of the corrected competition is gone


def test_collections_that_say_nothing_are_reported_and_the_rest_is_published(connection, tmp_path):
    connection.client["BASKETBALL"]["archive"].insert_one({"_id": 1})
    unknown = []
    manifest = _publish(connection, tmp_path, names=[LF2, "archive"], on_unknown=unknown.extend)
    assert unknown == ["archive"] and len(manifest["competitions"]) == 1


def test_no_collections_is_an_empty_but_valid_manifest(connection, tmp_path):
    manifest = _publish(connection, tmp_path, names=[])
    validate_talent_manifest(manifest)
    assert manifest["competitions"] == [] and not [k for k in _tree(tmp_path) if k.startswith("players/")]


def test_the_branch_carries_the_guard_that_keeps_vercel_from_building_it_regression(connection, tmp_path):
    """Bug found after the first run (#906): Vercel builds every branch of the repo, and ``talent-data`` has no ``frontend`` folder, so both projects (Analytics and Talent) raised
    "The specified Root Directory frontend does not exist". ``web-data`` has always carried ``frontend/vercel.json`` (the folder exists and the deployments are off); this branch must too."""
    _publish(connection, tmp_path, names=[LF2])
    assert json.loads((tmp_path / "frontend" / "vercel.json").read_text(encoding="utf-8")) == {"git": {"deploymentEnabled": False}}
    _publish(connection, tmp_path, names=[])                                       # an empty publication keeps it too: the branch is never without it
    assert (tmp_path / "frontend" / "vercel.json").is_file()


def test_the_manifest_says_the_category_age_group_and_name_of_each_competition_from_the_catalogue(connection, tmp_path):
    """#914: a youth competition is ``formacion`` with its age group and the name people read; the others are senior, FBCYL included; the manifest still satisfies the contract."""
    youth = [dict(e, category="formacion", age_group="U16", label="Campeonato juvenil de prueba") if e["competition"] == "LF CHALLENGE" else e for e in CATALOGUE]
    manifest = publish_talent_data(connection, tmp_path, ScopedSealer(MASTER, open_access=False), [LF2, CHALLENGE, FBCYL], youth)
    validate_talent_manifest(manifest)
    challenge = _by(manifest, "LF CHALLENGE")
    assert (challenge["category"], challenge["age_group"], challenge["competition_label"]) == ("formacion", "U16", "Campeonato juvenil de prueba")
    for senior in (_by(manifest, "L.F.-2"), _by(manifest, "Primera Nacional Femenina")):
        assert senior["category"] == "senior" and "age_group" not in senior and "competition_label" not in senior


def test_a_competition_the_catalogue_does_not_know_has_no_category_it_is_not_guessed(connection, tmp_path):
    without = [e for e in CATALOGUE if e["competition"] != "LF CHALLENGE"]
    manifest = publish_talent_data(connection, tmp_path, ScopedSealer(MASTER, open_access=False), [LF2, CHALLENGE, FBCYL], without)
    assert "category" not in _by(manifest, "LF CHALLENGE") and _by(manifest, "L.F.-2")["category"] == "senior"
