"""The single name normaliser (#1128) and the places that used their own accent strippers."""
import pytest

from src.market.identity import name_key as feb_name_key
from src.market.identity_link import external_players, link_players
from src.utils.text import plain_words, strip_accents


@pytest.mark.parametrize("raw, expected", [
    ("O'Neill", ["O", "NEILL"]),
    ("O´NEILL", ["O", "NEILL"]),
    ("O’Neill", ["O", "NEILL"]),
    ("Łukasz Ø. Straße", ["LUKASZ", "O", "STRASSE"]),
    ("Iñaki Ibañez-Pérez", ["INAKI", "IBANEZ", "PEREZ"]),
    ("Isı Çelik", ["ISI", "CELIK"]),
    ("  J.  GARCÍA  ", ["J", "GARCIA"]),
])
def test_plain_words_is_one_table_for_apostrophes_special_letters_and_accents(raw, expected):
    assert plain_words(raw) == expected


def test_strip_accents_maps_letters_nfkd_cannot_decompose():
    assert strip_accents("ŁØßı") == "LOssi" and strip_accents("é") == "e"


def test_apostrophe_spellings_of_the_same_player_link_regression():
    """«O'Neill» (FIBA) and «O´NEILL» (FEB) with the same birth went to review: the apostrophe was a letter of the word."""
    feb = [{"person_id": "feb:1", "name": "O´NEILL ANDERSON", "birth": "2000-01-01"}]
    player = {"id": "f1", "name": "O'Neill Anderson", "birth": "2000-01-01"}

    assert [(l["status"], l["feb"]) for l in link_players(feb, [player])] == [("linked", "feb:1")]


def test_feb_name_key_maps_special_letters_regression():
    assert feb_name_key("A. ŁUKASZ ØSTERGAARD") == feb_name_key("A. LUKASZ OSTERGAARD")


def _doc(birth):
    return {"BOXSCORE": {"TEAM": [{"PLAYER": [{"id": "9", "name": "A B", "birth": birth, "min": "10:00"}]}]}}


def test_a_birth_corrected_in_a_later_game_wins_by_frequency_regression():
    """external_players kept the FIRST birth it saw; the most said one (as external_bio) is the value, a tie to the smallest."""
    docs = [_doc("2000-01-02"), _doc("2000-01-01"), _doc("2000-01-01")]

    assert external_players(docs)[0]["birth"] == "2000-01-01"
    assert external_players(list(reversed(docs)))[0]["birth"] == "2000-01-01"
