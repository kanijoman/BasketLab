"""Bio of a Talent player across sources (#910, epic #872): height always in whole cm, a canonical position and a field-by-field merge with provenance.

FEB leaves height and position empty (``-``) for most players (13 % and 10 % in the first sweep sample); NCAA writes the height in feet and inches and ACB/FIBA may do the same.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market.bio import HEIGHT_CONFLICT_CM, SOURCE_PRIORITY, canonical_position, merge_bio, normalize_height, position_group  # noqa: E402


@pytest.mark.parametrize("raw, cm", [
    (190, 190), (190.0, 190), ("190", 190), ("190 cm", 190), ("190cm", 190),
    ("1,90", 190), ("1.90", 190), ("1.90 m", 190), (1.9, 190),
    ("6-7", 201), ("6'7\"", 201), ("6' 7\"", 201), ("6 ft 7 in", 201), ("6-07", 201), ("5'11\"", 180), ("6'", 183), ("6-0", 183),
    (79, 201), ("79", 201), ("79 in", 201),
])
def test_height_is_always_whole_cm_whatever_the_source_writes(raw, cm):
    assert normalize_height(raw) == cm


@pytest.mark.parametrize("raw", [None, "", "-", "  ", "n/a", "abc", True, 0, "0", -5, 47, 95, 100, 119, 241, 300, 1.0, "9-9", "6-14", "1,2,3", float("nan"), [], {}])
def test_unreadable_or_impossible_height_is_none_never_a_guess(raw):
    assert normalize_height(raw) is None


def test_the_edges_of_the_range_are_kept():
    assert (normalize_height(120), normalize_height(240), normalize_height(48), normalize_height(94)) == (120, 240, 122, 239)


@pytest.mark.parametrize("raw, fine, group", [
    ("Base", "Base", "G"), ("base", "Base", "G"), ("  BASE ", "Base", "G"), ("Escolta", "Escolta", "G"), ("Alero", "Alero", "F"),
    ("Ala-Pívot", "Ala-Pívot", "F"), ("A-Pívot", "Ala-Pívot", "F"), ("Ala-Pivot", "Ala-Pívot", "F"), ("Pívot", "Pívot", "C"), ("pivot", "Pívot", "C"),
    ("PG", "Base", "G"), ("SG", "Escolta", "G"), ("SF", "Alero", "F"), ("PF", "Ala-Pívot", "F"), ("C", "Pívot", "C"),
    ("G", None, "G"), ("F", None, "F"), ("Guard", None, "G"), ("Forward", None, "F"), ("Center", "Pívot", "C"),
    ("G-F", None, "G"), ("F/C", None, "F"),
])
def test_position_is_canonical_across_sources(raw, fine, group):
    assert (canonical_position(raw), position_group(raw)) == (fine, group)


@pytest.mark.parametrize("raw", [None, "", "-", "Entrenador", "xyz", 5, True])
def test_unknown_position_is_none_in_both(raw):
    assert canonical_position(raw) is None and position_group(raw) is None


def _c(source, **fields):
    return {"source": source, **fields}


def test_the_priority_is_feb_fiba_acb_ncaa():
    assert SOURCE_PRIORITY == ("feb", "fiba", "acb", "ncaa") and HEIGHT_CONFLICT_CM == 3


def test_a_field_empty_in_one_source_is_filled_by_the_other():
    merged = merge_bio([_c("feb", birth="2004-05-06", height=None, position=None), _c("ncaa", birth=None, height="6-7", position="G")])
    assert (merged["birth"], merged["height"], merged["position"], merged["position_group"]) == ("2004-05-06", 201, None, "G")
    assert merged["bio_src"] == {"birth": "feb", "height": "ncaa", "position_group": "ncaa"} and merged["bio_conflict"] == []


def test_two_values_the_priority_wins_whatever_the_order_of_the_input():
    sources = [_c("ncaa", height="6-8"), _c("acb", height=203), _c("feb", height=204), _c("fiba", height=205)]
    for ordered in (sources, list(reversed(sources))):
        merged = merge_bio(ordered)
        assert merged["height"] == 204 and merged["bio_src"]["height"] == "feb"


def test_a_height_conflict_is_more_than_three_cm_and_keeps_the_winner():
    assert merge_bio([_c("feb", height=200), _c("ncaa", height=203)])["bio_conflict"] == []
    merged = merge_bio([_c("feb", height=200), _c("ncaa", height=204)])
    assert merged["height"] == 200 and merged["bio_conflict"] == ["height"]


def test_a_conflict_is_seen_even_with_the_source_in_the_middle():
    assert merge_bio([_c("feb", height=200), _c("acb", height=201), _c("ncaa", height=206)])["bio_conflict"] == ["height"]


def test_birth_conflict_is_any_difference_and_position_conflict_is_a_different_group():
    merged = merge_bio([_c("feb", birth="2004-05-06", position="Base"), _c("acb", birth="2004-05-07", position="Escolta"), _c("ncaa", position="C")])
    assert merged["birth"] == "2004-05-06" and merged["bio_conflict"] == ["birth", "position"]


def test_a_source_that_is_not_in_the_list_counts_last_and_nothing_known_is_none():
    assert merge_bio([_c("zzz", height=190), _c("ncaa", height=191)])["height"] == 191
    empty = merge_bio([_c("feb", height="-"), _c("ncaa")])
    assert empty["height"] is None and empty["birth"] is None and empty["bio_src"] == {} and empty["bio_conflict"] == []
    assert merge_bio([])["height"] is None


def test_the_inputs_are_not_changed():
    source = [_c("ncaa", height="6-7"), _c("feb", height=None)]
    before = [dict(s) for s in source]
    merge_bio(source)
    assert source == before
