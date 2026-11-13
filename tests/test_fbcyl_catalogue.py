"""The FBCYL youth competitions in the catalogue (#920, epic #872): only the autonomic ones, from cadete upwards, and the senior ones; men and women.

Decided by the user (13/11/2026) after the spike #915: infantil, provincial, escolar, minibásket and menores are out. The fixture is the REAL answer of the combos of fbcyl.es for the autonomic
territory (``territorial=1``) of 2024, 2025 and 2026; nothing here asks the network.
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.competition_catalogue import load_catalogue  # noqa: E402
from src.services.competition_category import competition_categories  # noqa: E402
from src.services.fbcyl_catalogue import catalogue_entries, category_label, classify_category, is_tournament  # noqa: E402

COMBOS = json.loads((Path(__file__).parent / "fixtures" / "fbcyl_autonomic_combos.json").read_text(encoding="utf-8"))
EXISTING_2026 = [{"league": "fbcyl", "competition": "1ª FASE-GRUPO A-1", "fbcyl": {"competition_id": "7298"}}, {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-2", "fbcyl": {"competition_id": "7299"}}]


@pytest.mark.parametrize("text, kind", [
    ("1ª DIVISION MASCULINA", ("senior", None)), ("1ª DIVISION FEMENINA", ("senior", None)), ("1ª DIV. FEMENINA", ("senior", None)), ("2ª DIVISION FEMENINA", ("senior", None)),
    ("SENIOR FBCYL FEMENINO", ("senior", None)),
    ("1ªDIV. - CAD. FEM. AUT.", ("formacion", "U16")), ("1ªDIV. - CAD. MASC.AUT.", ("formacion", "U16")), ("2ªDIV.- CAD. MASC. AUT.", ("formacion", "U16")), ("1ªDIV.-CAD.FEM.AUT.", ("formacion", "U16")),
    ("LIGA UEMC JUNIOR MASCULINO", ("formacion", "U18")), ("LIGA UEMC JUNIOR FEMENINO", ("formacion", "U18")), ("2ªDIV.- JUN. FEM. AUT.", ("formacion", "U18")), ("1ªDIV.-JUN. MASC.AUT.", ("formacion", "U18")),
    ("1ªDIV.- INF. MASC. AUT.", ("excluded", None)), ("2ªDIV.- INF. FEM. AUT.", ("excluded", None)), ("1ªDIV.-INF.FEM. AUT.", ("excluded", None)),
    ("MINIBASKET MASCULINO AUTONOMICO", ("excluded", None)), ("MINIBASKET FEMENINO AUTONOMICO", ("excluded", None)), ("LIGA 3X3", ("excluded", None)),
    ("TORNEO DE PRUEBA NUEVO", ("unknown", None)), ("", ("unknown", None)),
])
def test_a_category_is_senior_cadete_junior_excluded_or_unknown_and_what_is_not_known_is_never_guessed(text, kind):
    assert classify_category(text) == kind


@pytest.mark.parametrize("text, gender, label", [
    ("1ª DIVISION MASCULINA", "M", "1ª División masculina"), ("1ª DIV. FEMENINA", "F", "1ª División femenina"), ("2ª DIVISION FEMENINA", "F", "2ª División femenina"),
    ("SENIOR FBCYL FEMENINO", "F", "Sénior FBCYL femenino"),
    ("1ªDIV. - CAD. FEM. AUT.", "F", "1ª División cadete femenino"), ("1ªDIV.-CAD.FEM.AUT.", "F", "1ª División cadete femenino"), ("2ªDIV.- CAD. MASC. AUT.", "M", "2ª División cadete masculino"),
    ("2ªDIV.- JUN. FEM. AUT.", "F", "2ª División júnior femenino"), ("1ªDIV.-JUN. MASC.AUT.", "M", "1ª División júnior masculino"),
    ("LIGA UEMC JUNIOR MASCULINO", "M", "Liga UEMC júnior masculino"), ("LIGA UEMC JUNIOR FEMENINO", "F", "Liga UEMC júnior femenino"),
])
def test_every_category_has_a_readable_name_with_its_division_level_and_gender(text, gender, label):
    assert category_label(text, gender) == label


def test_a_tournament_of_selections_inside_a_category_is_not_a_league():
    assert is_tournament("Tº INTERNACIONAL SELECCIONES U16 F - MEDINA y CIGALES-U16F 01") and is_tournament("Tº DIPUTACION SALAMANCA MASCULINO")
    assert not is_tournament("1ª DIV CADETE MASC - FASE PREVIA CLASIFICACIÓN-GRUPO A") and not is_tournament("1ª FASE-GRUPO A-1")


def _new(season, existing=(), active=True):
    return catalogue_entries(COMBOS, season, existing, active=active)


def test_2026_has_the_senior_cadete_and_junior_groups_men_and_women_and_nothing_of_infantil_or_minibasket():
    entries, unknown = _new("2026", EXISTING_2026)
    assert unknown == []
    by_age = {}
    for e in entries:
        by_age.setdefault((e["category"], e.get("age_group")), []).append(e)
    assert {k: len(v) for k, v in by_age.items()} == {("senior", None): 3, ("formacion", "U16"): 18, ("formacion", "U18"): 16}       # the two groups already in the catalogue are not added again
    labels = {e["label"] for e in entries}
    assert "1ª División masculina" in labels and "Liga UEMC júnior masculino" in labels and "Liga UEMC júnior femenino" in labels and "1ª División cadete masculino" in labels
    assert not any(("INF" in e["note"].upper() or "MINI" in e["note"].upper()) for e in entries)


def test_the_gender_of_the_men_is_there_and_the_senior_men_are_added():
    entries, _ = _new("2026", EXISTING_2026)
    assert {e["fbcyl"]["gender"] for e in entries} == {"M", "F"}
    assert [e["group_label"] for e in entries if e["label"] == "1ª División masculina"] == ["1ª FASE. 1ª DIV. MASCULINA-GRUPO A", "1ª FASE. 1ª DIV. MASCULINA-GRUPO B"]


def test_the_international_selections_tournament_listed_under_cadete_is_left_out():
    entries, _ = _new("2026", EXISTING_2026)
    assert not any(e["group_label"].startswith("Tº") for e in entries) and all(e["fbcyl"]["competition_id"] != "7257" for e in entries)


def test_an_entry_has_what_the_scraper_and_the_catalogue_need():
    entries, _ = _new("2026", EXISTING_2026)
    entry = next(e for e in entries if e["fbcyl"]["competition_id"] == "7249")
    assert entry == {"league": "fbcyl", "competition": "1ª DIV CADETE FEM - FASE PREVIA CLASIFICACIÓN-GRUPO A G7249", "season_label": "2026", "season_value": "2026", "active": True,
                     "note": "1ª División cadete femenino, 1ª DIV CADETE FEM - FASE PREVIA CLASIFICACIÓN-GRUPO A", "category": "formacion", "age_group": "U16", "label": "1ª División cadete femenino",
                     "group_label": "1ª DIV CADETE FEM - FASE PREVIA CLASIFICACIÓN-GRUPO A", "fbcyl": {"competition_id": "7249", "category": "1126", "gender": "F", "territory": "1"}}


def test_the_text_of_a_group_has_its_spaces_collapsed():
    combos = [{"season": "2025", "gender": "F", "category": "1015", "category_text": "1ªDIV. - CAD. FEM. AUT.", "competitions": [{"id": "6999", "text": "4ª FASE. FASE FINAL - 1ªDIV CAD FEM -  -F4 "}]}]
    (entry,), _ = catalogue_entries(combos, "2025", [])
    assert entry["group_label"] == "4ª FASE. FASE FINAL - 1ªDIV CAD FEM - -F4" and entry["competition"] == "4ª FASE. FASE FINAL - 1ªDIV CAD FEM - -F4 G6999"


def test_a_paused_season_is_added_paused_so_it_is_loaded_in_batches():
    entries, _ = _new("2025", active=False)
    assert entries and all(e["active"] is False for e in entries) and {e["season_value"] for e in entries} == {"2025"}


def test_running_it_twice_adds_nothing_and_never_touches_what_is_there():
    first, _ = _new("2026", EXISTING_2026)
    again, _ = catalogue_entries(COMBOS, "2026", EXISTING_2026 + first)
    assert again == []
    assert _new("2026", EXISTING_2026)[0] == first                                         # deterministic


def test_a_category_it_does_not_know_is_reported_and_not_added():
    combos = COMBOS + [{"season": "2026", "gender": "M", "category": "9999", "category_text": "COPA NUEVA DE ALGO", "competitions": [{"id": "1", "text": "GRUPO UNICO"}]}]
    entries, unknown = catalogue_entries(combos, "2026", EXISTING_2026)
    assert unknown == ["COPA NUEVA DE ALGO"] and all(e["fbcyl"]["category"] != "9999" for e in entries)


def test_the_generated_entries_load_in_the_catalogue_and_say_their_category_age_and_name(tmp_path):
    entries, _ = _new("2026", EXISTING_2026)
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"competitions": EXISTING_FULL + entries}), encoding="utf-8")
    catalogue = load_catalogue(path)
    assert len(catalogue) == len(EXISTING_FULL) + len(entries)
    from src.database import get_collection_name

    entry = next(e for e in entries if e["fbcyl"]["competition_id"] == "7242")
    name = get_collection_name(f"FBCYL_{entry['competition']}", entry["season_value"], "")
    assert competition_categories([name], catalogue) == {name: {"category": "formacion", "age_group": "U18", "label": "Liga UEMC júnior femenino", "group_label": entry["group_label"]}}


EXISTING_FULL = [
    {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-1", "season_label": "2026", "season_value": "2026", "active": True, "fbcyl": {"competition_id": "7298", "category": "1129", "gender": "F", "territory": "1"}},
    {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-2", "season_label": "2026", "season_value": "2026", "active": True, "fbcyl": {"competition_id": "7299", "category": "1129", "gender": "F", "territory": "1"}},
]


def test_two_groups_of_different_competitions_never_share_a_collection_name_and_none_reads_as_a_year():
    from src.database import get_collection_name

    entries = _new("2026", EXISTING_2026)[0] + _new("2025", active=False)[0] + _new("2024", active=False)[0]
    names = [get_collection_name(f"FBCYL_{e['competition']}", e["season_value"], "") for e in entries]
    assert len(names) == len(set(names))
    assert not any(re.search(r"(?:^|_)\d{4}(?:_|$)", name.replace(f"_{e['season_value']}_", "_")) for name, e in zip(names, entries))          # the only year in a name is the season


class _FakeSite:
    """The combos of fbcyl.es as the scraper answers them (from the real fixture): ``(text, value)`` pairs, and the territory it was asked for."""

    def __init__(self):
        self.asked = []

    def fetch_categories_ajax(self, season, gender, territory):
        self.asked.append(("categories", season, gender, territory))
        return [(c["category_text"], c["category"]) for c in COMBOS if c["season"] == season and c["gender"] == gender]

    def fetch_competitions_ajax(self, category, gender, territory):
        self.asked.append(("competitions", category, gender, territory))
        return [(g["text"], g["id"]) for c in COMBOS if c["category"] == category and c["gender"] == gender for g in c["competitions"]]


def test_the_combos_are_asked_for_the_autonomic_territory_with_a_pause_and_give_the_same_entries():
    from src.services.fbcyl_catalogue import fetch_combos

    site, pauses = _FakeSite(), []
    got = fetch_combos(site, "2026", sleep=pauses.append)
    assert all(a[3] == "1" for a in site.asked) and {a[2] if a[0] == "categories" else a[2] for a in site.asked} >= {"M", "F"}
    assert len(pauses) == len(site.asked) and all(p >= 1 for p in pauses)                       # one second between requests: the site is somebody else's
    assert catalogue_entries(got, "2026", EXISTING_2026) == catalogue_entries(COMBOS, "2026", EXISTING_2026)


def test_the_runner_adds_the_seasons_it_is_told_to_and_leaves_the_rest_of_the_file_as_it_is(tmp_path):
    from src.services.fbcyl_catalogue import update_catalogue_file

    path = tmp_path / "competitions.json"
    original = {"competitions": [{"competition": "LF ENDESA", "competition_url": "https://example.invalid/c", "season_label": "2026/2027", "season_value": "2026", "groups": "all", "active": True}] + EXISTING_FULL}
    path.write_text(json.dumps(original, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = update_catalogue_file(path, COMBOS, {"2026": True, "2025": False})
    written = json.loads(path.read_text(encoding="utf-8"))["competitions"]
    assert written[:3] == original["competitions"] and len(written) == 3 + report["added"]
    assert report["added"] == 37 + report["paused_added"] and report["unknown"] == []
    assert {e["season_value"] for e in written[3:]} == {"2026", "2025"} and all(e["active"] == (e["season_value"] == "2026") for e in written[3:])
    again = update_catalogue_file(path, COMBOS, {"2026": True, "2025": False})
    assert again["added"] == 0 and json.loads(path.read_text(encoding="utf-8"))["competitions"] == written          # idempotent, and no byte moves
    load_catalogue(path)                                                                                             # and it is a valid catalogue
