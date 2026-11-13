"""The category of each competition (#914, #918, epic #872): senior or formación, and for formación its age group (U14 infantil, U15-U16 cadete, U17-U18 júnior; U19-U22 are senior).

It lives in the catalogue (``config/competitions.json``), not in the name of the competition, and goes to the manifest of ``web-data`` and to the one of ``talent-data``. The age groups are
normalised once, in ``competition_category``; whatever is not in the table is never forced into it.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.web_data import publish_web_data  # noqa: E402
from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue  # noqa: E402
from src.services.competition_category import AGE_GROUPS, CATEGORIES, category_of_age, competition_categories, normalize_age_group  # noqa: E402
from tests.test_local_web_data import FBCYL, FEB, MASTER, cheap_lineups, handler  # noqa: E402,F401  (fixtures)

CATALOGUE = load_catalogue(DEFAULT_CATALOGUE)
FORMATION = {"C ESP CLUBES CAD FEM", "C ESP CLUBES CAD MASC", "C ESP CLUBES JR FEM", "C ESP CLUBES JR MASC", "CE SSAA Cadete Fem.", "CE SSAA Cadete Mas."}


def test_the_age_groups_are_infantil_cadete_and_junior_and_u20_is_not_one_of_them():
    assert AGE_GROUPS == {"U14": "Infantil", "U16": "Cadete", "U18": "Júnior"} and CATEGORIES == ("senior", "formacion")


@pytest.mark.parametrize("raw, code", [
    ("U14", "U14"), ("u14", "U14"), ("U-14", "U14"), ("sub14", "U14"), ("Sub-14", "U14"), ("infantil", "U14"), ("INF", "U14"), ("Infantil", "U14"),
    ("U16", "U16"), ("cadete", "U16"), ("CAD", "U16"), ("Cadete", "U16"), ("sub-16", "U16"), ("U15", "U16"), ("u-15", "U16"), ("sub15", "U16"),
    ("U18", "U18"), ("junior", "U18"), ("Júnior", "U18"), ("JR", "U18"), ("JÚNIOR", "U18"), ("sub 18", "U18"), ("U17", "U18"), ("sub-17", "U18"),
])
def test_every_way_of_writing_an_age_group_gives_its_code(raw, code):
    assert normalize_age_group(raw) == code


@pytest.mark.parametrize("raw", [None, "", "  ", "senior", "sénior", "U19", "U20", "u-21", "sub22", "U13", "U23", "sub23", "juvenil", "alevin", "xyz", 16, True, ["U16"], {}])
def test_what_is_not_an_age_group_is_none_and_never_forced_into_one(raw):
    assert normalize_age_group(raw) is None            # U19-U22 are senior (no age group), «juvenil» is not «júnior»: nothing is guessed


@pytest.mark.parametrize("raw, category", [
    ("U14", "formacion"), ("infantil", "formacion"), ("U15", "formacion"), ("U16", "formacion"), ("cadete", "formacion"), ("U17", "formacion"), ("U18", "formacion"), ("Júnior", "formacion"),
    ("U19", "senior"), ("U20", "senior"), ("sub-20", "senior"), ("u21", "senior"), ("U-22", "senior"), ("sub 22", "senior"),
])
def test_the_category_of_an_age_u14_to_u18_is_formacion_and_u19_to_u22_are_senior_players_over_18(raw, category):
    assert category_of_age(raw) == category


@pytest.mark.parametrize("raw", [None, "", "U13", "U23", "sub23", "juvenil", "senior", "xyz", 20, True])
def test_an_age_that_is_not_in_the_table_has_no_category(raw):
    assert category_of_age(raw) is None


def _entry(**over):
    return {"competition": "CE TEST", "competition_url": "https://example.invalid/c", "season_label": "2025/2026", "season_value": "2025", "groups": "all", **over}


def _load(tmp_path, *entries):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"competitions": list(entries)}), encoding="utf-8")
    return load_catalogue(path)


def test_the_catalogue_validates_the_category_and_the_age_group_of_an_entry(tmp_path):
    (ok,) = _load(tmp_path, _entry(category="formacion", age_group="cadete", label="Cadete test"))
    assert (ok["category"], ok["age_group"], ok["label"]) == ("formacion", "U16", "Cadete test")        # normalised on load
    (plain,) = _load(tmp_path, _entry())
    assert "category" not in plain or plain["category"] == "senior"
    (u15,) = _load(tmp_path, _entry(category="formacion", age_group="U15", label="Cadete U15"))
    assert u15["age_group"] == "U16"                                                       # U15 is cadete
    for bad in ({"category": "juvenil"}, {"category": "senior", "age_group": "U16"}, {"category": "formacion", "age_group": "juvenil"}, {"category": "formacion", "age_group": "U20", "label": "x"},
                {"age_group": "U16"}, {"label": 5}, {"category": "formacion", "label": " "}):
        with pytest.raises(ValueError, match="competitions entry #1"):
            _load(tmp_path, _entry(**bad))


def test_u19_to_u22_are_senior_so_a_formacion_entry_cannot_say_u20(tmp_path):
    with pytest.raises(ValueError, match="U19"):
        _load(tmp_path, _entry(category="formacion", age_group="U20", label="Mundial U20"))
    (senior,) = _load(tmp_path, _entry(label="Campeonato U20"))
    assert senior.get("category", "senior") == "senior" and "age_group" not in senior


def test_a_youth_entry_needs_its_age_group_and_its_name(tmp_path):
    with pytest.raises(ValueError, match="age_group"):
        _load(tmp_path, _entry(category="formacion", label="Sin edad"))
    with pytest.raises(ValueError, match="label"):
        _load(tmp_path, _entry(category="formacion", age_group="U16"))


def test_the_six_youth_championships_of_the_real_catalogue_are_formacion_with_their_age_group_and_every_other_competition_is_not():
    youth = [e for e in CATALOGUE if e.get("category") == "formacion" and e["league"] == "feb"]
    assert {e["competition"] for e in youth} == FORMATION
    assert all(e["age_group"] in ("U16", "U18") and e["label"] for e in youth)
    assert {e["age_group"] for e in youth if "CAD" in e["competition"] or "Cadete" in e["competition"]} == {"U16"}
    assert {e["age_group"] for e in youth if "JR" in e["competition"]} == {"U18"}
    assert all(e.get("category", "senior") == "senior" for e in CATALOGUE if e["league"] == "feb" and e["competition"] not in FORMATION)
    fbcyl_youth = [e for e in CATALOGUE if e["league"] == "fbcyl" and e.get("category") == "formacion"]
    assert fbcyl_youth and {e["age_group"] for e in fbcyl_youth} == {"U16", "U18"} and all(e["label"] and e["group_label"] for e in fbcyl_youth)      # #920: cadete and júnior, never infantil


@pytest.mark.parametrize("collection, category, age_group, label", [
    ("C_ESP_CLUBES_JR_FEM_2024_2025_PRIMERA_FASE_A", "formacion", "U18", "Campeonato de España de clubes · Júnior femenino"),
    ("C_ESP_CLUBES_CAD_MASC_2025_2026_3º-4º_3º-4º", "formacion", "U16", "Campeonato de España de clubes · Cadete masculino"),
    ("CE_SSAA_Cadete_Fem_2024_2025_Play-Off_1-8_Final", "formacion", "U16", "Selecciones autonómicas · Cadete femenino"),
    ("CE_SSAA_Cadete_Mas_2022_2023_Fase_Grupos_A", "formacion", "U16", "Selecciones autonómicas · Cadete masculino"),
])
def test_a_formation_collection_has_its_category_age_group_and_name_from_the_catalogue_whatever_the_phase_or_season(collection, category, age_group, label):
    assert competition_categories([collection], CATALOGUE) == {collection: {"category": category, "age_group": age_group, "label": label}}


def test_a_senior_collection_is_senior_without_age_group_and_one_the_catalogue_does_not_know_says_nothing():
    got = competition_categories(["LF_ENDESA_2025_2026_Liga_Regular_Único", "L_F_-2_2025_2026_Liga_Regular_B", "TORNEO_X_2026_2027_Liga_Regular", FBCYL], CATALOGUE)
    assert got["LF_ENDESA_2025_2026_Liga_Regular_Único"] == {"category": "senior"} and got["L_F_-2_2025_2026_Liga_Regular_B"] == {"category": "senior"}
    assert "TORNEO_X_2026_2027_Liga_Regular" not in got                   # not guessed: the browser shows it as senior with the name it has
    assert got[FBCYL] == {"category": "senior"}


def test_the_result_does_not_depend_on_the_order_and_changes_nothing():
    names = ["CE_SSAA_Cadete_Fem_2024_2025_3º-4º_3º-4º", "PRIMERA_FEB_2026_2027_Liga_Regular_Único"]
    before = json.dumps(CATALOGUE, sort_keys=True)
    assert competition_categories(names, CATALOGUE) == competition_categories(list(reversed(names)), CATALOGUE)
    assert json.dumps(CATALOGUE, sort_keys=True) == before and competition_categories([], CATALOGUE) == {}


def test_the_rows_entry_of_the_manifest_has_the_category_when_it_is_known_and_the_bytes_do_not_change_between_runs(handler, tmp_path):
    said = {FEB: {"category": "formacion", "age_group": "U16", "label": "Cadete test", "group_label": "Fase de grupos A"}, FBCYL: {"category": "senior"}}
    manifest = publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL], categories=said)
    by = {e["collection"]: e for e in manifest["rows"]}
    assert (by[FEB]["category"], by[FEB]["age_group"], by[FEB]["competition_label"], by[FEB]["group_label"]) == ("formacion", "U16", "Cadete test", "Fase de grupos A")
    assert by[FBCYL]["category"] == "senior" and not {"age_group", "competition_label", "group_label"} & set(by[FBCYL])
    none = publish_web_data(handler, tmp_path / "none", ScopedSealer(MASTER), [FEB])
    assert "category" not in none["rows"][0]                                # without a category the entry is what it was
    before = {p.name: p.read_bytes() for p in (tmp_path / "rows").glob("*.json")}
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL], categories=said)
    assert {p.name: p.read_bytes() for p in (tmp_path / "rows").glob("*.json")} == before
