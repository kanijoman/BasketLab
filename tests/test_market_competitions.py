"""Competition and season of each collection (B2, #878): the unit of a Talent row. Competitions are never mixed (LF Endesa is not LF Challenge, senior is not youth, FEB is not FBCYL);
only the phases and groups of the SAME competition and season are put together (Tercera FEB has dozens of subgroups, the Copa has groups and play-offs).

The names are the real ones of the archive (``tests/fixtures`` has no database): ``{competition}_{season label}_{group}``, FBCYL ``FBCYL_{group}_{season value}_``."""
import random

import pytest

from src.market.competitions import competitions_of

COPA = [f"COPA_ESPAÑA_2024_2025_FASE_DE_GRUPOS_{g}" for g in "ABCDEFGH"] + ["COPA_ESPAÑA_2024_2025_PLAYOFFS_1_2_Final", "COPA_ESPAÑA_2024_2025_PLAYOFFS_1_4_Final"]
TERCERA = ["TERCERA_FEB_2026_2027_Liga_Regular_A-B", "TERCERA_FEB_2026_2027_Liga_Regular_A-A", "TERCERA_FEB_2026_2027_Liga_Regular_B-A"]
SEGUNDA = ["SEGUNDA_FEB_2025_2026_Liga_Regular_A", "SEGUNDA_FEB_2025_2026_ELIMINATORIAS_1_8_Final", "SEGUNDA_FEB_2026_2027_Liga_Regular_A"]
WOMEN = ["LF_ENDESA_2026_2027_Liga_Regular_Único", "LF_CHALLENGE_2026_2027_Liga_Regular_Único", "L_F_-2_2025_2026_Liga_Regular_A"]
YOUTH = ["C_ESP_CLUBES_JR_FEM_2025_2026_PRIMERA_FASE_A", "C_ESP_CLUBES_JR_MASC_2025_2026_PRIMERA_FASE_A", "CE_SSAA_Cadete_Fem._2025_2026_Final"]
FBCYL = ["FBCYL_1ª_FASE-GRUPO_A-1_2026_", "FBCYL_1ª_FASE-GRUPO_A-2_2026_"]
META = {"L_F_-2_2025_2026_Liga_Regular_A": {"competition_label": "L.F.-2", "season_value": "2025", "season_label": "2025/2026", "group_label": "Liga Regular · A"}}
CATALOGUE = [
    {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-1", "season_value": "2026", "season_label": "2026", "note": "Primera Nacional Femenina, grupo A-1",
     "fbcyl": {"competition_id": "7298", "category": "1129", "gender": "F", "territory": "1"}},
    {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-2", "season_value": "2026", "season_label": "2026", "note": "Primera Nacional Femenina, grupo A-2",
     "fbcyl": {"competition_id": "7299", "category": "1129", "gender": "F", "territory": "1"}},
]


def _groups(names, **kw):
    found, unknown = competitions_of(names, META, CATALOGUE, **kw)
    return {c.key: (c, [m.collection for m in members]) for c, members in found.items()}, unknown


def test_the_phases_and_groups_of_one_competition_and_season_are_one_competition():
    groups, _ = _groups(COPA + TERCERA)
    copa = next(v for v in groups.values() if v[0].competition == "COPA ESPAÑA")
    assert sorted(copa[1]) == sorted(COPA) and copa[0].season == "2024"
    tercera = next(v for v in groups.values() if v[0].competition == "TERCERA FEB")
    assert len(tercera[1]) == 3 and tercera[0].season == "2026"


def test_competitions_that_share_a_prefix_are_never_mixed():
    """LF, LF ENDESA, LF CHALLENGE and L.F.-2; senior and youth; men and women of the same championship."""
    groups, _ = _groups(WOMEN + YOUTH)
    assert sorted(c.competition for c, _ in groups.values()) == sorted(["LF ENDESA", "LF CHALLENGE", "L.F.-2", "C ESP CLUBES JR FEM", "C ESP CLUBES JR MASC", "CE SSAA Cadete Fem."])
    assert all(len(members) == 1 for _, members in groups.values())


def test_the_same_competition_in_two_seasons_is_two_competitions():
    groups, _ = _groups(SEGUNDA)
    keyed = {(c.competition, c.season): members for c, members in groups.values()}
    assert sorted(keyed) == [("SEGUNDA FEB", "2025"), ("SEGUNDA FEB", "2026")] and len(keyed[("SEGUNDA FEB", "2025")]) == 2


def test_the_metadata_of_the_collection_wins_over_its_name():
    """The name is sanitised (``L_F_-2``); the label of the scrape is the real one, and its season value is the year the season starts in."""
    groups, _ = _groups(["L_F_-2_2025_2026_Liga_Regular_A"])
    c, _members = next(iter(groups.values()))
    assert (c.competition, c.season, c.season_label, c.league) == ("L.F.-2", "2025", "2025/2026", "feb")


def test_a_fbcyl_group_is_a_group_of_its_competition_not_a_competition():
    """A-1 and A-2 are two groups of the Primera Nacional Femenina (same category, territory and season), like the subgroups of Tercera FEB."""
    groups, _ = _groups(FBCYL)
    assert len(groups) == 1
    c, members = next(iter(groups.values()))
    assert (c.league, c.competition, c.season) == ("fbcyl", "Primera Nacional Femenina", "2026") and sorted(members) == sorted(FBCYL)


def test_feb_and_fbcyl_are_never_mixed_even_with_the_same_season():
    groups, _ = _groups(TERCERA + FBCYL)
    assert sorted(c.league for c, _ in groups.values()) == ["fbcyl", "feb"]


def test_a_collection_that_says_nothing_is_reported_not_guessed():
    groups, unknown = _groups(["archive", "SEGUNDA_FEB_sin_temporada", "FBCYL_otro_2026_"] + TERCERA)
    assert sorted(unknown) == ["FBCYL_otro_2026_", "SEGUNDA_FEB_sin_temporada", "archive"] and len(groups) == 1


def test_the_result_does_not_depend_on_the_order_of_the_collections():
    names = COPA + TERCERA + SEGUNDA + WOMEN + YOUTH + FBCYL
    shuffled = names[:]
    random.Random(7).shuffle(shuffled)
    assert list(_groups(names)[0].items()) == list(_groups(shuffled)[0].items())
    assert list(_groups(names)[0]) == sorted(_groups(names)[0])                    # sorted by key: the files and the manifest come out in a fixed order


@pytest.mark.parametrize("empty", [[], ()])
def test_no_collections_is_no_competitions(empty):
    assert competitions_of(empty, {}, []) == ({}, [])
