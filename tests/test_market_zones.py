"""The shots by zone of a Talent row (#994): per player AND team (the granularity of the row) the made and attempted shots of each of the 10 zones of the engine, and the same for the whole
competition, in a sealed file of its own per competition and season (the search never downloads it: only the profile does). FEB and FBCYL, built from the shots the exporter reads."""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_market_publish import FBCYL, LF2, MASTER, _by, _manifest, _open, _publish, _tree, connection  # noqa: E402,F401
from src.live_core.zones import ZONES  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.market.contract import validate_talent_manifest  # noqa: E402
from src.market.zones import ZONE_ORDER, zone_table  # noqa: E402
from src.shotcharts.owned_shots import iter_owned_shots  # noqa: E402


def _zones(out, entry):
    z = entry["zones"]
    return json.loads(open_sealed(json.loads((out / z["file"]).read_text(encoding="utf-8")), z["wraps"], {"talent": scope_key(MASTER, "talent")}))


def _shots(connection, name, fbcyl):
    return list(iter_owned_shots(connection.get_collection(name), fbcyl))


class TestZoneTable:
    def test_the_zones_are_the_ten_of_the_engine_in_a_fixed_order(self):
        assert ZONE_ORDER == tuple(ZONES) and len(ZONE_ORDER) == 10

    def test_feb_counts_per_player_and_team_and_the_league_adds_up_with_the_shots_nobody_owns(self, connection):
        shots = _shots(connection, LF2, False)
        table = zone_table(shots, fbcyl=False)
        assert len(table["league"]) == 20 and table["league"][1::2] == [sum(1 for s in shots if s[5] == z) for z in ZONE_ORDER]
        owned = sum(1 for s in shots if s[1] is not None)
        assert sum(sum(v[1::2]) for v in table["players"].values()) == owned and owned < len(shots)          # a dorsal that matches nobody counts for the league only
        assert all(k.startswith("feb:") and "|" in k for k in table["players"])
        assert all(v[0::2][i] <= v[1::2][i] for v in table["players"].values() for i in range(10))

    def test_fbcyl_is_keyed_by_the_uuid(self, connection):
        table = zone_table(_shots(connection, FBCYL, True), fbcyl=True)
        assert "fbcyl:34001-00|34001" in table["players"]

    def test_the_answer_does_not_depend_on_the_order_of_the_shots(self, connection):
        shots = _shots(connection, LF2, False)
        expected = zone_table(shots, fbcyl=False)
        random.Random(3).shuffle(shots)
        assert zone_table(shots, fbcyl=False) == expected

    def test_no_shots_is_an_empty_table_with_zeros(self):
        assert zone_table([], fbcyl=False) == {"league": [0] * 20, "players": {}}


class TestPublication:
    def test_every_competition_has_a_sealed_zones_file_that_satisfies_the_contract(self, connection, tmp_path):
        manifest = _publish(connection, tmp_path)
        validate_talent_manifest(manifest)
        assert manifest == _manifest(tmp_path)
        for entry in manifest["competitions"]:
            data = _zones(tmp_path, entry)
            assert data["format"] == 1 and data["zones"] == list(ZONE_ORDER) and len(data["league"]) == 20

    def test_every_key_is_a_row_of_the_competition_and_the_players_with_shots_are_there(self, connection, tmp_path):
        manifest = _publish(connection, tmp_path)
        entry = _by(manifest, "L.F.-2")
        data = _zones(tmp_path, entry)
        keys = {f"{r['person_id']}|{r['team_id']}" for r in _open(tmp_path, entry)["rows"]}
        assert data["players"] and set(data["players"]) <= keys                              # a key of the file is always a row: the profile finds it
        assert "feb:10101|101" in data["players"] and sum(data["players"]["feb:10101|101"][1::2]) > 0

    def test_the_zones_of_groups_of_one_competition_are_added(self, connection, tmp_path):
        manifest = _publish(connection, tmp_path)
        one = zone_table(_shots(connection, LF2, False), fbcyl=False)
        assert _zones(tmp_path, _by(manifest, "L.F.-2"))["league"] == one["league"]          # one collection here: the same shots

    def test_the_same_run_keeps_every_byte_and_no_zones_file_is_left_orphan(self, connection, tmp_path):
        _publish(connection, tmp_path)
        before = _tree(tmp_path)
        _publish(connection, tmp_path)
        assert _tree(tmp_path) == before
        _publish(connection, tmp_path, names=(FBCYL,))
        assert len([p for p in _tree(tmp_path) if "zones" in p]) == 1
