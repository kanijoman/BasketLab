"""The nationality of a person across sources (#996): FEB writes the country in Spanish capitals (``ESPAÑA``), FIBA with its three-letter code (``ESP``, ``SLO``, ``GER``). A player with several passports
is reported with ALL of them, so the same country written two ways must be ONE nationality, and what the table does not know is kept as it came (never dropped, never merged by guess)."""
import random

import pytest

from src.market.countries import country, nationalities


@pytest.mark.parametrize("raw,expected", [
    ("ESP", "ESPAÑA"), ("ESPAÑA", "ESPAÑA"), ("España", "ESPAÑA"), ("  espana ", "ESPAÑA"),
    ("SLO", "ESLOVENIA"), ("GER", "ALEMANIA"), ("LAT", "LETONIA"), ("SRB", "SERBIA"), ("USA", "ESTADOS UNIDOS"), ("ENG", "INGLATERRA"),
    ("Estados Unidos", "ESTADOS UNIDOS"), ("REPÚBLICA DOMINICANA", "REPÚBLICA DOMINICANA"), ("DOM", "REPÚBLICA DOMINICANA"),
])
def test_a_country_is_the_same_whatever_the_source_writes(raw, expected):
    assert country(raw) == expected


def test_what_the_table_does_not_know_is_kept_as_it_came_and_nothing_says_nothing():
    assert country("ZZZ") == "ZZZ" and country("Atlántida") == "ATLÁNTIDA"
    assert country(None) is None and country("") is None and country("   ") is None


def test_the_nationalities_of_a_person_are_all_the_different_ones_in_the_order_given_without_repeats():
    assert nationalities(["ESPAÑA", "ESP", "USA", "Estados Unidos", None, "ESP"]) == ["ESPAÑA", "ESTADOS UNIDOS"]
    assert nationalities([]) == [] and nationalities([None, ""]) == []


def test_two_passports_are_two_nationalities_not_a_conflict():
    assert nationalities(["ESPAÑA", "SENEGAL"]) == ["ESPAÑA", "SENEGAL"]


def test_every_code_the_table_has_maps_to_one_name_that_maps_to_itself():
    from src.market.countries import FIBA_CODES

    names = set(FIBA_CODES.values())
    assert all(country(name) == name for name in names)
    assert len(FIBA_CODES) >= 150 and all(len(code) == 3 and code.isupper() for code in FIBA_CODES)


def test_the_order_of_the_input_decides_the_order_of_the_output_and_nothing_else():
    values = ["ESPAÑA", "USA", "SEN", "FRA"]
    for _ in range(5):
        random.shuffle(values)
        assert nationalities(values) == [country(v) for v in values]
