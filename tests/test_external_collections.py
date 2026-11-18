"""The collections of the external sources and what the exporter and the manifest say of them (#884, D0, PR B).

A competition of an external source is stored, like every other, in one collection named after it: ``<SOURCE>_<competition>_<season>_<conference>`` (``NCAA_D1_2026_SEC``), so that its source reads from the name
(``source_of``) as the FBCYL ones do from theirs, and the exporter puts it in the ``league`` of its rows entry. The tests store REAL FEB games badged as a source (``tests/market_helpers.badged``).
"""
import json
import sys
from pathlib import Path

import pytest

from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import games  # noqa: E402

from market_helpers import badged  # noqa: E402

from src.local_data.contract import validate_manifest  # noqa: E402
from src.local_data.export import export_collection  # noqa: E402
from src.services.competition_catalogue import EXTERNAL_LEAGUES, external_collections, load_catalogue  # noqa: E402
from src.utils.collection_utils import is_fbcyl, source_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _entry(source, **over):
    base = {"competition": "D1" if source == "ncaa" else "U18 EuroBasket", "season_label": "2026/2027", "season_value": "2026", "league": source, "division": "D1", "gender": "M"}
    if source == "ncaa":
        base["conference"] = "SEC"
    if source == "fiba":
        base["fiba"] = {"event": "fiba-test-event-2026"}
    return {**base, **over}


def _catalogue(tmp_path, *entries):
    path = tmp_path / "competitions.json"
    path.write_text(json.dumps({"competitions": list(entries)}), encoding="utf-8")
    return load_catalogue(path)


class TestNames:
    def test_the_collection_of_each_competition_carries_its_source_and_its_conference(self, tmp_path):
        cat = _catalogue(tmp_path, _entry("ncaa"), _entry("ncaa", conference="Ivy League"), _entry("fiba"), _entry("acb", competition="Liga Endesa", division="ACB"))
        assert list(external_collections(cat)) == ["NCAA_D1_2026_SEC", "NCAA_D1_2026_Ivy_League", "FIBA_U18_EuroBasket_2026_", "ACB_Liga_Endesa_2026_"]

    def test_it_maps_each_collection_to_its_entry_and_leaves_out_the_paused_ones(self, tmp_path):
        cat = _catalogue(tmp_path, _entry("ncaa"), _entry("ncaa", conference="Big Ten", active=False), _entry("fiba"))
        found = external_collections(cat)
        assert set(found) == {"NCAA_D1_2026_SEC", "FIBA_U18_EuroBasket_2026_"} and found["NCAA_D1_2026_SEC"]["conference"] == "SEC"

    def test_two_seasons_of_a_competition_are_two_collections(self, tmp_path):
        cat = _catalogue(tmp_path, _entry("fiba"), _entry("fiba", season_label="2025/2026", season_value="2025"))
        assert len(external_collections(cat)) == 2

    @pytest.mark.parametrize("name, source", [
        ("NCAA_D1_2026_SEC", "ncaa"), ("FIBA_U18_EuroBasket_2026_", "fiba"), ("ACB_Liga_Endesa_2026_", "acb"),
        ("PRIMERA_FEB_2025_2026_Liga_Regular_Único", None), ("FBCYL_1ª_FASE-GRUPO_A-1_2026_", None), ("LF_ENDESA_2026_2027_Liga_Regular_Único", None),
        ("NCAAB_2026", None), ("", None),                      # only the exact prefix: a FEB competition that merely begins with the letters is not external
    ])
    def test_the_source_is_read_from_the_name(self, name, source):
        assert source_of(name) == source

    @pytest.mark.parametrize("name", ["NCAA_D1_2026_SEC", "FIBA_U18_EuroBasket_2026_", "ACB_Liga_Endesa_2026_"])
    def test_an_external_collection_is_not_fbcyl_so_no_pipeline_takes_it_for_one(self, name):
        assert is_fbcyl(name) is False

    def test_the_sources_are_one_list(self):
        assert EXTERNAL_LEAGUES == ("acb", "fiba", "ncaa")


@pytest.mark.parametrize("source", EXTERNAL_LEAGUES)
def test_the_rows_of_an_external_competition_say_their_source_as_their_league(source):
    name = {"acb": "ACB_Liga_Endesa_2026_", "fiba": "FIBA_U18_EuroBasket_2026_", "ncaa": "NCAA_D1_2026_SEC"}[source]
    db = new_mock_db("BASKETBALL")
    db[name].insert_many([badged(g, source) for g in games.build_games()])
    payload = export_collection(db[name], name)
    assert payload["league"] == source and payload["games"] == 12
    assert {row["team_id"] for row in payload["team_rows"]} == {f"{source}:{i}" for i in ("101", "102", "103", "104")}


def test_feb_and_fbcyl_rows_keep_their_league():
    db = new_mock_db("BASKETBALL")
    db["PRIMERA_FEB_2025_2026_Liga_Regular_Único"].insert_many(games.build_games())
    assert export_collection(db["PRIMERA_FEB_2025_2026_Liga_Regular_Único"], "PRIMERA_FEB_2025_2026_Liga_Regular_Único")["league"] == "feb"


class TestManifestContract:
    def _manifest(self, league):
        row = {"collection": "X", "league": league, "games": 1, "file": "rows/x.json", "bytes": 1, "sha256": "0" * 64, "wraps": []}
        return {"schema": 1, "v": 2, **{k: [] for k in ("derived", "shots", "rotations", "matches", "possessions", "possession_csv", "lineups", "inout", "consistency", "rival_adjusted", "assist_connections", "calendar", "reports")},
                "rows": [row]}

    @pytest.mark.parametrize("league", ["feb", "fbcyl", "acb", "fiba", "ncaa"])
    def test_the_manifest_accepts_the_league_of_every_source(self, league):
        validate_manifest(self._manifest(league))

    def test_it_refuses_a_league_that_is_not_a_source(self):
        with pytest.raises(ValueError, match="league"):
            validate_manifest(self._manifest("euroleague"))
