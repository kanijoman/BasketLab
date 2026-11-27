"""One shared word is not proof of club when the clubs are of another kind (#1127): «C.D. LEON» is not «BALONCESTO LEON»."""
import pytest

from src.market.identity_link import _club_match


@pytest.mark.parametrize("mine, theirs", [
    ("C.D. LEON", "BALONCESTO LEON"),                 # a multi-sport club of the city and the basketball one
    ("CB AVILA BALONCESTO", "C.D. AVILA"),
    ("U.D. BURGOS", "CB BURGOS"),
])
def test_clubs_of_the_same_city_but_another_kind_are_no_proof_regression(mine, theirs):
    assert _club_match([mine], [theirs]) == []


@pytest.mark.parametrize("mine, theirs, shared", [
    ("BALONCESTO LA FLECHA", "BALONCESTO LA FLECHA", ["FLECHA"]),       # the real case of #978
    ("BALONCESTO LA FLECHA", "C.B. LA FLECHA", ["FLECHA"]),             # the same kind written another way
    ("CB AVILA BALONCESTO", "BALONCESTO AVILA", ["AVILA"]),
    ("C.D. ARTXANDA", "CD ARTXANDA", ["ARTXANDA"]),
    ("LEON", "BALONCESTO LEON", ["LEON"]),                              # a name with no kind says nothing against
    ("C.D. LEON PALENCIA", "BALONCESTO LEON PALENCIA", ["LEON", "PALENCIA"]),   # two distinctive words: as before
])
def test_the_same_kind_of_club_or_two_words_keep_the_proof(mine, theirs, shared):
    assert _club_match([mine], [theirs]) == shared
